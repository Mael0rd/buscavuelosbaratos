from bvb import requisitos, visas


def _rows(cc, c, n):
    return [{"o": f"O{i}", "d": f"D{i}", "n": f"Ciudad {i}", "c": c, "cc": cc.lower(), "r": "caribe", "p": 200 + i,
             "km": 1000, "m": {}, "bm": None, "dir": 0, "rs": None, "ds": None, "img": "", "deal": None}
            for i in range(n)]


def _pp(cid, iso, name):
    return {"id": cid, "passport": iso, "cc": iso.lower(), "name": name, "demonym": name}


PPS = [_pp("costa-rica", "CR", "Costa Rica"), _pp("mexico", "MX", "México"), _pp("colombia", "CO", "Colombia"),
       _pp("peru", "PE", "Perú"), _pp("chile", "CL", "Chile"), _pp("argentina", "AR", "Argentina")]


def test_dominicana_page_has_eticket_and_visa_table():
    pages = requisitos.build(_rows("DO", "República Dominicana", 6), PPS, [], {})
    assert len(pages) == 1
    p = pages[0]
    assert p["slug"] == "republica-dominicana" and p["url"] == "/requisitos/republica-dominicana"
    assert p["forms"][0][0] == "e-Ticket" and p["forms"][0][3]
    assert len(p["passports"]) == 6 and p["indexable"]
    assert any("e-Ticket" in a for _, a in p["faq"])


def test_few_routes_no_page_unless_curated():
    assert requisitos.build(_rows("JM", "Jamaica", 3), PPS, [], {}) == []
    assert requisitos.build(_rows("AW", "Aruba", 2), PPS, [], {})[0]["forms"][0][0].startswith("ED Card")


def test_schengen_and_yellow_fever():
    es = requisitos.build(_rows("ES", "España", 6), PPS, [], {})[0]
    assert es["schengen"] and any(f[0].startswith("EES") for f in es["forms"])
    co = requisitos.build(_rows("CO", "Colombia", 6), PPS, [], {})[0]
    assert co["yf_risk"] and co["cr_exit_yf"]
    assert next(x for x in co["passports"] if x["id"] == "colombia")["key"] == "own"


def test_nicaragua_override():
    data, _ = visas.load()
    assert data["MX"]["NI"]["status"] == "visa required"
    assert data["CR"]["NI"]["status"] == "visa free"
    assert "consultada" in visas._note("MX", "NI", "visa")
