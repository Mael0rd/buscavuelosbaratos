from bvb import facebook, instagram, meta
from tests.test_whatsapp import NOW, add, conn

CFG = {
    "site": {"domain": "buscavuelosbaratos.com"},
    "alerts": {"api_base": "https://api.buscavuelosbaratos.com"},
    "countries": {"costa-rica": {"name": "Costa Rica"}},
    "social": {"quiet_hours": [23, 6], "timezone": "America/Costa_Rica",
               "facebook": {"enabled": True, "per_run": 1, "per_day": 2, "min_gap_hours": 0},
               "instagram": {"enabled": True, "username": "buscavuelosbaratos"}},
    "verify": {"cache_hours": 3}, "freshness": {"max_age_hours": 6},
}
SESSION = {"token": "SYS", "page_id": "10", "page_name": "Busca Vuelos Baratos", "page_token": "PAGE",
           "ig_id": "178", "ig_username": "buscavuelosbaratos"}


def test_publica_foto_con_enlace_tocable(monkeypatch):
    monkeypatch.setattr(facebook, "_online", lambda url: True)
    out = []
    poster = lambda text, img: out.append((text, img)) or f"p{len(out)}"
    c = conn()
    add(c, "buena", score=0.5)
    add(c, "otra", score=0.6)
    assert facebook.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"facebook": 1}
    text, img = out[0]
    assert img == "https://buscavuelosbaratos.com/og/social-buena.jpg"
    assert "https://buscavuelosbaratos.com/oferta/buena?src=facebook" in text
    assert text.startswith("🇨🇷 San José → Madrid por $610 ida y vuelta")
    facebook.publish(c, CFG, NOW, session=SESSION, poster=poster)
    assert facebook.publish(c, CFG, NOW, session=SESSION, poster=poster) == {"facebook": 0}  # máximo diario


def test_sin_token_se_omite(monkeypatch):
    monkeypatch.delenv("META_SYSTEM_TOKEN", raising=False)
    assert facebook.publish(conn(), CFG, NOW) == {}


def test_meta_session_lee_pagina_e_instagram(monkeypatch):
    class R:
        ok = True
        def json(self):
            return {"data": [{"id": "9", "name": "Otra página", "access_token": "X"},
                             {"id": "10", "name": "Busca Vuelos Baratos", "username": "buscavuelosbaratos",
                              "access_token": "PAGE",
                              "instagram_business_account": {"id": "178", "username": "buscavuelosbaratos"}}]}
    monkeypatch.setenv("META_SYSTEM_TOKEN", "SYS")
    monkeypatch.setattr(meta, "_cache", {})
    monkeypatch.setattr(meta.requests, "get", lambda *a, **k: R())
    s = meta.session("buscavuelosbaratos")
    assert s["page_id"] == "10" and s["page_token"] == "PAGE" and s["ig_id"] == "178"
    # Instagram usa el usuario del sistema por graph.facebook.com, sin renovar nada
    tok, me = instagram.get_session(CFG, NOW)
    assert tok == "SYS" and me["id"] == "178" and me["graph"] == meta.GRAPH
