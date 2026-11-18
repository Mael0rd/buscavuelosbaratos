"""¿Cuándo viajar a…? Mejor época por precio y clima.

- /cuando-viajar: portada con los 12 meses y todos los destinos.
- /cuando-viajar/<destino>: mes más barato (historial de precios de todas las
  ciudades de salida), clima de cada mes y precios por ciudad de salida.
- /cuando-viajar/en-<mes>: "¿A dónde viajar en enero?", destinos baratos y con
  buen clima ese mes.

Precio por mes: cada ruta se compara con su propio promedio (así una ruta cara no
pesa más que una barata) y se promedia por destino → "% sobre/bajo lo normal".
"""
from datetime import date
from statistics import median

from . import clima, geo
from .routes import MONTHS

MIN_MONTHS_INDEX = 3   # meses con precio para indexar la página del destino
MONTH_SLUGS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def _months_ahead(today: date) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(12):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _price_index(rows: list[dict]) -> dict:
    """{ "2027-01": (índice, precio mínimo, nº de rutas) } para un destino."""
    rel, low = {}, {}
    for x in rows:
        if len(x["m"]) < 2:
            continue
        med = median(x["m"].values())
        for ym, p in x["m"].items():
            rel.setdefault(ym, []).append(p / med)
            low[ym] = min(low.get(ym, p), p)
    return {ym: (sum(v) / len(v), low[ym], len(v)) for ym, v in rel.items()}


def _label(pct: int) -> str:
    if pct <= -8:
        return "barato"
    if pct >= 8:
        return "caro"
    return "normal"


def build(xp_rows: list[dict], climate: dict, origin_names: dict, today: date | None = None) -> list[dict]:
    today = today or date.today()
    ahead = _months_ahead(today)
    by = {}
    for x in xp_rows:
        if x["ds"]:  # solo destinos con página /destino/
            by.setdefault(x["d"], []).append(x)
    pages = []
    for code, rows in by.items():
        rows.sort(key=lambda x: x["p"])
        first = rows[0]
        idx = _price_index(rows)
        cl = climate.get(code)
        if not cl and len(idx) < MIN_MONTHS_INDEX:
            continue
        months = []
        for ym in ahead:
            mi = int(ym[5:]) - 1
            i = idx.get(ym)
            pct = round((i[0] - 1) * 100) if i else None
            rk = clima.rain_kind(cl["rain"][mi]) if cl else None
            months.append({
                "ym": ym, "mi": mi, "name": MONTHS[mi], "short": MONTHS[mi][:3], "year": ym[:4],
                "pct": pct, "low": round(i[1]) if i else None, "nr": i[2] if i else 0, "level": _label(pct) if pct is not None else None,
                "tmax": round(cl["tmax"][mi]) if cl else None, "tmin": round(cl["tmin"][mi]) if cl else None,
                "rain": cl["rain"][mi] if cl else None, "rk": rk[0] if rk else None, "rtxt": rk[1] if rk else None,
                "feel": clima.feel(cl["tmax"][mi]) if cl else None,
            })
        priced = [m for m in months if m["pct"] is not None]
        cheap = min(priced, key=lambda m: m["pct"]) if priced else None
        dear = max(priced, key=lambda m: m["pct"]) if priced else None
        # Mejor combinación: barato y sin mucha lluvia
        penalty = {"dry": 0, "some": 6, "wet": 18, None: 0}
        best = min(priced, key=lambda m: m["pct"] + penalty[m["rk"]]) if priced else None
        for m in months:
            m["is_cheap"] = m is cheap
            m["is_best"] = m is best
        wet = [m["name"] for m in sorted(months, key=lambda m: m["mi"]) if m["rk"] == "wet"]
        dry = [m["name"] for m in sorted(months, key=lambda m: m["mi"]) if m["rk"] == "dry"]
        warm = max(months, key=lambda m: m["tmax"] or -99) if cl else None
        cool = min(months, key=lambda m: m["tmax"] or 99) if cl else None
        cc, reg = first["cc"], first["r"]
        origins = []
        for x in rows:
            bm = min(x["m"].items(), key=lambda kv: kv[1]) if x["m"] else None
            origins.append({"o": x["o"], "name": origin_names.get(x["o"], x["o"]), "p": x["p"],
                            "bm": bm[0] if bm else None, "dir": x["dir"], "rs": x["rs"], "m": x["m"]})
        slug = first["ds"]
        page = {
            "code": code, "slug": slug, "name": first["n"], "country": first["c"], "cc": cc, "region": reg,
            "img": first["img"], "low": first["p"], "months": months, "cheap": cheap, "dear": dear,
            "best": best, "wet": wet, "dry": dry, "warm": warm, "cool": cool, "climate": bool(cl),
            "elev": (cl or {}).get("elev"), "origins": origins[:15], "n_origins": len(rows),
            "save": round((1 - (1 + cheap["pct"] / 100) / (1 + dear["pct"] / 100)) * 100)
            if cheap and dear and dear["pct"] > cheap["pct"] else 0,
            "indexable": bool(cl) and len(priced) >= MIN_MONTHS_INDEX,
            "url": f"/cuando-viajar/{slug}",
            "deal": next((x["deal"] for x in rows if x["deal"]), None),
        }
        page["faq"] = faq(page)
        page["summary"] = summary(page)
        pages.append(page)
    pages.sort(key=lambda p: (-p["n_origins"], p["name"]))
    return pages


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def _ranges(months: list[dict], key) -> str:
    """Meses seguidos que cumplen `key`, en orden de calendario: 'de junio a octubre'."""
    flags = [False] * 12
    for m in months:
        flags[m["mi"]] = bool(key(m))
    if all(flags):
        return "todo el año"
    if not any(flags):
        return ""
    start = flags.index(False)  # empezar en un mes que no cumple, para no partir un tramo
    runs, cur = [], []
    for k in range(1, 13):
        i = (start + k) % 12
        if flags[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    parts = [MONTHS[r[0]] if len(r) == 1 else f"de {MONTHS[r[0]]} a {MONTHS[r[-1]]}" for r in runs]
    return _list(parts)


def summary(p: dict) -> str:
    bits = []
    if p["cheap"]:
        c = p["cheap"]
        bits.append(f"El mes más barato para volar a {p['name']} en los próximos meses es {c['name']}"
                    + (f" ({-c['pct']}% bajo lo normal)" if c["pct"] < 0 else "") + ".")
    if p["climate"]:
        rainy = _ranges(p["months"], lambda m: m["rk"] == "wet")
        bits.append(f"Temporada de lluvias: {rainy}." if rainy and rainy != "todo el año"
                    else ("Llueve bastante todo el año." if rainy else "Es seco casi todo el año."))
    return " ".join(bits)


def faq(p: dict) -> list[tuple[str, str]]:
    n = p["name"]
    out = []
    if p["cheap"]:
        c, d = p["cheap"], p["dear"]
        a = (f"Según los precios que vimos desde {p['n_origins']} ciudad{'es' if p['n_origins'] > 1 else ''} de "
             f"Latinoamérica, el mes más barato de los próximos meses es {c['name']} de {c['year']}")
        a += f", con vuelos desde ${c['low']} ida y vuelta." if c["low"] else "."
        if d and d is not c and d["pct"] - c["pct"] >= 5:
            a += f" El más caro es {d['name']}: volar en {c['name']} sale alrededor de {p['save']}% más barato."
        out.append((f"¿Cuál es el mes más barato para volar a {n}?", a))
    if p["best"] and p["climate"]:
        b = p["best"]
        out.append((f"¿Cuál es la mejor época para viajar a {n}?",
                    f"Combinando precio y clima, {b['name']}: los vuelos están "
                    f"{'por debajo de lo normal' if b['pct'] < 0 else 'en su precio normal'} y el clima es "
                    f"{b['feel']} ({b['tmax']}° de máxima y {b['tmin']}° de mínima) y {b['rtxt']}."))
    if p["climate"]:
        rainy = _ranges(p["months"], lambda m: m["rk"] == "wet")
        if rainy == "todo el año":
            a = f"En {n} llueve bastante todo el año; lleva paraguas o impermeable."
        elif rainy:
            a = f"En {n} la temporada de lluvias va {rainy}" if rainy.startswith("de ") else \
                f"En {n} el mes más lluvioso es {rainy}"
            dry = _ranges(p["months"], lambda m: m["rk"] == "dry")
            a += f". Los meses más secos: {dry}." if dry else "."
        else:
            a = f"{n} es seco casi todo el año: pocas lluvias en cualquier mes."
        out.append((f"¿Cuándo llueve en {n}?", a))
        w, c = p["warm"], p["cool"]
        out.append((f"¿Qué temperatura hace en {n}?",
                    f"El mes más caluroso es {w['name']} (máximas de {w['tmax']}°) y el más fresco, "
                    f"{c['name']} (máximas de {c['tmax']}° y mínimas de {c['tmin']}°). Promedios de 2016 a 2025."))
    return out


def month_pages(pages: list[dict], today: date | None = None) -> list[dict]:
    """Una página por mes del año: destinos baratos y con buen clima ese mes."""
    today = today or date.today()
    out = []
    for mi, slug in enumerate(MONTH_SLUGS):
        items = []
        for p in pages:
            m = next(x for x in p["months"] if x["mi"] == mi)
            if not p["climate"] and m["pct"] is None:
                continue
            items.append({"p": p, "m": m, "price": m["low"] or p["low"]})
        groups = [
            ("beach", "🏖️ Sol y calor", [x for x in items if (x["m"]["tmax"] or 0) >= 27 and x["m"]["rk"] != "wet"]),
            ("mild", "🌤️ Clima agradable", [x for x in items if 18 <= (x["m"]["tmax"] or 0) < 27 and x["m"]["rk"] != "wet"]),
            ("cold", "🧥 Frío o invierno", [x for x in items if x["m"]["tmax"] is not None and x["m"]["tmax"] < 18]),
            ("wet", "🌧️ Temporada de lluvias", [x for x in items if x["m"]["rk"] == "wet" and (x["m"]["tmax"] or 0) >= 18]),
        ]
        for _, _, xs in groups:
            xs.sort(key=lambda x: ((x["m"]["pct"] if x["m"]["pct"] is not None else 0) + x["price"] / 100))
        cheap = sorted([x for x in items if x["m"]["pct"] is not None and x["m"]["pct"] <= -8 and x["m"]["nr"] >= 2],
                       key=lambda x: x["m"]["pct"])[:8]
        ym = next(m["ym"] for m in pages[0]["months"] if m["mi"] == mi) if pages else ""
        page = {"mi": mi, "name": MONTHS[mi], "slug": f"en-{slug}", "year": ym[:4],
                "groups": [g for g in groups if g[2]], "cheap": cheap, "n": len(items),
                "has_prices": any(x["m"]["pct"] is not None for x in items)}
        page["faq"] = month_faq(page, items)
        out.append(page)
    return out


def _names(xs: list[dict], k: int = 4) -> str:
    return _list([f"{x['p']['name']} (${x['price']})" for x in xs[:k]])


def month_faq(mp: dict, items: list[dict]) -> list[tuple[str, str]]:
    mn = mp["name"]
    out = []
    budget = sorted(items, key=lambda x: x["price"])
    if budget:
        out.append((f"¿A dónde viajar en {mn} con poco dinero?",
                    f"Los destinos con vuelos ida y vuelta más baratos que vimos para {mn} son {_names(budget)}. "
                    "El precio depende de tu ciudad de salida: en cada destino ves el de la tuya."))
    if mp["cheap"]:
        out.append((f"¿Qué destinos están más baratos de lo normal en {mn}?",
                    f"En {mn} bajan más que de costumbre los vuelos a "
                    + _list([f"{x['p']['name']} ({x['m']['pct']}%)" for x in mp["cheap"][:4]]) + "."))
    beach = next((xs for k, _, xs in mp["groups"] if k == "beach"), [])
    if beach:
        out.append((f"¿Dónde hace calor en {mn}?",
                    f"Con sol, calor y poca lluvia en {mn}: {_names(beach)}."))
    cold = next((xs for k, _, xs in mp["groups"] if k == "cold"), [])
    if cold:
        out.append((f"¿Dónde hace frío en {mn}?",
                    f"Si buscas frío o invierno en {mn}: {_names(cold)}."))
    return out


def regions(pages: list[dict]) -> list[tuple[str, list[dict]]]:
    by = {}
    for p in pages:
        by.setdefault(p["region"] or "otros", []).append(p)
    order = list(geo.REGIONS)
    return [(geo.REGIONS.get(k, "Otros destinos"), sorted(v, key=lambda p: p["name"]))
            for k, v in sorted(by.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)]


def chart(p: dict, w: int = 440, h: int = 240) -> dict | None:
    """Coordenadas del gráfico de clima (lluvia en barras, máxima y mínima en líneas), ene→dic."""
    if not p["climate"]:
        return None
    ms = sorted(p["months"], key=lambda m: m["mi"])
    left, right, top, bottom = 6, 6, 22, 24
    iw, ih = w - left - right, h - top - bottom
    step = iw / 12
    rmax = max(200, max(m["rain"] for m in ms))
    lo = min(m["tmin"] for m in ms) - 3
    hi = max(m["tmax"] for m in ms) + 3

    def ty(t):
        return round(top + ih * (1 - (t - lo) / (hi - lo)), 1)
    bars, hi_pts, lo_pts, labels = [], [], [], []
    for i, m in enumerate(ms):
        x = left + step * i
        bh = round(ih * m["rain"] / rmax, 1)
        bars.append({"x": round(x + step * .2, 1), "y": round(top + ih - bh, 1), "w": round(step * .6, 1), "h": bh,
                     "rk": m["rk"], "mm": m["rain"], "name": m["name"]})
        cx = round(x + step / 2, 1)
        hi_pts.append(f"{cx},{ty(m['tmax'])}")
        lo_pts.append(f"{cx},{ty(m['tmin'])}")
        labels.append({"x": cx, "t": m["short"], "tmax": m["tmax"], "tmin": m["tmin"],
                       "yh": ty(m["tmax"]), "yl": ty(m["tmin"])})
    return {"w": w, "h": h, "bars": bars, "hi": " ".join(hi_pts), "lo": " ".join(lo_pts),
            "labels": labels, "base": top + ih, "rmax": rmax}
