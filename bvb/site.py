"""Genera la web estática en ./site (lista para GitHub Pages / Cloudflare Pages)."""
import shutil
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import SITE_DIR, STATIC_DIR, TEMPLATES_DIR
from .copywriter import fmt_date, savings_pct


def build(conn, cfg: dict) -> int:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      autoescape=select_autoescape(["html"]))
    env.filters["fecha"] = fmt_date

    rows = conn.execute(
        """SELECT * FROM deals WHERE published_at >= datetime('now', ?)
           ORDER BY published_at DESC""",
        (f"-{cfg['deals']['show_days']} days",),
    ).fetchall()
    deals = []
    for r in rows:
        d = dict(r)
        d["dest_name"] = cfg["destinations"].get(d["destination"], {}).get("name", d["destination"])
        d["ahorro"] = savings_pct(d)
        deals.append(d)

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / "oferta").mkdir(parents=True)
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, SITE_DIR / "static")

    ctx = {"site": cfg["site"], "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    (SITE_DIR / "index.html").write_text(
        env.get_template("index.html").render(deals=deals, **ctx), encoding="utf-8")
    for d in deals:
        (SITE_DIR / "oferta" / f"{d['slug']}.html").write_text(
            env.get_template("deal.html").render(d=d, **ctx), encoding="utf-8")

    (SITE_DIR / "CNAME").write_text(cfg["site"]["domain"] + "\n")
    urls = [f"https://{cfg['site']['domain']}/"] + [
        f"https://{cfg['site']['domain']}/oferta/{d['slug']}.html" for d in deals]
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: https://{cfg['site']['domain']}/sitemap.xml\n")
    return len(deals)
