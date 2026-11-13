"""Contenido propio de cada página de país (/pais/<id>) para que se posicione sola.

Todo sale de los datos que el sistema ya junta cada hora (rutas con historial y
ciudades de salida), así que el texto es único por país y se actualiza solo, aunque
ese día no haya ofertas. Incluye el vocabulario local de cada país ("term": pasajes,
tiquetes, boletos de avión...) en el título, la descripción y los subtítulos.
"""
from collections import Counter

TOP_DESTS = 10
# Destinos por los que más se pregunta: si el país tiene datos de ellos, van a las preguntas frecuentes
POPULAR = ["MIA", "NYC", "MAD", "CUN", "ORL", "BOG", "LAX", "PTY", "MEX", "BCN", "SJO", "LIM", "SCL", "BUE"]


def _money(x) -> str:
    return f"${x:.0f}"


def _join(items: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    return items[0] if len(items) == 1 else (", ".join(items[:-1]) + " y " + items[-1] if items else "")


def summarize(c: dict) -> dict:
    """Agrega a la sección del país: destinos más baratos, mes más barato, preguntas y descripción."""
    name, term = c["name"], c.get("term") or "boletos de avión"
    routes = c.get("routes") or []

    # Destino más barato por destino (entre todas las ciudades de salida del país)
    best: dict = {}
    for r in routes:
        b = best.get(r["destination"])
        if not b or r["typical"] < b["typical"]:
            best[r["destination"]] = r
    top = sorted(best.values(), key=lambda r: r["typical"])[:TOP_DESTS]

    months = Counter(r["cheapest_month"][0] for r in routes if r.get("cheapest_month"))
    best_month = None
    if months:
        label, n = months.most_common(1)[0]
        best_month = {"label": label, "n": n, "total": sum(months.values())}

    cities = [o for o in c.get("cities") or [] if o.get("n_dests")]
    faq = []
    if top:
        t = top[0]
        rest = _join([f"{r['dest_name']} ({_money(r['typical'])})" for r in top[1:4]])
        faq.append((f"¿Cuál es el destino internacional más barato desde {name}?",
                    f"Según los precios que revisamos cada hora, {t['dest_name']}"
                    f"{', ' + t['dest_country'] if t.get('dest_country') else ''} es el más barato: "
                    f"unos {_money(t['typical'])} USD ida y vuelta saliendo de {t['origin_name']}."
                    + (f" Le siguen {rest}." if rest else "")))
    if best_month:
        faq.append((f"¿Cuál es el mes más barato para volar desde {name}?",
                    f"En nuestras búsquedas recientes, {best_month['label']} es el mes de salida más barato en "
                    f"{best_month['n']} de {best_month['total']} rutas internacionales desde {name}. "
                    f"Cada ruta tiene su propio historial de precios por mes."))
    for code in POPULAR:
        r = best.get(code)
        if r and len([q for q in faq if q[0].startswith("¿Cuánto cuesta")]) < 3:
            faq.append((f"¿Cuánto cuesta un vuelo de {name} a {r['dest_name']}?",
                        f"El precio típico de un vuelo ida y vuelta de {r['origin_name']} a {r['dest_name']} "
                        f"es de unos {_money(r['typical'])} USD; el más barato que vimos fue de "
                        f"{_money(r['low'])} USD."
                        + (f" El mes más barato es {r['cheapest_month'][0]}." if r.get("cheapest_month") else "")))
    if len(cities) > 1:
        faq.append((f"¿Desde qué aeropuertos de {name} hay vuelos baratos?",
                    "Revisamos las salidas desde " + _join([f"{o['name']} ({o['code']})" for o in cities])
                    + ". Cada ciudad tiene su propia página con sus destinos más baratos."))
    faq.append((f"¿Cómo encuentro {term} baratos desde {name}?",
                f"Revisamos cada hora miles de tarifas desde {name} y comparamos cada precio con su historial. "
                f"Cuando una ruta está muy por debajo de lo normal, verificamos el precio en vivo en Google "
                f"Flights antes de publicarla. También puedes crear una alerta gratis para tu ruta."))

    deals = c.get("deals") or []
    if deals:
        lead = f"{len(deals)} oferta{'s' if len(deals) != 1 else ''} verificada{'s' if len(deals) != 1 else ''} ahora desde {name}"
        sample = ", ".join(f"{d['dest_name']} {_money(d['price'])}" for d in deals[:3])
    else:
        lead = f"Vuelos y {term} baratos desde {name}"
        sample = ", ".join(f"{r['dest_name']} desde {_money(r['low'])}" for r in top[:3])
    desc = f"{lead}" + (f": {sample}" if sample else "") + \
        ". Precios revisados cada hora, historial por ruta y alertas gratis."

    c.update(term=term, top_dests=top, best_month=best_month, n_routes=len(routes),
             n_dests=len(best), faq=faq, seo_desc=desc[:300])
    return c


def home_faq(countries: list[dict], deals: list[dict]) -> list[tuple[str, str]]:
    """Preguntas frecuentes de la portada (generales + la oferta más barata del momento)."""
    out = []
    if deals:
        d = min(deals, key=lambda x: x["price"])
        out.append(("¿Cuál es el vuelo más barato que hay ahora?",
                    f"En este momento, la oferta verificada más barata es {d['origin_name']} – {d['dest_name']} "
                    f"por ${d['price']:.0f} USD ida y vuelta. Las ofertas cambian varias veces al día."))
    out += [
        ("¿Las ofertas son reales?",
         "Sí. Cada oferta se confirma en vivo en Google Flights antes de publicarse, y mostramos el precio "
         "verificado. Los precios de los vuelos cambian rápido, así que puede subir después de publicada."),
        ("¿Ustedes venden los boletos?",
         "No. Te llevamos a la agencia o aerolínea donde se compra el vuelo, al mismo precio. Si compras, "
         "podemos recibir una pequeña comisión que no te cuesta nada extra."),
        ("¿Desde qué países buscan vuelos baratos?",
         "Buscamos vuelos internacionales que salen de " + _join([c["name"] for c in countries]) + "."),
        ("¿Cómo recibo las ofertas desde mi ciudad?",
         "Síguenos en Telegram o WhatsApp, o crea una alerta gratis para tu ruta y te avisamos cuando el "
         "precio baje."),
    ]
    return out
