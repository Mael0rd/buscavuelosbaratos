"""Publica en Telegram la mejor oferta activa de un país, como ejemplo.
No cambia el historial (la oferta puede volver a salir normalmente).

Uso:  python -m bvb.post_example costa-rica
"""
import sys

from . import telegram
from .config import env, load_config
from .db import connect
from .site import active_deals


def main(country: str) -> None:
    cfg = load_config()
    if country not in cfg["countries"]:
        raise SystemExit(f"País desconocido: {country}. Opciones: {', '.join(cfg['countries'])}")
    deals = [d for d in active_deals(connect(), cfg) if d["country"] == country]
    if not deals:
        raise SystemExit(f"No hay ofertas activas desde {cfg['countries'][country]['name']} ahora mismo.")
    if not env("TELEGRAM_BOT_TOKEN") or not env("TELEGRAM_CHANNEL"):
        raise SystemExit("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL.")
    d = deals[0]
    text, markup = telegram.build_message(d, f"https://{cfg['site']['domain']}",
                                          cfg["countries"][country]["name"])
    print(text)
    if not telegram.send(text, markup):
        raise SystemExit("Telegram rechazó el mensaje (revisa el error de arriba).")
    print(f"\nPublicado: {d['origin_name']} → {d['dest_name']} ${d['price']:.0f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "costa-rica")
