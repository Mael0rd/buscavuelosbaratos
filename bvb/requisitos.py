"""Requisitos para viajar a <país>: visa por pasaporte, formularios, salud, seguro y aduana.

/requisitos            todos los países
/requisitos/<país>     un país de destino (los que tienen vuelos desde varias ciudades)

La visa sale de los datos de Passport Index (bvb/visas). Lo demás (formularios,
seguro, vacunas) está revisado a mano en fuentes oficiales y noticias: REVIEWED dice
cuándo. Revisar cada 2–3 meses: estos requisitos cambian seguido.
"""
from . import visas
from .routes import slugify

REVIEWED = "2026-11-18"
MIN_ROUTES = 5  # países con menos rutas no tienen página

# Países de América con riesgo de fiebre amarilla (OMS). Si vienes de uno, varios destinos
# piden el certificado internacional de vacunación.
YF_RISK = {"AR": "Argentina (zonas del norte)", "BO": "Bolivia", "BR": "Brasil", "CO": "Colombia",
           "EC": "Ecuador", "GF": "Guayana Francesa", "GY": "Guyana", "PA": "Panamá (zonas del este)",
           "PY": "Paraguay", "PE": "Perú", "SR": "Surinam", "TT": "Trinidad y Tobago", "VE": "Venezuela"}
# Costa Rica exige la vacuna a costarricenses y residentes que viajen a estos países (Ministerio de Salud, 2026)
CR_YF_EXIT = {"BO", "BR", "CO", "EC", "GF", "GY", "PY", "PE", "SR", "TT", "VE"}
MERCOSUR_ID = {"AR", "BR", "UY", "PY", "CL", "BO", "PE", "CO", "EC"}  # se puede viajar con documento de identidad
CA4 = {"GT", "SV", "HN", "NI"}

# Formularios y requisitos propios de cada país. ("nombre", "qué es", "enlace oficial" o "", obligatorio)
FORMS = {
    "MX": [("FMM Digital (Forma Migratoria Múltiple)",
            "Si llegas en avión ya no se llena antes: en los principales aeropuertos se genera al pasar migración (en "
            "los filtros automáticos, escaneando el código QR del ticket). Guárdala: te la pueden pedir al salir.", "https://www.gob.mx/inm", True),
           ("Visitax (solo Quintana Roo)",
            "Si vas a Cancún, Tulum, Playa del Carmen u otro destino de Quintana Roo, el estado cobra un impuesto al "
            "turista que se paga en línea antes de salir de México.", "https://visitax.gob.mx", True)],
    "CO": [("Check-MIG",
            "Pre-registro migratorio gratuito de Migración Colombia. Hoy es opcional y sugerido, pero agiliza la "
            "entrada y algunas aerolíneas lo piden. Se llena entre 72 horas y 1 hora antes del vuelo.",
            "https://www.migracioncolombia.gov.co", False)],
    "DO": [("e-Ticket",
            "Formulario electrónico obligatorio y gratuito para entrar y salir del país (migración, aduana y salud "
            "en uno). Se recomienda llenarlo hasta 72 horas antes. Cuidado con sitios que lo cobran.",
            "https://eticket.migracion.gob.do", True)],
    "CU": [("D'Viajeros",
            "Declaración digital obligatoria (migración, salud y aduana). Al terminar recibes un código QR que "
            "muestras en el check-in y al llegar.", "https://dviajeros.mitrans.gob.cu", True),
           ("Tarjeta del turista o visa electrónica",
            "La mayoría de turistas la necesita; la venden aerolíneas y agencias o se pide en línea.", "", True)],
    "AW": [("ED Card de Aruba",
            "Tarjeta de embarque y desembarque en línea, obligatoria para todos (también bebés y niños). Cuesta "
            "US$20 y se pide hasta 7 días antes del vuelo; necesitas la aprobación antes de abordar.",
            "https://www.edcardaruba.aw", True)],
    "CW": [("DI Card (Digital Immigration Card)",
            "Tarjeta de inmigración digital obligatoria y gratuita; se llena en los 7 días antes del vuelo.",
            "https://dicardcuracao.com", True)],
    "GB": [("ETA del Reino Unido",
            "Desde el 25 de febrero de 2026 es obligatoria para quienes no necesitan visa (por ejemplo, Argentina, "
            "Brasil, Chile, Costa Rica, Guatemala, México, Panamá, Paraguay, Perú y Uruguay). Cuesta £16, vale 2 años "
            "y se pide en línea o en la app oficial con al menos 3 días hábiles de anticipación.",
            "https://www.gov.uk/eta", True)],
    "US": [("ESTA (solo pasaportes del Programa de Exención de Visas)",
            "De los pasaportes latinoamericanos, solo Chile entra con ESTA; los demás necesitan visa B1/B2.",
            "https://esta.cbp.dhs.gov", False),
           ("I-94", "El registro de entrada es automático si llegas en avión; puedes consultarlo en línea.",
            "https://i94.cbp.dhs.gov", False)],
    "CA": [("eTA de Canadá",
            "Quienes no necesitan visa y llegan en avión deben pedir la eTA en línea antes de viajar (cuesta C$7). "
            "Usa solo el sitio del Gobierno de Canadá.", "https://www.canada.ca/en/immigration-refugees-citizenship/services/visit-canada/eta.html", True)],
    "EC": [("Galápagos: tarjeta de control de tránsito y tasa del parque",
            "Para ir a Galápagos se compra la Tarjeta de Control de Tránsito antes del vuelo, se paga la tasa de "
            "ingreso al Parque Nacional al llegar y se pide seguro médico.", "https://www.gobiernogalapagos.gob.ec", True)],
}
SCHENGEN_FORMS = [
    ("EES (Sistema de Entradas y Salidas)",
     "Desde 2026 el control fronterizo registra tus huellas y una foto la primera vez que entras al espacio "
     "Schengen. No hay que pedir nada antes: se hace en el aeropuerto.", "https://travel-europe.europa.eu/ees", True),
    ("ETIAS (todavía no funciona)",
     "Permiso electrónico previsto para quienes no necesitan visa; aún no está en marcha (se espera para 2027). "
     "Hoy no hay que pagar nada: desconfía de sitios que lo cobren.", "https://travel-europe.europa.eu/etias", False),
]
INSURANCE = {
    "CU": "Obligatorio por ley: el seguro médico debe cubrir emergencias, evacuación y repatriación. Lleva la póliza impresa o en el celular.",
    "AR": "Desde 2025 (Decreto 366/2025) los extranjeros deben declarar al entrar que tienen seguro de salud, y los "
          "hospitales públicos pueden cobrar la atención que no sea urgente a quienes no residen en el país.",
    "EC": "Para Galápagos es obligatorio; para el resto del país no se exige, pero se recomienda.",
    "SCHENGEN": "Si necesitas visa Schengen, el seguro es obligatorio (mínimo €30.000 de cobertura médica). Sin visa no se "
                "exige siempre, pero en la frontera te pueden pedir comprobar cómo cubrirías gastos: llévalo.",
}


def _country_pages(xp_rows: list[dict], vi_passports: list[dict], vi_pairs: list[dict], cfg: dict) -> list[dict]:
    nm = visas.names()
    by_cc = {}
    for r in xp_rows:
        if r["cc"]:
            by_cc.setdefault(r["cc"].upper(), []).append(r)
    pair_url = {(v["pp"]["id"], v["dest"]): v["url"] for v in vi_pairs}
    data, _ = visas.load()
    pages = []
    for cc, rows in by_cc.items():
        if len(rows) < (2 if cc in FORMS else MIN_ROUTES):
            continue
        name = nm.get(cc) or rows[0]["c"]
        rules_cc = visas.SAME_RULES.get(cc, cc)  # Puerto Rico → reglas de EE. UU.
        schengen = rules_cc in visas.SCHENGEN
        by_pp = []
        for p in vi_passports:
            own = p["passport"] == rules_cc or p["cc"].upper() == cc
            rec = (data.get(p["passport"]) or {}).get(rules_cc)
            if own:
                e = {"key": "own", "label": "Es tu país", "short": "Es tu país"}
            elif not rec:
                continue
            else:
                e = visas.entry(rec)
            by_pp.append({"id": p["id"], "name": p["name"], "cc": p["cc"], "demonym": p["demonym"], **e,
                          "url": pair_url.get((p["id"], cc)), "note": "" if own else visas._note(p["passport"], rules_cc, e["key"])})
        if len([x for x in by_pp if x["key"] != "own"]) < 5 and cc not in FORMS:
            continue
        forms = list(FORMS.get(rules_cc, [])) + (SCHENGEN_FORMS if schengen else [])
        insurance = INSURANCE.get(rules_cc) or (INSURANCE["SCHENGEN"] if schengen else "")
        rows.sort(key=lambda x: x["p"])
        seen, flights = set(), []
        for r in rows:  # la ruta más barata a cada ciudad del país
            if r["d"] not in seen:
                seen.add(r["d"])
                flights.append(r)
        free = [x for x in by_pp if x["key"] in ("free", "arrival", "eta")]
        page = {"cc": cc, "name": name, "slug": slugify(name), "rules_cc": rules_cc, "schengen": schengen,
                "passports": by_pp, "n_free": len(free), "n_pp": len([x for x in by_pp if x["key"] != "own"]),
                "forms": forms, "insurance": insurance, "yf_risk": cc in YF_RISK,
                "cr_exit_yf": cc in CR_YF_EXIT, "mercosur": cc in MERCOSUR_ID, "ca4": cc in CA4,
                "flights": flights[:6], "cities": [r for r in flights if r["ds"]][:12],
                "n_routes": len(rows), "url": f"/requisitos/{slugify(name)}",
                "official": visas.OFFICIAL.get(rules_cc) or (visas.SCHENGEN_OFFICIAL if schengen else None)}
        page["faq"] = faq(page)
        page["indexable"] = bool(forms or insurance) or page["n_pp"] >= 10
        pages.append(page)
    pages.sort(key=lambda p: -p["n_routes"])
    return pages


def _list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def faq(p: dict) -> list[tuple[str, str]]:
    n = p["name"]
    must = [f[0] for f in p["forms"] if f[3]]
    out = [(f"¿Qué necesito para viajar a {n}?",
            "Pasaporte vigente (idealmente con 6 meses de vigencia), boleto de regreso, reserva de hospedaje y "
            "dinero suficiente para tu estadía"
            + (f"; además: {_list(must)}" if must else "") + ". Según tu pasaporte, también puedes necesitar visa.")]
    free = [x["name"] for x in p["passports"] if x["key"] in ("free", "arrival", "eta")]
    need = [x["name"] for x in p["passports"] if x["key"] in ("visa", "evisa")]
    if free or need:
        a = ""
        if free:
            a += f"No necesitan visa (o la reciben al llegar) con pasaporte de {_list(free)}. "
        if need:
            a += f"Necesitan visa: {_list(need)}."
        out.append((f"¿Qué latinoamericanos necesitan visa para {n}?", a.strip()))
    if p["forms"]:
        out.append((f"¿Hay que llenar algún formulario para entrar a {n}?",
                    " ".join(f"{f[0]}: {f[1]}" for f in p["forms"][:2])))
    if p["insurance"]:
        out.append((f"¿Es obligatorio el seguro de viaje para {n}?", p["insurance"]))
    if p["yf_risk"]:
        out.append((f"¿Necesito la vacuna de la fiebre amarilla para {n}?",
                    f"{n} tiene zonas con riesgo de fiebre amarilla, así que la vacuna se recomienda. Aplícatela al "
                    "menos 10 días antes"
                    + (". Si viajas desde Costa Rica es obligatoria: sin el certificado la aerolínea no te deja abordar."
                       if p["cr_exit_yf"] else ".")
                    + " Además, al volver o seguir a otros países te pueden pedir el certificado."))
    return out


def build(xp_rows, vi_passports, vi_pairs, cfg) -> list[dict]:
    return _country_pages(xp_rows, vi_passports, vi_pairs, cfg)
