from bvb import countrypage


def route(dest, typical, origin="San José", month=("marzo 2027", 300), low=None):
    return {"destination": dest, "dest_name": dest.title(), "dest_country": "X", "origin_name": origin,
            "typical": typical, "low": low or typical - 20, "cheapest_month": month, "slug": dest.lower()}


def test_summary_with_data():
    c = {"name": "Costa Rica", "term": "tiquetes aéreos", "deals": [],
         "routes": [route("MIA", 200), route("MIA", 180, "Liberia"), route("MAD", 700, month=("abril 2027", 650)),
                    route("BOG", 150)],
         "cities": [{"name": "San José", "code": "SJO", "n_dests": 3}, {"name": "Liberia", "code": "LIR", "n_dests": 1}]}
    countrypage.summarize(c)
    assert [r["destination"] for r in c["top_dests"]] == ["BOG", "MIA", "MAD"]
    assert c["top_dests"][1]["origin_name"] == "Liberia"  # la salida más barata por destino
    assert c["best_month"] == {"label": "marzo 2027", "n": 3, "total": 4}
    qs = [q for q, _ in c["faq"]]
    assert "¿Cuánto cuesta un vuelo de Costa Rica a Mia?" in qs and "¿Cuánto cuesta un vuelo de Costa Rica a Mad?" in qs
    assert any("San José (SJO) y Liberia (LIR)" in a for _, a in c["faq"])
    assert "tiquetes aéreos" in c["seo_desc"] and "Bog desde $130" in c["seo_desc"]


def test_summary_without_data_still_has_text():
    c = countrypage.summarize({"name": "Cuba", "term": "pasajes", "routes": [], "cities": [], "deals": []})
    assert c["top_dests"] == [] and c["best_month"] is None
    assert len(c["faq"]) == 1 and "pasajes baratos desde Cuba" in c["faq"][0][0]
    assert c["seo_desc"].startswith("Vuelos y pasajes baratos desde Cuba")
