import sqlite3

import requests

from bvb import extras
from bvb.refdata import Ref

REF = Ref(cities=[{"code": "MAD", "name": "Madrid", "country_code": "ES", "name_translations": {"en": "Madrid"}},
                  {"code": "MEX", "name": "Ciudad de México", "country_code": "MX",
                   "name_translations": {"en": "Mexico City"}},
                  {"code": "CUR", "name": "Curazao", "country_code": "CW", "name_translations": {"en": "Curacao"}}],
          countries=[{"code": "ES", "name": "España", "name_translations": {"en": "Spain"}},
                     {"code": "MX", "name": "México", "name_translations": {"en": "Mexico"}},
                     {"code": "CW", "name": "Curazao", "name_translations": {"en": "Curaçao"}}],
          airlines=[])

CFG = {"extras": {"enabled": True, "trs": 598846, "max_per_page": 2, "pause_seconds": 0,
                  "services": {
                      "esim": {"icon": "📶", "title": "Internet en {country}", "button": "eSIM {country}",
                               "variants": [{"id": "yesim", "weight": 1,
                                             "urls": ["https://yesim.app/country/{country_slug}/",
                                                      "https://yesim.app/"]},
                                            {"id": "saily", "weight": 1,
                                             "urls": ["https://saily.com/esim-{country_slug}/",
                                                      "https://saily.com/"]}]},
                      "tours": {"title": "Qué hacer en {city}",
                                "variants": [{"id": "klook", "urls": ["https://www.klook.com/search/?query={city_en}",
                                                                      "https://www.klook.com/"]}]},
                      "autos": {"title": "Auto", "variants": [{"id": "eb", "urls": ["https://eb.com/"]}]}}}}


class Resp:
    def __init__(self, url, status=200, data=None):
        self.url, self.status_code, self._data = url, status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def close(self):
        pass


class FakeHTTP:
    """GET: 404 para las URLs en `missing`, redirección a la portada para `soft`. POST: API de enlaces."""
    def __init__(self, missing=(), soft=(), api_fail=False):
        self.missing, self.soft, self.api_fail = set(missing), set(soft), api_fail
        self.gets, self.posts = [], []

    def get(self, url, **kw):
        self.gets.append(url)
        if url in self.missing:
            return Resp(url, 404)
        if url in self.soft:
            return Resp("https://" + url.split("/")[2] + "/", 200)
        return Resp(url)

    def post(self, url, json=None, **kw):
        self.posts.append(json)
        if self.api_fail:
            return Resp(url, 500)
        links = [{"url": x["url"], "code": "success", "partner_url": f"https://tp.st/{x['sub_id']}"}
                 for x in json["links"]]
        return Resp(url, data={"result": {"links": links}, "code": "success"})


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


def make(monkeypatch, http, c=None):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "803749")
    monkeypatch.delenv("BVB_MOCK", raising=False)
    return extras.Extras(c or conn(), CFG, REF, session=http)


def test_slugify_and_dest_info():
    assert extras.slugify("United States") == "united-states"
    assert extras.slugify("Curaçao") == "curacao"
    i = extras.dest_info("MEX", REF)
    assert (i["city"], i["country"], i["country_slug"], i["city_en"]) == (
        "Ciudad de México", "México", "mexico", "Mexico%20City")
    assert extras.dest_info("MEX", REF, {"MX": "mx"})["country_slug"] == "mx"


def test_variant_is_stable_and_respects_weights():
    vs = [{"id": "a", "weight": 3}, {"id": "b", "weight": 1}]
    picks = [extras.pick_variant(vs, f"D{i}:esim")["id"] for i in range(400)]
    assert picks == [extras.pick_variant(vs, f"D{i}:esim")["id"] for i in range(400)]
    assert 0.6 < picks.count("a") / 400 < 0.9
    assert extras.pick_variant([{"id": "x", "weight": 0}], "k") is None


def test_blocks_links_and_subids(monkeypatch):
    http = FakeHTTP()
    plan = make(monkeypatch, http).prepare(["MAD"])
    blocks = plan["MAD"]
    assert [b["service"] for b in blocks] == ["esim", "tours"]  # max_per_page = 2
    esim = blocks[0]
    assert esim["title"] == "Internet en España" and esim["brand"] in ("yesim", "saily")
    assert "spain" in esim["url"]
    assert esim["links"] == {"oferta": f"https://tp.st/oferta_{esim['brand']}",
                             "ruta": f"https://tp.st/ruta_{esim['brand']}"}
    body = http.posts[0]
    assert body["trs"] == 598846 and body["marker"] == 803749 and len(body["links"]) == 4


def test_missing_page_falls_back_and_is_cached(monkeypatch):
    c = conn()
    missing = {"https://yesim.app/country/curacao/", "https://saily.com/esim-curacao/"}
    http = FakeHTTP(missing=missing, soft={"https://www.klook.com/search/?query=Curacao"})
    plan = make(monkeypatch, http, c).prepare(["CUR"])
    urls = {b["service"]: b["url"] for b in plan["CUR"]}
    assert urls["esim"] in ("https://yesim.app/", "https://saily.com/")
    assert urls["tours"] == "https://www.klook.com/"  # redirigía a la portada: no existe
    n = len(http.gets)
    http2 = FakeHTTP()
    make(monkeypatch, http2, c).prepare(["CUR"])
    assert http2.gets == [] and http2.posts == [] and n > 0  # todo salió de la caché


def test_api_down_uses_direct_links(monkeypatch):
    plan = make(monkeypatch, FakeHTTP(api_fail=True)).prepare(["MAD"])
    b = plan["MAD"][0]
    assert b["links"]["oferta"] == b["url"]  # Drive lo convierte en el navegador


def test_offline_or_disabled(monkeypatch):
    monkeypatch.setenv("BVB_MOCK", "1")
    http = FakeHTTP()
    plan = extras.Extras(conn(), CFG, REF, session=http).prepare(["MAD"])
    assert http.gets == [] and http.posts == []
    assert plan["MAD"][0]["url"] in ("https://yesim.app/", "https://saily.com/")
    assert extras.Extras(conn(), {"extras": {"enabled": False}}, REF, session=http).prepare(["MAD"]) == {}


def test_check_budget(monkeypatch):
    ex = make(monkeypatch, FakeHTTP())
    ex.checks_left = 0
    plan = ex.prepare(["MAD"])
    assert plan["MAD"][0]["url"] in ("https://yesim.app/", "https://saily.com/")


def test_brand_limited_to_its_regions(monkeypatch):
    cfg = {"extras": {"enabled": True, "trs": 1, "pause_seconds": 0,
                      "regions": {"asia": ["JP"], "europa": ["ES"]},
                      "services": {"tours": {"title": "t", "variants": [
                          {"id": "klook", "regions": ["asia"], "urls": ["https://k.com/"]},
                          {"id": "tiqets", "regions": ["europa"], "urls": ["https://t.com/"]},
                          {"id": "civ", "weight": 0, "urls": ["https://c.com/"]}]}}}}
    monkeypatch.setenv("BVB_MOCK", "1")
    ref = Ref(cities=[{"code": "MAD", "name": "Madrid", "country_code": "ES"},
                      {"code": "TYO", "name": "Tokio", "country_code": "JP"},
                      {"code": "CUN", "name": "Cancún", "country_code": "MX"}],
              countries=[], airlines=[])
    plan = extras.Extras(conn(), cfg, ref, session=FakeHTTP()).prepare(["MAD", "TYO", "CUN"])
    assert [b["brand"] for b in plan["MAD"]] == ["tiqets"]
    assert [b["brand"] for b in plan["TYO"]] == ["klook"]
    assert plan["CUN"] == []  # sin marca con buena oferta: no se muestra el bloque


def test_direct_program_skips_api(monkeypatch):
    cfg = {"extras": {"enabled": True, "trs": 1, "pause_seconds": 0, "services": {"tours": {
        "title": "t", "variants": [{"id": "civitatis", "direct_param": "aid=123",
                                    "urls": ["https://www.civitatis.com/es/{city_slug_es}/", "https://c.com/"]}]}}}}
    http = FakeHTTP()
    plan = make(monkeypatch, http).__class__(conn(), cfg, REF, session=http).prepare(["MEX"])
    b = plan["MEX"][0]
    assert b["url"] == "https://www.civitatis.com/es/ciudad-de-mexico/?aid=123"
    assert b["links"]["oferta"] == b["url"] and http.posts == []
