"""Explorador por presupuesto: "¿A dónde puedo volar con $300?".

- /a-donde-volar: herramienta interactiva (ciudad de salida, presupuesto, mes,
  región, solo directos) que lee /data/explorar.json.
- /a-donde-volar/desde-<ciudad>: una página por ciudad de salida, con los destinos
  agrupados por presupuesto ya escritos en el HTML (para Google) y la herramienta
  preseleccionada.

Los precios son los más bajos vistos en las búsquedas recientes (referencia, sin
verificar); los que tienen oferta verificada vigente lo indican.
"""
import json
from collections import Counter
from datetime import date, timedelta

from . import geo
from .routes import MONTHS

RECENT_DAYS = 7
TIERS = [(300, "Menos de $300"), (500, "Entre $300 y $500"), (800, "Entre $500 y $800"), (None, "Más de $800")]
MIN_DESTS_INDEX = 6  # una ciudad con menos destinos no se indexa (página pobre)


def month_short(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1][:3]} {y[2:]}"


def month_long(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def items(conn, cfg: dict, origins: list[dict], route_pages: list[dict], deals: list[dict],
          dest_slug, photo_of, dest_pages: set | None = None) -> list[dict]:
    """Una fila por ruta vista en la última semana, lista para el JSON y las plantillas."""
    since = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    origin_by_code = {o["code"]: o for o in origins}
    page_of = {(r["origin"], r["destination"]): r["slug"] for r in route_pages}
    deal_of = {}
    for d in sorted(deals, key=lambda x: x["price"]):
        deal_of.setdefault((d["origin"], d["destination"]), d)
    out = []
    for r in conn.execute("SELECT * FROM routes WHERE updated_at >= ? AND last_price > 0", (since,)):
        r = dict(r)
        o = origin_by_code.get(r["origin"])
        if not o:
            continue
        months = {k: v for k, v in json.loads(r["month_prices"] or "{}").items() if v}
        price = min([r["last_price"], *months.values()])
        best = min(months.items(), key=lambda x: x[1]) if months else None
        cc, reg = geo.country(r["dest_country"] or "")
        deal = deal_of.get((r["origin"], r["destination"]))
        out.append({
            "o": r["origin"], "d": r["destination"], "n": r["dest_name"], "c": r["dest_country"] or "",
            "cc": cc, "r": reg, "p": round(price), "km": round(r["km"] or 0),
            "m": {k: round(v) for k, v in sorted(months.items())},
            "bm": best[0] if best else None, "dir": 1 if r["direct_seen"] else 0,
            "rs": page_of.get((r["origin"], r["destination"])),
            "ds": (lambda sl: sl if dest_pages is None or sl in dest_pages else None)(
                dest_slug(r["dest_name"], r["destination"])),
            "img": photo_of(r["destination"]),
            "deal": {"s": deal["slug"], "p": round(deal["price"])} if deal else None,
        })
    return sorted(out, key=lambda x: (x["o"], x["p"]))


def origin_pages(rows: list[dict], origins: list[dict]) -> list[dict]:
    """Datos de cada página /a-donde-volar/desde-<ciudad>."""
    by = {}
    for x in rows:
        by.setdefault(x["o"], []).append(x)
    pages = []
    for o in origins:
        mine = sorted(by.get(o["code"], []), key=lambda x: x["p"])
        tiers, lo = [], 0
        for cap, label in TIERS:
            sel = [x for x in mine if x["p"] >= lo and (cap is None or x["p"] < cap)]
            if sel:
                tiers.append({"label": label, "cap": cap, "items": sel})
            lo = cap or lo
        regions = Counter(x["r"] for x in mine)
        months = Counter(x["bm"] for x in mine if x["bm"])
        p = {**o, "items": mine, "tiers": tiers, "n": len(mine),
             "under300": sum(1 for x in mine if x["p"] < 300),
             "under500": sum(1 for x in mine if x["p"] < 500),
             "top_region": geo.REGIONS[regions.most_common(1)[0][0]] if regions else None,
             "best_month": month_long(months.most_common(1)[0][0]) if months else None,
             "cheapest": mine[0] if mine else None,
             "farthest_cheap": max((x for x in mine if x["p"] < 600), key=lambda x: x["km"], default=None),
             "indexable": len(mine) >= MIN_DESTS_INDEX}
        p["faq"] = faq(p)
        pages.append(p)
    return pages


def faq(p: dict) -> list[tuple[str, str]]:
    name = p["name"]
    if not p["cheapest"]:
        return []
    c = p["cheapest"]
    out = [(f"¿Cuál es el destino internacional más barato desde {name}?",
            f"En nuestras búsquedas de la última semana, {c['n']}{', ' + c['c'] if c['c'] else ''}, "
            f"desde unos ${c['p']} ida y vuelta.")]
    cheap = [x["n"] for x in p["items"] if x["p"] < 300][:6]
    n300 = p["under300"]
    out.append((f"¿A dónde puedo viajar con $300 desde {name}?",
                (f"A {n300} destino{'s' if n300 != 1 else ''} internacional{'es' if n300 != 1 else ''} "
                 f"con vuelo de ida y vuelta por menos de $300: {', '.join(cheap)}.") if n300 else
                f"Por menos de $300 no vimos destinos internacionales esta semana; con $500 llegas a "
                f"{p['under500']} destinos."))
    if p["best_month"]:
        out.append((f"¿Cuál es el mes más barato para viajar desde {name}?",
                    f"El mes en que más destinos tienen su precio más bajo es {p['best_month']}."))
    if p["farthest_cheap"]:
        f = p["farthest_cheap"]
        out.append((f"¿Qué destino lejano es barato desde {name}?",
                    f"{f['n']} está a unos {f['km']:,} km y lo vimos por ${f['p']} ida y vuelta.".replace(",", ".")))
    return out


def write_json(rows: list[dict], path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def month_options(rows: list[dict]) -> list[tuple[str, str]]:
    ms = sorted({m for x in rows for m in x["m"]})
    return [(m, month_long(m).capitalize()) for m in ms[:12]]
