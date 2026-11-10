"""Obtiene precios desde la Aviasales Data API (Travelpayouts).

Usa /aviasales/v3/prices_for_dates: devuelve los boletos más baratos
encontrados por usuarios de Aviasales en las últimas ~48 h (precios en caché).
"""
import json
import time
from datetime import date

import requests

from .config import ROOT, env

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES_BASE = "https://www.aviasales.com"


def _months_ahead(n: int) -> list[str]:
    today = date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def affiliate_link(relative_link: str, marker: str) -> str:
    """Convierte el 'link' relativo de la API en un enlace de afiliado.
    Verifica el formato en tu panel de Travelpayouts (generador de enlaces)."""
    if not relative_link:
        return ""
    url = AVIASALES_BASE + relative_link
    if marker:
        url += ("&" if "?" in url else "?") + f"marker={marker}"
    return url


def fetch_route(origin: str, destination: str, month: str, cfg: dict) -> list[dict]:
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": month,
        "one_way": "false" if cfg["search"]["round_trip"] else "true",
        "sorting": "price",
        "direct": "false",
        "unique": "false",
        "currency": cfg["site"]["currency"],
        "limit": cfg["search"]["limit_per_query"],
        "page": 1,
        "token": env("TRAVELPAYOUTS_TOKEN"),
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success", True):
        raise RuntimeError(f"API error {origin}-{destination} {month}: {payload}")
    return payload.get("data", [])


def normalize(raw: dict, marker: str) -> dict:
    return {
        "origin": raw.get("origin"),
        "destination": raw.get("destination"),
        "price": float(raw.get("price")),
        "airline": raw.get("airline", ""),
        "departure_at": raw.get("departure_at", ""),
        "return_at": raw.get("return_at", ""),
        "transfers": int(raw.get("transfers", 0) or 0),
        "link": affiliate_link(raw.get("link", ""), marker),
    }


def fetch_all(cfg: dict) -> list[dict]:
    marker = env("TRAVELPAYOUTS_MARKER")

    if env("BVB_MOCK") == "1":
        with open(ROOT / "tests/fixtures/sample_prices.json", encoding="utf-8") as f:
            return [normalize(x, marker) for x in json.load(f)]

    if not env("TRAVELPAYOUTS_TOKEN"):
        # Sin token todavía: se publica la web vacía en vez de fallar
        print("[aviso] Falta TRAVELPAYOUTS_TOKEN: no se buscan precios en esta corrida")
        return []

    tickets = []
    for origin in cfg["origins"]:
        for dest in cfg["destinations"]:
            for month in _months_ahead(cfg["search"]["months_ahead"]):
                try:
                    rows = fetch_route(origin, dest, month, cfg)
                    tickets += [normalize(x, marker) for x in rows]
                except Exception as e:  # una ruta fallida no detiene el resto
                    print(f"[aviso] {origin}-{dest} {month}: {e}")
                time.sleep(0.4)  # respetar límites de la API
    return tickets
