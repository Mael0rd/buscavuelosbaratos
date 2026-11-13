"""Feriados y puentes por país (/feriados y /feriados/<país>-<año>).

Los feriados oficiales salen de la librería `holidays` (mantenida por la comunidad,
basada en las leyes de cada país). Con ellos se calculan:
  - fines de semana largos (3+ días libres seguidos sin pedir vacaciones)
  - puentes: cuántos días de vacaciones hay que pedir para descansar más días
Para cada puente se sugieren destinos baratos desde las ciudades del país, con el
precio más bajo visto para salir ese mes y un enlace de búsqueda con las fechas exactas.
"""
import json
from datetime import date, timedelta

import holidays

from . import geo
from .config import env
from .fetch import affiliate_link, with_subid
from .routes import MONTHS

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DAYS_SHORT = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

# Puerto Rico solo viene en inglés
PR_ES = {
    "New Year's Day": "Año Nuevo", "Epiphany": "Día de Reyes", "Martin Luther King Jr. Day": "Día de Martin Luther King",
    "Emancipation Day": "Día de la Abolición de la Esclavitud", "Good Friday": "Viernes Santo",
    "Memorial Day": "Día de la Recordación", "Juneteenth National Independence Day": "Juneteenth",
    "Independence Day": "Día de la Independencia de EE. UU.", "Puerto Rico Constitution Day": "Día de la Constitución",
    "Labor Day": "Día del Trabajo", "Columbus Day": "Día de la Raza", "Veterans Day": "Día del Veterano",
    "Puerto Rican Identity Day": "Día de la Puertorriqueñidad", "Thanksgiving Day": "Día de Acción de Gracias",
    "Christmas Day": "Navidad",
}
# Categorías extra: Uruguay (Carnaval y Semana de Turismo, libres para casi todos) y
# Costa Rica (feriados "de pago no obligatorio", que muchos tienen libres).
EXTRA_CATEGORIES = {"UY": ("bank", ""), "CR": ("optional", " (no obligatorio)")}


def _name(cc: str, name: str) -> str:
    if cc == "PR":
        base, obs = name.replace(" (observed)", ""), "(observed)" in name
        if base.startswith("George Washington Day"):
            base = "Día de los Presidentes y Próceres de Puerto Rico"
        return PR_ES.get(base, base) + (" (trasladado)" if obs else "")
    return name.replace("(observado)", "(trasladado)")


def _country(cc: str, year: int, categories=("public",)):
    try:
        return holidays.country_holidays(cc, years=year, language="es", categories=categories)
    except (NotImplementedError, KeyError, ValueError):
        return holidays.country_holidays(cc, years=year, categories=categories)


def holidays_for(cc: str, year: int) -> dict:
    """{fecha: nombre} de los feriados oficiales del año."""
    out = {d: n for d, n in _country(cc, year).items() if d.year == year}
    extra = EXTRA_CATEGORIES.get(cc)
    if extra:
        for d, n in _country(cc, year, (extra[0],)).items():
            if d.year == year and d not in out:
                out[d] = n + extra[1]
    return {d: "; ".join(_name(cc, x) for x in out[d].split("; ")) for d in sorted(out)}


def fmt(d: date, short: bool = False) -> str:
    return f"{(DAYS_SHORT if short else DAYS)[d.weekday()]} {d.day} {MONTHS[d.month - 1][:3] if short else 'de ' + MONTHS[d.month - 1]}"


def fmt_range(a: date, b: date) -> str:
    if a.month == b.month:
        return f"{DAYS_SHORT[a.weekday()]} {a.day} – {DAYS_SHORT[b.weekday()]} {b.day} de {MONTHS[a.month - 1]}"
    return f"{DAYS_SHORT[a.weekday()]} {a.day} {MONTHS[a.month - 1][:3]} – {DAYS_SHORT[b.weekday()]} {b.day} {MONTHS[b.month - 1][:3]}"


def _window(h: date, off, k: int) -> dict | None:
    """Ventana de días seguidos más larga que contiene h con exactamente k días hábiles."""
    best = None
    for st in range(-9, 1):
        for en in range(0, 10):
            a, b = h + timedelta(days=st), h + timedelta(days=en)
            days = [a + timedelta(days=i) for i in range((b - a).days + 1)]
            work = [d for d in days if not off(d)]
            if len(work) == k and (best is None or len(days) > best["n"]):
                best = {"a": a, "b": b, "n": len(days), "k": k, "work": work}
    return best


def breaks(hol: dict, year: int, max_vacation: int = 2, min_ratio: float = 2.5) -> list[dict]:
    """Un descanso por feriado (o grupo de feriados seguidos) de lunes a viernes:
    los días libres sin pedir nada y, si conviene, el mejor puente: pedir 1 o 2 días
    de vacaciones para descansar al menos min_ratio días por cada día pedido."""
    off = lambda d: d.weekday() >= 5 or d in hol  # noqa: E731
    seen, out = set(), []
    for h in sorted(hol):
        if h.weekday() >= 5:
            continue
        base = _window(h, off, 0)
        key = (base["a"], base["b"])
        if key in seen:
            continue
        seen.add(key)
        tip = None
        for k in range(1, max_vacation + 1):
            w = _window(h, off, k)
            if w and w["n"] > base["n"] and w["n"] / k >= min_ratio and \
                    (tip is None or w["n"] / k > tip["n"] / tip["k"]):
                tip = w
        if base["n"] < 3 and not tip:
            continue  # feriado suelto entre semana, sin puente que valga la pena
        names = list(dict.fromkeys(hol[d] for d in sorted(hol)
                                   if (tip or base)["a"] <= d <= (tip or base)["b"]))
        if tip:
            tip.update(range=fmt_range(tip["a"], tip["b"]), ask=[fmt(d, short=True) for d in tip["work"]])
        span = tip or base
        out.append({"a": base["a"], "b": base["b"], "n": base["n"], "range": fmt_range(base["a"], base["b"]),
                    "long": base["n"] >= 3, "tip": tip, "names": names,
                    "trip_a": span["a"], "trip_b": span["b"], "trip_n": span["n"],
                    "month": span["a"].strftime("%Y-%m"),
                    "month_name": MONTHS[(h if h.year == year else span["a"]).month - 1]})
    out = [x for x in out if x["trip_b"].year == year]
    # Un descanso que ya queda dentro del puente de otro (p. ej. Semana Santa dentro de
    # San José + Semana Santa en Colombia) no se repite.
    covered = lambda x, y: y is not x and y["tip"] and y["tip"]["a"] <= x["a"] and x["b"] <= y["tip"]["b"] \
        and y["tip"]["n"] > x["trip_n"]  # noqa: E731
    return [x for x in out if not any(covered(x, y) for y in out)]


def _ideas(brk: dict, rows_by_origin: dict, origins: list[dict], marker: str, sub: str, photo_of) -> dict:
    """Destinos sugeridos por ciudad: los más baratos para salir ese mes (corto si el
    descanso es corto) y la búsqueda con las fechas exactas del puente."""
    short = brk["trip_n"] <= 4
    dep, ret = brk["trip_a"], brk["trip_b"]
    out = {}
    for o in origins:
        cands = []
        for r in rows_by_origin.get(o["code"], []):
            p = r["m"].get(brk["month"])
            if not p or (short and r["km"] > 3000):
                continue
            path = f"/search/{o['code']}{dep:%d%m}{r['d']}{ret:%d%m}1"
            cands.append({**r, "pm": p, "url": with_subid(affiliate_link(path, marker), sub)})
        cands.sort(key=lambda x: x["pm"])
        if cands:
            out[o["code"]] = cands[:4]
    return out


def build(cfg: dict, xp_rows: list[dict], origins: list[dict], year: int, today: date, photo_of=None) -> list[dict]:
    """Datos de cada página de país."""
    rows_by_origin = {}
    for r in xp_rows:
        rows_by_origin.setdefault(r["o"], []).append(r)
    marker = env("TRAVELPAYOUTS_MARKER") or ""
    pages = []
    for cid, c in cfg["countries"].items():
        cc = c["cc"].upper()
        try:
            hol = holidays_for(cc, year)
        except Exception as e:  # noqa: BLE001 — un país sin datos no tumba la web
            print(f"[feriados] {cc}: {e}")
            continue
        if not hol:
            continue
        upcoming = {}
        for y in (today.year, year):
            if y != year:
                upcoming.update({d: n for d, n in holidays_for(cc, y).items() if d >= today})
        upcoming.update({d: n for d, n in hol.items() if d >= today})
        mine = [o for o in origins if o["country"] == cid]
        brks = breaks(hol, year)
        for b in brks:
            b["ideas"] = _ideas(b, rows_by_origin, mine, marker, f"feriados_{cid}", photo_of)
        long_free = [b for b in brks if b["long"]]
        tips = [b for b in brks if b["tip"]]
        best = max(tips, key=lambda b: (b["tip"]["n"], b["tip"]["n"] / b["tip"]["k"]), default=None)
        total_vac = sum(b["tip"]["k"] for b in tips)
        total_rest = sum(b["trip_n"] for b in brks)
        cal = calendar(hol, brks, year)
        p = {"id": cid, "name": c["name"], "cc": c["cc"], "flag": c["flag"], "year": year,
             "slug": f"{cid}-{year}", "holidays": [{"d": d, "name": n, "txt": fmt(d), "weekend": d.weekday() >= 5}
                                                   for d, n in sorted(hol.items())],
             "breaks": brks, "long_free": long_free, "best": best, "origins": mine, "calendar": cal,
             "next": [{"iso": d.isoformat(), "name": n} for d, n in sorted(upcoming.items())][:12],
             "n_weekday": sum(1 for d in hol if d.weekday() < 5), "total_vac": total_vac, "total_rest": total_rest,
             "semana_santa": next(((d, n) for d, n in sorted(hol.items()) if "Santo" in n or "Turismo" in n), None)}
        p["faq"] = faq(p)
        pages.append(p)
    return pages


def calendar(hol: dict, brks: list[dict], year: int) -> list[dict]:
    """12 meses para el calendario visual: cada día con su tipo (feriado, puente, finde)."""
    bridge = {d for b in brks if b["tip"] for d in b["tip"]["work"]}
    longw = {b["a"] + timedelta(days=i) for b in brks if b["long"] for i in range(b["n"])}
    months = []
    for m in range(1, 13):
        first = date(year, m, 1)
        nxt = date(year + (m == 12), m % 12 + 1, 1)
        cells = [None] * first.weekday()
        d = first
        while d < nxt:
            kind = ("hol" if d in hol else "bridge" if d in bridge else "long" if d in longw
                    else "we" if d.weekday() >= 5 else "")
            cells.append({"n": d.day, "k": kind, "t": hol.get(d, "Día para pedir de vacaciones" if d in bridge else "")})
            d += timedelta(days=1)
        months.append({"name": MONTHS[m - 1].capitalize(), "cells": cells,
                       "n_hol": sum(1 for x in hol if x.month == m)})
    return months


def faq(p: dict) -> list[tuple[str, str]]:
    n, y = p["name"], p["year"]
    out = [(f"¿Cuántos feriados hay en {n} en {y}?",
            f"{len(p['holidays'])} feriados oficiales, de los cuales {p['n_weekday']} caen entre lunes y viernes.")]
    if p["long_free"]:
        lst = "; ".join(f"{b['range']} ({b['n']} días)" for b in p["long_free"][:6])
        out.append((f"¿Cuáles son los fines de semana largos de {y} en {n}?", f"Sin pedir vacaciones: {lst}."))
    if p["best"]:
        t = p["best"]["tip"]
        out.append((f"¿Cuál es el mejor puente de {y} en {n}?",
                    f"{t['range']}: pidiendo {t['k']} día{'s' if t['k'] > 1 else ''} de vacaciones "
                    f"({', '.join(t['ask'])}) descansas {t['n']} días seguidos."))
    if p["semana_santa"]:
        d, name = p["semana_santa"]
        out.append((f"¿Cuándo es Semana Santa {y} en {n}?", f"El {name.lower()} cae el {fmt(d)} de {y}."))
    return out
