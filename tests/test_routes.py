import json
import sqlite3

from bvb import db, routes
from bvb.refdata import Ref

CFG = {"countries": {"costa-rica": {"name": "Costa Rica", "cc": "CR", "origins": ["SJO"]}},
       "deals": {"history_days": 60}}
REF = Ref(cities=[{"code": "SJO", "name": "San José", "country_code": "CR", "coordinates": {"lat": 9.99, "lon": -84.2}},
                  {"code": "MAD", "name": "Madrid", "country_code": "ES", "coordinates": {"lat": 40.47, "lon": -3.56}},
                  {"code": "MIA", "name": "Miami", "country_code": "US", "coordinates": {"lat": 25.79, "lon": -80.29}}],
          countries=[{"code": "ES", "name": "España"}, {"code": "US", "name": "Estados Unidos"}],
          airlines=[{"code": "IB", "name": "Iberia"}])


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


def t(price, dest="MAD", transfers=1):
    return {"origin": "SJO", "destination": dest, "price": price, "airline": "IB", "transfers": transfers,
            "departure_at": "2027-03-10T10:00", "return_at": "2027-03-20T10:00", "link": "https://x",
            "month_min": {"2027-02": price + 80, "2027-03": price, "2027-04": price + 40}}


def history(c, dest, prices):
    for i, p in enumerate(prices):
        c.execute("INSERT INTO prices_daily VALUES ('SJO', ?, date('now', ?), ?)", (dest, f"-{len(prices) - i} days", p))


def test_slug_is_readable_and_unique():
    r = {"origin": "SJO", "destination": "MAD", "origin_name": "San José", "dest_name": "Madrid"}
    assert routes.route_slug(r) == "san-jose-a-madrid-sjo-mad"


def test_pages_only_with_enough_history_and_stats():
    c = conn()
    routes.update(c, {("SJO", "MAD"): t(620), ("SJO", "MIA"): t(250, "MIA", 0)}, REF, "2026-11-11")
    history(c, "MAD", [700, 650, 620, 690])
    history(c, "MIA", [260, 255])                      # solo 2 días: aún no tiene página
    pages = routes.build_pages(c, CFG, [], [], min_days=3)
    assert [p["destination"] for p in pages] == ["MAD"]
    p = pages[0]
    assert p["low"] == 620 and p["typical"] == 670 and p["days"] == 4
    assert p["cheapest_month"] == ("marzo 2027", 620)
    assert p["airlines"] == ["Iberia"] and p["chart"] is not None
    qs = [q for q, _ in routes.faq(p)]
    assert "¿Cuál es el mes más barato para volar de San José a Madrid?" in qs


def test_direct_flag_is_sticky():
    c = conn()
    routes.update(c, {("SJO", "MIA"): t(250, "MIA", transfers=0)}, REF, "2026-11-10")
    routes.update(c, {("SJO", "MIA"): t(260, "MIA", transfers=1)}, REF, "2026-11-11")
    assert c.execute("SELECT direct_seen FROM routes").fetchone()[0] == 1
