"""Pipeline: buscar → detectar ofertas → guardar historial → textos → web → Telegram.

Uso:  python -m bvb.main             (todo)
      python -m bvb.main --no-social (sin publicar en Telegram)
      python -m bvb.main --build-only (solo arma la web con el historial: sin buscar,
                                       verificar, enviar alertas ni publicar; para vistas previas)
"""
import argparse
from datetime import datetime, timezone

from . import deals as dl
from . import alerts, facebook, fresh, instagram, refdata, routes, site, telegram, threads, verify, whatsapp
from .config import load_config
from .copywriter import write_copy
from .db import connect
from .fetch import fetch_all


def build_only() -> None:
    cfg, ref, conn = load_config(), refdata.load(), connect()
    print(f"Web generada con {site.build(conn, cfg, ref=ref)} ofertas activas (solo armado, sin publicar)")


def run(no_social: bool = False) -> None:
    cfg = load_config()
    ref = refdata.load()
    conn = connect()
    today = datetime.now(timezone.utc).date().isoformat()

    sc = cfg["search"]
    removed = (dl.purge_domestic(conn, ref) + dl.purge_too_many_stops(conn, sc["max_transfers"])
               + dl.purge_short_trips(conn, sc["min_trip_days"]))
    if removed:
        print(f"Ofertas retiradas (nacionales, con muchas escalas o viajes cortos): {removed}")

    tickets = fetch_all(cfg)
    best = dl.drop_domestic(dl.route_best(tickets, sc["max_transfers"], sc["min_trip_days"]), ref)
    print(f"Tarifas obtenidas: {len(tickets)} · rutas internacionales: {len(best)}")
    routes.update(conn, best, ref, today)

    # Comparar contra el historial ANTERIOR a hoy; luego guardar lo de hoy
    funnel: dict = {}
    found = dl.find_deals(conn, best, cfg, ref, today, funnel)
    ratios = funnel.pop("_ratios", [])
    print(f"Embudo ({len(best)} rutas): descartadas {dict(sorted(funnel.items(), key=lambda x: -x[1]))} · pasan el precio: {len(found)}")
    if ratios:  # cuántas rutas quedarían bajo el tope si se multiplicara por f
        print("Calibración del tope (rutas bajo tope×f):",
              {f: sum(1 for r, _ in ratios if r <= f) for f in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0)},
              f"de {len(ratios)}")
    dl.update_daily(conn, best, today)
    dl.prune(conn, today, cfg["deals"]["history_days"] + 5)
    checker = fresh.Checker(cfg)

    # Solo se guardan ofertas cuyo precio se vio hace poco (honestidad ante el público)
    saved = skipped = 0
    ages = []
    for d in found:
        found_at = checker.is_fresh(d)
        if not found_at:
            skipped += 1
            st, seen = checker.check(d)  # (caché) para registrar hace cuánto se vio
            if st == "match":
                ages.append(round(fresh.age_hours(seen)))
            continue
        d["found_at"] = found_at
        d["slug"] = dl.make_slug(d)
        d.update(write_copy(d))
        dl.save_deal(conn, d)
        saved += 1
    print(f"Ofertas nuevas: {saved} (descartadas por precio no reciente: {skipped})")
    if ages:
        print(f"  horas desde que se vieron las descartadas: {sorted(ages)}")

    # Revisar las ofertas publicadas: las que subieron o ya no se confirman, terminan
    expired = fresh.revalidate(conn, checker, cfg)
    print(f"Ofertas terminadas en esta corrida: {len(expired)}")

    subs = alerts.fetch_subscriptions(cfg)
    if subs:
        st = alerts.process(conn, best, cfg, ref, today, subs, checker)
        print(f"Alertas activas: {len(subs)} · avisos enviados: "
              f"{st['telegram']} por Telegram, {st['email']} por correo")

    # Web honesta: verificar en vivo lo que se muestra (re-verifica las viejas primero)
    verifier = verify.Verifier(conn, cfg)
    if not verifier.providers:
        print("[verificación] sin SERPAPI_KEY ni APIFY_TOKEN: la web y Telegram no mostrarán ofertas nuevas")
    print(f"Verificación para la web: {verifier.refresh_web()}")

    n = site.build(conn, cfg, ref=ref)
    print(f"Web generada con {n} ofertas activas")
    print(f"Frescura: {checker.stats} · consultas: {checker.calls}")

    if not no_social:
        edited = telegram.mark_expired_posts(conn, cfg)
        if edited:
            print(f"Posts marcados como terminados en Telegram: {edited}")
        print(f"Publicadas en Telegram: {telegram.publish(conn, cfg, verifier=verifier)}")
        th = threads.publish(conn, cfg, verifier=verifier)
        if th:
            print(f"Publicadas en Threads: {th}")
        ig = instagram.publish(conn, cfg, verifier=verifier)
        if ig:
            print(f"Publicadas en Instagram: {ig}")
        fb = facebook.publish(conn, cfg, verifier=verifier)
        if fb:
            print(f"Publicadas en Facebook: {fb}")
        wa = whatsapp.relay(conn, cfg, verifier=verifier)
        if wa:
            print(f"Listas para WhatsApp (enviadas al administrador): {wa}")
    print(verifier.summary())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-social", action="store_true")
    p.add_argument("--build-only", action="store_true")
    a = p.parse_args()
    build_only() if a.build_only else run(a.no_social)
