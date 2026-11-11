"""Pipeline: buscar → detectar ofertas → guardar historial → textos → web → Telegram.

Uso:  python -m bvb.main             (todo)
      python -m bvb.main --no-social (sin publicar en Telegram)
"""
import argparse
from datetime import datetime, timezone

from . import deals as dl
from . import alerts, fresh, refdata, site, telegram
from .config import load_config
from .copywriter import write_copy
from .db import connect
from .fetch import fetch_all


def run(no_social: bool = False) -> None:
    cfg = load_config()
    ref = refdata.load()
    conn = connect()
    today = datetime.now(timezone.utc).date().isoformat()

    removed = dl.purge_domestic(conn, ref) + dl.purge_too_many_stops(conn, cfg["search"]["max_transfers"])
    if removed:
        print(f"Ofertas retiradas (nacionales o con muchas escalas): {removed}")

    tickets = fetch_all(cfg)
    best = dl.drop_domestic(dl.route_best(tickets, cfg["search"]["max_transfers"]), ref)
    print(f"Tarifas obtenidas: {len(tickets)} · rutas internacionales: {len(best)}")

    # Comparar contra el historial ANTERIOR a hoy; luego guardar lo de hoy
    found = dl.find_deals(conn, best, cfg, ref, today)
    dl.update_daily(conn, best, today)
    dl.prune(conn, today, cfg["deals"]["history_days"] + 5)
    checker = fresh.Checker(cfg)

    # Solo se guardan ofertas cuyo precio se vio hace poco (honestidad ante el público)
    saved = skipped = 0
    for d in found:
        found_at = checker.is_fresh(d)
        if not found_at:
            skipped += 1
            continue
        d["found_at"] = found_at
        d["slug"] = dl.make_slug(d)
        d.update(write_copy(d))
        dl.save_deal(conn, d)
        saved += 1
    print(f"Ofertas nuevas: {saved} (descartadas por precio no reciente: {skipped})")

    # Revisar las ofertas publicadas: las que subieron o ya no se confirman, terminan
    expired = fresh.revalidate(conn, checker, cfg)
    print(f"Ofertas terminadas en esta corrida: {len(expired)}")

    subs = alerts.fetch_subscriptions(cfg)
    if subs:
        st = alerts.process(conn, best, cfg, ref, today, subs, checker)
        print(f"Alertas activas: {len(subs)} · avisos enviados: "
              f"{st['telegram']} por Telegram, {st['email']} por correo")

    n = site.build(conn, cfg)
    print(f"Web generada con {n} ofertas activas")
    print(f"Frescura: {checker.stats} · consultas: {checker.calls}")

    if not no_social:
        edited = telegram.mark_expired_posts(conn, cfg)
        if edited:
            print(f"Posts marcados como terminados en Telegram: {edited}")
        print(f"Publicadas en Telegram: {telegram.publish(conn, cfg)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-social", action="store_true")
    run(p.parse_args().no_social)
