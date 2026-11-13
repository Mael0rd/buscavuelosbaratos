from datetime import datetime, timezone

import pytest

from bvb import instagram
from tests.test_whatsapp import NOW, add, conn

CFG = {
    "site": {"domain": "buscavuelosbaratos.com"},
    "alerts": {"api_base": "https://api.buscavuelosbaratos.com"},
    "countries": {"costa-rica": {"name": "Costa Rica"}},
    "social": {"quiet_hours": [23, 6], "timezone": "America/Costa_Rica",
               "instagram": {"enabled": True, "per_run": 1, "per_day": 2, "min_gap_hours": 0,
                             "username": "buscavuelosbaratos", "hashtags": ["#VuelosBaratos"]}},
    "verify": {"cache_hours": 3}, "freshness": {"max_age_hours": 6},
}
SESSION = ("TOK", {"id": "1", "username": "buscavuelosbaratos"})


@pytest.fixture
def posts(monkeypatch):
    monkeypatch.setattr(instagram, "_online", lambda url: "nueva" not in url)
    out = []
    return out, lambda caption, img: out.append((caption, img)) or f"p{len(out)}"


def test_publica_la_mejor_en_linea_y_verificada(posts):
    out, poster = posts
    c = conn()
    add(c, "nueva", score=0.1)                       # su página aún no está en línea
    add(c, "sin-verificar", score=0.2, verified_h=None, status=None)
    add(c, "buena", score=0.5)
    add(c, "otra", score=0.6)
    assert instagram.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"instagram": 1}
    cap, img = out[0]
    assert img == "https://buscavuelosbaratos.com/og/social-buena.jpg"
    assert cap.startswith("🇨🇷 San José → Madrid por $610 ida y vuelta")
    assert "35% menos" in cap and "1–10 feb · 1 escala" in cap
    assert "@buscavuelosbaratos" in cap and "buscavuelosbaratos.com/oferta/buena" in cap
    assert cap.splitlines()[-1] == "#VuelosBaratos #VuelosCostaRica #Madrid #ViajarAMadrid"
    assert len(cap) <= 2200
    instagram.publish(c, CFG, NOW, session=SESSION, poster=poster)
    assert instagram.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"instagram": 0}  # máximo diario


def test_espaciado_minimo(posts):
    _, poster = posts
    c = conn()
    add(c, "a", score=0.5)
    add(c, "b", score=0.6)
    cfg = {**CFG, "social": {**CFG["social"], "instagram": {**CFG["social"]["instagram"], "min_gap_hours": 3}}}
    assert instagram.publish(c, cfg, NOW, session=SESSION, poster=poster) == {"instagram": 1}
    assert instagram.publish(c, cfg, NOW, session=SESSION, poster=poster) == {"instagram": 0}


def test_de_noche_y_desactivado(posts):
    _, poster = posts
    noche = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)
    assert instagram.publish(conn(), CFG, noche, session=SESSION, poster=poster) == {"instagram": "horario sin publicar"}
    off = {**CFG, "social": {**CFG["social"], "instagram": {"enabled": False}}}
    assert instagram.publish(conn(), off, NOW, session=SESSION, poster=poster) == {}


def test_hashtag():
    assert instagram.hashtag("San José") == "#SanJose"
    assert instagram.hashtag("Viajar a Ciudad de México") == "#ViajarACiudadDeMexico"
    assert instagram.hashtag("¿?") == ""


def test_token_del_secret_se_guarda_y_se_renueva(monkeypatch):
    store = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("INSTAGRAM_TOKEN", "SECRETO")
    monkeypatch.setattr(instagram, "_kv_get", lambda cfg: store.get("v"))
    monkeypatch.setattr(instagram, "_kv_put", lambda cfg, v: store.update(v={"value": v, "updated_at": "2026-11-20 18:00:00"}) or True)
    monkeypatch.setattr(instagram, "_me", lambda t: {"id": "1", "username": "x"} if t in ("SECRETO", "NUEVO") else None)
    monkeypatch.setattr(instagram, "refresh", lambda t: "NUEVO")
    tok, _ = instagram.get_session(CFG, NOW)
    assert tok == "SECRETO" and store["v"]["value"] == "SECRETO"
    store["v"]["updated_at"] = "2026-11-10 18:00:00"
    tok, _ = instagram.get_session(CFG, NOW)
    assert tok == "NUEVO" and store["v"]["value"] == "NUEVO"
    monkeypatch.setattr(instagram, "_me", lambda t: None)
    assert instagram.get_session(CFG, NOW) is None
