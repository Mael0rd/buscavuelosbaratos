"""Cuenta de Instagram con publicación automática por la API oficial (gratis).

Dos formas de conectarse (se usa la primera que funcione):
1. Token de usuario del sistema (secret META_SYSTEM_TOKEN, ver bvb/meta.py): no vence;
   publica por graph.facebook.com en el Instagram conectado a la página de Facebook.
2. Token de Instagram (secret INSTAGRAM_TOKEN, "API de Instagram con inicio de sesión
   de Instagram", graph.instagram.com): vence a los 60 días y se renueva solo.
La cuenta tiene que ser profesional (empresa o creador).

Cada publicación es una imagen del feed: la vertical 4:5 de la oferta (la misma de
Threads) con un texto que lleva gancho, datos, hashtags y "enlace en la bio".
En Instagram los enlaces del texto no se pueden tocar, por eso el texto manda al
enlace del perfil (la portada muestra primero las ofertas del país del visitante)
y deja escrita la dirección corta de la oferta por si alguien la copia.

Con INSTAGRAM_TOKEN: cada semana se renueva solo y el nuevo se guarda en el almacén
privado del servidor de alertas (/api/kv/instagram_token).
"""
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests

from . import meta, telegram
from .alerts import admin_token
from .config import env
from .copywriter import fmt_stops, savings_pct
from .fresh import age_hours
from .ogimage import short_dates
from .threads import _hours_since, _online
from .verify import priority

GRAPH = "https://graph.instagram.com/v21.0"
KV_KEY = "instagram_token"
SCHEMA = """
CREATE TABLE IF NOT EXISTS instagram_posts (
    deal_id INTEGER PRIMARY KEY, post_id TEXT, posted_at TEXT DEFAULT (datetime('now'))
);
"""


# ---------- token ----------
def _kv_url(cfg: dict) -> str:
    return f"{cfg['alerts']['api_base']}/api/kv/{KV_KEY}"


def _kv_get(cfg: dict) -> dict | None:
    try:
        r = requests.get(_kv_url(cfg), headers={"Authorization": f"Bearer {admin_token()}"}, timeout=15)
        return r.json() if r.ok else None
    except Exception:
        return None


def _kv_put(cfg: dict, value: str) -> bool:
    try:
        r = requests.put(_kv_url(cfg), json={"value": value},
                         headers={"Authorization": f"Bearer {admin_token()}"}, timeout=15)
        return r.ok
    except Exception:
        return False


def _me(token: str) -> dict | None:
    try:
        r = requests.get(f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token}, timeout=15)
        j = r.json() if r.ok else {}
        if not (j.get("user_id") or j.get("id")):
            return None
        return {"id": str(j.get("user_id") or j["id"]), "username": j.get("username", ""), "graph": GRAPH}
    except Exception:
        return None


def refresh(token: str) -> str | None:
    try:
        r = requests.get("https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=15)
        return r.json().get("access_token") if r.ok else None
    except Exception:
        return None


def get_session(cfg: dict, now: datetime) -> tuple[str, dict] | None:
    """(token, perfil) válidos. Primero el usuario del sistema (META_SYSTEM_TOKEN); si no,
    el token de Instagram guardado y luego el del secret, renovándolo si toca."""
    ms = meta.session(cfg.get("social", {}).get("instagram", {}).get("username", ""))
    if ms and ms.get("ig_id"):
        return ms["token"], {"id": ms["ig_id"], "username": ms.get("ig_username", ""), "graph": meta.GRAPH}
    if ms:
        print("[instagram] ⚠ la página no tiene un Instagram conectado (o falta asignarlo al usuario del sistema)")
    stored = _kv_get(cfg)
    candidates = []
    if stored and stored.get("value"):
        candidates.append(("guardado", stored["value"], stored.get("updated_at")))
    if env("INSTAGRAM_TOKEN"):
        candidates.append(("secret", env("INSTAGRAM_TOKEN").strip(), None))
    for source, token, updated in candidates:
        me = _me(token)
        if not me:
            continue
        if source == "secret" and not (stored and stored.get("value") == token):
            _kv_put(cfg, token)  # primera vez (o token nuevo puesto a mano): desde aquí se renueva solo
            updated = now.isoformat()
        age = _hours_since(updated, now)  # Meta exige ≥24 h de antigüedad; vence a los 60 días
        if age is not None and age >= 24 * 7:
            new = refresh(token)
            if new and _kv_put(cfg, new):
                print("[instagram] token renovado por 60 días más")
                token = new
            else:
                print("[instagram] ⚠ no se pudo renovar el token; se reintenta en la próxima corrida")
        return token, me
    if candidates:
        print("[instagram] ⚠ el token no funciona (¿venció?). Genera uno nuevo y ponlo en el secret INSTAGRAM_TOKEN")
    return None


# ---------- texto ----------
QUESTIONS = ["¿Con quién irías? Etiquétalo 👇", "Guárdalo antes de que suba 📌",
             "Mándaselo a quien te llevarías ✈️", "¿Te animas? Cuéntanos 👀"]


def hashtag(name: str) -> str:
    """'San José' → '#SanJose' (Instagram no acepta tildes raras, espacios ni signos)."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", s) if w)
    return f"#{s}" if s else ""


def build_caption(d: dict, cfg: dict, now: datetime | None = None) -> str:
    """Gancho (ruta y precio), ahorro, datos, pregunta, enlace en la bio y hashtags.
    Instagram permite 2.200 caracteres y 30 hashtags; usamos pocos y relevantes."""
    icfg = cfg.get("social", {}).get("instagram") or {}
    domain = cfg["site"]["domain"]
    price = d.get("live_price") or d["price"]
    ahorro = savings_pct(d)
    lines = [f"{d.get('flag', '')} {d['origin_name']} → {d['dest_name']} por ${price:.0f} ida y vuelta ✈️".strip()]
    if ahorro >= 10 and d.get("baseline"):
        lines.append(f"Normalmente ronda ${d['baseline']:.0f}: {ahorro}% menos 🔥")
    extra = f"🗓️ {short_dates(d.get('departure_at', ''), d.get('return_at', ''))} · {fmt_stops(d['transfers'])}"
    if d.get("verified_at"):
        extra += f" · ✅ verificado {telegram.ago(d['verified_at'], now)}"
    lines += [extra, "",
              QUESTIONS[sum(map(ord, d["slug"])) % len(QUESTIONS)], "",
              f"🔗 Resérvalo desde el enlace de nuestro perfil (@{icfg.get('username', 'buscavuelosbaratos')})",
              f"o entra a {domain}/oferta/{d['slug']}",
              "Los precios cambian rápido: si ya subió, activa una alerta gratis en la web.", ""]
    tags = list(icfg.get("hashtags") or ["#VuelosBaratos", "#OfertasDeVuelos", "#Viajes"])
    tags += [t for t in (hashtag(f"Vuelos {(cfg.get('countries', {}).get(d['country']) or {}).get('name', d['origin_name'])}"),
                         hashtag(d["dest_name"]), hashtag(f"Viajar a {d['dest_name']}")) if t]
    lines.append(" ".join(dict.fromkeys(tags[:15])))
    return "\n".join(lines)[:2200]


# ---------- publicación ----------
def _post(uid: str, token: str, caption: str, image_url: str, graph: str = GRAPH) -> str | None:
    """Crea el contenedor con la imagen, espera a que Meta la procese y lo publica."""
    r = requests.post(f"{graph}/{uid}/media", timeout=30,
                      data={"image_url": image_url, "caption": caption, "access_token": token})
    if not r.ok:
        print(f"[instagram] ⚠ no se pudo crear la publicación: {r.text[:200]}")
        return None
    cid = r.json()["id"]
    for _ in range(12):  # hasta ~60 s
        time.sleep(5)
        st = requests.get(f"{graph}/{cid}", params={"fields": "status_code,status", "access_token": token},
                          timeout=15).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            print(f"[instagram] ⚠ Meta rechazó la imagen: {st.get('status')}")
            return None
    r = requests.post(f"{graph}/{uid}/media_publish", timeout=30,
                      data={"creation_id": cid, "access_token": token})
    if not r.ok:
        print(f"[instagram] ⚠ no se pudo publicar: {r.text[:200]}")
        return None
    return r.json().get("id")


def publish(conn, cfg: dict, now: datetime | None = None, verifier=None, session=None, poster=None) -> dict:
    icfg = cfg.get("social", {}).get("instagram") or {}
    if not icfg.get("enabled"):
        return {}
    now = now or datetime.now(timezone.utc)
    if telegram._quiet(now, cfg["social"]["timezone"], cfg["social"]["quiet_hours"]):
        return {"instagram": "horario sin publicar"}
    conn.executescript(SCHEMA)
    sent_24h = conn.execute(
        "SELECT COUNT(*) FROM instagram_posts WHERE posted_at >= datetime('now','-1 day')").fetchone()[0]
    free = min(icfg.get("per_run", 1), icfg.get("per_day", 3) - sent_24h)
    if free <= 0:
        return {"instagram": 0}
    # Espaciar: en el feed, varias seguidas cansan más que en Threads o Telegram
    gap = float(icfg.get("min_gap_hours", 3))
    if conn.execute("SELECT COUNT(*) FROM instagram_posts WHERE posted_at >= datetime('now', ?)",
                    (f"-{gap * 60:.0f} minutes",)).fetchone()[0]:
        return {"instagram": 0}
    session = session or get_session(cfg, now)
    if not session:
        if not env("INSTAGRAM_TOKEN") and not env("META_SYSTEM_TOKEN"):
            print("[instagram] falta el secret META_SYSTEM_TOKEN (o INSTAGRAM_TOKEN); se omite")
        return {}
    token, me = session
    poster = poster or (lambda caption, img: _post(me["id"], token, caption, img, me.get("graph", GRAPH)))
    site = f"https://{cfg['site']['domain']}"
    max_age = cfg["freshness"]["max_age_hours"]
    rows = [dict(x) for x in conn.execute(
        """SELECT * FROM deals WHERE status='active' AND found_at IS NOT NULL
             AND published_at >= datetime('now','-1 day')
             AND COALESCE(verify_status, '') != 'rechazada'
             AND id NOT IN (SELECT deal_id FROM instagram_posts)""").fetchall()]
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
        # Instagram solo acepta JPEG entre 4:5 y 1.91:1: la vertical 4:5 o, si aún no
        # está en línea, la horizontal 1200×630 de la página.
        if not _online(f"{site}/oferta/{d['slug']}"):
            continue
        img = f"{site}/og/social-{d['slug']}.jpg"
        if not _online(img):
            img = f"{site}/og/oferta-{d['slug']}.jpg"
            if not _online(img):
                continue
        pid = poster(build_caption(d, cfg, now), img)
        if not pid:
            break  # error de Meta: no insistir en esta corrida
        conn.execute("INSERT OR IGNORE INTO instagram_posts (deal_id, post_id) VALUES (?, ?)", (d["id"], pid))
        conn.commit()
        done += 1
    print(f"[instagram] cuenta @{me.get('username', '?')}")
    return {"instagram": done}
