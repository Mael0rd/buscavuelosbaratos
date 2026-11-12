"""Canales de WhatsApp por región, en modo semiautomático (sin riesgo de bloqueo).

WhatsApp no tiene API oficial para publicar en canales. Por eso el bot de
Telegram le manda al administrador (variable WHATSAPP_RELAY_CHAT: su ID de chat)
cada oferta verificada ya redactada en formato WhatsApp, dentro de un bloque que
se copia con un toque, más un botón para abrir el canal. Él la pega en el canal.

El enlace del texto apunta a la página de la oferta (WhatsApp arma la vista
previa con la imagen del precio) con ?src=wa_<región>: la página cambia el SubID
del botón de reserva para medir las ventas que vienen de WhatsApp.
"""
import html
from datetime import datetime, timezone

from . import telegram
from .copywriter import fmt_date, fmt_stops, savings_pct
from .fresh import age_hours
from .verify import priority

SCHEMA = """
CREATE TABLE IF NOT EXISTS whatsapp_posts (
    deal_id INTEGER, region TEXT, sent_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (deal_id, region)
);
"""


def relay_chat() -> str:
    return str(telegram._vars().get("WHATSAPP_RELAY_CHAT") or "").strip()


def regions(cfg: dict) -> dict:
    """Regiones con canal de WhatsApp configurado (social.regions.<id>.whatsapp)."""
    return {rid: r for rid, r in (cfg.get("social", {}).get("regions") or {}).items()
            if (r.get("whatsapp") or {}).get("url")}


def wa_links(cfg: dict) -> dict:
    """{id_país: {"url", "name"}} del canal de WhatsApp de su región (para la web)."""
    out = {}
    for rid, r in regions(cfg).items():
        out.update({cid: {"url": r["whatsapp"]["url"], "name": r.get("name", rid)}
                    for cid in r.get("countries", [])})
    return out


def build_text(d: dict, site_url: str, src: str, now: datetime | None = None) -> str:
    """Texto listo para pegar en WhatsApp (*negrita*, ~tachado~)."""
    ahorro = savings_pct(d)
    price = d.get("live_price") or d["price"]
    lines = [f"🔥 *{ahorro}% MENOS DE LO NORMAL*" if ahorro >= 10 else "✈️ *VUELO EN OFERTA*", ""]
    dest = d["dest_name"] + (f", {d['dest_country']}" if d.get("dest_country") else "")
    lines.append(f"{d.get('flag', '')} *{d['origin_name']} → {dest}*".strip())
    p = f"💸 *${price:.0f} USD* ida y vuelta"
    if ahorro >= 10 and d.get("baseline"):
        p += f"  ~${d['baseline']:.0f}~"
    lines.append(p)
    fechas = fmt_date(d["departure_at"]) + (f" – {fmt_date(d['return_at'])}" if d.get("return_at") else "")
    lines.append(f"🗓️ {fechas} · {fmt_stops(d['transfers'])}")
    if d.get("verified_at"):
        lines.append(f"✅ Precio verificado {telegram.ago(d['verified_at'], now)}")
    lines += ["", f"👉 {site_url}/oferta/{d['slug']}?src={src}"]
    return "\n".join(lines)


def relay(conn, cfg: dict, now: datetime | None = None, verifier=None) -> dict:
    """Manda al administrador las mejores ofertas nuevas de cada región, listas para WhatsApp."""
    chat = relay_chat()
    regs = regions(cfg)
    if not regs:
        return {}
    if not chat or not telegram.env("TELEGRAM_BOT_TOKEN"):
        print("[whatsapp] falta la variable WHATSAPP_RELAY_CHAT (tu ID de chat de Telegram); se omite")
        return {}
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    site = f"https://{cfg['site']['domain']}"
    soc, vcfg = cfg["social"], cfg["verify"]
    max_age = cfg["freshness"]["max_age_hours"]
    stats = {}
    for rid, r in regs.items():
        wa = r["whatsapp"]
        countries = [c for c in r.get("countries", []) if c in cfg["countries"]]
        if not countries:
            continue
        if telegram._quiet(now, telegram._country_tz(cfg, countries[0]), soc["quiet_hours"]):
            stats[rid] = "horario sin publicar"
            continue
        sent_24h = conn.execute(
            "SELECT COUNT(*) FROM whatsapp_posts WHERE region=? AND sent_at >= datetime('now','-1 day')",
            (rid,)).fetchone()[0]
        free = min(wa.get("per_run", 1), wa.get("per_day", 3) - sent_24h)
        stats[rid] = 0
        if free <= 0:
            continue
        marks = ",".join("?" * len(countries))
        rows = [dict(x) for x in conn.execute(
            f"""SELECT * FROM deals WHERE status='active' AND country IN ({marks})
                  AND found_at IS NOT NULL AND published_at >= datetime('now','-1 day')
                  AND COALESCE(verify_status, '') != 'rechazada'
                  AND id NOT IN (SELECT deal_id FROM whatsapp_posts WHERE region=?)""",
            (*countries, rid)).fetchall()]
        for d in sorted(rows, key=lambda x: priority(x, cfg, now)):
            if free <= 0:
                break
            fa = age_hours(d["found_at"], now)
            if fa is None or fa > max_age:
                continue
            if verifier is not None and verifier.ensure(d) != "ok":
                continue
            d = dict(conn.execute("SELECT * FROM deals WHERE id=?", (d["id"],)).fetchone())
            va = age_hours(d.get("verified_at"), now)
            if d.get("verify_status") != "ok" or va is None or va > vcfg["cache_hours"]:
                continue  # nunca se manda nada sin verificación reciente
            text = build_text(d, site, f"wa_{rid}", now)
            n = sent_24h + stats[rid] + 1
            msg = (f"📲 <b>Para WhatsApp · {html.escape(r.get('name', rid))}</b> ({n}/{wa.get('per_day', 3)} hoy)\n"
                   f"Toca el bloque para copiarlo y pégalo en el canal:\n\n<pre>{html.escape(text)}</pre>")
            markup = {"inline_keyboard": [[{"text": "🟢 Abrir canal de WhatsApp", "url": wa["url"]}]]}
            if not telegram.send(msg, markup, chat_id=chat):
                print("[whatsapp] ⚠ no se pudo enviar: escríbele /start al bot desde tu cuenta y revisa WHATSAPP_RELAY_CHAT")
                stats[rid] = "error al enviar"
                break
            conn.execute("INSERT OR IGNORE INTO whatsapp_posts (deal_id, region) VALUES (?, ?)", (d["id"], rid))
            conn.commit()
            stats[rid] += 1
            free -= 1
    return stats
