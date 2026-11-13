"""Página de Facebook con publicación automática (API oficial, gratis).

Usa el token de usuario del sistema (secret META_SYSTEM_TOKEN, ver bvb/meta.py), que no
vence. Cada publicación es una foto (la imagen 4:5 de la oferta) con un texto cuyo
enlace SÍ se puede tocar: va a /oferta/<slug>?src=facebook, y la página usa ese SubID
en el botón de reserva. Las fotos llegan a más gente que los posts de solo enlace.

Los grupos de Facebook no tienen API (Meta la quitó en 2024): ahí se comparte a mano.
"""
from datetime import datetime, timezone

import requests

from . import meta, telegram
from .config import env
from .copywriter import fmt_stops, savings_pct
from .fresh import age_hours
from .ogimage import short_dates
from .threads import _online
from .verify import priority

SCHEMA = """
CREATE TABLE IF NOT EXISTS facebook_posts (
    deal_id INTEGER PRIMARY KEY, post_id TEXT, posted_at TEXT DEFAULT (datetime('now'))
);
"""
QUESTIONS = ["¿Con quién irías? Etiquétalo 👇", "¿Te animas? 👀", "Compártelo con tu compa de viaje ✈️",
             "Guárdalo antes de que suba 📌"]


def build_text(d: dict, site_url: str, now: datetime | None = None) -> str:
    price = d.get("live_price") or d["price"]
    ahorro = savings_pct(d)
    lines = [f"{d.get('flag', '')} {d['origin_name']} → {d['dest_name']} por ${price:.0f} ida y vuelta ✈️".strip()]
    if ahorro >= 10 and d.get("baseline"):
        lines.append(f"Normalmente ronda ${d['baseline']:.0f}: {ahorro}% menos 🔥")
    extra = f"🗓️ {short_dates(d.get('departure_at', ''), d.get('return_at', ''))} · {fmt_stops(d['transfers'])}"
    if d.get("verified_at"):
        extra += f" · ✅ verificado {telegram.ago(d['verified_at'], now)}"
    lines += [extra, "", f"👉 Reserva aquí: {site_url}/oferta/{d['slug']}?src=facebook", "",
              QUESTIONS[sum(map(ord, d["slug"])) % len(QUESTIONS)],
              "Los precios cambian rápido. 🔔 Alertas gratis: " + f"{site_url}/alertas?src=facebook"]
    return "\n".join(lines)


def _post(page_id: str, page_token: str, text: str, image_url: str) -> str | None:
    r = requests.post(f"{meta.GRAPH}/{page_id}/photos", timeout=60,
                      data={"url": image_url, "message": text, "published": "true", "access_token": page_token})
    if not r.ok:
        print(f"[facebook] ⚠ no se pudo publicar: {r.text[:200]}")
        return None
    j = r.json()
    return j.get("post_id") or j.get("id")


def publish(conn, cfg: dict, now: datetime | None = None, verifier=None, session=None, poster=None) -> dict:
    fcfg = cfg.get("social", {}).get("facebook") or {}
    if not fcfg.get("enabled"):
        return {}
    now = now or datetime.now(timezone.utc)
    if telegram._quiet(now, cfg["social"]["timezone"], cfg["social"]["quiet_hours"]):
        return {"facebook": "horario sin publicar"}
    conn.executescript(SCHEMA)
    sent_24h = conn.execute(
        "SELECT COUNT(*) FROM facebook_posts WHERE posted_at >= datetime('now','-1 day')").fetchone()[0]
    free = min(fcfg.get("per_run", 1), fcfg.get("per_day", 4) - sent_24h)
    if free <= 0:
        return {"facebook": 0}
    gap = float(fcfg.get("min_gap_hours", 2))
    if conn.execute("SELECT COUNT(*) FROM facebook_posts WHERE posted_at >= datetime('now', ?)",
                    (f"-{gap * 60:.0f} minutes",)).fetchone()[0]:
        return {"facebook": 0}
    session = session or meta.session(fcfg.get("page", ""))
    if not session:
        if not env("META_SYSTEM_TOKEN"):
            print("[facebook] falta el secret META_SYSTEM_TOKEN; se omite")
        return {}
    poster = poster or (lambda text, img: _post(session["page_id"], session["page_token"], text, img))
    site = f"https://{cfg['site']['domain']}"
    max_age = cfg["freshness"]["max_age_hours"]
    rows = [dict(x) for x in conn.execute(
        """SELECT * FROM deals WHERE status='active' AND found_at IS NOT NULL
             AND published_at >= datetime('now','-1 day')
             AND COALESCE(verify_status, '') != 'rechazada'
             AND id NOT IN (SELECT deal_id FROM facebook_posts)""").fetchall()]
    done = 0
    for d in sorted(rows, key=lambda x: priority(x, cfg, now)):
        if done >= free:
            break
        fa = age_hours(d["found_at"], now)
        if fa is None or fa > max_age:
            continue
        if verifier is not None and verifier.ensure(d) != "ok":
            continue
        d = dict(conn.execute("SELECT * FROM deals WHERE id=?", (d["id"],)).fetchone())
        va = age_hours(d.get("verified_at"), now)
        if d.get("verify_status") != "ok" or va is None or va > cfg["verify"]["cache_hours"]:
            continue
        if not _online(f"{site}/oferta/{d['slug']}"):
            continue
        img = f"{site}/og/social-{d['slug']}.jpg"
        if not _online(img):
            img = f"{site}/og/oferta-{d['slug']}.jpg"
            if not _online(img):
                continue
        pid = poster(build_text(d, site, now), img)
        if not pid:
            break
        conn.execute("INSERT OR IGNORE INTO facebook_posts (deal_id, post_id) VALUES (?, ?)", (d["id"], pid))
        conn.commit()
        done += 1
    print(f"[facebook] página {session.get('page_name', '?')}")
    return {"facebook": done}
