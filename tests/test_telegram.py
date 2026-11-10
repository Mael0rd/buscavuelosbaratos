from urllib.parse import unquote

from bvb.telegram import build_message

ROW = {
    "slug": "sjo-mad-2027-02-x", "country": "costa-rica",
    "origin": "SJO", "origin_name": "San José", "origin_airport": "SJO",
    "destination": "MAD", "dest_name": "Madrid", "dest_country": "España",
    "destination_airport": "MAD", "price": 480.0, "baseline": 740.0,
    "departure_at": "2027-02-03T17:00:00-06:00", "return_at": "2027-02-17T12:05:00+01:00",
    "transfers": 1, "airline_name": "Iberia", "link": "https://www.aviasales.com/search/x?marker=1",
}


def test_message_format_and_buttons():
    text, markup = build_message(ROW, "https://buscavuelosbaratos.com", "Costa Rica")
    assert "35% MENOS DE LO NORMAL" in text
    assert "<s>$740</s>" in text
    assert "3 de febrero a las 17:00" in text and "17 de febrero a las 12:05" in text
    assert "1 escala · Iberia" in text
    assert "http" not in text  # ningún enlace visible en el texto
    buttons = [b[0] for b in markup["inline_keyboard"]]
    assert buttons[0]["url"] == ROW["link"]
    assert "buscavuelosbaratos.com/oferta/sjo-mad-2027-02-x.html" in unquote(buttons[1]["url"])
    assert buttons[2]["url"].endswith("/pais/costa-rica.html")


def test_no_savings_header_without_history():
    text, _ = build_message({**ROW, "baseline": None}, "https://x.com", "Costa Rica")
    assert "VUELO EN OFERTA" in text and "<s>" not in text


def test_html_is_escaped():
    text, _ = build_message({**ROW, "dest_name": "A<b>&"}, "https://x.com", "Costa Rica")
    assert "A&lt;b&gt;&amp;" in text
