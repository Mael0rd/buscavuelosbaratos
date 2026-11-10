"""Publicación en el canal de Telegram: mensaje con formato y botones
(los enlaces van dentro de los botones, sin mostrar la dirección)."""
import html
from urllib.parse import quote

import requests

from .config import env
from .copywriter import fmt_date, fmt_stops, savings_pct


def _when(iso: str) -> str:
    """'2027-02-03T17:00:00-06:00' -> '3 de febrero a las 17:00'."""
    out = fmt_date(iso)
    if iso and len(iso) >= 16 and iso[10] == "T":
        out += f" a las {iso[11:16]}"
    return out


def build_message(row: dict, site_url: str, country_name: str) -> tuple[str, dict]:
    e = html.escape
    ahorro = savings_pct(row)
    header = (f"🔥 <b>{ahorro}% MENOS DE LO NORMAL</b>" if ahorro >= 10
              else "✈️ <b>VUELO EN OFERTA</b>")
    dest = e(row["dest_name"]) + (f", {e(row['dest_country'])}" if row.get("dest_country") else "")
    lines = [
        header,
        "",
        f"💸 <b>${row['price']:.0f} USD</b> ida y vuelta",
    ]
    if ahorro >= 10 and row.get("baseline"):
        lines[-1] += f"  <s>${row['baseline']:.0f}</s>"
    lines += [
        "",
        f"🛫 Salida de <b>{e(row['origin_name'])}</b> ({e(row.get('origin_airport') or row['origin'])}), {e(country_name)}",
        f"🛬 Llegada a <b>{dest}</b> ({e(row.get('destination_airport') or row['destination'])})",
        "",
        f"🗓️ Ida: {_when(row['departure_at'])}",
    ]
    if row.get("return_at"):
        lines.append(f"🗓️ Vuelta: {_when(row['return_at'])}")
    detalle = fmt_stops(row["transfers"]).capitalize()
    if row.get("airline_name"):
        detalle += f" · {e(row['airline_name'])}"
    lines += [f"🔁 {detalle}", "", "<i>Precio encontrado recientemente; puede cambiar.</i>"]

    deal_url = f"{site_url}/oferta/{row['slug']}.html"
    share_text = (f"✈️ {row['origin_name']} → {row['dest_name']} por ${row['price']:.0f} "
                  f"ida y vuelta. Mira la oferta: {deal_url}")
    markup = {"inline_keyboard": [
        [{"text": "🎟️ Reservar ahora", "url": row["link"] or deal_url}],
        [{"text": "📲 Compartir en WhatsApp", "url": "https://wa.me/?text=" + quote(share_text)}],
        [{"text": f"🔎 Más ofertas desde {country_name}",
          "url": f"{site_url}/pais/{row['country']}.html"}],
    ]}
    return "\n".join(lines), markup


def send(text: str, markup: dict) -> bool:
    r = requests.post(
        f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
        json={"chat_id": env("TELEGRAM_CHANNEL"), "text": text, "parse_mode": "HTML",
              "reply_markup": markup, "link_preview_options": {"is_disabled": True}},
        timeout=20,
    )
    if not r.ok:
        print(f"[telegram] error {r.status_code}: {r.text[:200]}")
    return r.ok


def publish_pending(conn, cfg: dict) -> int:
    """Publica las mejores ofertas nuevas (hasta social.max_per_run). El resto
    queda solo en la web, para no saturar el canal."""
    if not env("TELEGRAM_BOT_TOKEN") or not env("TELEGRAM_CHANNEL"):
        print("[telegram] sin credenciales, se omite")
        return 0
    site_url = f"https://{cfg['site']['domain']}"
    max_per_run = cfg["social"]["max_per_run"]
    # Pendientes viejas (p. ej. de antes de conectar Telegram) no se envían
    conn.execute("""UPDATE deals SET telegram_sent=2
                    WHERE telegram_sent=0 AND published_at < datetime('now', '-1 day')""")
    rows = conn.execute(
        "SELECT * FROM deals WHERE telegram_sent=0 ORDER BY score ASC").fetchall()
    sent = 0
    for i, row in enumerate(rows):
        if i >= max_per_run:
            conn.execute("UPDATE deals SET telegram_sent=2 WHERE id=?", (row["id"],))
            continue
        country = cfg["countries"].get(row["country"], {}).get("name", "tu país")
        text, markup = build_message(dict(row), site_url, country)
        if send(text, markup):
            conn.execute("UPDATE deals SET telegram_sent=1 WHERE id=?", (row["id"],))
            sent += 1
    conn.commit()
    return sent
