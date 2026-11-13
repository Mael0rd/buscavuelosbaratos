from datetime import date

from bvb import feriados


def test_puentes_colombia_2027():
    h = feriados.holidays_for("CO", 2027)
    assert len(h) == 19 and h[date(2027, 3, 22)].startswith("Día de San José")
    bs = feriados.breaks(h, 2027)
    sj = next(b for b in bs if b["a"] == date(2027, 3, 20))
    assert sj["long"] and sj["n"] == 3 and sj["tip"]["n"] == 9 and sj["tip"]["k"] == 2
    assert sj["tip"]["ask"] == ["mar 23 mar", "mié 24 mar"]
    # Semana Santa queda dentro del puente de 9 días: no se repite
    assert not any(b["a"] == date(2027, 3, 25) for b in bs)


def test_feriado_suelto_y_no_obligatorios_costa_rica():
    h = feriados.holidays_for("CR", 2027)
    assert "(no obligatorio)" in h[date(2027, 8, 2)]
    sep = next(b for b in feriados.breaks(h, 2027) if b["a"] == date(2027, 9, 15))
    assert not sep["long"] and sep["tip"]["n"] == 5 and sep["tip"]["k"] == 2


def test_puerto_rico_en_espanol_y_uruguay_turismo():
    pr = feriados.holidays_for("PR", 2027)
    assert pr[date(2027, 7, 25)] == "Día de la Constitución" and pr[date(2027, 3, 26)] == "Viernes Santo"
    uy = feriados.holidays_for("UY", 2027)
    assert uy[date(2027, 3, 24)] == "Semana de Turismo"


def test_ideas_con_fechas_exactas():
    b = {"trip_a": date(2027, 3, 20), "trip_b": date(2027, 3, 28), "trip_n": 9, "month": "2027-03"}
    rows = {"BOG": [{"d": "CUN", "n": "Cancún", "km": 2400, "m": {"2027-03": 357}},
                    {"d": "MAD", "n": "Madrid", "km": 8000, "m": {"2027-04": 600}}]}
    ideas = feriados._ideas(b, rows, [{"code": "BOG"}], "803749", "feriados_colombia", None)
    assert [x["d"] for x in ideas["BOG"]] == ["CUN"]  # Madrid no tiene precio en marzo
    assert "/search/BOG2003CUN28031" in ideas["BOG"][0]["url"]
    assert ideas["BOG"][0]["url"].endswith("marker=803749.feriados_colombia")
