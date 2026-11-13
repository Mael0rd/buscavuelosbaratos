"""¿Necesito visa? Requisitos de entrada por pasaporte y destino.

Datos: Passport Index (github.com/imorte/passport-index-data, licencia MIT). En cada
corrida se intenta bajar la versión más reciente (caché de 7 días en data/ref); si
falla, se usa la copia del repositorio (assets/visas). La página siempre dice de
qué fecha son los datos y pide confirmar con la fuente oficial antes de viajar.

Páginas:
  /visas                              elegir pasaporte
  /visas/<gentilicio>                 todos los países, con buscador y filtros
  /visas/<gentilicio>/<destino>       solo destinos a los que hay vuelos desde ese país
"""
import json
import re
import time

import requests

from . import geo
from .config import REF_DIR, ROOT
from .routes import slugify

ASSETS = ROOT / "assets" / "visas"
REMOTE = "https://raw.githubusercontent.com/imorte/passport-index-data/main/"
MAX_AGE = 7 * 86400

# país del sitio → (pasaporte ISO, gentilicio en plural para la URL y los textos)
PASSPORTS = {
    "mexico": ("MX", "mexicanos"), "guatemala": ("GT", "guatemaltecos"), "el-salvador": ("SV", "salvadoreños"),
    "honduras": ("HN", "hondureños"), "nicaragua": ("NI", "nicaragüenses"), "costa-rica": ("CR", "costarricenses"),
    "panama": ("PA", "panameños"), "cuba": ("CU", "cubanos"), "dominicana": ("DO", "dominicanos"),
    "puerto-rico": ("US", "puertorriqueños"), "colombia": ("CO", "colombianos"), "venezuela": ("VE", "venezolanos"),
    "ecuador": ("EC", "ecuatorianos"), "peru": ("PE", "peruanos"), "bolivia": ("BO", "bolivianos"),
    "chile": ("CL", "chilenos"), "argentina": ("AR", "argentinos"), "uruguay": ("UY", "uruguayos"),
    "paraguay": ("PY", "paraguayos"),
}

# Estados → (clave, texto corto, explicación)
STATUS = {
    "visa free": ("free", "No necesitas visa", "Puedes entrar como turista solo con tu pasaporte."),
    "visa on arrival": ("arrival", "Visa al llegar", "La visa se tramita en el aeropuerto al llegar; casi siempre hay que pagar una tarifa."),
    "eta": ("eta", "Autorización electrónica", "No es una visa, pero debes pedir un permiso en línea antes de viajar (suele aprobarse en minutos o días)."),
    "e-visa": ("evisa", "Visa electrónica", "Necesitas visa, pero se tramita en línea, sin ir a la embajada."),
    "visa required": ("visa", "Necesitas visa", "Debes tramitar la visa en la embajada o consulado antes de viajar."),
    "no admission": ("no", "Entrada no permitida", "Hoy no se admite la entrada de turistas con este pasaporte."),
}
ORDER = ["free", "arrival", "eta", "evisa", "visa", "no"]
GROUP_TITLES = {"free": "✅ Sin visa", "arrival": "🛬 Visa al llegar", "eta": "📱 Autorización electrónica",
                "evisa": "💻 Visa electrónica", "visa": "🛂 Necesitas visa", "no": "⛔ Entrada no permitida"}

# Territorios que usan las reglas de entrada de otro país
SAME_RULES = {"PR": "US", "VI": "US", "GU": "US"}

SCHENGEN = {"AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IT", "LV", "LI",
            "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH"}
OFFICIAL = {
    "US": ("Departamento de Estado de EE. UU.", "https://travel.state.gov/content/travel/en/us-visas/tourism-visit/visitor.html"),
    "CA": ("Gobierno de Canadá", "https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada.html"),
    "GB": ("Gobierno del Reino Unido", "https://www.gov.uk/check-uk-visa"),
    "MX": ("Instituto Nacional de Migración de México", "https://www.gob.mx/inm"),
    "AU": ("Gobierno de Australia", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-finder"),
    "JP": ("Ministerio de Relaciones Exteriores de Japón", "https://www.mofa.go.jp/j_info/visit/visa/index.html"),
}
SCHENGEN_OFFICIAL = ("Comisión Europea (visados Schengen)", "https://home-affairs.ec.europa.eu/policies/schengen/visa-policy_en")


def _note(passport: str, dest: str, key: str) -> str:
    """Contexto extra para los destinos más buscados."""
    if dest in SCHENGEN or dest == "CY":
        base = ("Las estancias de turismo en el espacio Schengen son de hasta 90 días dentro de cualquier periodo "
                "de 180 días, sumando todos los países Schengen. ")
        if key == "free":
            return base + ("Europa prepara ETIAS, un permiso electrónico de unos €20 para quienes hoy no necesitan "
                           "visa; todavía no funciona y se espera para 2027 (sin fecha publicada en noviembre de 2026). "
                           "Mientras tanto no hay que pedir nada: desconfía de sitios que lo cobren hoy.")
        return base
    if dest == "US" and key == "visa":
        return ("La visa de turista de EE. UU. es la B1/B2: se llena el formulario DS-160, se paga la tarifa y se "
                "asiste a una entrevista en el consulado. Los tiempos de espera para la cita pueden ser largos: "
                "revísalos antes de comprar el vuelo.")
    if dest == "US" and key == "eta":
        return "Con este pasaporte se viaja con ESTA (Programa de Exención de Visas), que se pide en línea."
    if dest == "CA" and passport == "MX":
        return ("Desde 2024, los mexicanos necesitan visa para Canadá, salvo quienes viajan en avión y tienen una visa "
                "de EE. UU. vigente o tuvieron una visa canadiense en los últimos 10 años: ellos pueden pedir la eTA.")
    if dest == "GB" and key == "eta":
        return "El Reino Unido pide la ETA (autorización electrónica de viaje) antes de volar; se tramita en línea o en su app."
    if dest == "CU":
        return ("Cuba pide a la mayoría de turistas una tarjeta del turista (visa de turismo), que suelen vender las "
                "aerolíneas o agencias, además del formulario electrónico de entrada D'Viajeros.")
    if dest == "DO" and key == "free":
        return "Para entrar y salir de República Dominicana hay que llenar el formulario electrónico gratuito (e-Ticket)."
    return ""


def _download(name: str):
    path = REF_DIR / f"visas-{name}"
    if path.exists() and time.time() - path.stat().st_mtime < MAX_AGE:
        return path.read_text(encoding="utf-8")
    try:
        r = requests.get(REMOTE + name, timeout=60)
        r.raise_for_status()
        REF_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text, encoding="utf-8")
        return r.text
    except Exception as e:  # noqa: BLE001
        print(f"[visas] no se pudo actualizar {name} ({e.__class__.__name__}); se usa la copia del repositorio")
        return path.read_text(encoding="utf-8") if path.exists() else None


def load() -> tuple[dict, str]:
    """({pasaporte: {destino: {"status", "days"}}}, fecha de los datos 'AAAA-MM-DD')."""
    snap = json.loads((ASSETS / "passport-index.json").read_text(encoding="utf-8"))
    data, updated = snap["data"], snap["updated"]
    raw, readme = _download("passport-index.json"), _download("README.md")
    if raw and readme:
        m = re.search(r"Last updated:\s*\*\*(\d{1,2}) (\w+) (\d{4})\*\*", readme)
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
                  "october", "november", "december"]
        try:
            fresh = json.loads(raw)
            if m and m.group(2).lower() in months:
                d = f"{m.group(3)}-{months.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"
                if d >= updated:
                    data = {p: fresh.get(p, data.get(p, {})) for p in data}
                    updated = d
        except ValueError:
            pass
    return data, updated


def names() -> dict:
    return json.loads((ASSETS / "paises_es.json").read_text(encoding="utf-8"))


def entry(rec: dict | None) -> dict:
    rec = rec or {"status": "visa required"}
    key, short, text = STATUS.get(rec.get("status"), STATUS["visa required"])
    days = rec.get("days")
    label = short + (f" · hasta {days} días" if days and key in ("free", "arrival", "eta") else "")
    return {"key": key, "short": short, "label": label, "text": text, "days": days}


def fmt_date(iso: str) -> str:
    from .routes import MONTHS
    y, m, d = iso.split("-")
    return f"{int(d)} de {MONTHS[int(m) - 1]} de {y}"


def build(cfg: dict, xp_rows: list[dict], origins: list[dict]) -> tuple[list, list, str]:
    """(páginas por pasaporte, páginas pasaporte-destino, fecha de los datos)."""
    data, updated = load()
    nm = names()
    by_cc_name = {}  # nombre del país en las rutas ("EE. UU.") → ISO
    for r in xp_rows:
        if r["cc"]:
            by_cc_name[r["cc"].upper()] = r["c"]
    origin_country = {o["code"]: o["country"] for o in origins}
    passports, pairs = [], []
    for cid, (pp, demonym) in PASSPORTS.items():
        if cid not in cfg["countries"] or pp not in data:
            continue
        c = cfg["countries"][cid]
        slug = slugify(demonym)
        reqs = data[pp]
        rows_here = [r for r in xp_rows if origin_country.get(r["o"]) == cid and r["cc"]]
        flights_to = {}
        for r in sorted(rows_here, key=lambda x: x["p"]):
            flights_to.setdefault(r["cc"].upper(), []).append(r)
        own = c["cc"].upper()
        items = []
        for dest, rec in reqs.items():
            if dest in (own, pp):
                continue
            e = entry(rec)
            items.append({"cc": dest.lower(), "name": nm.get(dest, dest), "slug": slugify(nm.get(dest, dest)),
                          **e, "has_page": dest in flights_to and SAME_RULES.get(dest) not in (own, pp),
                          "from": flights_to[dest][0]["p"] if dest in flights_to else None})
        items.sort(key=lambda x: x["name"])
        counts = {k: sum(1 for x in items if x["key"] == k) for k in ORDER}
        easy = counts["free"] + counts["arrival"]
        # Destinos sin visa (o con visa al llegar) más baratos desde este país
        cheap = []
        for dest, rs in flights_to.items():
            rec = reqs.get(dest) or reqs.get(SAME_RULES.get(dest, ""))
            if not rec or dest in (own, pp) or SAME_RULES.get(dest) in (own, pp):
                continue
            e = entry(rec)
            if e["key"] in ("free", "arrival"):
                cheap.append({**rs[0], "visa": e, "slug": slugify(nm.get(dest) or rs[0]["c"] or dest)})
        cheap.sort(key=lambda x: x["p"])
        pg = {"id": cid, "name": c["name"], "cc": c["cc"], "passport": pp, "demonym": demonym, "slug": slug,
              "us_passport": pp == "US" and cid != "united-states",
              "items": items, "groups": [(k, GROUP_TITLES[k], [x for x in items if x["key"] == k]) for k in ORDER],
              "counts": counts, "easy": easy, "total": len(items), "cheap": cheap[:8], "updated": updated}
        pg["faq"] = passport_faq(pg)
        passports.append(pg)
        for dest, rs in flights_to.items():
            if dest in (own, pp) or SAME_RULES.get(dest) in (own, pp):  # vuelos "nacionales"
                continue
            rec = reqs.get(dest) or reqs.get(SAME_RULES.get(dest, ""))
            if not rec:
                continue  # sin datos para ese destino: mejor no publicar una respuesta inventada
            e = entry(rec)
            dname = nm.get(dest) or rs[0]["c"] or dest
            off = OFFICIAL.get(dest) or (SCHENGEN_OFFICIAL if dest in SCHENGEN else None)
            pair = {"pp": pg, "dest": dest, "dname": dname, "dslug": slugify(dname), "visa": e,
                    "note": _note(pp, dest, e["key"]), "official": off, "flights": rs[:8],
                    "region": geo.region(rs[0]["c"]), "updated": updated,
                    "url": f"/visas/{slug}/{slugify(dname)}"}
            pair["faq"] = pair_faq(pair)
            pairs.append(pair)
        pg["pairs"] = sorted([x for x in pairs if x["pp"] is pg], key=lambda x: x["dname"])
    return passports, pairs, updated


def passport_faq(p: dict) -> list[tuple[str, str]]:
    d, cnt = p["demonym"], p["counts"]
    out = [(f"¿A cuántos países pueden viajar los {d} sin visa?",
            f"Con pasaporte {('de EE. UU.' if p['us_passport'] else 'de ' + p['name'])} se puede entrar sin visa a "
            f"{cnt['free']} países y con visa al llegar a {cnt['arrival']} más; en {cnt['eta']} hace falta una "
            f"autorización electrónica y en {cnt['evisa']} una visa electrónica (datos del {fmt_date(p['updated'])}).")]
    if p["cheap"]:
        x = p["cheap"][0]
        out.append((f"¿Cuál es el destino sin visa más barato para {d}?",
                    f"En nuestras búsquedas recientes, {x['n']} ({x['c']}), con vuelos ida y vuelta desde unos ${x['p']}."))
    return out


def pair_faq(x: dict) -> list[tuple[str, str]]:
    pp, v = x["pp"], x["visa"]
    q = f"¿Los {pp['demonym']} necesitan visa para {x['dname']}?"
    a = {"free": f"No. {v['text']}" + (f" Puedes quedarte hasta {v['days']} días." if v["days"] else ""),
         "arrival": f"No antes de viajar: {v['text'].lower()}",
         "eta": f"No necesitan visa, pero sí una autorización electrónica: {v['text'].lower()}",
         "evisa": f"Sí, pero electrónica: {v['text'].lower()}",
         "visa": f"Sí. {v['text']}",
         "no": v["text"]}[v["key"]]
    out = [(q, a)]
    if x["flights"]:
        f = x["flights"][0]
        out.append((f"¿Cuánto cuesta volar a {x['dname']} desde {pp['name']}?",
                    f"El vuelo ida y vuelta más barato que vimos recientemente fue a {f['n']}, desde unos ${f['p']}."))
    return out
