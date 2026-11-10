"""Detección de ofertas.

Una tarifa es oferta si:
  - hay historial suficiente y está >= drop_pct por debajo de la mediana, o
  - no hay historial suficiente y está por debajo del max_price del destino.
Se evita repetir la misma ruta/mes durante repost_days, salvo que baje más.
"""
import statistics
from datetime import datetime, timezone


def _month(departure_at: str) -> str:
    return (departure_at or "")[:7]


def save_observations(conn, tickets: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO observations
           (origin, destination, depart_month, price, airline, departure_at,
            return_at, transfers, link)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [
            (t["origin"], t["destination"], _month(t["departure_at"]), t["price"],
             t["airline"], t["departure_at"], t["return_at"], t["transfers"], t["link"])
            for t in tickets
        ],
    )
    conn.commit()


def baseline(conn, origin, destination, days, exclude_run_start=None):
    q = """SELECT price FROM observations
           WHERE origin=? AND destination=? AND found_at >= datetime('now', ?)"""
    args = [origin, destination, f"-{days} days"]
    if exclude_run_start:
        q += " AND found_at < ?"
        args.append(exclude_run_start)
    prices = [r["price"] for r in conn.execute(q, args)]
    return (statistics.median(prices), len(prices)) if prices else (None, 0)


def recently_published(conn, origin, destination, month, days):
    return conn.execute(
        """SELECT price FROM deals
           WHERE origin=? AND destination=? AND depart_month=?
             AND published_at >= datetime('now', ?)
           ORDER BY price ASC LIMIT 1""",
        (origin, destination, month, f"-{days} days"),
    ).fetchone()


def find_deals(conn, tickets: list[dict], cfg: dict, run_start: str) -> list[dict]:
    dcfg = cfg["deals"]
    # Quedarse con la tarifa más barata por ruta + mes de salida
    best: dict[tuple, dict] = {}
    for t in tickets:
        key = (t["origin"], t["destination"], _month(t["departure_at"]))
        if key not in best or t["price"] < best[key]["price"]:
            best[key] = t

    deals = []
    for (origin, dest, month), t in best.items():
        dest_cfg = cfg["destinations"].get(dest, {})
        med, n = baseline(conn, origin, dest, dcfg["history_days"], run_start)

        if med and n >= dcfg["min_samples"]:
            is_deal = t["price"] <= med * (1 - dcfg["drop_pct"])
            ref = med
        else:
            cap = dest_cfg.get("max_price")
            is_deal = cap is not None and t["price"] <= cap
            ref = None  # sin historial: no afirmamos un % de ahorro

        if not is_deal:
            continue

        prev = recently_published(conn, origin, dest, month, dcfg["repost_days"])
        if prev and t["price"] > prev["price"] * (1 - dcfg["repost_extra_drop"]):
            continue

        deals.append({**t, "depart_month": month, "baseline": ref,
                      "dest_name": dest_cfg.get("name", dest)})
    return sorted(deals, key=lambda d: d["price"] / (d["baseline"] or d["price"]))


def make_slug(d: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return f"{d['origin']}-{d['destination']}-{d['depart_month']}-{stamp}".lower()


def save_deal(conn, d: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO deals
           (slug, origin, destination, depart_month, price, baseline, airline,
            departure_at, return_at, transfers, link, copy_web, copy_social)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["slug"], d["origin"], d["destination"], d["depart_month"], d["price"],
         d["baseline"], d["airline"], d["departure_at"], d["return_at"],
         d["transfers"], d["link"], d["copy_web"], d["copy_social"]),
    )
    conn.commit()
