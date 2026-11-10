"""Pipeline: buscar → detectar ofertas → guardar historial → textos → web → Telegram.

Uso:  python -m bvb.main             (todo)
      python -m bvb.main --no-social (sin publicar en Telegram)
"""
import argparse
from datetime import datetime, timezone

from . import deals as dl
from . import refdata, site, telegram
from .config import load_config
from .copywriter import write_copy
from .db import connect
from .fetch import fetch_all


def run(no_social: bool = False) -> None:
    cfg = load_config()
    ref = refdata.load()
    conn = connect()
    today = datetime.now(timezone.utc).date().isoformat()

    removed = dl.purge_domestic(conn, ref)
    if removed:
        print(f"Ofertas nacionales retiradas: {removed}")

    tickets = fetch_all(cfg)
    best = dl.drop_domestic(dl.route_best(tickets, cfg["search"]["max_transfers"]), ref)
    print(f"Tarifas obtenidas: {len(tickets)} · rutas internacionales: {len(best)}")

    # Comparar contra el historial ANTERIOR a hoy; luego guardar lo de hoy
    found = dl.find_deals(conn, best, cfg, ref, today)
    dl.update_daily(conn, best, today)
    dl.prune(conn, today, cfg["deals"]["history_days"] + 5)
    print(f"Ofertas nuevas: {len(found)}")

    for d in found:
        d["slug"] = dl.make_slug(d)
        d.update(write_copy(d))
        dl.save_deal(conn, d)

    n = site.build(conn, cfg)
    print(f"Web generada con {n} ofertas activas")

    if not no_social:
        sent = telegram.publish_pending(conn, cfg)
        print(f"Publicadas en Telegram: {sent}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-social", action="store_true")
    run(p.parse_args().no_social)
