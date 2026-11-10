"""Alertas de ruta: lee las suscripciones del servidor de alertas (Cloudflare
Worker) y avisa por Telegram o correo cuando la ruta pasa la regla de oferta."""
import hashlib
import html

import requests

from . import deals as dl
from . import telegram
from .config import env
from .copywriter import fmt_stops, savings_pct


def admin_token() -> str:
    """Clave compartida con el Worker (derivada del token del bot)."""
    return hashlib.sha256(("bvb-admin:" + env("TELEGRAM_BOT_TOKEN")).encode()).hexdigest()


def fetch_subscriptions(cfg: dict) -> list[dict]:
    if not env("TELEGRAM_BOT_TOKEN"):
        print("[alertas] sin TELEGRAM_BOT_TOKEN, se omiten")
        return []
    try:
        r = requests.get(f"{cfg['alerts']['api_base']}/api/subscriptions",
                         headers={"Authorization": f"Bearer {admin_token()}"}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[alertas] no se pudieron leer las alertas: {e}")
        return []


def should_send(conn, sub_id: int, price: float, acfg: dict) -> bool:
    row = conn.execute(
        """SELECT price FROM alert_log WHERE sub_id=? AND sent_at >= datetime('now', ?)
           ORDER BY price ASC LIMIT 1""",
        (sub_id, f"-{acfg['repeat_days']} days")).fetchone()
    return not row or price <= row[0] * (1 - acfg["repeat_extra_drop"])


def telegram_alert(d: dict, cfg: dict) -> tuple[str, dict]:
    site = f"https://{cfg['site']['domain']}"
    country = cfg["countries"].get(d["country"], {}).get("name", "tu país")
    text, _ = telegram.build_message({**d, "slug": d.get("slug", "")}, site, country)
    lines = text.split("\n")
    lines[0] = (f"🔔 <b>TU ALERTA: {html.escape(d['origin_name'])} → {html.escape(d['dest_name'])}</b>")
    ahorro = savings_pct(d)
    if ahorro >= 10:
        lines.insert(1, f"🔥 {ahorro}% menos de lo normal")
    lines.append("Para ver o quitar tus alertas: /misalertas")
    markup = {"inline_keyboard": [
        [{"text": "🎟️ Reservar ahora", "url": d["link"] or site}],
        [{"text": f"🔎 Más ofertas desde {country}", "url": f"{site}/pais/{d['country']}.html"}],
    ]}
    return "\n".join(lines), markup


def email_alert(d: dict, cfg: dict, unsub_url: str) -> tuple[str, str]:
    e = html.escape
    site = f"https://{cfg['site']['domain']}"
    ahorro = savings_pct(d)
    dest = e(d["dest_name"]) + (f", {e(d['dest_country'])}" if d.get("dest_country") else "")
    subject = f"🔔 Oferta: {d['origin_name']} → {d['dest_name']} por ${d['price']:.0f} ida y vuelta"
    fechas = telegram._when(d["departure_at"])
    if d.get("return_at"):
        fechas += f" — vuelta {telegram._when(d['return_at'])}"
    detalle = fmt_stops(d["transfers"]).capitalize()
    if d.get("airline_name"):
        detalle += f" · {e(d['airline_name'])}"
    body = f"""<div style="font-family:system-ui,Arial,sans-serif;max-width:520px;margin:auto;color:#14213d">
  <p style="color:#5c6577;margin:0">Tu alerta de vuelos</p>
  <h2 style="margin:4px 0 12px">{e(d['origin_name'])} → {dest}</h2>
  <p style="font-size:30px;font-weight:800;color:#e85d04;margin:0">${d['price']:.0f}
    <span style="font-size:14px;color:#5c6577;font-weight:500">USD ida y vuelta</span></p>
  {f'<p style="color:#2a7f62;font-weight:600;margin:6px 0">{ahorro}% menos de lo normal (~${d["baseline"]:.0f})</p>' if ahorro >= 10 else ''}
  <p>🗓️ Ida: {e(fechas)}<br>🔁 {detalle}</p>
  <p style="margin:24px 0"><a href="{e(d['link'] or site)}" style="background:#e85d04;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Ver vuelo y precio actual</a></p>
  <p style="color:#5c6577;font-size:13px">Precio encontrado recientemente; puede cambiar en cualquier momento.
    Algunos enlaces son de afiliado: si compras, recibimos una comisión sin costo extra para ti.</p>
  <p style="color:#5c6577;font-size:13px"><a href="{site}/pais/{d['country']}.html" style="color:#5c6577">Más ofertas desde tu país</a>
    · <a href="{e(unsub_url)}" style="color:#5c6577">Dejar de recibir esta alerta</a></p></div>"""
    return subject, body


def send_email(to: str, subject: str, body: str, unsub_url: str, cfg: dict) -> bool:
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {env('RESEND_API_KEY')}"},
        json={"from": cfg["alerts"]["mail_from"], "to": [to], "subject": subject, "html": body,
              "headers": {"List-Unsubscribe": f"<{unsub_url}>"}},
        timeout=20,
    )
    if not r.ok:
        print(f"[alertas] correo falló {r.status_code}: {r.text[:200]}")
    return r.ok


def process(conn, best: dict, cfg: dict, ref, today: str, subs: list[dict]) -> dict:
    acfg = cfg["alerts"]
    stats = {"telegram": 0, "email": 0}
    for s in subs:
        route = (s["origin"], s["destination"])
        t = best.get(route)
        if not t:
            continue
        d = dl.evaluate(conn, route, t, cfg, ref, today)
        if not d or not should_send(conn, s["id"], d["price"], acfg):
            continue
        ok = False
        if s["channel"] == "telegram":
            text, markup = telegram_alert(d, cfg)
            ok = telegram.send(text, markup, chat_id=s["address"])
        elif s["channel"] == "email":
            if not env("RESEND_API_KEY") or stats["email"] >= acfg["max_emails_per_run"]:
                continue
            unsub = f"{acfg['api_base']}/api/unsubscribe?t={s['token']}"
            subject, body = email_alert(d, cfg, unsub)
            ok = send_email(s["address"], subject, body, unsub, cfg)
        if ok:
            conn.execute("INSERT INTO alert_log (sub_id, price) VALUES (?, ?)", (s["id"], d["price"]))
            stats[s["channel"]] += 1
    conn.commit()
    return stats
