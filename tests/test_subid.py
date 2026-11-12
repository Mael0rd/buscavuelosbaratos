from bvb.fetch import affiliate_link, with_subid
from bvb import telegram


def test_agrega_subid_al_marker():
    url = affiliate_link("/search/SJO0112MAD08121?t=abc", "803749")
    assert with_subid(url, "tg_general").endswith("marker=803749.tg_general")


def test_reemplaza_subid_y_limpia_caracteres():
    url = "https://www.aviasales.com/search/X?marker=803749.viejo&x=1"
    assert with_subid(url, "web_oferta_el-salvador") == \
        "https://www.aviasales.com/search/X?marker=803749.web_oferta_el_salvador&x=1"


def test_sin_marker_o_sin_subid_no_cambia():
    assert with_subid("https://x.com/?a=1", "tg") == "https://x.com/?a=1"
    assert with_subid("https://x.com/?marker=1", "") == "https://x.com/?marker=1"
    assert with_subid("", "tg") == ""


def test_boton_de_telegram_lleva_subid():
    row = {"price": 300, "baseline": 400, "dest_name": "Madrid", "origin_name": "San José",
           "origin": "SJO", "destination": "MAD", "departure_at": "2027-02-01T10:00:00Z",
           "return_at": "2027-02-10T10:00:00Z", "transfers": 0, "slug": "x", "country": "costa-rica",
           "link": "https://www.aviasales.com/search/X?marker=803749"}
    _, markup = telegram.build_message(row, "https://buscavuelosbaratos.com", "Costa Rica", subid="tg_costa-rica")
    assert markup["inline_keyboard"][0][0]["url"].endswith("marker=803749.tg_costa_rica")
