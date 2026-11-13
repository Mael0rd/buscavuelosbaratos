"""Equipaje y tarifas por aerolínea (/equipaje y /equipaje/<aerolínea>).

Datos revisados a mano en las páginas oficiales y en noticias de cada aerolínea
(fecha en REVIEWED). Las reglas cambian seguido: cada página dice cuándo se revisó y
enlaza a la fuente oficial. Medidas en cm (largo x ancho x alto) y peso en kg; None =
no hay límite publicado o no se incluye.
"""
REVIEWED = "2026-11-13"

# Cada tarifa: (nombre, artículo personal, equipaje de mano, maleta en bodega, nota)
AIRLINES = [
    {"slug": "avianca", "name": "Avianca", "country": "Colombia", "cc": "co", "kind": "tradicional",
     "aliases": ["Avianca", "Avianca Costa Rica", "Avianca El Salvador", "Avianca Ecuador", "Avianca Guatemala"],
     "personal": {"dims": (45, 35, 25), "kg": None},
     "carry": {"dims": (55, 35, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Light", True, True, False, "Tarifa más barata en vuelos internacionales en América: desde el 27 de enero de 2026 incluye equipaje de mano de 10 kg."),
         ("Basic", True, False, False, "Solo en vuelos nacionales de Colombia: únicamente artículo personal."),
         ("Classic y superiores", True, True, True, "Suman maleta en bodega y más flexibilidad; revisa el detalle al comprar."),
     ],
     "tip": "En rutas internacionales dentro de América ya no hay tarifa sin equipaje de mano: la Light lo incluye.",
     "official": "https://www.avianca.com"},
    {"slug": "copa", "name": "Copa Airlines", "country": "Panamá", "cc": "pa", "kind": "tradicional",
     "aliases": ["Copa Airlines", "Copa"],
     "personal": {"dims": (43, 25, 22), "kg": None},
     "carry": {"dims": (56, 36, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Economy Basic", True, True, False, "Incluye equipaje de mano; la maleta en bodega se paga aparte."),
         ("Economy Classic", True, True, True, "1 maleta de 23 kg."),
         ("Economy Full", True, True, True, "2 maletas de 23 kg y máxima flexibilidad."),
     ],
     "tip": "Todas las tarifas incluyen equipaje de mano, también la más barata.",
     "official": "https://www.copaair.com"},
    {"slug": "latam", "name": "LATAM", "country": "Chile", "cc": "cl", "kind": "tradicional",
     "aliases": ["LATAM", "LATAM Airlines", "LATAM Airlines Brasil", "LATAM Airlines Peru", "LATAM Airlines Colombia",
                 "LATAM Airlines Ecuador", "LATAM Airlines Chile"],
     "personal": {"dims": (45, 35, 20), "kg": None},
     "carry": {"dims": (55, 35, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Basic", True, False, False, "Solo bolso o mochila pequeña (vuelos dentro de Sudamérica y entre Sudamérica y Centroamérica/Caribe)."),
         ("Light", True, True, False, "Suma equipaje de mano de 10 kg."),
         ("Full", True, True, True, "Suma 1 maleta de 23 kg, asiento estándar y cambios sin cargo."),
     ],
     "tip": "En vuelos largos (EE. UU., Europa) las tarifas y lo que incluyen cambian: revisa al comprar.",
     "official": "https://www.latamairlines.com"},
    {"slug": "aeromexico", "name": "Aeroméxico", "country": "México", "cc": "mx", "kind": "tradicional",
     "aliases": ["Aeroméxico", "Aeromexico", "Aeroméxico Connect"],
     "personal": {"dims": None, "kg": None},
     "carry": {"dims": (55, 40, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Básica", True, True, False, "Equipaje de mano y artículo personal: 10 kg entre los dos. Sin maleta en bodega."),
         ("Clásica", True, True, True, "1 maleta (25 kg en vuelos nacionales, 23 kg en internacionales)."),
         ("AM Plus", True, True, True, "1 maleta y más beneficios."),
     ],
     "tip": "Los 10 kg de cabina son la suma del equipaje de mano y el artículo personal.",
     "official": "https://www.aeromexico.com"},
    {"slug": "jetblue", "name": "JetBlue", "country": "EE. UU.", "cc": "us", "kind": "tradicional",
     "aliases": ["JetBlue", "JetBlue Airways"],
     "personal": {"dims": (43, 33, 20), "kg": None},
     "carry": {"dims": (56, 36, 23), "kg": None},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Main Base (antes Blue Basic)", True, True, False, "Incluye equipaje de mano; sin selección de asiento."),
         ("Main", True, True, False, "Con asiento y sin cargo por cambios."),
         ("Main Flex", True, True, False, "Además, reembolso al medio de pago."),
     ],
     "tip": "Desde el 3 de noviembre de 2026 la primera maleta cuesta US$50 (US$55 en temporada alta) pagada con anticipación en rutas de EE. UU., Latinoamérica y el Caribe.",
     "official": "https://www.jetblue.com/legal/fees"},
    {"slug": "volaris", "name": "Volaris", "country": "México", "cc": "mx", "kind": "bajo costo",
     "aliases": ["Volaris", "Volaris Costa Rica", "Volaris El Salvador"],
     "personal": {"dims": (45, 35, 20), "kg": None},
     "carry": {"dims": (55, 40, 25), "kg": 20},
     "checked": {"kg": 25, "linear": 158},
     "fares": [
         ("Zero", True, False, False, "Solo un objeto personal debajo del asiento."),
         ("Flex", True, None, None, "Eliges uno: equipaje de mano o maleta de 15 kg (solo en web y app)."),
         ("Plus", True, True, True, "Equipaje de mano y maleta de 25 kg, cambios ilimitados."),
         ("Básica", True, False, True, "Maleta de 15 kg; desde el 26 de octubre de 2026 solo en call center y aeropuertos."),
     ],
     "tip": "Los 20 kg de cabina son la suma del objeto personal y el equipaje de mano.",
     "official": "https://cms.volaris.com/es/viajando-con-volaris/politica-de-equipaje/"},
    {"slug": "viva-aerobus", "name": "Viva Aerobus", "country": "México", "cc": "mx", "kind": "bajo costo",
     "aliases": ["Viva Aerobus", "VivaAerobus", "Viva"],
     "personal": {"dims": (45, 35, 20), "kg": None},
     "carry": {"dims": (55, 40, 25), "kg": 10},
     "checked": {"kg": 25, "linear": 158},
     "fares": [
         ("Zero", True, False, False, "Solo artículo personal."),
         ("Light", True, True, False, "Equipaje de mano de 10 kg."),
         ("Smart", True, True, True, "Equipaje de mano de 15 kg y maleta de 25 kg."),
     ],
     "tip": "Viva está reorganizando los nombres de sus paquetes: revisa qué incluye el tuyo al comprar.",
     "official": "https://www.vivaaerobus.com"},
    {"slug": "arajet", "name": "Arajet", "country": "República Dominicana", "cc": "do", "kind": "bajo costo",
     "aliases": ["Arajet"],
     "personal": {"dims": (40, 25, 20), "kg": 6},
     "carry": {"dims": (56, 46, 25), "kg": 12},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Basic", True, False, False, "Artículo personal de 6 kg (10 kg en vuelos con Brasil)."),
         ("Classic", True, True, False, "Equipaje de mano de 12 kg."),
         ("Comfort", True, False, True, "Maleta de 23 kg."),
         ("Extra", True, True, True, "Equipaje de mano y maleta de 23 kg."),
     ],
     "tip": "El artículo personal de Arajet es de los más chicos: 40 x 25 x 20 cm.",
     "official": "https://www.arajet.com"},
    {"slug": "jetsmart", "name": "JetSMART", "country": "Chile", "cc": "cl", "kind": "bajo costo",
     "aliases": ["JetSMART", "JetSMART Airlines", "JetSMART Argentina", "JetSMART Peru", "JetSMART Colombia"],
     "personal": {"dims": (45, 35, 25), "kg": 10},
     "carry": {"dims": (55, 35, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Tarifa base", True, False, False, "Incluye solo bolso o mochila pequeña; equipaje de mano y maleta se pagan aparte o en paquetes."),
     ],
     "tip": "La mochila incluida puede pesar hasta 10 kg, más que en muchas aerolíneas de bajo costo.",
     "official": "https://jetsmart.com"},
    {"slug": "sky-airline", "name": "Sky Airline", "country": "Chile", "cc": "cl", "kind": "bajo costo",
     "aliases": ["Sky Airline", "SKY Airline", "Sky Airline Peru"],
     "personal": {"dims": (45, 35, 25), "kg": None},
     "carry": {"dims": (55, 35, 25), "kg": 10},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Basic (antes Zero)", True, False, False, "Solo artículo personal."),
         ("Light", True, True, False, "Equipaje de mano."),
         ("Max (antes Plus)", True, True, True, "1 maleta de 23 kg."),
         ("Max Flex (antes Full)", True, True, True, "2 maletas de 23 kg y máxima flexibilidad."),
     ],
     "tip": "En 2025 Sky cambió los nombres de sus tarifas; lo que incluye cada una se mantuvo.",
     "official": "https://www.skyairline.com"},
    {"slug": "wingo", "name": "Wingo", "country": "Colombia", "cc": "co", "kind": "bajo costo",
     "aliases": ["Wingo"],
     "personal": {"dims": (40, 35, 25), "kg": 10},
     "carry": {"dims": (55, 45, 25), "kg": 12},
     "checked": {"kg": 23, "linear": 158},
     "fares": [
         ("Go Basic", True, False, False, "Artículo personal de hasta 10 kg."),
         ("Go Standard", True, True, False, "Equipaje de mano de 12 kg."),
         ("Go Plus", True, True, True, "Maleta de 23 kg."),
         ("Go Extra", True, True, True, "Maleta de 23 kg y cambios ilimitados."),
     ],
     "tip": "Todas sus tarifas permiten al menos un cambio sin penalidad (pagando la diferencia).",
     "official": "https://www.wingo.com"},
]

GONE = [("Spirit Airlines", "dejó de operar el 2 de mayo de 2026")]


def fits(bag: tuple, limit: tuple | None) -> bool:
    """¿Cabe una pieza de medidas bag en el límite? Compara de mayor a menor (se puede girar)."""
    if not limit:
        return False
    return all(b <= lim for b, lim in zip(sorted(bag, reverse=True), sorted(limit, reverse=True)))


def build(route_pages: list[dict]) -> list[dict]:
    """Aerolíneas con sus rutas más baratas (donde aparece en las tarifas vistas)."""
    out = []
    for a in AIRLINES:
        names = {x.lower() for x in a["aliases"]}
        rs = [r for r in route_pages if any(x.lower() in names for x in r.get("airlines") or [])]
        rs.sort(key=lambda r: r["typical"])
        cheapest = next((f for f in a["fares"]), None)
        out.append({**a, "routes": rs[:12], "n_routes": len(rs), "cheapest": cheapest,
                    "faq": faq(a)})
    return out


def _dims(d) -> str:
    return " x ".join(str(x) for x in d) + " cm" if d else "no publicado"


def faq(a: dict) -> list[tuple[str, str]]:
    n, f0 = a["name"], a["fares"][0]
    inc = "artículo personal" + (" y equipaje de mano" if f0[2] else "") + (" y maleta en bodega" if f0[3] else "")
    out = [(f"¿Qué incluye la tarifa más barata de {n}?", f"La tarifa {f0[0]} incluye {inc}. {f0[4]}"),
           (f"¿Qué medidas tiene el equipaje de mano de {n}?",
            f"Hasta {_dims(a['carry']['dims'])}" + (f" y {a['carry']['kg']} kg" if a["carry"]["kg"] else "") + "."),
           (f"¿Qué medidas tiene el artículo personal de {n}?",
            f"{_dims(a['personal']['dims'])}" + (f", hasta {a['personal']['kg']} kg" if a["personal"]["kg"] else "")
            + "; debe caber debajo del asiento delantero.")]
    return out
