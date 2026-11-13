import sqlite3
from datetime import date

from bvb import hubs, ogimage
from bvb.routes import SCHEMA
from bvb.site import dest_slug

CFG = {"countries": {"costa-rica": {"name": "Costa Rica", "cc": "CR", "origins": ["SJO", "LIR"]},
                     "mexico": {"name": "México", "cc": "MX", "origins": ["MEX"]}},
       "origin_names": {"SJO": "San José", "LIR": "Liberia", "MEX": "Ciudad de México"}}


def db(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    today = date.today().isoformat()
    for o, d, dn, price, direct in rows:
        conn.execute("""INSERT INTO routes (origin, destination, origin_name, dest_name, dest_country,
                        last_price, direct_seen, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
                     (o, d, CFG["origin_names"][o], dn, "X", price, direct, today))
    conn.execute("INSERT INTO routes (origin, destination, origin_name, dest_name, last_price, updated_at) "
                 "VALUES ('SJO','OLD','San José','Vieja',50,'2020-01-01')")  # vieja: no cuenta
    return conn


def test_origin_hubs_all_cities_sorted_and_recent_only():
    conn = db([("SJO", "MAD", "Madrid", 700, 0), ("SJO", "BOG", "Bogotá", 150, 1), ("MEX", "MAD", "Madrid", 650, 1)])
    origins, dests = hubs.build(conn, CFG, [], [], dest_slug)
    by = {o["code"]: o for o in origins}
    assert set(by) == {"SJO", "LIR", "MEX"}                # todas, aunque no tengan datos
    assert [r["dest_name"] for r in by["SJO"]["dests"]] == ["Bogotá", "Madrid"]
    assert by["SJO"]["cheapest"]["destination"] == "BOG" and by["SJO"]["direct"] == ["Bogotá"]
    assert by["SJO"]["slug"] == "san-jose-sjo" and by["LIR"]["dests"] == []
    assert "Bogotá" in by["SJO"]["faq"][0][1]
    # Madrid solo tiene 2 ciudades, sin ofertas ni historial: no se publica (página pobre)
    assert dests == []


def test_dest_hub_with_deal_or_enough_origins():
    conn = db([("SJO", "MAD", "Madrid", 700, 0), ("MEX", "MAD", "Madrid", 650, 1), ("LIR", "MAD", "Madrid", 720, 0)])
    deal = {"origin": "SJO", "destination": "MIA", "dest_name": "Miami", "dest_country": "EE. UU.", "price": 180}
    _, dests = hubs.build(conn, CFG, [deal], [], dest_slug)
    by = {d["destination"]: d for d in dests}
    assert set(by) == {"MAD", "MIA"}
    assert by["MAD"]["cheapest"]["origin"] == "MEX" and by["MAD"]["low"] == 650
    assert by["MAD"]["dest_slug"] == "madrid-mad" and by["MAD"]["origins"][0]["origin_slug"] == "ciudad-de-mexico-mex"
    assert by["MIA"]["deals"] == [deal] and by["MIA"]["low"] == 180


def test_og_images(tmp_path):
    d = {"origin_name": "San José", "origin": "SJO", "dest_name": "Una ciudad con un nombre larguísimo de verdad",
         "dest_country": "País", "price": 321, "departure_at": "2027-01-05", "return_at": "2027-01-12",
         "transfers": 1, "verify_status": "ok", "tone": 3}
    ogimage.deal_image(d, "cr", tmp_path / "a.jpg")
    ogimage.page_image("Vuelos baratos desde Santiago de los Caballeros", "sub", tmp_path / "b.jpg", cc="do", kicker="RD")
    from PIL import Image
    for f in ("a.jpg", "b.jpg"):
        assert Image.open(tmp_path / f).size == (1200, 630)


def test_dest_pages_never_disappear():
    conn = db([("SJO", "MAD", "Madrid", 700, 0), ("MEX", "MAD", "Madrid", 650, 1), ("LIR", "MAD", "Madrid", 720, 0)])
    deal = {"origin": "SJO", "destination": "MIA", "dest_name": "Miami", "dest_country": "EE. UU.", "price": 180}
    hubs.build(conn, CFG, [deal], [], dest_slug)
    # Al día siguiente: Miami ya no tiene oferta y Madrid se ve desde una sola ciudad
    conn.execute("DELETE FROM routes WHERE origin IN ('MEX', 'LIR')")
    _, dests = hubs.build(conn, CFG, [], [], dest_slug)
    by = {d["destination"]: d for d in dests}
    assert set(by) == {"MAD", "MIA"}                      # las dos páginas siguen existiendo
    assert by["MIA"]["stale"] and by["MIA"]["dest_slug"] == "miami-mia" and by["MIA"]["low"] == 180
    assert not by["MAD"]["stale"] and by["MAD"]["low"] == 700 and len(by["MAD"]["origins"]) == 1
    assert dests[-1]["destination"] == "MIA"              # las que no tienen datos van al final
