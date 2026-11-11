"""Verificación en vivo con Google Flights antes de publicar en Telegram.

Travelpayouts (caché, gratis) encuentra las candidatas; aquí se confirma la
mejor justo antes de publicarla:
  - el mismo viaje (mismas fechas, máx. 1 escala) sigue a ese precio (± tolerancia), y
  - si Google da su "nivel de precio" para la ruta, debe ser "low" (bajo).

Proveedores en cadena (cuenta propia en cada uno): SerpApi → Apify.
El presupuesto mensual se reparte solo: (lo que queda del mes) ÷ (días que
faltan), y cada hora usa una fracción de lo del día. Una verificación sirve
para todos los canales (se guarda en la oferta por `cache_hours`).
"""
import math
from calendar import monthrange
from datetime import datetime, timedelta, timezone

import requests

from .config import env
from .fresh import age_hours, iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS verify_log (
    ts TEXT, provider TEXT, deal_id INTEGER,
    result TEXT,            -- ok | subio | no_es_baja | sin_resultados | quota | error
    live_price REAL, level TEXT
);
CREATE INDEX IF NOT EXISTS idx_verify_log ON verify_log(ts);
"""
SPENT = ("ok", "subio", "no_es_baja", "sin_resultados")  # resultados que gastaron una búsqueda


class QuotaExceeded(Exception):
    pass


# ---------- proveedores ----------
def _find(obj, *names):
    """Busca recursivamente la primera clave con alguno de esos nombres."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in names:
                return v
        for v in obj.values():
            r = _find(v, *names)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, *names)
            if r is not None:
                return r
    return None


def _range(v):
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return float(v[0]), float(v[1])
    if isinstance(v, dict):
        lo = v.get("low_price", v.get("low"))
        hi = v.get("high_price", v.get("high"))
        if lo is not None and hi is not None:
            return float(lo), float(hi)
    return None, None


def parse_serpapi(data: dict) -> dict:
    if data.get("error"):
        msg = str(data["error"])
        if "run out" in msg.lower() or "limit" in msg.lower():
            raise QuotaExceeded(msg)
        if "no results" in msg.lower() or "hasn't returned any results" in msg.lower():
            return {"price": None, "level": None, "low": None, "high": None}
        raise RuntimeError(msg)
    prices = [f["price"] for f in (data.get("best_flights") or []) + (data.get("other_flights") or [])
              if isinstance(f.get("price"), (int, float))]
    ins = data.get("price_insights") or {}
    lo, hi = _range(ins.get("typical_price_range"))
    price = min(prices) if prices else ins.get("lowest_price")
    return {"price": float(price) if price is not None else None,
            "level": (ins.get("price_level") or None), "low": lo, "high": hi}


class SerpApi:
    name = "serpapi"
    URL = "https://serpapi.com/search.json"

    def __init__(self, monthly: int):
        self.monthly = monthly

    @property
    def configured(self) -> bool:
        return bool(env("SERPAPI_KEY"))

    def search(self, origin: str, dest: str, dep: str, ret: str) -> dict:
        params = {"engine": "google_flights", "departure_id": origin, "arrival_id": dest,
                  "outbound_date": dep, "return_date": ret, "type": 1, "adults": 1,
                  "stops": 2,  # 1 escala o menos
                  "currency": "USD", "hl": "es", "api_key": env("SERPAPI_KEY")}
        r = requests.get(self.URL, params=params, timeout=60)
        if r.status_code == 429:
            raise QuotaExceeded(r.text[:200])
        try:
            data = r.json()
        except ValueError:
            r.raise_for_status()
            raise
        return parse_serpapi(data)


def parse_apify(items: list) -> dict:
    best = None
    for it in items or []:
        its = it.get("itineraries") or []
        if any(len(i.get("segments") or []) > 2 for i in its):
            continue  # más de 1 escala
        p = _find(it.get("price") or {}, "grandTotal", "total")
        if p is None:
            p = it.get("price") if isinstance(it.get("price"), (int, float)) else None
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        if best is None or p < best[0]:
            best = (p, it)
    if not best:
        return {"price": None, "level": None, "low": None, "high": None}
    lvl = _find(best[1], "price_level", "priceLevel")
    lo, hi = _range(_find(best[1], "typical_price_range", "typicalPriceRange"))
    return {"price": best[0], "level": (str(lvl).lower() if lvl else None), "low": lo, "high": hi}


class Apify:
    name = "apify"
    URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

    def __init__(self, monthly: int, actor: str):
        self.monthly = monthly
        self.actor = actor

    @property
    def configured(self) -> bool:
        return bool(env("APIFY_TOKEN"))

    def search(self, origin: str, dest: str, dep: str, ret: str) -> dict:
        body = {"endpoint": "flight-offers", "originLocationCode": origin,
                "destinationLocationCode": dest, "departureDate": dep, "returnDate": ret,
                "adults": 1, "max": 3, "currencyCode": "USD"}
        r = requests.post(self.URL.format(actor=self.actor), params={"token": env("APIFY_TOKEN"), "timeout": 120},
                          json=body, timeout=150)
        if r.status_code in (402, 403):
            raise QuotaExceeded(r.text[:200])
        r.raise_for_status()
        return parse_apify(r.json())


class Mock:
    """Modo prueba (BVB_MOCK=1): confirma el precio y lo marca como bajo."""
    name = "mock"
    monthly = 10_000
    configured = True

    def __init__(self, deal_price_of):
        self.deal_price_of = deal_price_of

    def search(self, origin, dest, dep, ret):
        return {"price": self.deal_price_of(), "level": "low", "low": None, "high": None}


# ---------- verificador con presupuesto ----------
class Verifier:
    def __init__(self, conn, cfg: dict, now: datetime | None = None, providers: list | None = None):
        self.conn, self.cfg = conn, cfg
        self.vcfg = cfg["verify"]
        self.now = now or datetime.now(timezone.utc)
        conn.executescript(SCHEMA)
        self._current_price = None
        if providers is not None:
            self.providers = providers
        elif env("BVB_MOCK") == "1":
            self.providers = [Mock(lambda: self._current_price)]
        else:
            self.providers = [SerpApi(self.vcfg["serpapi_monthly"]),
                              Apify(self.vcfg["apify_monthly"], self.vcfg["apify_actor"])]
        self.providers = [p for p in self.providers if p.configured]
        self.run_stats = {"ok": 0, "rechazadas": 0, "desde_cache": 0, "sin_presupuesto": 0}

    # --- uso ---
    def _count(self, where: str, args=()) -> int:
        return self.conn.execute(
            f"SELECT COUNT(*) FROM verify_log WHERE result IN ({','.join('?' * len(SPENT))}) AND {where}",
            (*SPENT, *args)).fetchone()[0]

    def _month(self) -> str:
        return self.now.strftime("%Y-%m")

    def used_month(self, provider: str | None = None) -> int:
        if provider:
            return self._count("substr(ts,1,7)=? AND provider=?", (self._month(), provider))
        return self._count("substr(ts,1,7)=?", (self._month(),))

    def exhausted(self, provider: str) -> bool:
        p = next(x for x in self.providers if x.name == provider)
        quota_hit = self.conn.execute(
            "SELECT 1 FROM verify_log WHERE result='quota' AND provider=? AND substr(ts,1,7)=? LIMIT 1",
            (provider, self._month())).fetchone()
        return bool(quota_hit) or self.used_month(provider) >= p.monthly

    def budget(self) -> dict:
        monthly = sum(p.monthly for p in self.providers)
        used = self.used_month()
        remaining = max(0, monthly - used)
        days_left = monthrange(self.now.year, self.now.month)[1] - self.now.day + 1
        daily = remaining / days_left if days_left else 0
        used_today = self._count("substr(ts,1,10)=?", (self.now.strftime("%Y-%m-%d"),))
        used_hour = self._count("substr(ts,1,13)=?", (self.now.strftime("%Y-%m-%dT%H"),))
        q = self.cfg["social"]["quiet_hours"]
        active = 24 - ((q[1] - q[0]) % 24) if q[0] != q[1] else 24
        hour_cap = max(1, math.ceil((daily + used_today) / active))
        allowed = max(0, min(hour_cap - used_hour, math.floor(daily + used_today) - used_today, remaining))
        return {"monthly": monthly, "used_month": used, "daily": round(daily + used_today, 1),
                "used_today": used_today, "allowed_now": allowed}

    def _log(self, provider, deal_id, result, price=None, level=None):
        self.conn.execute("INSERT INTO verify_log VALUES (?,?,?,?,?,?)",
                          (iso(self.now), provider, deal_id, result, price, level))
        self.conn.commit()

    # --- verificación ---
    def _search(self, deal: dict, deal_id):
        dep = (deal["departure_at"] or "")[:10]
        ret = (deal.get("return_at") or "")[:10]
        o = deal.get("origin_airport") or deal["origin"]
        d = deal.get("destination_airport") or deal["destination"]
        self._current_price = deal["price"]
        for p in self.providers:
            if self.exhausted(p.name):
                continue
            try:
                return p.name, p.search(o, d, dep, ret)
            except QuotaExceeded as e:
                print(f"[verificación] {p.name} sin cupo este mes: {e}")
                self._log(p.name, deal_id, "quota")
            except Exception as e:
                print(f"[verificación] {p.name} error: {e}")
                self._log(p.name, deal_id, "error")
        return None, None

    def ensure(self, deal: dict) -> str:
        """'ok' si la oferta está verificada (ahora o hace < cache_hours),
        'rechazada' si no pasó, 'sin_presupuesto' si no se pudo verificar."""
        cached_age = age_hours(deal.get("verified_at"), self.now)
        if deal.get("verify_status") == "ok" and cached_age is not None and cached_age <= self.vcfg["cache_hours"]:
            self.run_stats["desde_cache"] += 1
            return "ok"
        if not self.providers or self.budget()["allowed_now"] <= 0:
            self.run_stats["sin_presupuesto"] += 1
            return "sin_presupuesto"
        provider, res = self._search(deal, deal["id"])
        if res is None:
            self.run_stats["sin_presupuesto"] += 1
            return "sin_presupuesto"

        live, level = res["price"], (res["level"] or "").lower() or None
        tol = self.vcfg["price_tolerance"]
        if live is None:
            result = "sin_resultados"
        elif live > deal["price"] * (1 + tol):
            result = "subio"
        elif self.vcfg["require_low_level"] and level and level != "low":
            result = "no_es_baja"
        else:
            result = "ok"
        self._log(provider, deal["id"], result, live, level)

        fields = {"verified_at": iso(self.now), "live_price": live, "price_level": level,
                  "typical_low": res["low"], "typical_high": res["high"],
                  "verify_status": "ok" if result == "ok" else "rechazada"}
        if result == "ok" and live and live > deal["price"]:
            fields["price"] = live  # se muestra el mayor: nunca prometer menos de lo real
        if result == "subio":  # Google confirma que subió: la oferta termina en todos lados
            fields.update(status="expired", expired_at=iso(self.now), expire_reason="subio")
        self.conn.execute(f"UPDATE deals SET {', '.join(k + '=?' for k in fields)} WHERE id=?",
                          (*fields.values(), deal["id"]))
        self.conn.commit()
        deal.update(fields)
        self.run_stats["ok" if result == "ok" else "rechazadas"] += 1
        return "ok" if result == "ok" else "rechazada"

    def summary(self) -> str:
        b = self.budget()
        per = ", ".join(f"{p.name} {self.used_month(p.name)}/{p.monthly}" for p in self.providers) or "sin proveedores"
        return (f"Verificación: este mes {b['used_month']}/{b['monthly']} ({per}) · hoy {b['used_today']}"
                f"/{b['daily']:.0f} · esta corrida {self.run_stats}")
