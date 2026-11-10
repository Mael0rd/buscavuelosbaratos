"""Pipeline completo: buscar → guardar → detectar → redactar → web → Telegram.

Uso:  python -m bvb.main            (todo)
      python -m bvb.main --no-social (sin publicar en redes)
"""
import argparse

from . import deals as dl
from . import site, telegram
from .config import load_config
from .copywriter import write_copy
from .db import connect
from .fetch import fetch_all


def run(no_social: bool = False) -> None:
    cfg = load_config()
    conn = connect()
    run_start = conn.execute("SELECT datetime('now')").fetchone()[0]

    tickets = fetch_all(cfg)
    print(f"Tarifas obtenidas: {len(tickets)}")

    # Detectar contra el historial ANTERIOR a esta corrida, luego guardar
    found = dl.find_deals(conn, tickets, cfg, run_start)
    dl.save_observations(conn, tickets)
    print(f"Ofertas nuevas: {len(found)}")

    for d in found:
        d["slug"] = dl.make_slug(d)
        d.update(write_copy(d))
        dl.save_deal(conn, d)

    n = site.build(conn, cfg)
    print(f"Web generada con {n} ofertas activas")

    if not no_social:
        sent = telegram.publish_pending(conn, f"https://{cfg['site']['domain']}")
        print(f"Publicadas en Telegram: {sent}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-social", action="store_true")
    run(p.parse_args().no_social)
