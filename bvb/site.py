"""Genera la web estática en ./site: portada con secciones por país,
una página por país y una por oferta."""
import hashlib
import shutil
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import SITE_DIR, STATIC_DIR, TEMPLATES_DIR
from . import telegram
from .verify import web_visible
from .copywriter import fmt_date, fmt_stops, savings_pct

PER_COUNTRY_HOME = 6


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
        out.append(d)
    return out


def build(conn, cfg: dict) -> int:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      autoescape=select_autoescape(["html"]))
    env.filters["fecha"] = fmt_date
    env.filters["escalas"] = fmt_stops
    env.filters["hace"] = telegram.ago

    deals = active_deals(conn, cfg)
    ended = active_deals(conn, cfg, status="expired")  # sus páginas siguen (con aviso), fuera de listas
    channels = telegram.channel_links(cfg)
    countries = []
    for cid, c in cfg["countries"].items():
        countries.append({"id": cid, "name": c["name"], "flag": c["flag"], "cc": c["cc"], "origins": c["origins"],
                          "deals": [d for d in deals if d["country"] == cid]})

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / "oferta").mkdir(parents=True)
    (SITE_DIR / "pais").mkdir()
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
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    by_id = {c["id"]: c for c in countries}

    def write(path, template, **kw):
        (SITE_DIR / path).write_text(env.get_template(template).render(**ctx, **kw), encoding="utf-8")

    write("index.html", "index.html")
    write("alertas.html", "alertas.html")
    for c in countries:
        write(f"pais/{c['id']}.html", "country.html", c=c)
    for d in deals + ended:
        write(f"oferta/{d['slug']}.html", "deal.html", d=d, c=by_id.get(d["country"]))

    base = f"https://{cfg['site']['domain']}"
    urls = ([f"{base}/", f"{base}/alertas.html"] + [f"{base}/pais/{c['id']}.html" for c in countries]
            + [f"{base}/oferta/{d['slug']}.html" for d in deals])
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    (SITE_DIR / "CNAME").write_text(cfg["site"]["domain"] + "\n")
    return len(deals)
