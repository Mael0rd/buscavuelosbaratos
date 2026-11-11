"""Detección de ofertas "de verdad".

Por cada ruta (origen-destino) se toma el boleto más barato de la corrida, en
cualquier mes. Es oferta si:
  - con >= min_days días de historial: está >= drop_pct por debajo de la
    mediana de los mínimos diarios de esa ruta;
  - sin historial suficiente: está bajo un tope que depende de la distancia.
Una ruta no se repite durante repost_days salvo que baje repost_extra_drop más.
"""
import math
import statistics
from datetime import date, datetime, timedelta, timezone

from .config import origin_country_map


def haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def cold_cap(km_round_trip: float, cc: dict) -> float:
    return cc["k"] * km_round_trip ** cc["exp"]


def trip_days(departure_at: str, return_at: str) -> int | None:
    """Días entre la fecha de ida y la de vuelta (None si falta alguna)."""
    try:
        return (date.fromisoformat((return_at or "")[:10]) - date.fromisoformat((departure_at or "")[:10])).days
    except ValueError:
        return None


def route_best(tickets: list[dict], max_transfers: int, min_trip_days: int = 0) -> dict:
    """Boleto más barato por ruta, con los mínimos de cada mes en t['month_prices']."""
    best, months = {}, {}
    for t in tickets:
        if not t["destination"] or t["destination"] == t["origin"]:
            continue
        if max(t["transfers"], t["return_transfers"]) > max_transfers:
            continue
        if min_trip_days:
            days = trip_days(t["departure_at"], t["return_at"])
            if days is None or days < min_trip_days:
                continue
        k = (t["origin"], t["destination"])
        if k not in best or t["price"] < best[k]["price"]:
            best[k] = t
        m = months.setdefault(k, {})
        mo = (t["departure_at"] or "")[:7]
        m[mo] = min(m.get(mo, t["price"]), t["price"])
    for k, t in best.items():
        best[k] = {**t, "month_prices": sorted(months[k].values()), "month_min": dict(sorted(months[k].items()))}
    return best


def drop_domestic(best: dict, ref) -> dict:
    """Solo viajes internacionales: descarta rutas dentro del mismo país."""
    out = {}
    for (o, d), t in best.items():
        co, cd = ref.country_code(o), ref.country_code(d)
        if co and cd and co == cd:
            continue
        out[(o, d)] = t
    return out


def purge_domestic(conn, ref) -> int:
    """Borra ofertas e historial de rutas nacionales ya guardadas (idempotente)."""
    removed = 0
    for table in ("deals", "prices_daily"):
        routes = conn.execute(f"SELECT DISTINCT origin, destination FROM {table}").fetchall()
        for o, d in routes:
            co, cd = ref.country_code(o), ref.country_code(d)
            if co and cd and co == cd:
                cur = conn.execute(f"DELETE FROM {table} WHERE origin=? AND destination=?", (o, d))
                if table == "deals":
                    removed += cur.rowcount
    conn.commit()
    return removed


def purge_short_trips(conn, min_trip_days: int) -> int:
    """Retira ofertas guardadas cuyo viaje dura menos de min_trip_days."""
    rows = conn.execute("SELECT id, departure_at, return_at FROM deals").fetchall()
    bad = [r[0] for r in rows
           if (lambda n: n is None or n < min_trip_days)(trip_days(r[1], r[2]))]
    conn.executemany("DELETE FROM deals WHERE id=?", [(i,) for i in bad])
    conn.commit()
    return len(bad)


def purge_too_many_stops(conn, max_transfers: int) -> int:
    """Retira ofertas guardadas con más escalas que las permitidas hoy."""
    cur = conn.execute("DELETE FROM deals WHERE transfers > ?", (max_transfers,))
    conn.commit()
    return cur.rowcount


def month_baseline(t: dict, min_months: int):
    """Precio típico de la ruta según los OTROS meses de esta misma corrida."""
    others = list(t.get("month_prices", []))
    if t["price"] in others:
        others.remove(t["price"])
    return statistics.median(others) if len(others) >= min_months - 1 else None


def update_daily(conn, best: dict, today: str) -> None:
    conn.executemany(
        """INSERT INTO prices_daily (origin, destination, day, min_price) VALUES (?,?,?,?)
           ON CONFLICT(origin, destination, day)
           DO UPDATE SET min_price = MIN(min_price, excluded.min_price)""",
        [(o, d, today, t["price"]) for (o, d), t in best.items()],
    )
    conn.commit()


def prune(conn, today: str, keep_days: int) -> None:
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    conn.execute("DELETE FROM prices_daily WHERE day < ?", (cutoff,))
    conn.execute("DELETE FROM deals WHERE published_at < datetime('now', '-120 days')")
    conn.commit()


def baseline(conn, origin, destination, today: str, days: int):
    start = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    prices = [r[0] for r in conn.execute(
        """SELECT min_price FROM prices_daily
           WHERE origin=? AND destination=? AND day >= ? AND day < ?""",
        (origin, destination, start, today))]
    return (statistics.median(prices), len(prices)) if prices else (None, 0)


def recently_published(conn, origin, destination, days: int):
    """Oferta reciente de la ruta que impide repetirla. Cuentan las activas y las
    que terminaron hace menos de 24 h (evita el vaivén publicar/terminar/publicar);
    una oferta terminada hace más tiempo ya no bloquea."""
    return conn.execute(
        """SELECT price FROM deals WHERE origin=? AND destination=?
             AND published_at >= datetime('now', ?)
             AND (COALESCE(status, 'active') = 'active'
                  OR expired_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 day'))
           ORDER BY price ASC LIMIT 1""",
        (origin, destination, f"-{days} days"),
    ).fetchone()


def evaluate(conn, route: tuple, t: dict, cfg: dict, ref, today: str, stats: dict | None = None):
    """Aplica la regla de oferta a una ruta. Devuelve la oferta (dict) o None.
    No revisa repeticiones: eso depende de dónde se publique.
    stats (opcional) cuenta por qué se descarta cada ruta."""
    def no(reason):
        if stats is not None:
            stats[reason] = stats.get(reason, 0) + 1
        return None

    o, d = route
    dcfg = cfg["deals"]
    med, n = baseline(conn, o, d, today, dcfg["history_days"])
    if med and n >= dcfg["min_days"]:
        base, threshold = med, med * (1 - dcfg["drop_pct"])
        if t["price"] > threshold:
            return no("con_historial_no_baja_lo_suficiente")
    else:
        # Sin historial: tope por distancia Y bien por debajo de los otros meses
        a, b = ref.coords(o), ref.coords(d)
        if not a or not b:
            return no("sin_coordenadas")
        cs = dcfg["cold_start"]
        cap = cold_cap(2 * haversine_km(a, b), cs)
        mb = month_baseline(t, cs["min_months"])
        base = None
        if stats is not None:  # precio / tope, para calibrar el tope con datos reales
            stats.setdefault("_ratios", []).append((t["price"] / cap, mb is None))
        if mb is None:  # pocos meses con precio: solo pasa si es muy barata
            threshold = cap * cs["few_months_factor"]
            if t["price"] > threshold:
                return no("pocos_meses_y_sobre_tope_estricto")
        else:
            month_thr = mb * (1 - cs["month_drop"])
            threshold = min(cap, month_thr)
            over_cap, over_month = t["price"] > cap, t["price"] > month_thr
            if over_cap and over_month:
                return no("sobre_tope_y_no_baja_vs_meses")
            if over_cap:
                return no("sobre_tope_distancia")
            if over_month:
                return no("no_baja_vs_otros_meses")
    if t["price"] > threshold:
        return None
    cid = origin_country_map(cfg).get(o, "otros")
    return {
        **t,
        "country": cid,
        "flag": cfg["countries"].get(cid, {}).get("flag", ""),
        "baseline": base,
        "threshold": threshold,
        "score": t["price"] / threshold,  # menor = mejor oferta
        "origin_name": ref.city_name(o),
        "dest_name": ref.city_name(d),
        "dest_country": ref.country_name(ref.country_code(d)),
        "airline_name": ref.airline_name(t["airline"]),
    }


def find_deals(conn, best: dict, cfg: dict, ref, today: str, stats: dict | None = None) -> list[dict]:
    dcfg = cfg["deals"]
    out = []
    for route, t in best.items():
        deal = evaluate(conn, route, t, cfg, ref, today, stats)
        if not deal:
            continue
        prev = recently_published(conn, *route, dcfg["repost_days"])
        if prev and t["price"] > prev["price"] * (1 - dcfg["repost_extra_drop"]):
            if stats is not None:
                stats["ya_publicada_en_7_dias"] = stats.get("ya_publicada_en_7_dias", 0) + 1
            continue
        out.append(deal)
    return sorted(out, key=lambda x: x["score"])


def make_slug(d: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return f"{d['origin']}-{d['destination']}-{d['departure_at'][:7]}-{stamp}".lower()


COLS = ("slug", "country", "flag", "origin", "origin_name", "origin_airport",
        "destination", "dest_name", "dest_country", "destination_airport",
        "price", "baseline", "threshold", "score", "airline", "airline_name",
        "departure_at", "return_at", "transfers", "link", "copy_web", "copy_social", "found_at")


def save_deal(conn, d: dict) -> None:
    conn.execute(
        f"INSERT OR IGNORE INTO deals ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})",
        tuple(d.get(c) for c in COLS),
    )
    conn.commit()
