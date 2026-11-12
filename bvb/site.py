"""Genera la web estática en ./site: portada con secciones por país,
una página por país, una por destino y una por oferta."""
import hashlib
import re
import shutil
import unicodedata
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import SITE_DIR, STATIC_DIR, TEMPLATES_DIR
from . import hubs, ogimage, routes, telegram
from .verify import web_visible
from .copywriter import fmt_date, fmt_stops, savings_pct

PER_COUNTRY_HOME = 6
INFO_PAGES = {"como-verificamos": "Cómo verificamos los precios",
              "quienes-somos": "Quiénes somos",
              "privacidad": "Política de privacidad"}


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
    channel_labels = telegram.channel_labels(cfg)
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

    # Páginas permanentes por ciudad de origen y por destino
    origins, dest_hubs = hubs.build(conn, cfg, deals, route_pages, dest_slug)
    origin_by_code = {o["code"]: o for o in origins}
    for c in countries:
        c["cities"] = [o for o in origins if o["country"] == c["id"]]
    for d in deals + ended:
        o = origin_by_code.get(d["origin"])
        d["origin_slug"] = o["slug"] if o else None

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / "oferta").mkdir(parents=True)
    (SITE_DIR / "pais").mkdir()
    (SITE_DIR / "destino").mkdir()
    (SITE_DIR / "vuelos").mkdir()
    (SITE_DIR / "desde").mkdir()
    (SITE_DIR / "og").mkdir()
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, SITE_DIR / "static")
        if (STATIC_DIR / "favicon.ico").exists():  # los navegadores lo piden en la raíz
            shutil.copy(STATIC_DIR / "favicon.ico", SITE_DIR / "favicon.ico")

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
           "channels": channels, "channel_labels": channel_labels,
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "updated_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "origins": origins, "og": "/og/inicio.jpg"}
    by_id = {c["id"]: c for c in countries}

    def write(path, template, **kw):
        # Cloudflare Pages sirve /x/y.html en /x/y (y redirige la versión con .html): usamos esa URL
        page = "/" if path == "index.html" else "/" + path.removesuffix(".html")
        html = env.get_template(template).render({**ctx, "page_path": page, **kw})
        (SITE_DIR / path).write_text(html, encoding="utf-8")

    def og(name, fn, *args, **kw):
        """Genera la imagen para compartir; si algo falla, la página usa la general."""
        try:
            fn(*args, SITE_DIR / "og" / f"{name}.jpg", **kw)
            return f"/og/{name}.jpg"
        except Exception as e:  # noqa: BLE001 — una imagen nunca debe tumbar la corrida
            print(f"  ⚠ imagen {name}: {e}")
            return "/og/inicio.jpg"

    og("inicio", ogimage.page_image, "Vuelos baratos desde Latinoamérica",
       "Ofertas de ida y vuelta muy por debajo de su precio normal", tone=1)

    write("index.html", "index.html")
    write("alertas.html", "alertas.html", og=og("alertas", ogimage.page_image, "Alertas de vuelos baratos",
                                                 "Te avisamos por correo o Telegram cuando baje tu ruta", tone=2))
    for c in countries:
        img = og(f"pais-{c['id']}", ogimage.page_image, f"Vuelos baratos desde {c['name']}",
                 f"{len(c['deals'])} ofertas verificadas ahora" if c["deals"] else "Ofertas de ida y vuelta verificadas",
                 cc=c["cc"], tone=sum(map(ord, c["id"])) % 6)
        write(f"pais/{c['id']}.html", "country.html", c=c, og=img)
    for o in origins:
        sub = (f"{o['n_dests']} destinos internacionales · desde ${o['cheapest']['last_price']:.0f}"
               if o["cheapest"] else "Destinos internacionales de ida y vuelta")
        o["og"] = og(f"desde-{o['slug']}", ogimage.page_image, f"Vuelos baratos desde {o['name']}", sub,
                     cc=o["cc"], kicker=o["country_name"], tone=sum(map(ord, o["code"])) % 6)
        write(f"desde/{o['slug']}.html", "origin.html", o=o, c=by_id.get(o["country"]), og=o["og"])
    destinations = {}
    for h in dest_hubs:
        destinations[h["dest_slug"]] = h
        h["og"] = og(f"destino-{h['dest_slug']}", ogimage.page_image, f"Vuelos baratos a {h['dest_name']}",
                     f"Desde ${h['low']:.0f} ida y vuelta" + (f" · {h['dest_country']}" if h["dest_country"] else ""),
                     tone=h["tone"])
        write(f"destino/{h['dest_slug']}.html", "destination.html", dest=h, deals=h["deals"], og=h["og"])
    for d in deals + ended:
        img = og(f"oferta-{d['slug']}", ogimage.deal_image, d, (by_id.get(d["country"]) or {}).get("cc", ""))
        write(f"oferta/{d['slug']}.html", "deal.html", d=d, c=by_id.get(d["country"]), dest_pages=destinations, og=img)
    for r in route_pages:
        o = origin_by_code.get(r["origin"])
        dh = destinations.get(dest_slug(r["dest_name"], r["destination"]))
        r["origin_slug"] = o["slug"] if o else None
        r["dest_slug"] = dh["dest_slug"] if dh else None
        write(f"vuelos/{r['slug']}.html", "route.html", r=r, c=by_id.get(r["country"]), faqs=routes.faq(r),
              og=(r["deal"] and f"/og/oferta-{r['deal']['slug']}.jpg") or (dh or {}).get("og") or (o or {}).get("og", ctx["og"]))
    for page, title in INFO_PAGES.items():
        write(f"{page}.html", f"{page}.html", title=title)
    write("404.html", "404.html", page_path=None)

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
        target = f"/vuelos/{rs}" if rs else f"/pais/{x['country']}"
        redirects.append(f"/oferta/{x['slug']} {target} 301")
        redirects.append(f"/oferta/{x['slug']}.html {target} 301")
    (SITE_DIR / "_redirects").write_text("\n".join(redirects[:1900]) + ("\n" if redirects else ""))

    base = f"https://{cfg['site']['domain']}"
    urls = ([f"{base}/", f"{base}/alertas"] + [f"{base}/{p}" for p in INFO_PAGES]
            + [f"{base}/pais/{c['id']}" for c in countries]
            + [f"{base}/desde/{o['slug']}" for o in origins]
            + [f"{base}/destino/{s}" for s in destinations]
            + [f"{base}/vuelos/{r['slug']}" for r in route_pages]
            + [f"{base}/oferta/{d['slug']}" for d in deals])
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    return len(deals)
