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


def savings_pct(d: dict) -> int:
    if not d.get("baseline"):
        return 0
    return max(0, round((1 - d["price"] / d["baseline"]) * 100))


def template_copy(d: dict) -> dict:
    escalas = "directo" if d["transfers"] == 0 else f"{d['transfers']} escala(s)"
    ahorro = savings_pct(d)
    ahorro_txt = f" (~{ahorro}% menos de lo normal)" if ahorro >= 10 else ""
    fechas = fmt_date(d["departure_at"])
    if d.get("return_at"):
        fechas += f" – {fmt_date(d['return_at'])}"
    web = (f"Vuelo ida y vuelta {d['origin']} → {d['dest_name']} por ${d['price']:.0f}"
           f"{ahorro_txt}. Fechas: {fechas}. Vuelo {escalas}. Los precios cambian rápido: "
           f"revisa disponibilidad antes de que suba.")
    social = (f"✈️ {d['origin']} → {d['dest_name']} desde ${d['price']:.0f} ida y vuelta{ahorro_txt}\n"
              f"📅 {fechas} · {escalas}\n👉 {d['link']}")
    return {"copy_web": web, "copy_social": social}


def claude_copy(d: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    facts = {k: d[k] for k in ("origin", "dest_name", "price", "airline",
                               "departure_at", "return_at", "transfers")}
    facts["ahorro_pct"] = savings_pct(d)
    prompt = (
        "Eres el redactor de buscavuelosbaratos.com, sitio de ofertas de vuelos desde "
        "Costa Rica. Con estos datos, escribe en español neutro y cercano:\n"
        "1) copy_web: 2-3 frases para la página de la oferta.\n"
        "2) copy_social: post corto para Telegram/Facebook (máx 280 caracteres, 2-3 emojis, "
        "sin hashtags excesivos, sin el enlace).\n"
        "No inventes datos que no estén aquí. Responde solo JSON con esas dos claves.\n\n"
        f"{json.dumps(facts, ensure_ascii=False)}"
    )
    msg = client.messages.create(model=MODEL, max_tokens=500,
                                 messages=[{"role": "user", "content": prompt}])
    text = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    out = json.loads(text)
    out["copy_social"] = out["copy_social"].rstrip() + f"\n👉 {d['link']}"
    return out


def write_copy(d: dict) -> dict:
    if env("ANTHROPIC_API_KEY"):
        try:
            return claude_copy(d)
        except Exception as e:
            print(f"[aviso] Claude falló, uso plantilla: {e}")
    return template_copy(d)
