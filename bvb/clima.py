"""Clima promedio por mes de cada destino (para "¿Cuándo viajar a…?").

Fuente: NASA POWER (power.larc.nasa.gov), promedios climatológicos mensuales de
temperatura máxima, mínima y lluvia. Datos públicos de la NASA, de uso libre
(se pide citar la fuente). La rejilla es de ~50 km, así que en ciudades de
montaña la temperatura se corrige por altura (−6,5 °C por cada 1.000 m) con la
elevación del aeropuerto (OurAirports, dominio público).

Se guarda en la tabla `climate` del historial: el clima no cambia, así que cada
destino se descarga una sola vez (unos cuantos por corrida).
"""
import csv
import io
import json
import time

import requests

from .config import REF_DIR, env

# Datos diarios de 10 años: la "climatología" de POWER da extremos del mes, no el promedio.
POWER = ("https://power.larc.nasa.gov/api/temporal/daily/point"
         "?parameters=T2M_MAX,T2M_MIN,PRECTOTCORR&community=RE&longitude={lon:.4f}&latitude={lat:.4f}"
         "&start=20160101&end=20251231&format=JSON")
AIRPORTS_CSV = "https://davidmegginson.github.io/ourairports-data/airports.csv"
AIRPORTS_TP = "https://api.travelpayouts.com/data/en/airports.json"
DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
LAPSE = 6.5 / 1000  # °C por metro
PER_RUN = 45
SCHEMA = """CREATE TABLE IF NOT EXISTS climate (
    code TEXT PRIMARY KEY, data TEXT, fetched_at TEXT)"""


def _cached(name: str, url: str, max_age: int = 30 * 86400) -> bytes | None:
    path = REF_DIR / name
    if path.exists() and time.time() - path.stat().st_mtime < max_age:
        return path.read_bytes()
    try:
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        REF_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return r.content
    except Exception as e:  # noqa: BLE001
        print(f"[aviso] clima: no se pudo bajar {name}: {e}")
        return path.read_bytes() if path.exists() else None


def elevations() -> dict:
    """Código de ciudad o aeropuerto (IATA) → elevación en metros."""
    raw = _cached("ourairports.csv", AIRPORTS_CSV)
    if not raw:
        return {}
    by_airport = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))):
        code, ft = row.get("iata_code"), row.get("elevation_ft")
        if code and ft and row.get("type") in ("large_airport", "medium_airport", "small_airport"):
            try:
                by_airport[code] = float(ft) * 0.3048
            except ValueError:
                pass
    out = dict(by_airport)
    tp = _cached("airports_tp.json", AIRPORTS_TP)
    if tp:  # códigos de ciudad con varios aeropuertos (NYC, SAO, BUE…): el primero con dato
        for a in json.loads(tp):
            city, code = a.get("city_code"), a.get("code")
            if city and city not in out and code in by_airport and a.get("flightable", True):
                out[city] = by_airport[code]
    return out


def parse(payload: dict, elev: float | None) -> dict | None:
    """Respuesta de NASA POWER → {"tmax": [12], "tmin": [12], "rain": [12 mm/mes]}."""
    p = (payload.get("properties") or {}).get("parameter") or {}
    acc = [[0.0, 0.0, 0.0, 0] for _ in range(12)]
    try:
        for day, hi in (p.get("T2M_MAX") or {}).items():
            lo, mm = p["T2M_MIN"][day], p["PRECTOTCORR"][day]
            if min(hi, lo, mm) < -900:  # valor de relleno (-999): sin dato
                continue
            a = acc[int(day[4:6]) - 1]
            a[0] += hi; a[1] += lo; a[2] += mm; a[3] += 1
    except (KeyError, TypeError, ValueError):
        return None
    if min(a[3] for a in acc) < 100:  # menos de ~4 años de datos en algún mes
        return None
    tmax = [a[0] / a[3] for a in acc]
    tmin = [a[1] / a[3] for a in acc]
    rain = [a[2] / a[3] * d for a, d in zip(acc, DAYS)]
    coords = (payload.get("geometry") or {}).get("coordinates") or []
    grid = float(coords[2]) if len(coords) > 2 and coords[2] is not None else None
    shift = 0.0
    # Solo se enfría la ciudad que está más alta que su rejilla (Bogotá, Quito…); no se calienta
    # la que está más baja, porque suele ser costera junto a montañas (Lima) y erraría.
    if elev is not None and grid is not None and elev - grid > 300:
        shift = (grid - elev) * LAPSE
    return {"tmax": [round(t + shift, 1) for t in tmax], "tmin": [round(t + shift, 1) for t in tmin],
            "rain": [round(r) for r in rain], "elev": round(elev) if elev is not None else None,
            "grid": round(grid) if grid is not None else None}


def ensure(conn, ref, codes: list[str], limit: int = PER_RUN) -> None:
    """Descarga el clima de los destinos que aún no lo tienen (máx. `limit` por corrida)."""
    conn.execute(SCHEMA)
    if env("BVB_MOCK") == "1" or ref is None:
        return
    have = {r[0] for r in conn.execute("SELECT code FROM climate")}
    todo = [c for c in dict.fromkeys(codes) if c not in have and ref.coords(c)][:limit]
    if not todo:
        return
    elev = elevations()
    ok = fails = 0
    for code in todo:
        lat, lon = ref.coords(code)
        try:
            r = requests.get(POWER.format(lat=lat, lon=lon), timeout=40)
            r.raise_for_status()
            data = parse(r.json(), elev.get(code))
        except Exception as e:  # noqa: BLE001
            print(f"[aviso] clima {code}: {e}")
            fails += 1
            if fails >= 3 and not ok:
                break
            continue
        if data:
            conn.execute("INSERT OR REPLACE INTO climate VALUES (?, ?, datetime('now'))",
                         (code, json.dumps(data)))
            ok += 1
    conn.commit()
    print(f"[clima] {ok} destinos nuevos ({len(have) + ok} en total)")


def load(conn) -> dict:
    conn.execute(SCHEMA)
    return {r[0]: json.loads(r[1]) for r in conn.execute("SELECT code, data FROM climate")}


def rain_kind(mm: float) -> tuple[str, str]:
    """Lluvia del mes → (clave, texto)."""
    if mm < 50:
        return "dry", "seco"
    if mm < 130:
        return "some", "algunas lluvias"
    return "wet", "lluvioso"


def feel(tmax: float) -> str:
    if tmax >= 30:
        return "caluroso"
    if tmax >= 25:
        return "cálido"
    if tmax >= 18:
        return "templado"
    if tmax >= 8:
        return "fresco"
    return "frío"
