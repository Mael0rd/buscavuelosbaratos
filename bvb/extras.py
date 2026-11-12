"""Servicios complementarios al vuelo (eSIM, tours, autos...) en las páginas de la web.

Para cada destino con página (oferta o ruta) se arma un bloque por servicio, con un
enlace de afiliado de Travelpayouts que lleva a la página de ese destino en la marca
(p. ej. la eSIM para España). Todo se configura en `extras:` de config.yaml.

- Prueba A/B: si un servicio tiene varias marcas ("variants"), cada destino recibe
  siempre la misma (reparto estable por peso), para comparar ventas por clic.
- Cobertura: cada marca puede limitarse a regiones/países (p. ej. Klook solo Asia).
- URLs candidatas: cada marca tiene una lista de URLs en orden de preferencia. Se usa la
  primera que exista (se comprueba una vez y se guarda en caché); la última es la
  portada de la marca y siempre se acepta.
- Enlaces de afiliado: API POST https://api.travelpayouts.com/links/v1/create
  (máx. 10 por consulta, 100 consultas/min), con SubID por página. Se guardan en caché
  (tabla extra_links). Si la API no responde, se muestra el enlace directo: el script
  Drive de Travelpayouts lo convierte en el navegador.
"""
import hashlib
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit

import requests

from .config import env

API_URL = "https://api.travelpayouts.com/links/v1/create"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
PLACES = ("oferta", "ruta")  # páginas donde se muestra (cada una con su SubID)

SCHEMA = """
CREATE TABLE IF NOT EXISTS extra_links (
    url TEXT, sub_id TEXT, partner_url TEXT, created_at TEXT,
    PRIMARY KEY (url, sub_id)
);
CREATE TABLE IF NOT EXISTS extra_urls (
    url TEXT PRIMARY KEY, ok INTEGER, checked_at TEXT   -- ok: 1 existe, 0 no existe, NULL no se pudo saber
);
"""


def slugify(text: str) -> str:
    """'United States' -> 'united-states', 'Curaçao' -> 'curacao'."""
    ascii_ = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def serves(v: dict, cc: str, regions: dict) -> bool:
    """¿La marca cubre este país? 'regions' (nombres definidos en extras.regions) o 'countries'
    limitan; 'exclude' quita. Sin límites, cubre todo."""
    allow = set(v.get("countries") or [])
    for r in v.get("regions") or []:
        allow |= set(regions.get(r) or [])
    deny = set(v.get("exclude") or [])
    for r in v.get("exclude_regions") or []:
        deny |= set(regions.get(r) or [])
    return (not allow or cc in allow) and cc not in deny


def pick_variant(variants: list[dict], key: str) -> dict | None:
    """Marca para este destino: reparto estable según 'weight' (por defecto, partes iguales)."""
    variants = [v for v in variants if v.get("weight", 1) > 0]
    if not variants:
        return None
    total = sum(v.get("weight", 1) for v in variants)
    n = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % total
    for v in variants:
        n -= v.get("weight", 1)
        if n < 0:
            return v
    return variants[-1]


def dest_info(code: str, ref, overrides: dict | None = None) -> dict:
    """Datos del destino para rellenar las plantillas de URL y textos."""
    cc = ref.country_code(code)
    country_en = ref.country_name_en(cc) if cc else ""
    city_en = ref.city_name_en(code)
    slugs = overrides or {}
    return {
        "iata": code,
        "cc": cc.lower(),
        "city": ref.city_name(code),
        "country": ref.country_name(cc) if cc else "",
        "city_en": quote(city_en),
        "city_slug": slugify(city_en),
        "city_slug_es": slugify(ref.city_name(code)),
        "country_slug": slugs.get(cc) or slugify(country_en),
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _is_home(path: str) -> bool:
    p = path.strip("/")
    return p == "" or bool(re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?", p))


class Extras:
    def __init__(self, conn, cfg: dict, ref, session=None):
        self.conn, self.ref = conn, ref
        self.cfg = cfg.get("extras") or {}
        self.http = session or requests.Session()
        self.token, self.marker = env("TRAVELPAYOUTS_TOKEN"), env("TRAVELPAYOUTS_MARKER")
        self.offline = env("BVB_MOCK") == "1"
        self.checks_left = int(self.cfg.get("max_url_checks_per_run", 150))
        self.links_left = int(self.cfg.get("max_new_links_per_run", 300))
        self.stats = {"verificadas": 0, "no_existen": 0, "enlaces_nuevos": 0, "sin_convertir": 0}
        conn.executescript(SCHEMA)

    # --- ¿Existe la página de la marca para este destino? ---
    def url_ok(self, url: str, last: bool) -> bool:
        if last:  # la portada de la marca: siempre sirve
            return True
        row = self.conn.execute("SELECT ok, checked_at FROM extra_urls WHERE url = ?", (url,)).fetchone()
        days = self.cfg.get("url_cache_days", 30)
        if row and row["checked_at"] >= _iso(_now() - timedelta(days=days if row["ok"] is not None else 3)):
            return row["ok"] != 0  # sin respuesta clara (bloqueo, 403...) se da por buena
        if self.offline or self.checks_left <= 0:
            return False  # sin comprobar todavía: por ahora se usa la siguiente candidata
        self.checks_left -= 1
        ok = None
        try:
            r = self.http.get(url, timeout=15, allow_redirects=True, stream=True,
                              headers={"User-Agent": UA, "Accept-Language": "es-419,es;q=0.9"})
            final = urlsplit(r.url)
            if r.status_code in (404, 410):
                ok = 0
            elif r.status_code < 400:
                # redirigir a la portada = la página no existe (404 "suave")
                ok = 0 if (_is_home(final.path) and not _is_home(urlsplit(url).path)) else 1
            r.close()
        except requests.RequestException:
            pass
        self.stats["verificadas"] += 1
        self.stats["no_existen"] += ok == 0
        self.conn.execute("INSERT OR REPLACE INTO extra_urls VALUES (?, ?, ?)", (url, ok, _iso(_now())))
        return ok != 0

    def best_url(self, templates: list[str], info: dict) -> str:
        for i, t in enumerate(templates):
            try:
                url = t.format(**info)
            except (KeyError, IndexError):
                continue
            if self.url_ok(url, last=i == len(templates) - 1):
                return url
        return ""

    # --- Enlaces de afiliado (API de Travelpayouts, con caché) ---
    def convert(self, pairs: list[tuple[str, str]]) -> dict:
        """[(url, sub_id)] -> {(url, sub_id): enlace de afiliado}. Lo que no se pueda, queda fuera."""
        out, missing = {}, []
        since = _iso(_now() - timedelta(days=self.cfg.get("link_cache_days", 60)))
        for url, sub in dict.fromkeys(pairs):
            row = self.conn.execute(
                "SELECT partner_url FROM extra_links WHERE url = ? AND sub_id = ? AND created_at >= ?",
                (url, sub, since)).fetchone()
            if row:
                out[(url, sub)] = row["partner_url"]
            else:
                missing.append((url, sub))
        trs = self.cfg.get("trs")
        if not missing or self.offline or not (self.token and self.marker and trs):
            return out
        missing = missing[:max(self.links_left, 0)]
        for i in range(0, len(missing), 10):
            chunk = missing[i:i + 10]
            body = {"trs": int(trs), "marker": int(self.marker.split(".")[0]),
                    "shorten": bool(self.cfg.get("shorten", True)),
                    "links": [{"url": u, "sub_id": s} for u, s in chunk]}
            try:
                r = self.http.post(API_URL, json=body, timeout=30,
                                   headers={"X-Access-Token": self.token})
                r.raise_for_status()
                links = ((r.json() or {}).get("result") or {}).get("links") or []
            except (requests.RequestException, ValueError) as e:
                print(f"[aviso] complementos: API de enlaces: {e}")
                break
            for (u, s), x in zip(chunk, links):
                if x.get("code") == "success" and x.get("partner_url"):
                    out[(u, s)] = x["partner_url"]
                    self.conn.execute("INSERT OR REPLACE INTO extra_links VALUES (?, ?, ?, ?)",
                                      (u, s, x["partner_url"], _iso(_now())))
                    self.stats["enlaces_nuevos"] += 1
                else:
                    self.stats["sin_convertir"] += 1
            self.links_left -= len(chunk)
            time.sleep(self.cfg.get("pause_seconds", 0.7))
        self.conn.commit()
        return out

    # --- Bloques por destino ---
    def prepare(self, dests: list[str]) -> dict:
        """{código destino: [bloque, ...]}; cada bloque trae su enlace por página (oferta/ruta)."""
        if not self.cfg.get("enabled"):
            return {}
        services = self.cfg.get("services") or {}
        overrides = self.cfg.get("country_slugs") or {}
        regions = self.cfg.get("regions") or {}
        limit = int(self.cfg.get("max_per_page", 3))
        plan = {}
        for code in dict.fromkeys(dests):
            info = dest_info(code, self.ref, overrides)
            blocks = []
            for sid, s in services.items():
                if len(blocks) >= limit:
                    break
                if info["cc"].upper() in (s.get("skip_countries") or []):
                    continue
                cands = [v for v in s.get("variants") or [] if serves(v, info["cc"].upper(), regions)]
                v = pick_variant(cands, f"{code}:{sid}")
                url = v and self.best_url(v.get("urls") or [], info)
                if not url:
                    continue
                fmt = lambda t: (t or "").format(**info)  # noqa: E731
                if v.get("direct_param"):  # programa directo (p. ej. Civitatis ?aid=...)
                    url += ("&" if "?" in url else "?") + v["direct_param"]
                blocks.append({"service": sid, "brand": v["id"], "icon": s.get("icon", ""),
                               "direct": bool(v.get("direct_param")),
                               "title": fmt(s.get("title")), "text": fmt(s.get("text")),
                               "button": fmt(s.get("button") or "Ver opciones"),
                               "label": v.get("label", v["id"].capitalize()), "url": url})
            plan[code] = blocks
        self.conn.commit()

        pairs = [(b["url"], f"{p}_{b['brand']}") for bs in plan.values() for b in bs for p in PLACES
                 if not b["direct"]]
        links = self.convert(pairs)
        for bs in plan.values():
            for b in bs:
                # sin enlace de afiliado todavía: el directo (Drive lo convierte en el navegador)
                b["links"] = {p: links.get((b["url"], f"{p}_{b['brand']}"), b["url"]) for p in PLACES}
        return plan


def prepare(conn, cfg: dict, ref, dests: list[str]) -> dict:
    ex = Extras(conn, cfg, ref)
    plan = ex.prepare(dests)
    if plan:
        n = sum(len(b) for b in plan.values())
        print(f"Complementos: {n} bloques en {len(plan)} destinos · {ex.stats}")
    return plan
