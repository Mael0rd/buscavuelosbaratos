"""Páginas permanentes por ruta (SEO): /vuelos/<origen>-a-<destino>-<cod>-<cod>.html

A diferencia de las ofertas (que caducan), cada ruta tiene una página estable
que acumula historial: precio típico, el más bajo visto, precio por mes de
salida, aerolíneas, si hay vuelos directos, la oferta verificada vigente (si
hay) y preguntas frecuentes con datos estructurados.
"""
import json
import re
import statistics
import unicodedata
from datetime import date, timedelta

from .deals import haversine_km

SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    origin TEXT, destination TEXT,
    origin_name TEXT, dest_name TEXT, dest_country TEXT, km REAL,
    month_prices TEXT,      -- JSON {"2027-01": 345, ...} de la última corrida
    airlines TEXT,          -- JSON [nombres] vistos (máx. 6)
    direct_seen INTEGER DEFAULT 0,
    last_price REAL, last_link TEXT, last_dep TEXT, last_ret TEXT,
    updated_at TEXT,
    PRIMARY KEY (origin, destination)
);
"""
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def route_slug(r: dict) -> str:
    return (f"{slugify(r['origin_name'])}-a-{slugify(r['dest_name'])}-"
            f"{r['origin'].lower()}-{r['destination'].lower()}")


def month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


# ---------- actualización en cada corrida ----------
def update(conn, best: dict, ref, today: str) -> int:
    """Guarda/actualiza los datos de cada ruta vista en esta corrida."""
    conn.executescript(SCHEMA)
    for (o, d), t in best.items():
        months = {}
        for tk_month, price in _month_prices(t):
            months[tk_month] = price
        prev = conn.execute("SELECT airlines, direct_seen FROM routes WHERE origin=? AND destination=?",
                            (o, d)).fetchone()
        airlines = json.loads(prev[0]) if prev and prev[0] else []
        name = ref.airline_name(t.get("airline", ""))
        if name and name not in airlines:
            airlines = (airlines + [name])[-6:]
        a, b = ref.coords(o), ref.coords(d)
        conn.execute(
            """INSERT INTO routes (origin, destination, origin_name, dest_name, dest_country, km,
                   month_prices, airlines, direct_seen, last_price, last_link, last_dep, last_ret, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(origin, destination) DO UPDATE SET
                   origin_name=excluded.origin_name, dest_name=excluded.dest_name,
                   dest_country=excluded.dest_country, km=excluded.km,
                   month_prices=excluded.month_prices, airlines=excluded.airlines,
                   direct_seen=MAX(routes.direct_seen, excluded.direct_seen),
                   last_price=excluded.last_price, last_link=excluded.last_link,
                   last_dep=excluded.last_dep, last_ret=excluded.last_ret, updated_at=excluded.updated_at""",
            (o, d, ref.city_name(o), ref.city_name(d), ref.country_name(ref.country_code(d)),
             haversine_km(a, b) if a and b else None, json.dumps(months), json.dumps(airlines, ensure_ascii=False),
             1 if (t.get("transfers", 1) == 0 or (prev and prev[1])) else 0,
             t["price"], t.get("link", ""), t.get("departure_at", ""), t.get("return_at", ""), today))
    conn.commit()
    return len(best)


def _month_prices(t: dict):
    """(mes, precio mínimo) por mes de salida, a partir de lo que trae route_best."""
    by_month = t.get("month_min") or {}
    if by_month:
        return sorted(by_month.items())
    m = (t.get("departure_at") or "")[:7]
    return [(m, t["price"])] if m else []


# ---------- páginas ----------
def build_pages(conn, cfg: dict, active: list[dict], ended: list[dict], min_days: int,
                index_min_days: int = 14, index_min_months: int = 2) -> list[dict]:
    """Rutas con suficientes datos para tener página propia, con sus estadísticas."""
    conn.executescript(SCHEMA)
    country_of = {code: cid for cid, c in cfg["countries"].items() for code in c["origins"]}
    since = (date.today() - timedelta(days=cfg["deals"]["history_days"])).isoformat()
    hist: dict = {}
    for o, d, day, p in conn.execute(
            "SELECT origin, destination, day, min_price FROM prices_daily WHERE day >= ? ORDER BY day", (since,)):
        hist.setdefault((o, d), []).append((day, p))

    deal_by_route = {}
    for x in active:
        deal_by_route.setdefault((x["origin"], x["destination"]), x)

    pages = []
    for r in conn.execute("SELECT * FROM routes").fetchall():
        r = dict(r)
        key = (r["origin"], r["destination"])
        points = hist.get(key, [])
        if len(points) < min_days or r["origin"] not in country_of:
            continue
        prices = [p for _, p in points]
        low_day, low = min(points, key=lambda x: x[1])
        months = sorted(json.loads(r["month_prices"] or "{}").items())
        cheapest = min(months, key=lambda x: x[1]) if months else None
        r.update(
            slug=route_slug(r), country=country_of[r["origin"]],
            typical=statistics.median(prices), low=low, low_day=low_day, days=len(points),
            points=points, months=[(month_label(m), p) for m, p in months],
            cheapest_month=(month_label(cheapest[0]), cheapest[1]) if cheapest else None,
            airlines=json.loads(r["airlines"] or "[]"), deal=deal_by_route.get(key),
            chart=sparkline(points),
            # Google solo indexa la página cuando ya tiene datos propios suficientes
            # (evita cientos de páginas casi iguales = "contenido a escala" de poco valor).
            indexable=len(points) >= index_min_days and len(months) >= index_min_months,
            lastmod=points[-1][0],
        )
        pages.append(r)

    # Rutas relacionadas: mismo origen y mismo destino (enlaces internos)
    by_origin, by_dest = {}, {}
    for p in pages:
        by_origin.setdefault(p["origin"], []).append(p)
        by_dest.setdefault(p["destination"], []).append(p)
    for p in pages:
        p["related_origin"] = sorted([x for x in by_origin[p["origin"]] if x is not p],
                                     key=lambda x: x["typical"])[:6]
        p["related_dest"] = sorted([x for x in by_dest[p["destination"]] if x is not p],
                                   key=lambda x: x["typical"])[:6]
    return sorted(pages, key=lambda x: (x["country"], x["typical"]))


def sparkline(points: list, w: int = 640, h: int = 160, pad: int = 24) -> dict | None:
    """Coordenadas para un gráfico SVG simple del precio mínimo diario."""
    if len(points) < 2:
        return None
    prices = [p for _, p in points]
    lo, hi = min(prices), max(prices)
    span = (hi - lo) or 1
    n = len(points) - 1
    coords = [(pad + i * (w - 2 * pad) / n, h - pad - (p - lo) * (h - 2 * pad) / span)
              for i, (_, p) in enumerate(points)]
    return {"w": w, "h": h, "path": " ".join(f"{x:.1f},{y:.1f}" for x, y in coords),
            "lo": lo, "hi": hi, "first": points[0][0], "last": points[-1][0]}


def faq(r: dict) -> list[tuple[str, str]]:
    o, d = r["origin_name"], r["dest_name"]
    out = [(f"¿Cuánto cuesta un vuelo de {o} a {d}?",
            f"En los últimos {r['days']} días, el precio típico de un vuelo ida y vuelta de {o} a {d} "
            f"fue de unos ${r['typical']:.0f} USD. El más barato que encontramos fue de ${r['low']:.0f} USD.")]
    if r["cheapest_month"]:
        out.append((f"¿Cuál es el mes más barato para volar de {o} a {d}?",
                    f"Según nuestras búsquedas más recientes, el mes de salida más barato es "
                    f"{r['cheapest_month'][0]}, desde ${r['cheapest_month'][1]:.0f} USD ida y vuelta."))
    out.append((f"¿Hay vuelos directos de {o} a {d}?",
                "Sí, hemos encontrado vuelos directos en esta ruta." if r["direct_seen"]
                else "En nuestras búsquedas recientes los vuelos más baratos tienen al menos una escala."))
    if r["airlines"]:
        out.append((f"¿Qué aerolíneas vuelan de {o} a {d}?",
                    "En las tarifas más baratas que hemos visto aparecen: " + ", ".join(r["airlines"]) + "."))
    return out
