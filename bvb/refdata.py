"""Datos de referencia de Travelpayouts (ciudades, países, aerolíneas).

Se descargan de api.travelpayouts.com/data (no requieren token) y se guardan
en data/ref durante 7 días. Se prefiere la versión en español.
"""
import json
import time

import requests

from .config import REF_DIR, ROOT, env

URL = "https://api.travelpayouts.com/data/{loc}/{kind}.json"
KINDS = ("cities", "countries", "airlines")
MAX_AGE = 7 * 86400


def _name(rec: dict) -> str:
    tr = rec.get("name_translations") or {}
    return tr.get("es") or rec.get("name") or tr.get("en") or rec.get("code", "")


def _download(kind: str) -> list:
    path = REF_DIR / f"{kind}.json"
    if path.exists() and time.time() - path.stat().st_mtime < MAX_AGE:
        return json.loads(path.read_text(encoding="utf-8"))
    for loc in ("es", "en"):
        try:
            r = requests.get(URL.format(loc=loc, kind=kind), timeout=60)
            r.raise_for_status()
            data = r.json()
            REF_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as e:
            print(f"[aviso] no se pudo bajar {kind} ({loc}): {e}")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _name_en(rec: dict) -> str:
    tr = rec.get("name_translations") or {}
    return tr.get("en") or rec.get("name") or rec.get("code", "")


class Ref:
    def __init__(self, cities: list, countries: list, airlines: list):
        self.cities = {c["code"]: c for c in cities if c.get("code")}
        self.countries = {c["code"]: _name(c) for c in countries if c.get("code")}
        self.countries_en = {c["code"]: _name_en(c) for c in countries if c.get("code")}
        self.airlines = {a["code"]: _name(a) for a in airlines if a.get("code")}

    def city_name(self, code: str) -> str:
        c = self.cities.get(code)
        return _name(c) if c else code

    def city_name_en(self, code: str) -> str:
        """Nombre en inglés (para buscar en sitios de marcas, p. ej. 'Mexico City')."""
        c = self.cities.get(code)
        return _name_en(c) if c else code

    def country_name_en(self, cc: str) -> str:
        return self.countries_en.get(cc, cc)

    def coords(self, code: str):
        c = (self.cities.get(code) or {}).get("coordinates") or {}
        if "lat" in c and "lon" in c:
            return float(c["lat"]), float(c["lon"])
        return None

    def country_code(self, code: str) -> str:
        return (self.cities.get(code) or {}).get("country_code", "")

    def country_name(self, cc: str) -> str:
        return self.countries.get(cc, cc)

    def airline_name(self, code: str) -> str:
        return self.airlines.get(code, code or "")


def load() -> Ref:
    if env("BVB_MOCK") == "1":
        data = json.loads((ROOT / "tests/fixtures/ref.json").read_text(encoding="utf-8"))
        return Ref(data["cities"], data["countries"], data["airlines"])
    return Ref(*(_download(k) for k in KINDS))
