from datetime import datetime, timezone

import pytest

from bvb import threads
from tests.test_whatsapp import NOW, add, conn

CFG = {
    "site": {"domain": "buscavuelosbaratos.com"},
    "alerts": {"api_base": "https://api.buscavuelosbaratos.com"},
    "social": {"quiet_hours": [23, 6], "timezone": "America/Costa_Rica",
               "threads": {"enabled": True, "per_run": 1, "per_day": 2, "topic": "Vuelos baratos",
                           "topics": {"mexico": "Vuelos baratos México"}}},
    "verify": {"cache_hours": 3}, "freshness": {"max_age_hours": 6},
}
SESSION = ("TOK", {"id": "1", "username": "buscavuelosbaratos"})


@pytest.fixture
def posts(monkeypatch):
    monkeypatch.setattr(threads, "_online", lambda url: "nueva" not in url)  # la oferta nueva aún no está en línea
    out = []
    return out, lambda text, img, topic: out.append((text, img, topic)) or f"p{len(out)}"


def test_publica_la_mejor_en_linea_y_verificada(posts):
    out, poster = posts
    c = conn()
    add(c, "nueva", score=0.1)                       # mejor, pero su página aún no se subió
    add(c, "sin-verificar", score=0.2, verified_h=None, status=None)
    add(c, "buena", score=0.5)
    add(c, "mx", country="mexico", score=0.6)
    assert threads.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"threads": 1}
    text, img, topic = out[0]
    assert img == "https://buscavuelosbaratos.com/og/oferta-buena.jpg" and topic == "Vuelos baratos"
    assert text.endswith("/oferta/buena?src=threads") and "$610" in text and len(text) <= 500
    threads.publish(c, CFG, NOW, session=SESSION, poster=poster)
    assert out[1][2] == "Vuelos baratos México"          # tema por país
    assert threads.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"threads": 0}  # máximo diario


def test_de_noche_y_desactivado(posts):
    _, poster = posts
    noche = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)
    assert threads.publish(conn(), CFG, noche, session=SESSION, poster=poster) == {"threads": "horario sin publicar"}
    off = {**CFG, "social": {**CFG["social"], "threads": {"enabled": False}}}
    assert threads.publish(conn(), off, NOW, session=SESSION, poster=poster) == {}


def test_token_del_secret_se_guarda_y_se_renueva(monkeypatch):
    store = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:A")
    monkeypatch.setenv("THREADS_TOKEN", "SECRETO")
    monkeypatch.setattr(threads, "_kv_get", lambda cfg: store.get("v"))
    monkeypatch.setattr(threads, "_kv_put", lambda cfg, v: store.update(v={"value": v, "updated_at": "2026-11-20 18:00:00"}) or True)
    monkeypatch.setattr(threads, "_me", lambda t: {"id": "1", "username": "x"} if t in ("SECRETO", "NUEVO") else None)
    monkeypatch.setattr(threads, "refresh", lambda t: "NUEVO")
    tok, _ = threads.get_session(CFG, NOW)
    assert tok == "SECRETO" and store["v"]["value"] == "SECRETO"     # primera vez: se guarda, no se renueva
    store["v"]["updated_at"] = "2026-11-10 18:00:00"                  # 10 días después: se renueva
    tok, _ = threads.get_session(CFG, NOW)
    assert tok == "NUEVO" and store["v"]["value"] == "NUEVO"
    monkeypatch.setattr(threads, "_me", lambda t: None)               # vencido
    assert threads.get_session(CFG, NOW) is None
