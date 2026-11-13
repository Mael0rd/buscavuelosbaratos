from bvb import visas

CFG = {"countries": {"costa-rica": {"name": "Costa Rica", "cc": "CR", "origins": ["SJO"]},
                     "puerto-rico": {"name": "Puerto Rico", "cc": "PR", "origins": ["SJU"]}}}
ORIGINS = [{"code": "SJO", "country": "costa-rica"}, {"code": "SJU", "country": "puerto-rico"}]


def row(o, d, name, ctry, cc, p):
    return {"o": o, "d": d, "n": name, "c": ctry, "cc": cc, "p": p, "r": "x", "rs": None, "ds": d.lower(),
            "img": "", "deal": None, "bm": None, "dir": 0, "km": 1000, "m": {}}


ROWS = [row("SJO", "MAD", "Madrid", "España", "es", 700), row("SJO", "NYC", "Nueva York", "EE. UU.", "us", 400),
        row("SJO", "SJU", "San Juan", "Puerto Rico", "pr", 300), row("SJO", "CUR", "Willemstad", "Curazao", "cw", 500),
        row("SJU", "MIA", "Miami", "EE. UU.", "us", 150), row("SJU", "MAD", "Madrid", "España", "es", 600)]


def test_paginas_por_pasaporte_y_destino(monkeypatch):
    monkeypatch.setattr(visas, "_download", lambda name: None)  # usa la copia del repositorio
    pps, pairs, updated = visas.build(CFG, ROWS, ORIGINS)
    cr = next(p for p in pps if p["passport"] == "CR")
    assert cr["slug"] == "costarricenses" and updated == "2026-02-17"
    by = {(x["pp"]["passport"], x["dest"]): x for x in pairs}
    assert by[("CR", "ES")]["visa"]["key"] == "free" and "ETIAS" in by[("CR", "ES")]["note"]
    assert by[("CR", "US")]["visa"]["key"] == "visa" and "B1/B2" in by[("CR", "US")]["note"]
    assert by[("CR", "PR")]["visa"]["key"] == "visa"          # Puerto Rico: reglas de EE. UU.
    assert ("CR", "CW") not in by                               # sin datos: no se inventa
    assert ("US", "US") not in by and ("US", "ES") in by        # Puerto Rico → EE. UU. es nacional
    assert [x["n"] for x in cr["cheap"]] == ["Madrid"]          # sin visa y con vuelo
    assert by[("CR", "ES")]["url"] == "/visas/costarricenses/espana"


def test_texto_del_estado():
    e = visas.entry({"status": "visa free", "days": 90})
    assert e["key"] == "free" and e["label"] == "No necesitas visa · hasta 90 días"
    assert visas.entry(None)["key"] == "visa"
