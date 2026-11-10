import sqlite3

from bvb import deals as dl
from bvb.db import SCHEMA

CFG = {
    "destinations": {"MIA": {"name": "Miami", "max_price": 250}},
    "deals": {"drop_pct": 0.25, "min_samples": 8, "history_days": 45,
              "repost_days": 7, "repost_extra_drop": 0.10},
}


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def t(price, month="2027-01"):
    return {"origin": "SJO", "destination": "MIA", "price": price, "airline": "AA",
            "departure_at": f"{month}-10", "return_at": f"{month}-17",
            "transfers": 0, "link": "x"}


def test_cold_start_uses_max_price():
    c = conn()
    assert len(dl.find_deals(c, [t(240)], CFG, "2999-01-01")) == 1
    assert len(dl.find_deals(c, [t(260)], CFG, "2999-01-01")) == 0


def test_history_median_rule():
    c = conn()
    dl.save_observations(c, [t(400)] * 10)          # mediana 400
    assert dl.find_deals(c, [t(310)], CFG, "2999-01-01") == []   # solo -22%
    found = dl.find_deals(c, [t(290)], CFG, "2999-01-01")        # -27%
    assert found and found[0]["baseline"] == 400


def test_no_repost_unless_cheaper():
    c = conn()
    d = dl.find_deals(c, [t(240)], CFG, "2999-01-01")[0]
    d.update(slug="a", copy_web="", copy_social="")
    dl.save_deal(c, d)
    assert dl.find_deals(c, [t(235)], CFG, "2999-01-01") == []   # casi igual
    assert len(dl.find_deals(c, [t(210)], CFG, "2999-01-01")) == 1  # bajó >10%
