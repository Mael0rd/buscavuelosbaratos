from datetime import date

from bvb import clima, temporada


def _row(o, d, m, ds="cancun-cun", p=None):
    return {"o": o, "d": d, "n": "Cancún", "c": "México", "cc": "mx", "r": "norteamerica",
            "p": p or min(m.values()), "km": 1000, "m": m, "bm": None, "dir": 1, "rs": f"{o}-{d}".lower(),
            "ds": ds, "img": "", "deal": None}


CL = {"CUN": {"tmax": [28, 29, 30, 31, 32, 32, 33, 33, 32, 30, 29, 28],
              "tmin": [19, 19, 21, 22, 24, 25, 25, 25, 24, 23, 21, 20],
              "rain": [40, 30, 25, 30, 90, 160, 120, 140, 220, 180, 80, 50], "elev": 6}}


def test_build_best_month_and_faq():
    rows = [_row("SJO", "CUN", {"2026-12": 400, "2027-01": 250, "2027-02": 300, "2027-03": 320}),
            _row("BOG", "CUN", {"2026-12": 500, "2027-01": 330, "2027-02": 360}),
            _row("LIM", "XXX", {"2027-01": 300}, ds=None)]  # sin página de destino: fuera
    pages = temporada.build(rows, CL, {"SJO": "San José"}, date(2026, 11, 18))
    assert len(pages) == 1
    t = pages[0]
    assert t["cheap"]["name"] == "enero" and t["dear"]["name"] == "diciembre"
    assert t["indexable"] and t["months"][0]["ym"] == "2026-11" and len(t["months"]) == 12
    assert t["cheap"]["low"] == 250 and t["save"] > 20
    qs = dict(t["faq"])
    assert "enero" in qs["¿Cuál es el mes más barato para volar a Cancún?"]
    assert "de junio a junio" not in qs["¿Cuándo llueve en Cancún?"]
    assert "junio" in qs["¿Cuándo llueve en Cancún?"] and "octubre" in qs["¿Cuándo llueve en Cancún?"]
    assert temporada.chart(t)["bars"][8]["rk"] == "wet"


def test_ranges_wraps_year():
    ms = [{"mi": i, "rk": "wet" if i in (11, 0, 1) else "dry"} for i in range(12)]
    assert temporada._ranges(ms, lambda m: m["rk"] == "wet") == "de diciembre a febrero"
    assert temporada._ranges(ms, lambda m: True) == "todo el año"


def test_month_pages_groups():
    rows = [_row("SJO", "CUN", {"2027-01": 250, "2027-02": 400}), _row("BOG", "CUN", {"2027-01": 300, "2027-02": 420})]
    pages = temporada.build(rows, CL, {}, date(2026, 11, 18))
    jan = temporada.month_pages(pages, date(2026, 11, 18))[0]
    assert jan["slug"] == "en-enero"
    assert [k for k, _, xs in jan["groups"]] == ["beach"]
    assert jan["cheap"] and jan["faq"]


def test_clima_parse_daily_and_altitude():
    days = {f"{y}{m:02d}{d:02d}": None for y in range(2016, 2021) for m in range(1, 13) for d in range(1, 29)}
    pay = {"geometry": {"coordinates": [-74.1, 4.7, 1790]},
           "properties": {"parameter": {"T2M_MAX": {k: 24.0 for k in days}, "T2M_MIN": {k: 14.0 for k in days},
                                        "PRECTOTCORR": {k: 2.0 for k in days}}}}
    bog = clima.parse(pay, 2548)  # Bogotá: más alta que la rejilla → se enfría ~4,9°
    assert 18.5 < bog["tmax"][0] < 19.5 and bog["rain"][0] == 62
    lima = clima.parse(pay, 30)  # más baja que la rejilla (costa): no se calienta
    assert lima["tmax"][0] == 24.0
    pay["properties"]["parameter"]["T2M_MAX"]["20160101"] = -999.0
    assert clima.parse(pay, None)["tmax"][0] == 24.0  # se ignora el día sin dato
