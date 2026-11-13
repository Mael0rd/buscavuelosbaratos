import sqlite3
from datetime import date

from bvb import db, explorer, geo, routes


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    c.executescript(routes.SCHEMA)
    return c


def add(c, o, d, name, ctry, price, months, direct=0, km=2000):
    import json
    c.execute("INSERT INTO routes (origin, destination, origin_name, dest_name, dest_country, km, month_prices, "
              "airlines, direct_seen, last_price, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (o, d, "San José", name, ctry, km, json.dumps(months), "[]", direct, price, date.today().isoformat()))


ORIGINS = [{"code": "SJO", "name": "San José", "slug": "san-jose-sjo", "cc": "CR"}]


def test_items_y_paginas_por_presupuesto():
    c = conn()
    add(c, "SJO", "MAD", "Madrid", "España", 720, {"2027-02": 650, "2027-05": 900}, km=8500)
    add(c, "SJO", "MIA", "Miami", "EE. UU.", 260, {"2026-12": 280}, direct=1)
    add(c, "SJO", "XXX", "Lejano", "País raro", 1200, {})
    add(c, "MEX", "MIA", "Miami", "EE. UU.", 200, {})          # otra ciudad: no es de SJO
    deals = [{"origin": "SJO", "destination": "MIA", "slug": "oferta-mia", "price": 249.0}]
    rows = explorer.items(c, {}, ORIGINS, [{"origin": "SJO", "destination": "MAD", "slug": "sjo-mad"}],
                          deals, lambda n, code: code.lower(), lambda code: "")
    by = {x["d"]: x for x in rows}
    assert set(by) == {"MAD", "MIA", "XXX"}
    assert by["MAD"]["p"] == 650 and by["MAD"]["bm"] == "2027-02" and by["MAD"]["cc"] == "es"
    assert by["MAD"]["r"] == "europa" and by["MAD"]["rs"] == "sjo-mad"
    assert by["MIA"]["deal"] == {"s": "oferta-mia", "p": 249} and by["MIA"]["dir"] == 1
    assert by["XXX"]["cc"] == "" and by["XXX"]["r"] == "otros"
    p = explorer.origin_pages(rows, ORIGINS)[0]
    assert [t["label"] for t in p["tiers"]] == ["Menos de $300", "Entre $500 y $800", "Más de $800"]
    assert p["under300"] == 1 and p["under500"] == 1 and not p["indexable"]  # menos de 6 destinos
    assert "Miami" in p["faq"][1][1] and p["cheapest"]["n"] == "Miami"


def test_paises():
    assert geo.country("España") == ("es", "europa")
    assert geo.cc("Peru") == "pe"          # sin tilde también
    assert geo.country("Desconocido") == ("", "otros")
