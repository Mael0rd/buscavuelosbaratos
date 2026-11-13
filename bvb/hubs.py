"""Páginas permanentes por ciudad de origen (/desde/<ciudad>) y por destino
(/destino/<ciudad>), pensadas para búsquedas como "vuelos baratos desde
San José" o "vuelos baratos a Madrid".

Se arman con la tabla `routes` (lo visto en las búsquedas recientes) y las
ofertas verificadas vigentes. Los precios de `routes` son de referencia (de
caché de Aviasales, sin verificar) y la página lo dice así; solo las ofertas
destacadas llevan precio verificado.
"""
from collections import Counter
from datetime import date, timedelta

from .routes import SCHEMA, slugify

RECENT_DAYS = 7          # rutas vistas en la última semana
MAX_DESTS = 40           # destinos listados por ciudad de origen
MIN_ORIGINS_DEST = 3     # un destino sin ofertas ni historial necesita ≥3 ciudades para tener página

# Destinos que alguna vez tuvieron página: no se borran nunca (una URL que desaparece da 404
# y le resta confianza al sitio ante Google). Sin datos recientes, la página queda con el
# último precio conocido y la invitación a crear una alerta.
DEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS dest_pages (
    destination TEXT PRIMARY KEY, dest_name TEXT, dest_country TEXT, slug TEXT,
    low REAL, first_seen TEXT, last_seen TEXT
);
"""


def origin_slug(name: str, code: str) -> str:
    return f"{slugify(name)}-{code.lower()}"


def _recent_routes(conn) -> list[dict]:
    conn.executescript(SCHEMA)
    since = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM routes WHERE updated_at >= ? AND last_price > 0 ORDER BY last_price", (since,))]


def build(conn, cfg: dict, deals: list[dict], route_pages: list[dict], dest_slug) -> tuple[list, list]:
    """Devuelve (ciudades de origen, destinos) con todo lo que necesitan las plantillas."""
    names = cfg.get("origin_names", {})
    country_of = {code: (cid, c) for cid, c in cfg["countries"].items() for code in c["origins"]}
    page_of = {(r["origin"], r["destination"]): r["slug"] for r in route_pages}
    rows = [r for r in _recent_routes(conn) if r["origin"] in country_of]

    # ---- ciudades de origen (todas, aunque aún no haya datos: son páginas fijas) ----
    origins = []
    for code, (cid, c) in country_of.items():
        name = names.get(code, code)
        mine = [r for r in rows if r["origin"] == code]
        for r in mine:
            r["route_slug"] = page_of.get((code, r["destination"]))
            r["dest_slug"] = dest_slug(r["dest_name"], r["destination"])
        months = Counter(r["cheapest_month"][0] for r in route_pages
                         if r["origin"] == code and r.get("cheapest_month"))
        best_month = None
        if months:
            label, n = months.most_common(1)[0]
            best_month = {"label": label, "n": n, "total": sum(months.values())}
        o = {"code": code, "name": name, "slug": origin_slug(name, code),
             "country": cid, "country_name": c["name"], "cc": c["cc"],
             "term": c.get("term") or "boletos de avión", "best_month": best_month,
             "deals": [d for d in deals if d["origin"] == code],
             "dests": mine[:MAX_DESTS], "n_dests": len(mine),
             "direct": [r["dest_name"] for r in mine if r["direct_seen"]][:12],
             "cheapest": mine[0] if mine else None}
        o["faq"] = origin_faq(o)
        origins.append(o)
    origin_by_code = {o["code"]: o for o in origins}

    # ---- destinos ----
    by_dest: dict = {}
    for r in rows:
        by_dest.setdefault(r["destination"], []).append(r)
    deals_by_dest: dict = {}
    for d in deals:
        deals_by_dest.setdefault(d["destination"], []).append(d)
    with_history = {r["destination"] for r in route_pages}

    dests = []
    for code in set(by_dest) | set(deals_by_dest):
        rs = sorted(by_dest.get(code, []), key=lambda r: r["last_price"])
        ds = deals_by_dest.get(code, [])
        if not ds and code not in with_history and len(rs) < MIN_ORIGINS_DEST:
            continue  # página demasiado pobre: mejor no publicarla
        ref = ds[0] if ds else rs[0]
        name = ref["dest_name"]
        origins_list = []
        for r in rs[:40]:
            o = origin_by_code.get(r["origin"])
            origins_list.append({**r, "route_slug": page_of.get((r["origin"], code)),
                                 "cc": o["cc"] if o else "", "country_name": o["country_name"] if o else "",
                                 "origin_slug": o["slug"] if o else ""})
        prices = [d["price"] for d in ds] + [r["last_price"] for r in rs]
        dd = {"destination": code, "dest_name": name, "dest_country": ref.get("dest_country", ""),
              "dest_slug": dest_slug(name, code), "deals": ds, "origins": origins_list,
              "low": min(prices), "cheapest": origins_list[0] if origins_list else None,
              "direct_from": [r["origin_name"] for r in rs if r["direct_seen"]][:12],
              "tone": sum(map(ord, code)) % 6}
        dd["faq"] = dest_faq(dd)
        dests.append(dd)
    dests += _keep_known(conn, dests, by_dest, origin_by_code, page_of)
    dests.sort(key=lambda x: (x.get("stale", False), -len(x["deals"]), -len(x["origins"])))
    return origins, dests


def _keep_known(conn, dests: list[dict], by_dest: dict, origin_by_code: dict, page_of: dict) -> list[dict]:
    """Registra los destinos con página y devuelve los que ya no cumplen el mínimo, para no borrarlos."""
    conn.executescript(DEST_SCHEMA)
    today = date.today().isoformat()
    known = {r["destination"]: dict(r) for r in conn.execute("SELECT * FROM dest_pages")}
    for d in dests:
        k = known.get(d["destination"])
        if k and k["slug"]:
            d["dest_slug"] = k["slug"]  # la URL no cambia aunque cambie el nombre
        conn.execute(
            "INSERT INTO dest_pages VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(destination) DO UPDATE SET "
            "dest_name = excluded.dest_name, dest_country = excluded.dest_country, low = excluded.low, "
            "last_seen = excluded.last_seen",
            (d["destination"], d["dest_name"], d["dest_country"], d["dest_slug"], d["low"], today, today))
    conn.commit()
    current = {d["destination"] for d in dests}
    kept = []
    for code, k in known.items():
        if code in current:
            continue
        rs = sorted(by_dest.get(code, []), key=lambda r: r["last_price"])
        origins_list = []
        for r in rs:
            o = origin_by_code.get(r["origin"])
            origins_list.append({**r, "route_slug": page_of.get((r["origin"], code)),
                                 "cc": o["cc"] if o else "", "country_name": o["country_name"] if o else "",
                                 "origin_slug": o["slug"] if o else ""})
        dd = {"destination": code, "dest_name": k["dest_name"], "dest_country": k["dest_country"] or "",
              "dest_slug": k["slug"], "deals": [], "origins": origins_list,
              "low": rs[0]["last_price"] if rs else k["low"], "cheapest": origins_list[0] if origins_list else None,
              "direct_from": [r["origin_name"] for r in rs if r["direct_seen"]][:12],
              "tone": sum(map(ord, code)) % 6, "stale": not rs, "last_seen": k["last_seen"]}
        dd["faq"] = dest_faq(dd)
        kept.append(dd)
    return kept


def origin_faq(o: dict) -> list[tuple[str, str]]:
    n, out = o["name"], []
    if o["cheapest"]:
        c = o["cheapest"]
        out.append((f"¿Cuál es el destino internacional más barato desde {n}?",
                    f"En nuestras búsquedas de los últimos días, el vuelo ida y vuelta más barato desde {n} "
                    f"fue a {c['dest_name']}{', ' + c['dest_country'] if c.get('dest_country') else ''}, "
                    f"desde unos ${c['last_price']:.0f} USD. Los precios cambian a diario."))
    if o["n_dests"]:
        out.append((f"¿A cuántos destinos internacionales se puede volar desde {n}?",
                    f"Esta semana encontramos tarifas desde {n} a {o['n_dests']} destinos internacionales "
                    f"con vuelo directo o una escala."))
    if o.get("best_month"):
        m = o["best_month"]
        out.append((f"¿Cuál es el mes más barato para volar desde {n}?",
                    f"En nuestras búsquedas recientes, {m['label']} es el mes de salida más barato en {m['n']} de "
                    f"las {m['total']} rutas internacionales que seguimos desde {n}."))
    if o["direct"]:
        out.append((f"¿A qué ciudades hay vuelos directos desde {n}?",
                    "Entre las tarifas baratas que vimos hay vuelos directos a: " + ", ".join(o["direct"]) + "."))
    out.append((f"¿Cómo encuentro {o.get('term', 'boletos de avión')} baratos desde {n}?",
                f"Revisamos cada hora miles de tarifas desde {n} y comparamos cada precio con su historial. "
                f"Cuando una ruta está muy por debajo de lo normal, la verificamos en Google Flights y la "
                f"publicamos aquí y en Telegram. También puedes crear una alerta gratis para tu ruta."))
    return out


def dest_faq(d: dict) -> list[tuple[str, str]]:
    n, out = d["dest_name"], []
    if d["cheapest"]:
        c = d["cheapest"]
        out.append((f"¿Desde dónde es más barato volar a {n}?",
                    f"En nuestras búsquedas recientes, la ciudad latinoamericana con el vuelo ida y vuelta más "
                    f"barato a {n} fue {c['origin_name']}, desde unos ${c['last_price']:.0f} USD."))
    if d["direct_from"]:
        out.append((f"¿Desde qué ciudades hay vuelos directos a {n}?",
                    "Vimos vuelos directos a " + n + " desde: " + ", ".join(d["direct_from"]) + "."))
    out.append((f"¿Cuándo hay ofertas de vuelos a {n}?",
                f"Las ofertas aparecen y desaparecen en horas. Revisamos los precios cada hora y publicamos solo "
                f"los que verificamos en Google Flights. Crea una alerta gratis y te avisamos cuando baje."))
    return out


def json_ld_faq(faq: list) -> list[dict]:
    return [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]
