from bvb import aerolineas


def test_cabe_girando_la_pieza():
    assert aerolineas.fits((35, 55, 25), (55, 35, 25))
    assert not aerolineas.fits((56, 35, 25), (55, 35, 25))
    assert not aerolineas.fits((40, 30, 20), None)


def test_datos_completos_y_rutas():
    for a in aerolineas.AIRLINES:
        assert a["carry"]["dims"] and a["fares"] and a["official"].startswith("https://")
        assert all(len(f) == 5 for f in a["fares"])
    rp = [{"slug": "sjo-pty", "typical": 250, "airlines": ["Copa Airlines"]},
          {"slug": "sjo-mia", "typical": 300, "airlines": ["Avianca"]}]
    by = {a["slug"]: a for a in aerolineas.build(rp)}
    assert [r["slug"] for r in by["copa"]["routes"]] == ["sjo-pty"]
    assert by["avianca"]["cheapest"][0] == "Light" and by["avianca"]["cheapest"][2]
    assert "equipaje de mano" in by["copa"]["faq"][0][1]
