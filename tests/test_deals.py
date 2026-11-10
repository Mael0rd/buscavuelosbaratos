import sqlite3

from bvb import deals as dl
from bvb.db import SCHEMA
from bvb.refdata import Ref

CFG = {
    "countries": {"costa-rica": {"name": "Costa Rica", "flag": "🇨🇷", "origins": ["SJO"]}},
    "deals": {"drop_pct": 0.30, "min_days": 7, "history_days": 60,
              "cold_start": {"k": 1.0, "exp": 0.65, "month_drop": 0.25, "min_months": 3, "few_months_factor": 0.75},
              "repost_days": 7, "repost_extra_drop": 0.10},
}
REF = Ref(
    cities=[{"code": "SJO", "name": "San José", "country_code": "CR",
             "coordinates": {"lat": 9.99, "lon": -84.20}},
            {"code": "MIA", "name": "Miami", "country_code": "US",
             "coordinates": {"lat": 25.79, "lon": -80.29}}],
    countries=[{"code": "US", "name": "Estados Unidos"}],
    airlines=[{"code": "AA", "name": "American Airlines"}],
)
TODAY = "2026-11-20"


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def t(price, month="2027-01", transfers=0):
    return {"origin": "SJO", "origin_airport": "SJO", "destination": "MIA",
            "destination_airport": "MIA", "price": price, "airline": "AA",
            "departure_at": f"{month}-10", "return_at": f"{month}-17",
            "transfers": transfers, "return_transfers": 0, "link": "x"}


def best(*tickets):
    return dl.route_best(list(tickets), max_transfers=2)


def seed_history(c, price, days=10):
    for i in range(1, days + 1):
        c.execute("INSERT INTO prices_daily VALUES ('SJO','MIA',?,?)", (f"2026-11-{20 - i:02d}", price))


def test_haversine_sjo_mia():
    km = dl.haversine_km((9.99, -84.20), (25.79, -80.29))
    assert 1700 < km < 1900


def test_route_best_picks_cheapest_month_and_drops_many_stops():
    b = best(t(300, "2027-01"), t(250, "2027-03"), t(100, transfers=3))
    assert b[("SJO", "MIA")]["price"] == 250


OTHER_MONTHS = [t(300, "2027-02"), t(310, "2027-03"), t(290, "2027-04")]  # típico ~$300


def test_cold_start_uses_distance_cap():
    c = conn()  # tope SJO-MIA ≈ $205; otros meses ~$300 → tope mensual $225
    assert len(dl.find_deals(c, best(t(190), *OTHER_MONTHS), CFG, REF, TODAY)) == 1
    assert dl.find_deals(c, best(t(215), *OTHER_MONTHS), CFG, REF, TODAY) == []


def test_cold_start_rejects_route_that_is_always_cheap():
    c = conn()  # bajo el tope, pero todos los meses cuestan lo mismo: no es oferta
    same = [t(150, "2027-02"), t(155, "2027-03"), t(148, "2027-04")]
    assert dl.find_deals(c, best(t(145), *same), CFG, REF, TODAY) == []


def test_cold_start_few_months_uses_stricter_cap():
    c = conn()  # 2 meses: tope estricto ≈ $205 × 0.75 ≈ $154
    assert dl.find_deals(c, best(t(170), t(300, "2027-02")), CFG, REF, TODAY) == []
    assert len(dl.find_deals(c, best(t(140), t(300, "2027-02")), CFG, REF, TODAY)) == 1


def test_history_requires_30pct_drop():
    c = conn()
    seed_history(c, 400)                                         # mediana 400
    assert dl.find_deals(c, best(t(300)), CFG, REF, TODAY) == []  # solo -25%
    found = dl.find_deals(c, best(t(270)), CFG, REF, TODAY)       # -32%
    assert found and found[0]["baseline"] == 400
    assert found[0]["dest_name"] == "Miami" and found[0]["country"] == "costa-rica"


def test_today_not_in_baseline():
    c = conn()
    seed_history(c, 400)
    dl.update_daily(c, best(t(100)), TODAY)  # el mínimo de hoy no cuenta en la mediana
    assert dl.baseline(c, "SJO", "MIA", TODAY, 60) == (400, 10)


def test_no_repost_unless_cheaper():
    c = conn()
    d = dl.find_deals(c, best(t(190), *OTHER_MONTHS), CFG, REF, TODAY)[0]
    d.update(slug="a", copy_web="", copy_social="")
    dl.save_deal(c, d)
    assert dl.find_deals(c, best(t(185), *OTHER_MONTHS), CFG, REF, TODAY) == []     # casi igual
    assert len(dl.find_deals(c, best(t(160), *OTHER_MONTHS), CFG, REF, TODAY)) == 1  # bajó >10%


def test_domestic_routes_are_dropped_and_purged():
    ref = Ref(cities=[{"code": "SCL", "country_code": "CL"}, {"code": "CJC", "country_code": "CL"},
                      {"code": "MIA", "country_code": "US"}], countries=[], airlines=[])
    tk = [dict(t(50), origin="SCL", destination="CJC"), dict(t(300), origin="SCL", destination="MIA")]
    b = dl.drop_domestic(best(*tk), ref)
    assert list(b) == [("SCL", "MIA")]

    c = conn()
    c.execute("INSERT INTO deals (slug, origin, destination) VALUES ('x','SCL','CJC'), ('y','SCL','MIA')")
    c.execute("INSERT INTO prices_daily VALUES ('SCL','CJC','2026-11-10',50)")
    assert dl.purge_domestic(c, ref) == 1
    assert [r[0] for r in c.execute("SELECT slug FROM deals")] == ["y"]
    assert c.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0] == 0
