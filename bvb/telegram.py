"""Publicación en Telegram: canal general + canales por país, con cupos por
hora/día, horario sin publicaciones, y edición de posts cuya oferta terminó."""
import html
import json
import os
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from .config import env
from .copywriter import fmt_date, fmt_stops, savings_pct
from .fresh import age_hours
from .verify import priority

API = "https://api.telegram.org/bot{token}/{method}"


def _when(iso: str) -> str:
    """'2027-02-03T17:00:00-06:00' -> '3 de febrero a las 17:00'."""
    out = fmt_date(iso)
    if iso and len(iso) >= 16 and iso[10] == "T":
        out += f" a las {iso[11:16]}"
    return out


def ago(found_at: str | None, now: datetime | None = None) -> str:
    h = age_hours(found_at, now)
    if h is None:
        return ""
    if h < 1:
        return f"hace {max(1, round(h * 60))} min"
    return f"hace {round(h)} h"


# ---------- mensajes ----------
def verified_lines(row: dict, now: datetime | None = None) -> list[str]:
    """'✅ Precio verificado hace X' (+ nivel de Google) o, si no, 'Precio visto hace X'."""
    if row.get("verify_status") == "ok" and row.get("verified_at"):
        out = [f"✅ <b>Precio verificado {ago(row['verified_at'], now)}</b> en Google Flights"]
        if (row.get("price_level") or "") == "low":
            rng = ""
            if row.get("typical_low") and row.get("typical_high"):
                rng = f" (normal: ${row['typical_low']:.0f}–${row['typical_high']:.0f})"
            out.append(f"📉 Google lo marca como <b>precio bajo</b>{rng}")
        out.append("<i>Los precios cambian rápido</i>")
        return out
    seen = ago(row.get("found_at"), now)
    return [f"<i>🕒 Precio visto {seen} · puede cambiar rápido</i>" if seen
            else "<i>Precio encontrado recientemente; puede cambiar.</i>"]


def build_message(row: dict, site_url: str, country_name: str,
                  now: datetime | None = None) -> tuple[str, dict]:
    e = html.escape
    ahorro = savings_pct(row)
    header = (f"🔥 <b>{ahorro}% MENOS DE LO NORMAL</b>" if ahorro >= 10
              else "✈️ <b>VUELO EN OFERTA</b>")
    dest = e(row["dest_name"]) + (f", {e(row['dest_country'])}" if row.get("dest_country") else "")
    lines = [header, "", f"💸 <b>${row['price']:.0f} USD</b> ida y vuelta"]
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
    lines += [f"🔁 {detalle}", ""]
    lines += verified_lines(row, now)

    deal_url = f"{site_url}/oferta/{row['slug']}.html"
    share_text = (f"✈️ {row['origin_name']} → {row['dest_name']} por ${row['price']:.0f} "
                  f"ida y vuelta. Mira la oferta: {deal_url}")
    markup = {"inline_keyboard": [
        [{"text": "🎟️ Ver precio actual y reservar", "url": row["link"] or deal_url}],
        [{"text": "📲 Compartir en WhatsApp", "url": "https://wa.me/?text=" + quote(share_text)}],
        [{"text": f"🔎 Más ofertas desde {country_name}",
          "url": f"{site_url}/pais/{row['country']}.html"}],
    ]}
    return "\n".join(lines), markup


def build_expired_message(row: dict, site_url: str, country_name: str) -> tuple[str, dict]:
    e = html.escape
    motivo = {"subio": "El precio subió.", "salida": "La fecha de salida ya está muy cerca."}.get(
        row.get("expire_reason"), "Ya no podemos confirmar este precio.")
    lines = [
        "❌ <b>OFERTA TERMINADA</b>",
        f"<i>{motivo}</i>",
        "",
        f"<s>{e(row['origin_name'])} → {e(row['dest_name'])} · ${row['price']:.0f} USD ida y vuelta</s>",
        f"<s>🗓️ {fmt_date(row['departure_at'])}"
        + (f" – {fmt_date(row['return_at'])}" if row.get("return_at") else "") + "</s>",
        "",
        "Activa las notificaciones del canal para enterarte primero de la próxima 🔔",
    ]
    alert_url = (f"{site_url}/alertas.html?o={quote(row['origin'])}&d={quote(row['destination'])}"
                 f"&dn={quote(row['dest_name'])}")
    markup = {"inline_keyboard": [
        [{"text": f"🔎 Ver ofertas actuales desde {country_name}",
          "url": f"{site_url}/pais/{row['country']}.html"}],
        [{"text": "🔔 Avísame si vuelve a bajar", "url": alert_url}],
    ]}
    return "\n".join(lines), markup


# ---------- API de Telegram ----------
def _call(method: str, payload: dict) -> dict | None:
    r = requests.post(API.format(token=env("TELEGRAM_BOT_TOKEN"), method=method),
                      json=payload, timeout=20)
    if not r.ok:
        print(f"[telegram] {method} error {r.status_code}: {r.text[:200]}")
        return None
    return r.json().get("result")


def send(text: str, markup: dict, chat_id: str | None = None):
    """Envía al canal general (por defecto) o a otro chat. Devuelve message_id o None."""
    res = _call("sendMessage", {
        "chat_id": chat_id or env("TELEGRAM_CHANNEL"), "text": text, "parse_mode": "HTML",
        "reply_markup": markup, "link_preview_options": {"is_disabled": True}})
    return res.get("message_id") if isinstance(res, dict) else None


def edit(chat_id: str, message_id: int, text: str, markup: dict) -> bool:
    return _call("editMessageText", {
        "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML",
        "reply_markup": markup, "link_preview_options": {"is_disabled": True}}) is not None


def bot_username() -> str:
    """Usuario del bot (para enlazarlo desde la web); vacío si no se puede obtener."""
    if not env("TELEGRAM_BOT_TOKEN"):
        return ""
    try:
        r = requests.get(API.format(token=env("TELEGRAM_BOT_TOKEN"), method="getMe"), timeout=15)
        return r.json().get("result", {}).get("username", "") if r.ok else ""
    except Exception:
        return ""


# ---------- canales ----------
def _vars() -> dict:
    """Variables del repositorio (GitHub las pasa como JSON en BVB_VARS) + entorno."""
    out = {}
    try:
        out.update(json.loads(env("BVB_VARS") or "{}"))
    except ValueError:
        pass
    out.update({k: v for k, v in os.environ.items() if k.startswith("TELEGRAM_CHANNEL")})
    return out


def channel_var(cid: str) -> str:
    return "TELEGRAM_CHANNEL_" + cid.upper().replace("-", "_")


def country_channels(cfg: dict) -> dict:
    """{id_país: chat} para los países con canal propio (variable TELEGRAM_CHANNEL_<PAÍS>)."""
    v = _vars()
    return {cid: v[channel_var(cid)].strip() for cid in cfg["countries"]
            if (v.get(channel_var(cid)) or "").strip()}


def channel_links(cfg: dict) -> dict:
    """Enlaces t.me públicos: {'main': url, '<país>': url}."""
    def link(chat):
        return f"https://t.me/{chat.lstrip('@')}" if chat and chat.startswith("@") else ""
    out = {"main": link(_vars().get("TELEGRAM_CHANNEL", "") or env("TELEGRAM_CHANNEL"))}
    out.update({cid: link(chat) for cid, chat in country_channels(cfg).items()})
    return {k: v for k, v in out.items() if v}


def _quiet(now: datetime, tzname: str, quiet: list) -> bool:
    try:
        hour = now.astimezone(ZoneInfo(tzname)).hour
    except Exception:
        return False
    start, end = quiet
    return hour >= start or hour < end if start > end else start <= hour < end


def _country_tz(cfg: dict, cid: str) -> str:
    for z in cfg.get("timezones", {}).get(cid, []):
        if not z.endswith("/"):
            return z
    return cfg["social"]["timezone"]


# ---------- publicación ----------
def publish(conn, cfg: dict, now: datetime | None = None, verifier=None) -> dict:
    """Publica en Telegram las mejores ofertas activas y recientes.

    Cada oferta se verifica en vivo UNA sola vez (verifier) y se reparte a su
    canal de país y al general, según el cupo libre de cada canal. Sin
    presupuesto de verificación no se publica (nunca sale nada sin verificar).
    verifier=None publica sin verificar (solo para pruebas)."""
    if not env("TELEGRAM_BOT_TOKEN"):
        print("[telegram] sin credenciales, se omite")
        return {}
    now = now or datetime.now(timezone.utc)
    soc, site = cfg["social"], f"https://{cfg['site']['domain']}"
    max_age = cfg["freshness"]["max_age_hours"]

    found = sorted(k for k in _vars() if k.startswith("TELEGRAM_CHANNEL_"))
    print(f"[telegram] variables de canal por país encontradas: {found or 'ninguna'} "
          f"(nombres esperados: TELEGRAM_CHANNEL_<PAÍS>, p. ej. {channel_var('mexico')})")

    general = env("TELEGRAM_CHANNEL")
    targets = []
    if general:
        targets.append(("general", general, soc["main"], soc["timezone"]))
    by_country = country_channels(cfg)
    for cid, chat in by_country.items():
        targets.append((cid, chat, soc["country"], _country_tz(cfg, cid)))

    stats, room, names = {}, {}, {}
    for name, chat, rules, tzname in targets:
        names[chat] = name
        if _quiet(now, tzname, soc["quiet_hours"]):
            stats[name] = "horario sin publicar"
            continue
        sent_24h = conn.execute(
            "SELECT COUNT(*) FROM telegram_posts WHERE chat_id=? AND posted_at >= datetime('now','-1 day')",
            (chat,)).fetchone()[0]
        stats[name] = 0
        free = min(rules["per_run"], rules["per_day"] - sent_24h)
        if free > 0:
            room[chat] = free
    if not room:
        return stats

    rows = conn.execute(
        """SELECT * FROM deals WHERE status='active' AND found_at IS NOT NULL
             AND published_at >= datetime('now','-1 day')
             AND COALESCE(verify_status, '') != 'rechazada'
           ORDER BY score ASC""").fetchall()
    rows = sorted(rows, key=lambda r: priority(dict(r), cfg, now))
    for row in rows:
        if not room:
            break
        d = dict(row)
        found_age = age_hours(d["found_at"], now)
        if found_age is None or found_age > max_age:
            continue
        posted = {r[0] for r in conn.execute("SELECT chat_id FROM telegram_posts WHERE deal_id=?", (d["id"],))}
        want = [c for c in (by_country.get(d["country"]), general) if c and c in room and c not in posted]
        if not want:
            continue
        if verifier is not None:
            res = verifier.ensure(d)
            if res != "ok":
                continue  # sin verificar (o rechazada): no se publica; las ya verificadas sí
        cname = cfg["countries"].get(d["country"], {}).get("name", "tu país")
        text, markup = build_message(d, site, cname, now)
        for chat in want:
            mid = send(text, markup, chat_id=chat)
            if mid:
                conn.execute("INSERT INTO telegram_posts (deal_id, chat_id, message_id) VALUES (?,?,?)",
                             (d["id"], chat, mid))
                stats[names[chat]] += 1
                room[chat] -= 1
                if room[chat] <= 0:
                    del room[chat]
        conn.commit()
    return stats


def mark_expired_posts(conn, cfg: dict) -> int:
    """Edita los posts de ofertas que terminaron para avisarlo en el canal."""
    if not env("TELEGRAM_BOT_TOKEN"):
        return 0
    site = f"https://{cfg['site']['domain']}"
    rows = conn.execute(
        """SELECT p.rowid AS post_rowid, p.chat_id, p.message_id, d.*
           FROM telegram_posts p JOIN deals d ON d.id = p.deal_id
           WHERE d.status='expired' AND p.edited=0""").fetchall()
    done = 0
    for r in rows:
        d = dict(r)
        cname = cfg["countries"].get(d["country"], {}).get("name", "tu país")
        text, markup = build_expired_message(d, site, cname)
        ok = edit(d["chat_id"], d["message_id"], text, markup)
        conn.execute("UPDATE telegram_posts SET edited=? WHERE rowid=?", (1 if ok else 2, d["post_rowid"]))
        done += ok
    conn.commit()
    return done
