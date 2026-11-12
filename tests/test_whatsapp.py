import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from bvb import db, fresh, telegram, whatsapp
from bvb.fetch import with_subid

NOW = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)  # 12:00 en Costa Rica
CFG = {
    "site": {"domain": "buscavuelosbaratos.com"},
    "countries": {"costa-rica": {"name": "Costa Rica", "flag": "🇨🇷", "cc": "CR", "origins": ["SJO"]},
                  "mexico": {"name": "México", "flag": "🇲🇽", "cc": "MX", "origins": ["MEX"]}},
    "timezones": {"costa-rica": ["America/Costa_Rica"], "mexico": ["America/Mexico_City"]},
    "social": {"quiet_hours": [23, 6], "timezone": "America/Costa_Rica",
               "regions": {"centroamerica": {"name": "Centroamérica", "countries": ["costa-rica"],
                                             "whatsapp": {"url": "https://whatsapp.com/channel/X",
                                                          "per_run": 1, "per_day": 2}}}},
    "verify": {"cache_hours": 3},
    "freshness": {"max_age_hours": 6},
}


def ts(h):
    return fresh.iso(NOW - timedelta(hours=h))


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


def add(c, slug, country="costa-rica", score=0.6, verified_h=1.0, status="ok", found_h=2):
    c.execute("""INSERT INTO deals (slug, country, flag, origin, origin_name, destination, dest_name, dest_country,
                 price, baseline, score, departure_at, return_at, transfers, link, found_at,
                 verify_status, verified_at, live_price)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (slug, country, "🇨🇷", "SJO", "San José", "MAD", "Madrid", "España", 620, 950, score,
               "2027-02-01T10:00:00Z", "2027-02-10T10:00:00Z", 1, "https://www.aviasales.com/s?marker=803749",
               ts(found_h), status, ts(verified_h) if verified_h is not None else None, 610))
    c.commit()


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("BVB_VARS", '{"WHATSAPP_RELAY_CHAT": "12345"}')
    monkeypatch.setattr(telegram, "send", lambda text, markup, chat_id=None: out.append((chat_id, text, markup)) or 1)
    return out


def test_texto_para_whatsapp():
    c = conn()
    add(c, "sjo-mad")
    d = dict(c.execute("SELECT * FROM deals").fetchone())
    t = whatsapp.build_text(d, "https://buscavuelosbaratos.com", "wa_centroamerica", NOW)
    assert "*San José → Madrid, España*" in t and "*$610 USD*" in t and "~$950~" in t
    assert t.endswith("https://buscavuelosbaratos.com/oferta/sjo-mad?src=wa_centroamerica")


def test_manda_la_mejor_verificada_de_la_region_al_administrador(sent):
    c = conn()
    add(c, "peor", score=0.8)
    add(c, "mejor", score=0.5)
    add(c, "sin-verificar", score=0.1, verified_h=None, status=None)
    add(c, "verificada-hace-mucho", score=0.2, verified_h=5)
    add(c, "de-mexico", country="mexico", score=0.1)
    assert whatsapp.relay(c, CFG, NOW) == {"centroamerica": 1}
    chat, text, markup = sent[0]
    assert chat == "12345" and "/oferta/mejor?src=wa_centroamerica" in text and "<pre>" in text
    assert markup["inline_keyboard"][0][0]["url"] == "https://whatsapp.com/channel/X"
    # siguiente corrida: no repite y respeta el máximo diario (2)
    whatsapp.relay(c, CFG, NOW)
    assert "/oferta/peor?" in sent[1][1]
    assert whatsapp.relay(c, CFG, NOW) == {"centroamerica": 0} and len(sent) == 2


def test_de_noche_no_manda(sent):
    c = conn()
    add(c, "x")
    noche = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)  # 00:00 en Costa Rica
    assert whatsapp.relay(c, CFG, noche) == {"centroamerica": "horario sin publicar"} and not sent


def test_sin_variable_no_hace_nada(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("BVB_VARS", "{}")
    assert whatsapp.relay(conn(), CFG, NOW) == {}


def test_enlaces_para_la_web():
    assert whatsapp.wa_links(CFG) == {"costa-rica": {"url": "https://whatsapp.com/channel/X", "name": "Centroamérica"}}
    assert with_subid("https://a.com/?marker=803749.web_oferta", "wa_centroamerica").endswith(".wa_centroamerica")
