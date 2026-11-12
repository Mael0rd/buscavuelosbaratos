"""Cuenta de Threads (Meta) con publicación automática por la API oficial (gratis).

Cada publicación lleva la imagen de la oferta (con el precio), un texto corto con
el enlace a la página de la oferta (?src=threads: la página usa ese SubID en el
botón de reserva) y un tema (topic tag) para aparecer ante gente que no sigue la
cuenta. Threads permite un solo tema por publicación.

Token: el primero se carga en el secret THREADS_TOKEN (token largo, 60 días). Cada
semana se renueva solo y el nuevo se guarda en el almacén privado del servidor de
alertas (/api/kv/threads_token), porque GitHub no deja que la corrida cambie sus
propios secrets. Si el guardado falla o vence, basta con poner uno nuevo en el secret.
"""
import time
from datetime import datetime, timezone

import requests

from . import telegram
from .alerts import admin_token
from .config import env
from .copywriter import fmt_date, fmt_stops, savings_pct
from .fresh import age_hours
from .verify import priority

GRAPH = "https://graph.threads.net/v1.0"
KV_KEY = "threads_token"
SCHEMA = """
CREATE TABLE IF NOT EXISTS threads_posts (
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
        r = requests.get(f"{GRAPH}/me", params={"fields": "id,username", "access_token": token}, timeout=15)
        return r.json() if r.ok and "id" in r.json() else None
    except Exception:
        return None


def get_session(cfg: dict, now: datetime) -> tuple[str, dict] | None:
    """(token, perfil) válidos. Prueba el guardado y luego el del secret; renueva si toca."""
    stored = _kv_get(cfg)
    candidates = []
    if stored and stored.get("value"):
        candidates.append(("guardado", stored["value"], stored.get("updated_at")))
    if env("THREADS_TOKEN"):
        candidates.append(("secret", env("THREADS_TOKEN").strip(), None))
    for source, token, updated in candidates:
        me = _me(token)
        if not me:
            continue
        if source == "secret" and not (stored and stored.get("value") == token):
            _kv_put(cfg, token)  # primera vez (o token nuevo puesto a mano): desde aquí se renueva solo
            updated = now.isoformat()
        # Renovar cada ~7 días (Meta exige que tenga al menos 24 h; vence a los 60)
        age = _hours_since(updated, now)
        if age is not None and age >= 24 * 7:
            new = refresh(token)
            if new and _kv_put(cfg, new):
                print("[threads] token renovado por 60 días más")
                token = new
            else:
                print("[threads] ⚠ no se pudo renovar el token; se reintenta en la próxima corrida")
        return token, me
    if candidates:
        print("[threads] ⚠ el token no funciona (¿venció?). Genera uno nuevo y ponlo en el secret THREADS_TOKEN")
    return None


def _hours_since(ts: str | None, now: datetime) -> float | None:
    """Horas desde una fecha de D1 ('2026-11-12 18:00:00', UTC) o ISO."""
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() / 3600


def refresh(token: str) -> str | None:
    try:
        r = requests.get("https://graph.threads.net/refresh_access_token",
                         params={"grant_type": "th_refresh_token", "access_token": token}, timeout=15)
        return r.json().get("access_token") if r.ok else None
    except Exception:
        return None


# ---------- publicación ----------
def build_text(d: dict, site_url: str, now: datetime | None = None) -> str:
    """Texto corto (Threads permite 500 caracteres)."""
    ahorro = savings_pct(d)
    price = d.get("live_price") or d["price"]
    dest = d["dest_name"] + (f", {d['dest_country']}" if d.get("dest_country") else "")
    head = f"🔥 {ahorro}% menos de lo normal" if ahorro >= 10 else "✈️ Vuelo en oferta"
    lines = [f"{head}: {d['origin_name']} → {dest} por ${price:.0f} ida y vuelta {d.get('flag', '')}".strip(), ""]
    fechas = fmt_date(d["departure_at"]) + (f" – {fmt_date(d['return_at'])}" if d.get("return_at") else "")
    lines.append(f"🗓️ {fechas} · {fmt_stops(d['transfers'])}")
    if d.get("verified_at"):
        lines.append(f"✅ Precio verificado {telegram.ago(d['verified_at'], now)}")
    lines += ["", f"👉 {site_url}/oferta/{d['slug']}?src=threads"]
    return "\n".join(lines)[:500]


def _online(url: str) -> bool:
    try:
        return requests.head(url, timeout=10, allow_redirects=True).status_code == 200
    except Exception:
        return False


def _post(uid: str, token: str, text: str, image_url: str, topic: str) -> str | None:
    """Crea el contenedor con la imagen, espera a que Meta la procese y lo publica."""
    r = requests.post(f"{GRAPH}/{uid}/threads", timeout=30, data={
        "media_type": "IMAGE", "image_url": image_url, "text": text,
        "topic_tag": topic, "access_token": token})
    if not r.ok:
        print(f"[threads] ⚠ no se pudo crear la publicación: {r.text[:200]}")
        return None
    cid = r.json()["id"]
    for _ in range(12):  # hasta ~60 s
        time.sleep(5)
        st = requests.get(f"{GRAPH}/{cid}", params={"fields": "status,error_message", "access_token": token},
                          timeout=15).json()
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            print(f"[threads] ⚠ Meta rechazó la imagen: {st.get('error_message')}")
            return None
    r = requests.post(f"{GRAPH}/{uid}/threads_publish", timeout=30,
                      data={"creation_id": cid, "access_token": token})
    if not r.ok:
        print(f"[threads] ⚠ no se pudo publicar: {r.text[:200]}")
        return None
    return r.json().get("id")


def publish(conn, cfg: dict, now: datetime | None = None, verifier=None, session=None, poster=None) -> dict:
    tcfg = cfg.get("social", {}).get("threads") or {}
    if not tcfg.get("enabled"):
        return {}
    now = now or datetime.now(timezone.utc)
    if telegram._quiet(now, cfg["social"]["timezone"], cfg["social"]["quiet_hours"]):
        return {"threads": "horario sin publicar"}
    conn.executescript(SCHEMA)
    sent_24h = conn.execute(
        "SELECT COUNT(*) FROM threads_posts WHERE posted_at >= datetime('now','-1 day')").fetchone()[0]
    free = min(tcfg.get("per_run", 1), tcfg.get("per_day", 8) - sent_24h)
    if free <= 0:
        return {"threads": 0}
    session = session or get_session(cfg, now)
    if not session:
        if not env("THREADS_TOKEN"):
            print("[threads] falta el secret THREADS_TOKEN; se omite")
        return {}
    token, me = session
    poster = poster or (lambda text, img, topic: _post(me["id"], token, text, img, topic))
    site = f"https://{cfg['site']['domain']}"
    max_age = cfg["freshness"]["max_age_hours"]
    rows = [dict(x) for x in conn.execute(
        """SELECT * FROM deals WHERE status='active' AND found_at IS NOT NULL
             AND published_at >= datetime('now','-1 day')
             AND COALESCE(verify_status, '') != 'rechazada'
             AND id NOT IN (SELECT deal_id FROM threads_posts)""").fetchall()]
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
        # La página y su imagen se suben al final de la corrida: solo se publican
        # las que ya están en línea (las nuevas salen en la corrida siguiente).
        page, img = f"{site}/oferta/{d['slug']}", f"{site}/og/oferta-{d['slug']}.jpg"
        if not (_online(page) and _online(img)):
            continue
        topic = (tcfg.get("topics") or {}).get(d["country"]) or tcfg.get("topic", "Vuelos baratos")
        pid = poster(build_text(d, site, now), img, topic)
        if not pid:
            break  # error de Meta: no insistir en esta corrida
        conn.execute("INSERT OR IGNORE INTO threads_posts (deal_id, post_id) VALUES (?, ?)", (d["id"], pid))
        conn.commit()
        done += 1
    print(f"[threads] cuenta @{me.get('username', '?')}")
    return {"threads": done}
