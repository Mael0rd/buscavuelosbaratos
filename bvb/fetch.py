"""Obtiene precios desde la Aviasales Data API (Travelpayouts).

Usa /aviasales/v3/prices_for_dates indicando SOLO el origen y unique=true:
devuelve el boleto más barato hacia cada destino (precios encontrados por
usuarios de Aviasales en las últimas ~48 h). Una consulta por origen y mes.
"""
import json
import re
import time
from datetime import date

import requests

from .config import ROOT, env, origin_country_map

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES_BASE = "https://www.aviasales.com"


def months_ahead(n: int, today: date | None = None) -> list[str]:
    today = today or date.today()
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def affiliate_link(relative_link: str, marker: str) -> str:
    """Convierte el 'link' relativo de la API en un enlace de afiliado."""
    if not relative_link:
        return ""
    url = AVIASALES_BASE + relative_link
    if marker:
        url += ("&" if "?" in url else "?") + f"marker={marker}"
    return url


_MARKER_RE = re.compile(r"([?&]marker=)(\d+)(?:\.[A-Za-z0-9_]*)?")


def with_subid(url: str, subid: str) -> str:
    """Agrega (o reemplaza) el SubID de Travelpayouts: marker=803749 → marker=803749.tg_mexico.

    Así las estadísticas de Travelpayouts separan clics y ventas por canal.
    Solo se permiten letras latinas, números y "_" (lo demás se cambia por "_")."""
    if not url or not subid:
        return url or ""
    clean = re.sub(r"[^A-Za-z0-9_]", "_", subid)
    return _MARKER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}.{clean}", url, count=1)


def fetch_origin_month(origin: str, month: str, cfg: dict) -> list[dict]:
    params = {
        "origin": origin,
        "departure_at": month,
        "one_way": "false" if cfg["search"]["round_trip"] else "true",
        "sorting": "price",
        "direct": "false",
        "unique": "true",
        "currency": cfg["site"]["currency"],
        "limit": cfg["search"]["limit_per_query"],
        "page": 1,
        "token": env("TRAVELPAYOUTS_TOKEN"),
    }
    r = requests.get(API_URL, params=params, timeout=45)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success", True):
        raise RuntimeError(f"API: {payload}")
    return payload.get("data", [])


def normalize(raw: dict, origin: str, marker: str) -> dict:
    dest = raw.get("destination", "")
    return {
        "origin": origin,
        "origin_airport": raw.get("origin_airport") or origin,
        "destination": dest,
        "destination_airport": raw.get("destination_airport") or dest,
        "price": float(raw.get("price")),
        "airline": raw.get("airline", ""),
        "departure_at": raw.get("departure_at", ""),
        "return_at": raw.get("return_at", ""),
        "transfers": int(raw.get("transfers", 0) or 0),
        "return_transfers": int(raw.get("return_transfers", 0) or 0),
        "link": affiliate_link(raw.get("link", ""), marker),
    }


def fetch_all(cfg: dict) -> list[dict]:
    marker = env("TRAVELPAYOUTS_MARKER")

    if env("BVB_MOCK") == "1":
        with open(ROOT / "tests/fixtures/sample_prices.json", encoding="utf-8") as f:
            return [normalize(x, x["origin"], marker) for x in json.load(f)]

    if not env("TRAVELPAYOUTS_TOKEN"):
        print("[aviso] Falta TRAVELPAYOUTS_TOKEN: no se buscan precios en esta corrida")
        return []

    tickets, errors = [], 0
    months = months_ahead(cfg["search"]["months_ahead"])
    for origin in origin_country_map(cfg):
        n = 0
        for month in months:
            try:
                rows = fetch_origin_month(origin, month, cfg)
                tickets += [normalize(x, origin, marker) for x in rows if x.get("price")]
                n += len(rows)
            except Exception as e:  # un fallo no detiene el resto
                errors += 1
                print(f"[aviso] {origin} {month}: {e}")
            time.sleep(cfg["search"]["pause_seconds"])
        print(f"  {origin}: {n} tarifas")
    if errors:
        print(f"[aviso] consultas con error: {errors}")
    return tickets
