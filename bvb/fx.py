"""Tipo de cambio euro → dólar para mostrar montos en USD (p. ej. compensaciones en euros).

Usa las tasas de referencia del Banco Central Europeo (API gratuita de Frankfurter, sin
clave). Si no responde, usa `fx.eur_usd` de config.yaml.
"""
import requests

from .config import env

URL = "https://api.frankfurter.app/latest?from=EUR&to=USD"


def eur_usd(cfg: dict) -> float:
    fallback = float((cfg.get("fx") or {}).get("eur_usd", 1.15))
    if env("BVB_MOCK") == "1":
        return fallback
    try:
        r = requests.get(URL, timeout=10)
        r.raise_for_status()
        rate = float(r.json()["rates"]["USD"])
        return rate if 0.5 < rate < 2 else fallback
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return fallback


def usd(eur: float, rate: float) -> int:
    """Monto en dólares redondeado a 5 (son aproximados)."""
    return int(round(eur * rate / 5) * 5)
