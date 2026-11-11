import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from bvb import db, telegram, verify
from bvb.fresh import iso

NOW = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
CFG = {
    "site": {"domain": "buscavuelosbaratos.com", "currency": "usd"},
    "countries": {"mexico": {"name": "México", "flag": "🇲🇽", "cc": "MX", "origins": ["MEX"]},
                  "chile": {"name": "Chile", "flag": "🇨🇱", "cc": "CL", "origins": ["SCL"]}},
    "timezones": {"mexico": ["America/Mexico_City"], "chile": ["America/Santiago"]},
    "deals": {"show_days": 14},
    "social": {"main": {"per_run": 1, "per_day": 10}, "country": {"per_run": 2, "per_day": 10},
               "quiet_hours": [23, 6], "timezone": "America/Costa_Rica"},
    "freshness": {"max_age_hours": 72},
    "verify": {"serpapi_monthly": 250, "apify_monthly": 1000, "apify_actor": "x~y",
               "cache_hours": 3, "price_tolerance": 0.15, "require_low_level": True,
               "freshness_weight_hours": 48, "web_reverify_hours": 12, "web_max_age_hours": 24},
}


class Fake:
    """Proveedor de prueba: responde lo que se le indique y cuenta búsquedas."""
    def __init__(self, name, monthly, answer=None, quota=False):
        self.name, self.monthly, self.answer, self.quota = name, monthly, answer, quota
        self.configured, self.calls = True, 0

    def search(self, o, d, dep, ret):
        self.calls += 1
        if self.quota:
            raise verify.QuotaExceeded("run out")
        return self.answer


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


def save(c, **kw):
    d = {"slug": "x", "country": "mexico", "origin": "MEX", "destination": "MAD",
         "origin_name": "Ciudad de México", "dest_name": "Madrid", "origin_airport": "MEX",
         "destination_airport": "MAD", "price": 500.0, "score": 0.8, "transfers": 0, "link": "https://x",
         "departure_at": "2027-02-03T10:00:00-06:00", "return_at": "2027-02-17T12:00:00+01:00",
         "found_at": iso(NOW - timedelta(hours=5))}
    d.update(kw)
    c.execute(f"INSERT INTO deals ({','.join(d)}) VALUES ({','.join('?' * len(d))})", tuple(d.values()))
    return dict(c.execute("SELECT * FROM deals WHERE slug=?", (d["slug"],)).fetchone())


ANS_OK = {"price": 495.0, "level": "low", "low": 690.0, "high": 1350.0}


# ---------- parsers ----------
def test_parse_serpapi():
    r = verify.parse_serpapi({"best_flights": [{"price": 530}], "other_flights": [{"price": 512}],
                              "price_insights": {"lowest_price": 512, "price_level": "low",
                                                 "typical_price_range": [690, 1350]}})
    assert r == {"price": 512.0, "level": "low", "low": 690.0, "high": 1350.0}
    with pytest.raises(verify.QuotaExceeded):
        verify.parse_serpapi({"error": "Your account has run out of searches."})
    assert verify.parse_serpapi({"error": "Google Flights hasn't returned any results for this query."})["price"] is None


def test_parse_apify_skips_two_stops():
    seg = lambda n: {"segments": [{}] * n}
    items = [{"price": {"grandTotal": "300.00"}, "itineraries": [seg(3), seg(1)]},          # 2 escalas: no
             {"price": {"grandTotal": "420.50"}, "itineraries": [seg(2), seg(2)],
              "googleFlights": {"priceLevel": "LOW", "typicalPriceRange": [600, 900]}}]
    assert verify.parse_apify(items) == {"price": 420.5, "level": "low", "low": 600.0, "high": 900.0}


# ---------- presupuesto ----------
def test_budget_splits_month_across_days_and_hours():
    v = verify.Verifier(conn(), CFG, NOW, providers=[Fake("serpapi", 250), Fake("apify", 1000)])
    b = v.budget()  # 20 de noviembre: quedan 11 días → ~113,6/día → ~7 por hora (17 h activas)
    assert b["monthly"] == 1250 and b["used_month"] == 0
    assert round(b["daily"]) == 114 and b["allowed_now"] == 7


def test_budget_counts_only_this_month_and_hour(monkeypatch):
    c = conn()
    v = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250)])
    for i in range(3):
        v._log("serpapi", 1, "ok")
    c.execute("INSERT INTO verify_log VALUES ('2026-10-30T10:00:00Z','serpapi',1,'ok',NULL,NULL)")
    b = v.budget()
    assert b["used_month"] == 3 and b["used_today"] == 3
    assert b["allowed_now"] == max(0, 2 - 3) == 0  # 247/11 ≈ 22/día → 2 por hora, ya se usaron 3


# ---------- verificación ----------
def test_ok_once_then_cached():
    c = conn()
    d = save(c)
    p = Fake("serpapi", 250, ANS_OK)
    v = verify.Verifier(c, CFG, NOW, providers=[p])
    assert v.ensure(d) == "ok" and p.calls == 1
    row = dict(c.execute("SELECT * FROM deals").fetchone())
    assert row["verify_status"] == "ok" and row["price_level"] == "low" and row["typical_high"] == 1350
    assert v.ensure(row) == "ok" and p.calls == 1          # caché: no gasta otra búsqueda


def test_price_up_and_typical_expires_deal():
    c = conn()
    d = save(c)
    v = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "price": 620.0, "level": "typical"})])
    assert v.ensure(d) == "rechazada"
    row = c.execute("SELECT status, expire_reason, verify_status FROM deals").fetchone()
    assert tuple(row) == ("expired", "subio", "rechazada")


def test_typical_level_rejected_but_stays_on_web():
    c = conn()
    d = save(c)
    v = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "level": "typical"})])
    assert v.ensure(d) == "rechazada"
    assert tuple(c.execute("SELECT status, verify_status FROM deals").fetchone()) == ("active", "rechazada")


def test_slightly_higher_live_price_is_shown():
    c = conn()
    d = save(c)
    verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "price": 530.0})]).ensure(d)
    assert c.execute("SELECT price FROM deals").fetchone()[0] == 530.0   # nunca se promete menos


def test_falls_back_to_apify_when_serpapi_quota_runs_out():
    c = conn()
    serp, apify = Fake("serpapi", 250, quota=True), Fake("apify", 1000, ANS_OK)
    v = verify.Verifier(c, CFG, NOW, providers=[serp, apify])
    assert v.ensure(save(c, slug="a")) == "ok" and apify.calls == 1
    assert v.exhausted("serpapi")
    v.ensure(save(c, slug="b"))
    assert serp.calls == 1 and apify.calls == 2      # no vuelve a intentar SerpApi este mes


def test_no_providers_means_no_budget():
    c = conn()
    assert verify.Verifier(c, CFG, NOW, providers=[]).ensure(save(c)) == "sin_presupuesto"


# ---------- publicación: una verificación, varios canales ----------
@pytest.fixture
def tg(monkeypatch):
    sent = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("TELEGRAM_CHANNEL", "@general")
    monkeypatch.setenv("BVB_VARS", '{"TELEGRAM_CHANNEL_MEXICO": "@mx"}')
    monkeypatch.setattr(telegram, "send", lambda text, markup, chat_id=None: sent.append((chat_id, text)) or len(sent))
    monkeypatch.setattr(telegram, "send_photo", lambda photo, text, markup, chat: sent.append((chat, text)) or len(sent))
    return sent


def test_one_verification_feeds_country_and_general(tg):
    c = conn()
    save(c, slug="mx1", score=0.5)
    save(c, slug="cl1", country="chile", origin="SCL", origin_name="Santiago", score=0.6)
    p = Fake("serpapi", 250, ANS_OK)
    v = verify.Verifier(c, CFG, NOW, providers=[p])
    stats = telegram.publish(c, CFG, NOW, verifier=v)
    assert stats == {"general": 1, "mexico": 1}
    assert sorted(ch for ch, _ in tg) == ["@general", "@mx"]       # la misma oferta a los 2 canales
    assert p.calls == 1                                              # ...con UNA sola verificación
    assert "Precio verificado" in tg[0][1] and "precio bajo" in tg[0][1] and "$690–$1350" in tg[0][1]


def test_rejected_is_skipped_and_next_is_tried(tg):
    c = conn()
    save(c, slug="mx1", score=0.5)
    save(c, slug="mx2", score=0.6)

    class Seq(Fake):
        def search(self, *a):
            self.calls += 1
            return {**ANS_OK, "price": 900.0, "level": "typical"} if self.calls == 1 else ANS_OK
    v = verify.Verifier(c, CFG, NOW, providers=[Seq("serpapi", 250)])
    telegram.publish(c, CFG, NOW, verifier=v)
    slugs = [r[0] for r in c.execute("SELECT d.slug FROM telegram_posts p JOIN deals d ON d.id=p.deal_id")]
    assert "mx1" not in slugs and "mx2" in slugs


def test_without_budget_nothing_is_published(tg):
    c = conn()
    save(c)
    v = verify.Verifier(c, CFG, NOW, providers=[])
    assert telegram.publish(c, CFG, NOW, verifier=v) == {"general": 0, "mexico": 0}
    assert tg == []


def test_fresher_price_is_verified_first(tg):
    c = conn()
    # Mejor descuento pero visto hace 70 h  vs  algo menos de descuento pero visto hace 2 h
    save(c, slug="vieja", score=0.60, found_at=iso(NOW - timedelta(hours=70)))
    save(c, slug="reciente", score=0.75, found_at=iso(NOW - timedelta(hours=2)))
    assert telegram.priority({"score": 0.60, "found_at": iso(NOW - timedelta(hours=70))}, CFG, NOW) > \
           telegram.priority({"score": 0.75, "found_at": iso(NOW - timedelta(hours=2))}, CFG, NOW)
    seen = []

    class Rec(Fake):
        def search(self, o, d, dep, ret):
            seen.append(self.calls)
            self.calls += 1
            return ANS_OK
    v = verify.Verifier(c, CFG, NOW, providers=[Rec("serpapi", 250)])
    telegram.publish(c, CFG, NOW, verifier=v)
    first = c.execute("SELECT d.slug FROM verify_log l JOIN deals d ON d.id=l.deal_id ORDER BY l.rowid LIMIT 1").fetchone()[0]
    assert first == "reciente"


# ---------- web: solo verificadas, re-verificación ----------
def test_web_shows_only_recently_verified():
    ok = {"verify_status": "ok", "verified_at": iso(NOW - timedelta(hours=5))}
    assert verify.web_visible(ok, CFG, NOW)
    assert not verify.web_visible({**ok, "verified_at": iso(NOW - timedelta(hours=30))}, CFG, NOW)
    assert not verify.web_visible({"verify_status": None}, CFG, NOW)
    assert not verify.web_visible({**ok, "verify_status": "rechazada"}, CFG, NOW)


def test_refresh_web_reverifies_old_ones_first():
    c = conn()
    save(c, slug="nueva", score=0.5)
    save(c, slug="vieja", score=0.9, verify_status="ok", verified_at=iso(NOW - timedelta(hours=13)))
    save(c, slug="reciente", score=0.9, verify_status="ok", verified_at=iso(NOW - timedelta(hours=2)))
    order = []

    class Rec(Fake):
        def search(self, o, d, dep, ret):
            self.calls += 1
            return ANS_OK
    v = verify.Verifier(c, CFG, NOW, providers=[Rec("serpapi", 250)])
    orig = v._verify
    v._verify = lambda d: order.append(d["slug"]) or orig(d)
    assert v.refresh_web() == {"reverificadas": 1, "nuevas": 1}
    assert order == ["vieja", "nueva"]          # 'reciente' (2 h) no gasta verificación


def test_reverification_that_finds_higher_price_ends_the_deal():
    c = conn()
    save(c, slug="v", verify_status="ok", verified_at=iso(NOW - timedelta(hours=13)))
    verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "price": 700.0, "level": "high"})]).refresh_web()
    assert tuple(c.execute("SELECT status, expire_reason FROM deals").fetchone()) == ("expired", "subio")


def test_publish_skips_unverified_but_posts_cached_when_budget_is_out(tg):
    c = conn()
    save(c, slug="sin_verificar", score=0.4)
    save(c, slug="verificada", score=0.9, verify_status="ok", verified_at=iso(NOW - timedelta(hours=1)))
    v = verify.Verifier(c, CFG, NOW, providers=[])     # sin presupuesto
    telegram.publish(c, CFG, NOW, verifier=v)
    posted = {r[0] for r in c.execute("SELECT d.slug FROM telegram_posts p JOIN deals d ON d.id=p.deal_id")}
    assert posted == {"verificada"}


def test_google_low_is_enough_even_if_price_changed():
    c = conn()
    d = save(c, price=140.0)
    v = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "price": 175.0})])  # +25%, pero "bajo"
    assert v.ensure(d) == "ok"
    assert c.execute("SELECT price FROM deals").fetchone()[0] == 175.0      # se muestra el de Google


def test_without_google_level_uses_15_percent():
    c = conn()
    v = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {"price": 160.0, "level": None, "low": None, "high": None})])
    assert v.ensure(save(c, slug="a", price=140.0)) == "ok"          # +14%
    v2 = verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {"price": 170.0, "level": None, "low": None, "high": None})])
    assert v2.ensure(save(c, slug="b", price=140.0)) == "rechazada"  # +21%


def test_lower_live_price_is_shown():
    c = conn()
    d = save(c, price=500.0)
    verify.Verifier(c, CFG, NOW, providers=[Fake("serpapi", 250, {**ANS_OK, "price": 470.0})]).ensure(d)
    assert c.execute("SELECT price FROM deals").fetchone()[0] == 470.0
