import sqlite3

from bvb import alerts
from bvb.db import SCHEMA
from bvb.refdata import Ref
from tests.test_deals import CFG as DEALS_CFG, REF, TODAY, OTHER_MONTHS, best, t

CFG = {**DEALS_CFG,
       "site": {"domain": "buscavuelosbaratos.com"},
       "alerts": {"api_base": "https://api.x", "repeat_days": 7, "repeat_extra_drop": 0.10,
                  "max_emails_per_run": 80, "mail_from": "x <a@b.c>"}}


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def test_alert_sent_once_then_only_if_cheaper(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts.telegram, "send", lambda text, markup, chat_id=None: sent.append((chat_id, text)) or True)
    c = conn()
    subs = [{"id": 1, "channel": "telegram", "address": "555", "origin": "SJO",
             "destination": "MIA", "dest_name": "Miami", "token": "tk"}]
    st = alerts.process(c, best(t(190), *OTHER_MONTHS), CFG, REF, TODAY, subs)
    assert st["telegram"] == 1 and sent[0][0] == "555"
    assert "TU ALERTA: San José → Miami" in sent[0][1]
    alerts.process(c, best(t(185), *OTHER_MONTHS), CFG, REF, TODAY, subs)  # casi igual: no repite
    assert len(sent) == 1
    alerts.process(c, best(t(160), *OTHER_MONTHS), CFG, REF, TODAY, subs)  # bajó >10%: avisa
    assert len(sent) == 2


def test_no_alert_when_not_a_deal(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts.telegram, "send", lambda *a, **k: sent.append(a) or True)
    subs = [{"id": 1, "channel": "telegram", "address": "5", "origin": "SJO",
             "destination": "MIA", "dest_name": "Miami", "token": "tk"}]
    alerts.process(conn(), best(t(290), *OTHER_MONTHS), CFG, REF, TODAY, subs)
    assert sent == []


def test_email_alert_has_unsubscribe(monkeypatch):
    got = {}
    monkeypatch.setenv("RESEND_API_KEY", "re_x")
    monkeypatch.setattr(alerts, "send_email",
                        lambda to, subject, body, unsub, cfg: got.update(to=to, subject=subject, body=body, unsub=unsub) or True)
    subs = [{"id": 2, "channel": "email", "address": "ana@example.com", "origin": "SJO",
             "destination": "MIA", "dest_name": "Miami", "token": "abc"}]
    st = alerts.process(conn(), best(t(190), *OTHER_MONTHS), CFG, REF, TODAY, subs)
    assert st["email"] == 1 and got["to"] == "ana@example.com"
    assert got["unsub"] == "https://api.x/api/unsubscribe?t=abc" and got["unsub"] in got["body"]
    assert "San José → Miami por $190" in got["subject"]


def test_admin_token_matches_worker(monkeypatch):
    # Mismo valor que calcula el Worker: sha256("bvb-admin:" + token)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    import hashlib
    assert alerts.admin_token() == hashlib.sha256(b"bvb-admin:123:ABC").hexdigest()
