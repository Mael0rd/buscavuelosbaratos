"""Genera la web estática en ./site: portada con secciones por país,
una página por país, una por destino y una por oferta."""
import hashlib
import json
import re
import shutil
import unicodedata
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import SITE_DIR, STATIC_DIR, TEMPLATES_DIR
from . import countrypage, explorer, extras, feriados, fx, geo, hubs, visas, ogimage, routes, telegram, whatsapp
from .fetch import with_subid
from .verify import web_visible
from .copywriter import fmt_date, fmt_stops, savings_pct

PER_COUNTRY_HOME = 6
INFO_PAGES = {"como-verificamos": "Cómo verificamos los precios",
              "quienes-somos": "Quiénes somos",
              "privacidad": "Política de privacidad",
              "reclamar-vuelo-retrasado": "Vuelo retrasado o cancelado: cuánto te pueden pagar y cómo reclamar"}


def card_image(url: str) -> tuple[str, str]:
    """Foto al tamaño de la tarjeta (~320x150) y al doble para pantallas retina. Unsplash recorta y comprime."""
    if "images.unsplash.com" not in url:
        return url, ""
    base = url.split("?")[0] + "?auto=format&fit=crop&q=60"
    return f"{base}&w=400&h=190", f"{base}&w=800&h=380"


def banner_image(url: str) -> tuple[str, str]:
    """Foto ancha y baja para encabezados (~720x180 y el doble para retina)."""
    if "images.unsplash.com" not in url:
        return url, ""
    base = url.split("?")[0] + "?auto=format&fit=crop&q=60"
    return f"{base}&w=720&h=180", f"{base}&w=1440&h=360"


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


def build(conn, cfg: dict, ref=None) -> int:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      autoescape=select_autoescape(["html"]))
    env.filters["fecha"] = fmt_date
    env.filters["escalas"] = fmt_stops
    env.filters["hace"] = telegram.ago
    env.filters["mes"] = lambda ym: explorer.month_short(ym) if ym else ""
    env.filters["subid"] = with_subid  # {{ link|subid("web_oferta") }}: SubID de Travelpayouts por fuente
    photos = cfg.get("dest_images") or {}
    env.globals["dest_banner"] = lambda code: (*banner_image(photos.get(code, "")),
                                               sum(map(ord, code or "")) % 6)  # (foto, foto 2x, degradado)
    env.filters["faq_ld"] = lambda qa: {"@type": "Question", "name": qa[0],
                                        "acceptedAnswer": {"@type": "Answer", "text": qa[1]}}

    deals = active_deals(conn, cfg)
    ended = active_deals(conn, cfg, status="expired")  # sus páginas siguen (con aviso), fuera de listas
    channels = telegram.channel_links(cfg)
    channel_labels = telegram.channel_labels(cfg)
    wa = whatsapp.wa_links(cfg)  # {país: canal de WhatsApp de su región}
    countries = []
    for cid, c in cfg["countries"].items():
        countries.append({"id": cid, "name": c["name"], "flag": c["flag"], "cc": c["cc"], "origins": c["origins"],
                          "term": c.get("term"),
                          "deals": [d for d in deals if d["country"] == cid]})

    # Páginas permanentes por ruta (SEO)
    seo = cfg.get("seo", {})
    route_pages = routes.build_pages(conn, cfg, deals, ended, seo.get("route_min_days", 3),
                                     seo.get("index_min_days", 14), seo.get("index_min_months", 2))
    slug_of_route = {(r["origin"], r["destination"]): r["slug"] for r in route_pages}
    for d in deals + ended:
        d["route_slug"] = slug_of_route.get((d["origin"], d["destination"]))
    for c in countries:
        c["routes"] = [r for r in route_pages if r["country"] == c["id"]]

    # Servicios complementarios (eSIM, tours, autos) por destino; requieren datos de referencia
    extra = extras.prepare(conn, cfg, ref, sorted({x["destination"] for x in deals + route_pages})) if ref else {}
    claim_link = extras.claim_link(conn, cfg, ref) if ref else ""
    eur_usd = fx.eur_usd(cfg)

    # Páginas permanentes por ciudad de origen y por destino
    origins, dest_hubs = hubs.build(conn, cfg, deals, route_pages, dest_slug)
    origin_by_code = {o["code"]: o for o in origins}
    for c in countries:
        c["cities"] = [o for o in origins if o["country"] == c["id"]]
        countrypage.summarize(c)  # destinos más baratos, mes más barato, preguntas frecuentes
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

    # Perfiles oficiales de la marca (sameAs en los datos estructurados de la portada):
    # Threads, canal general de Telegram, canales de WhatsApp y los de social.profiles.
    social = cfg.get("social", {})
    same_as = [(social.get(k) or {}).get("url", "") for k in ("instagram", "threads")] + [channels.get("main", "")]
    same_as += [w["url"] for w in wa.values() if w.get("url")] + list(social.get("profiles") or [])
    same_as = [u for u in dict.fromkeys(same_as) if u.startswith("http")]

    css = STATIC_DIR / "style.css"
    asset_v = hashlib.sha1(css.read_bytes()).hexdigest()[:8] if css.exists() else "1"
    ctx = {"site": cfg["site"], "asset_v": asset_v, "countries": countries, "total": len(deals),
           "per_home": PER_COUNTRY_HOME,
           "origin_names": cfg.get("origin_names", {}),
           "geo_countries": {cid: {"cc": c["cc"], "tz": cfg.get("timezones", {}).get(cid, []),
                                   "name": c["name"], "flag": c["flag"], "origins": c["origins"],
                                   "tg": channels.get(cid, ""), "wa": (wa.get(cid) or {}).get("url", "")}
                             for cid, c in cfg["countries"].items()},
           "alerts_api": cfg.get("alerts", {}).get("api_base", ""),
           "bot_username": telegram.bot_username(),
           "channels": channels, "channel_labels": channel_labels, "wa_links": wa,
           "threads_url": (cfg.get("social", {}).get("threads") or {}).get("url", ""),
           "same_as": same_as,
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "updated_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "origins": origins, "og": "/og/inicio.jpg", "extras": extra,
           "home_faq": countrypage.home_faq(countries, deals), "claim_link": claim_link,
           "eur_usd": eur_usd, "usd": lambda eur: fx.usd(eur, eur_usd)}
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
                     ("Ofertas de ida y vuelta verificadas" if h.get("stale") else f"Desde ${h['low']:.0f} ida y vuelta")
                     + (f" · {h['dest_country']}" if h["dest_country"] else ""),
                     tone=h["tone"])
        write(f"destino/{h['dest_slug']}.html", "destination.html", dest=h, deals=h["deals"], og=h["og"])
    for d in deals + ended:
        img = og(f"oferta-{d['slug']}", ogimage.deal_image, d, (by_id.get(d["country"]) or {}).get("cc", ""))
        if d in deals:  # versión vertical para redes (Threads); no la usa la página
            cc = (by_id.get(d["country"]) or {}).get("cc", "")
            photo = ogimage.fetch_photo(ogimage.photo_url((cfg.get("dest_images") or {}).get(d["destination"], "")))
            og(f"social-{d['slug']}", ogimage.social_image, d, cc, photo=photo)
        write(f"oferta/{d['slug']}.html", "deal.html", d=d, c=by_id.get(d["country"]), dest_pages=destinations, og=img)
    for r in route_pages:
        o = origin_by_code.get(r["origin"])
        dh = destinations.get(dest_slug(r["dest_name"], r["destination"]))
        r["origin_slug"] = o["slug"] if o else None
        r["dest_slug"] = dh["dest_slug"] if dh else None
        write(f"vuelos/{r['slug']}.html", "route.html", r=r, c=by_id.get(r["country"]), faqs=routes.faq(r),
              noindex=not r["indexable"],
              og=(r["deal"] and f"/og/oferta-{r['deal']['slug']}.jpg") or (dh or {}).get("og") or (o or {}).get("og", ctx["og"]))
    # Explorador por presupuesto: herramienta general + una página por ciudad de salida
    xp_rows = explorer.items(conn, cfg, origins, route_pages, deals, dest_slug,
                             lambda code: card_image(photos.get(code, ""))[0])
    xp_pages = explorer.origin_pages(xp_rows, origins)
    explorer.write_json(xp_rows, SITE_DIR / "data" / "explorar.json")
    xp_ctx = {"regions": geo.REGIONS, "months": explorer.month_options(xp_rows), "xp_pages": xp_pages,
              "xp_version": hashlib.sha1(json.dumps(xp_rows).encode()).hexdigest()[:8]}
    write("a-donde-volar.html", "explorer.html", **xp_ctx,
          og=og("a-donde-volar", ogimage.page_image, "¿A dónde puedes volar con $300?",
                "Elige tu ciudad y tu presupuesto: todos los destinos que caben", tone=2,
                kicker="Explorador de vuelos baratos"))
    (SITE_DIR / "a-donde-volar").mkdir(exist_ok=True)
    for xp in xp_pages:
        if not xp["n"]:
            continue
        img = og(f"xp-{xp['slug']}", ogimage.page_image, f"¿A dónde viajar desde {xp['name']}?",
                 f"{xp['under500']} destinos por menos de $500 ida y vuelta · desde ${xp['cheapest']['p']}",
                 cc=xp["cc"], tone=sum(map(ord, xp["code"])) % 6, kicker="Explorador por presupuesto")
        write(f"a-donde-volar/desde-{xp['slug']}.html", "explorer.html", p=xp, noindex=not xp["indexable"],
              og=img, **xp_ctx)

    # Feriados y puentes por país: el año en curso (y el siguiente desde octubre)
    today_d = date.today()
    fe_years = [today_d.year] + ([today_d.year + 1] if today_d.month >= 10 else [])
    fe_year = fe_years[-1]
    (SITE_DIR / "feriados").mkdir(exist_ok=True)
    fe_all = {}
    for y in fe_years:
        fe_all[y] = feriados.build(cfg, xp_rows, origins, y, today_d)
        for f in fe_all[y]:
            img = og(f"feriados-{f['slug']}", ogimage.page_image, f"Feriados {y} en {f['name']}",
                     f"{len(f['long_free'])} fines de semana largos y los mejores puentes del año",
                     cc=f["cc"], tone=sum(map(ord, f["id"])) % 6, kicker="Feriados y puentes")
            write(f"feriados/{f['slug']}.html", "feriados_pais.html", f=f, fe_pages=fe_all[y], og=img)
    fe_pages = fe_all[fe_year]
    write("feriados.html", "feriados.html", fe_pages=fe_pages, fe_year=fe_year,
          og=og("feriados", ogimage.page_image, f"Feriados {fe_year} en Latinoamérica",
                "Fines de semana largos, puentes y vuelos baratos por país", tone=0, kicker="Planifica tus viajes"))

    # ¿Necesito visa? por pasaporte y por pasaporte + destino (solo destinos con vuelos)
    vi_passports, vi_pairs, vi_date = visas.build(cfg, xp_rows, origins)
    vi_ctx = {"vi_passports": vi_passports, "vi_updated": visas.fmt_date(vi_date)}
    write("visas.html", "visas.html", **vi_ctx,
          og=og("visas", ogimage.page_image, "¿Necesito visa?",
                "A qué países puedes viajar sin visa con tu pasaporte", tone=3, kicker="Requisitos de viaje"))
    for vp in vi_passports:
        (SITE_DIR / "visas" / vp["slug"]).mkdir(parents=True, exist_ok=True)
        vp["og"] = og(f"visas-{vp['slug']}", ogimage.page_image, f"¿A dónde pueden viajar los {vp['demonym']} sin visa?",
                      f"{vp['easy']} países sin visa o con visa al llegar", cc=vp["cc"], tone=3,
                      kicker="Requisitos de viaje")
        write(f"visas/{vp['slug']}.html", "visas_pasaporte.html", p=vp, og=vp["og"], **vi_ctx)
    for vx in vi_pairs:
        write(f"visas/{vx['pp']['slug']}/{vx['dslug']}.html", "visas_destino.html", x=vx, og=vx["pp"]["og"], **vi_ctx)

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
    for f in fe_all[fe_years[0]]:  # feriados del año anterior: a la página del año actual
        redirects.insert(0, f"/feriados/{f['id']}-{fe_years[0] - 1} /feriados/{f['slug']} 301")
    (SITE_DIR / "_redirects").write_text("\n".join(redirects[:1900]) + ("\n" if redirects else ""))

    # Sitemap: solo páginas permanentes e indexables. Las /oferta/ duran horas o días
    # (gastarían rastreo); Google las descubre igual por los enlaces internos.
    base = f"https://{cfg['site']['domain']}"
    today = date.today().isoformat()
    urls = ([(f"{base}/", today), (f"{base}/alertas", None)] + [(f"{base}/{p}", None) for p in INFO_PAGES]
            + [(f"{base}/pais/{c['id']}", today) for c in countries]
            + [(f"{base}/desde/{o['slug']}", today) for o in origins]
            + [(f"{base}/destino/{s}", today) for s in destinations]
            + [(f"{base}/a-donde-volar", today)]
            + [(f"{base}/feriados", today)]
            + [(f"{base}/visas", today)] + [(f"{base}/visas/{v['slug']}", today) for v in vi_passports]
            + [(f"{base}{v['url']}", today) for v in vi_pairs]
            + [(f"{base}/feriados/{f['slug']}", today) for y in fe_years for f in fe_all[y]]
            + [(f"{base}/a-donde-volar/desde-{x['slug']}", today) for x in xp_pages if x["n"] and x["indexable"]]
            + [(f"{base}/vuelos/{r['slug']}", r["lastmod"]) for r in route_pages if r["indexable"]])
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>\n"
                  for u, m in urls) + "</urlset>\n")
    n_idx = sum(r["indexable"] for r in route_pages)
    print(f"[web] rutas: {len(route_pages)} páginas, {n_idx} indexables, {len(route_pages) - n_idx} con noindex")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    return len(deals)
