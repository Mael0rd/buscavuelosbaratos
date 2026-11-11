"""Genera la web estática en ./site: portada con secciones por país,
una página por país, una por destino y una por oferta."""
import hashlib
import re
import shutil
import unicodedata
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import SITE_DIR, STATIC_DIR, TEMPLATES_DIR
from . import routes, telegram
from .verify import web_visible
from .copywriter import fmt_date, fmt_stops, savings_pct

PER_COUNTRY_HOME = 6


def card_image(url: str) -> tuple[str, str]:
    """Foto al tamaño de la tarjeta (~320x150) y al doble para pantallas retina. Unsplash recorta y comprime."""
    if "images.unsplash.com" not in url:
        return url, ""
    base = url.split("?")[0] + "?auto=format&fit=crop&q=60"
    return f"{base}&w=400&h=190", f"{base}&w=800&h=380"


def dest_slug(name: str, code: str) -> str:
    """'São Paulo', 'SAO' -> 'sao-paulo-sao' (el código evita choques como San José CR / EE. UU.)."""
    ascii_ = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")
    return f"{words}-{code.lower()}" if words else code.lower()


def active_deals(conn, cfg: dict, status: str = "active") -> list[dict]:
    today = date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM deals
           WHERE COALESCE(status, 'active') = ?
             AND published_at >= datetime('now', ?) AND substr(departure_at, 1, 10) >= ?
           ORDER BY score ASC""",
        (status, f"-{cfg['deals']['show_days']} days", today),
    ).fetchall()
    now = datetime.now(timezone.utc)
    if status == "active" and cfg.get("verify"):
        rows = [r for r in rows if web_visible(dict(r), cfg, now)]  # solo verificadas en vivo
    seen, out = set(), []
    for r in rows:  # una oferta por ruta: la mejor
        key = (r["origin"], r["destination"])
        if key in seen:
            continue
        seen.add(key)
        d = dict(r)
        d["ahorro"] = savings_pct(d)
        d["dest_slug"] = dest_slug(d["dest_name"], d["destination"])
        d["img"], d["img2x"] = card_image((cfg.get("dest_images") or {}).get(d["destination"], ""))
        d["tone"] = sum(map(ord, d["destination"] or "")) % 6  # degradado fijo por destino si no hay foto
        out.append(d)
    return out


def build(conn, cfg: dict) -> int:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      autoescape=select_autoescape(["html"]))
    env.filters["fecha"] = fmt_date
    env.filters["escalas"] = fmt_stops
    env.filters["hace"] = telegram.ago
    env.filters["faq_ld"] = lambda qa: {"@type": "Question", "name": qa[0],
                                        "acceptedAnswer": {"@type": "Answer", "text": qa[1]}}

    deals = active_deals(conn, cfg)
    ended = active_deals(conn, cfg, status="expired")  # sus páginas siguen (con aviso), fuera de listas
    channels = telegram.channel_links(cfg)
    countries = []
    for cid, c in cfg["countries"].items():
        countries.append({"id": cid, "name": c["name"], "flag": c["flag"], "cc": c["cc"], "origins": c["origins"],
                          "deals": [d for d in deals if d["country"] == cid]})

    # Páginas permanentes por ruta (SEO)
    seo = cfg.get("seo", {})
    route_pages = routes.build_pages(conn, cfg, deals, ended, seo.get("route_min_days", 3))
    slug_of_route = {(r["origin"], r["destination"]): r["slug"] for r in route_pages}
    for d in deals + ended:
        d["route_slug"] = slug_of_route.get((d["origin"], d["destination"]))
    for c in countries:
        c["routes"] = [r for r in route_pages if r["country"] == c["id"]]

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / "oferta").mkdir(parents=True)
    (SITE_DIR / "pais").mkdir()
    (SITE_DIR / "destino").mkdir()
    (SITE_DIR / "vuelos").mkdir()
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, SITE_DIR / "static")

    css = STATIC_DIR / "style.css"
    asset_v = hashlib.sha1(css.read_bytes()).hexdigest()[:8] if css.exists() else "1"
    ctx = {"site": cfg["site"], "asset_v": asset_v, "countries": countries, "total": len(deals),
           "per_home": PER_COUNTRY_HOME,
           "origin_names": cfg.get("origin_names", {}),
           "geo_countries": {cid: {"cc": c["cc"], "tz": cfg.get("timezones", {}).get(cid, []),
                                   "name": c["name"], "flag": c["flag"], "origins": c["origins"],
                                   "tg": channels.get(cid, "")}
                             for cid, c in cfg["countries"].items()},
           "alerts_api": cfg.get("alerts", {}).get("api_base", ""),
           "bot_username": telegram.bot_username(),
           "channels": channels,
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "updated_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    by_id = {c["id"]: c for c in countries}

    def write(path, template, **kw):
        (SITE_DIR / path).write_text(env.get_template(template).render(**ctx, **kw), encoding="utf-8")

    write("index.html", "index.html")
    write("alertas.html", "alertas.html")
    for c in countries:
        write(f"pais/{c['id']}.html", "country.html", c=c)
    # shortcut: solo destinos con ofertas activas; la página desaparece cuando no hay, cambiar si afecta SEO
    destinations = {}
    for d in deals:  # deals ya viene ordenado de mejor a peor
        destinations.setdefault(d["dest_slug"], []).append(d)
    for slug, ds in destinations.items():
        write(f"destino/{slug}.html", "destination.html", dest=ds[0], deals=ds)
    for d in deals + ended:
        write(f"oferta/{d['slug']}.html", "deal.html", d=d, c=by_id.get(d["country"]), dest_pages=destinations)
    for r in route_pages:
        write(f"vuelos/{r['slug']}.html", "route.html", r=r, c=by_id.get(r["country"]), faqs=routes.faq(r))
    write("404.html", "404.html")

    # Ofertas que ya no tienen página: su URL redirige (301) a la página de la ruta o del país.
    # Cloudflare Pages lee el archivo _redirects (máx. 2.000 reglas estáticas).
    live = {d["slug"] for d in deals + ended}
    redirects = []
    for x in conn.execute(
            """SELECT slug, origin, destination, country FROM deals
               WHERE published_at >= datetime('now', ?) ORDER BY published_at DESC""",
            (f"-{seo.get('redirect_days', 90)} days",)).fetchall():
        if x["slug"] in live:
            continue
        rs = slug_of_route.get((x["origin"], x["destination"]))
        target = f"/vuelos/{rs}.html" if rs else f"/pais/{x['country']}.html"
        redirects.append(f"/oferta/{x['slug']}.html {target} 301")
    (SITE_DIR / "_redirects").write_text("\n".join(redirects[:1900]) + ("\n" if redirects else ""))

    base = f"https://{cfg['site']['domain']}"
    urls = ([f"{base}/", f"{base}/alertas.html"] + [f"{base}/pais/{c['id']}.html" for c in countries]
            + [f"{base}/destino/{s}.html" for s in destinations]
            + [f"{base}/vuelos/{r['slug']}.html" for r in route_pages]
            + [f"{base}/oferta/{d['slug']}.html" for d in deals])
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    return len(deals)
