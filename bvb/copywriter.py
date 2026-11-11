"""Textos para web y redes. Usa Claude si hay ANTHROPIC_API_KEY; si no, plantilla."""
import json

from .config import env

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MODEL = "claude-haiku-5-5"


def fmt_date(iso: str) -> str:
    if not iso or len(iso) < 10:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)} de {MONTHS[int(m) - 1]}"


def fmt_stops(n) -> str:
    n = int(n or 0)
    return "directo" if n == 0 else ("1 escala" if n == 1 else f"{n} escalas")


def savings_pct(d: dict) -> int:
    """% de ahorro solo si hay mediana real (no se inventa con el tope inicial)."""
    if not d.get("baseline"):
        return 0
    return max(0, round((1 - d["price"] / d["baseline"]) * 100))


def _dates(d: dict) -> str:
    out = fmt_date(d["departure_at"])
    if d.get("return_at"):
        out += f" – {fmt_date(d['return_at'])}"
    return out


def template_copy(d: dict) -> dict:
    ahorro = savings_pct(d)
    ahorro_txt = f" (~{ahorro}% menos de lo normal)" if ahorro >= 10 else ""
    dest = d["dest_name"] + (f", {d['dest_country']}" if d.get("dest_country") else "")
    aerolinea = f" con {d['airline_name']}" if d.get("airline_name") else ""
    web = (f"Vuelo ida y vuelta de {d['origin_name']} a {dest} por ${d['price']:.0f}{ahorro_txt}. "
           f"Fechas: {_dates(d)}. Vuelo {fmt_stops(d['transfers'])}{aerolinea}. "
           f"Los precios cambian rápido: revisa disponibilidad antes de que suba.")
    social = (f"{d.get('flag', '')} ✈️ {d['origin_name']} → {dest} desde ${d['price']:.0f} "
              f"ida y vuelta{ahorro_txt}\n📅 {_dates(d)} · {fmt_stops(d['transfers'])}\n👉 {d['link']}")
    return {"copy_web": web, "copy_social": social.strip()}


def claude_copy(d: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    facts = {
        "origen": d["origin_name"], "destino": d["dest_name"], "pais_destino": d.get("dest_country"),
        "precio_usd_ida_y_vuelta": round(d["price"]), "aerolinea": d.get("airline_name"),
        "salida": d["departure_at"][:10], "regreso": (d.get("return_at") or "")[:10],
        "escalas": fmt_stops(d["transfers"]),
        "ahorro_pct_vs_normal": savings_pct(d) or None,
    }
    prompt = (
        "Eres el redactor de buscavuelosbaratos.com, sitio de ofertas de vuelos para "
        "viajeros de Latinoamérica. Con estos datos, escribe en español neutro y cercano:\n"
        "1) copy_web: 2-3 frases para la página de la oferta.\n"
        "2) copy_social: post corto para Telegram (máx 280 caracteres, 2-3 emojis, sin hashtags, "
        "sin el enlace).\n"
        "No inventes datos que no estén aquí; si ahorro_pct_vs_normal es null, no menciones "
        "porcentajes. Responde solo JSON con esas dos claves.\n\n"
        f"{json.dumps(facts, ensure_ascii=False)}"
    )
    msg = client.messages.create(model=MODEL, max_tokens=500,
                                 messages=[{"role": "user", "content": prompt}])
    text = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    out = json.loads(text)
    out["copy_social"] = f"{d.get('flag', '')} {out['copy_social'].strip()}\n👉 {d['link']}".strip()
    return out


def write_copy(d: dict) -> dict:
    if env("ANTHROPIC_API_KEY"):
        try:
            return claude_copy(d)
        except Exception as e:
            print(f"[aviso] Claude falló, uso plantilla: {e}")
    return template_copy(d)
