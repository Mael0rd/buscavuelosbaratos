import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from bvb import db, fresh, telegram

NOW = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)  # 12:00 en Costa Rica / Ciudad de México
CFG = {
    "site": {"domain": "buscavuelosbaratos.com", "currency": "usd"},
    "countries": {"mexico": {"name": "México", "flag": "🇲🇽", "cc": "MX", "origins": ["MEX"]},
                  "costa-rica": {"name": "Costa Rica", "flag": "🇨🇷", "cc": "CR", "origins": ["SJO"]}},
    "timezones": {"mexico": ["America/Mexico_City"], "costa-rica": ["America/Costa_Rica"]},
    "deals": {"show_days": 14},
    "social": {"main": {"per_run": 1, "per_day": 10}, "country": {"per_run": 2, "per_day": 10},
               "quiet_hours": [23, 6], "timezone": "America/Costa_Rica"},
    "freshness": {"max_age_hours": 6, "stale_hours": 24, "price_tolerance": 0.10,
                  "min_days_before_departure": 2, "pause_seconds": 0},
}


def ts(hours_ago):
    return fresh.iso(NOW - timedelta(hours=hours_ago))


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


def deal(**kw):
    d = {"origin": "MEX", "destination": "MAD", "price": 500.0,
         "departure_at": "2027-02-03T10:00:00-06:00", "return_at": "2027-02-17T12:00:00+01:00"}
    d.update(kw)
    return d


def checker_with(entries):
    ch = fresh.Checker(CFG)
    ch.cache[("MEX", "MAD")] = entries
    return ch


def entry(value, hours_ago, dep="2027-02-03", ret="2027-02-17"):
    return {"value": value, "depart_date": dep, "return_date": ret, "found_at": ts(hours_ago)}


# ---------- frescura ----------
def test_fresh_match_recent():
    ch = checker_with([entry(495, 2)])
    assert ch.is_fresh(deal(), NOW) == ts(2)


def test_not_fresh_when_seen_long_ago():
    ch = checker_with([entry(495, 10)])
    assert ch.check(deal(), NOW)[0] == "match"
    assert ch.is_fresh(deal(), NOW) is None


def test_other_dates_do_not_count():
    ch = checker_with([entry(450, 1, dep="2027-02-04")])
    assert ch.check(deal(), NOW) == ("none", None)


def test_price_went_up():
    ch = checker_with([entry(700, 1)])
    assert ch.check(deal(found_at=ts(5)), NOW) == ("higher", None)


def test_found_at_without_timezone_is_utc():
    assert fresh.parse_ts("2026-11-20 16:00:00") == NOW - timedelta(hours=2)


# ---------- revisión de ofertas publicadas ----------
def save(c, **kw):
    d = {"slug": kw.pop("slug", "x"), "country": "mexico", "origin": "MEX", "destination": "MAD",
         "origin_name": "Ciudad de México", "dest_name": "Madrid", "price": 500.0, "score": 0.8,
         "departure_at": "2027-02-03T10:00:00-06:00", "return_at": "2027-02-17T12:00:00+01:00",
         "transfers": 0, "link": "https://x", "found_at": ts(3)}
    d.update(kw)
    cols = ",".join(d)
    c.execute(f"INSERT INTO deals ({cols}) VALUES ({','.join('?' * len(d))})", tuple(d.values()))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def status(c, i):
    r = c.execute("SELECT status, expire_reason, found_at FROM deals WHERE id=?", (i,)).fetchone()
    return tuple(r)


def test_revalidate_keeps_and_refreshes():
    c = conn()
    i = save(c)
    fresh.revalidate(c, checker_with([entry(500, 1)]), CFG, NOW)
    assert status(c, i) == ("active", None, ts(1))


def test_revalidate_expires_when_price_rises():
    c = conn()
    i = save(c)
    assert fresh.revalidate(c, checker_with([entry(650, 1)]), CFG, NOW) == [i]
    assert status(c, i)[:2] == ("expired", "subio")


def test_revalidate_expires_when_not_confirmed_for_a_day():
    c = conn()
    i = save(c, found_at=ts(30))
    fresh.revalidate(c, checker_with([]), CFG, NOW)
    assert status(c, i)[:2] == ("expired", "sin_confirmar")


def test_revalidate_keeps_recent_even_without_new_data():
    c = conn()
    i = save(c, found_at=ts(5))
    fresh.revalidate(c, checker_with([]), CFG, NOW)
    assert status(c, i)[0] == "active"


def test_revalidate_expires_near_departure():
    c = conn()
    i = save(c, departure_at="2026-11-21T10:00:00-06:00")
    fresh.revalidate(c, checker_with([entry(500, 1, dep="2026-11-21")]), CFG, NOW)
    assert status(c, i)[:2] == ("expired", "salida")


def test_old_database_gets_new_columns(tmp_path):
    path = tmp_path / "viejo.sqlite"
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE deals (id INTEGER PRIMARY KEY, slug TEXT UNIQUE, country TEXT,
                   origin TEXT, destination TEXT, price REAL, score REAL,
                   published_at TEXT DEFAULT (datetime('now')), telegram_sent INTEGER DEFAULT 0)""")
    old.execute("INSERT INTO deals (slug, origin, destination, price) VALUES ('a', 'SJO', 'MAD', 480)")
    old.commit()
    old.close()
    c = db.connect(path)
    cols = {r[1] for r in c.execute("PRAGMA table_info(deals)")}
    assert {"status", "found_at", "expire_reason"} <= cols
    assert c.execute("SELECT status FROM deals").fetchone()[0] == "active"  # las existentes quedan activas


# ---------- canales y cupos ----------
@pytest.fixture
def tg(monkeypatch):
    sent, edits = [], []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("TELEGRAM_CHANNEL", "@buscavuelosbaratos")
    monkeypatch.setenv("BVB_VARS", '{"TELEGRAM_CHANNEL_MEXICO": "@buscavuelosbaratos_mx"}')
    monkeypatch.setattr(telegram, "send", lambda text, markup, chat_id=None: sent.append((chat_id, text)) or len(sent))
    monkeypatch.setattr(telegram, "edit", lambda chat, mid, text, markup: edits.append((chat, mid, text)) or True)
    return sent, edits


def test_channels_from_repo_variables(tg):
    assert telegram.country_channels(CFG) == {"mexico": "@buscavuelosbaratos_mx"}
    assert telegram.channel_links(CFG) == {"main": "https://t.me/buscavuelosbaratos",
                                           "mexico": "https://t.me/buscavuelosbaratos_mx"}


def test_publish_quotas_per_channel(tg):
    sent, _ = tg
    c = conn()
    for i in range(4):
        save(c, slug=f"mx{i}", score=0.5 + i / 10, found_at=ts(1))
    save(c, slug="cr", country="costa-rica", origin="SJO", origin_name="San José", score=0.4, found_at=ts(1))
    stats = telegram.publish(c, CFG, NOW)
    assert stats == {"general": 1, "mexico": 2}
    chats = [s[0] for s in sent]
    assert chats.count("@buscavuelosbaratos") == 1 and chats.count("@buscavuelosbaratos_mx") == 2
    assert "San José" in sent[0][1]                 # el general lleva la mejor de toda la región
    assert all("Ciudad de México" in t for ch, t in sent[1:])  # el de México, solo de México
    assert "Precio visto hace 1 h" in sent[0][1]


def test_publish_skips_stale_prices_and_respects_daily_cap(tg):
    sent, _ = tg
    c = conn()
    save(c, slug="vieja", found_at=ts(8))
    assert telegram.publish(c, CFG, NOW)["mexico"] == 0
    save(c, slug="nueva", found_at=ts(1))
    for _ in range(10):
        c.execute("INSERT INTO telegram_posts (deal_id, chat_id, message_id) VALUES (99, '@buscavuelosbaratos_mx', 1)")
    assert telegram.publish(c, CFG, NOW)["mexico"] == 0


def test_quiet_hours(tg):
    c = conn()
    night = NOW + timedelta(hours=14)  # 08:00 UTC = 02:00 en Costa Rica / México
    save(c, found_at=fresh.iso(night - timedelta(hours=1)))
    assert telegram.publish(c, CFG, night) == {"general": "horario sin publicar", "mexico": "horario sin publicar"}


def test_expired_posts_are_edited_once(tg):
    _, edits = tg
    c = conn()
    i = save(c)
    c.execute("INSERT INTO telegram_posts (deal_id, chat_id, message_id) VALUES (?, '@buscavuelosbaratos_mx', 77)", (i,))
    c.execute("UPDATE deals SET status='expired', expire_reason='subio' WHERE id=?", (i,))
    assert telegram.mark_expired_posts(c, CFG) == 1
    assert telegram.mark_expired_posts(c, CFG) == 0
    chat, mid, text = edits[0]
    assert (chat, mid) == ("@buscavuelosbaratos_mx", 77)
    assert "OFERTA TERMINADA" in text and "El precio subió" in text and "<s>" in text


def test_recent_live_verification_prevents_stale_expiry():
    c = conn()
    i = save(c, found_at=ts(30))
    c.execute("UPDATE deals SET verify_status='ok', verified_at=? WHERE id=?", (ts(2), i))
    cfg = {**CFG, "verify": {"web_max_age_hours": 24}}
    fresh.revalidate(c, checker_with([]), cfg, NOW)
    assert status(c, i)[0] == "active"
