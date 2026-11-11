"""Frescura de precios: cuándo se vio realmente cada tarifa.

prices_for_dates devuelve precios de hasta 48 h atrás sin decir cuándo se
vieron. Para publicar con honestidad se consulta /v2/prices/latest de la ruta,
que sí trae `found_at`, y se busca el mismo viaje (mismas fechas de ida y vuelta).
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from .config import env

LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_hours(found_at: str | None, now: datetime | None = None) -> float | None:
    dt = parse_ts(found_at)
    if not dt:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


class Checker:
    """Consulta (con caché por corrida) los precios recientes de una ruta."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.fcfg = cfg["freshness"]
        self.cache: dict[tuple, list] = {}
        self.calls = 0
        self.stats = {"match": 0, "higher": 0, "none": 0}

    def _entries(self, origin: str, destination: str) -> list[dict]:
        key = (origin, destination)
        if key in self.cache:
            return self.cache[key]
        if env("BVB_MOCK") == "1":
            # Datos de prueba: el mismo viaje visto hace 1 hora
            self.cache[key] = None  # se resuelve en check()
            return None
        if not env("TRAVELPAYOUTS_TOKEN"):
            self.cache[key] = []
            return []
        params = {
            "origin": origin, "destination": destination,
            "currency": self.cfg["site"]["currency"], "period_type": "year",
            "one_way": "false", "page": 1, "limit": 100,
            "show_to_affiliates": "false", "sorting": "price",
            "token": env("TRAVELPAYOUTS_TOKEN"),
        }
        try:
            r = requests.get(LATEST_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json().get("data") or []
        except Exception as e:
            print(f"[frescura] {origin}-{destination}: {e}")
            data = []
        self.calls += 1
        time.sleep(self.fcfg.get("pause_seconds", 0.25))
        self.cache[key] = data
        return data

    def check(self, deal: dict, now: datetime | None = None) -> tuple[str, str | None]:
        """Devuelve (estado, found_at):
        - "match":  el mismo viaje se vio a este precio (o menos); found_at = cuándo.
        - "higher": el mismo viaje se vio después, pero más caro.
        - "none":   no hay registro reciente de ese viaje."""
        now = now or datetime.now(timezone.utc)
        entries = self._entries(deal["origin"], deal["destination"])
        if entries is None:  # modo prueba
            self.stats["match"] += 1
            return "match", iso(now - timedelta(hours=1))

        dep = (deal.get("departure_at") or "")[:10]
        ret = (deal.get("return_at") or "")[:10]
        tol = self.fcfg["price_tolerance"]
        same = [e for e in entries
                if str(e.get("depart_date", ""))[:10] == dep
                and str(e.get("return_date") or "")[:10] == ret
                and e.get("value") is not None]
        ok = [e for e in same if float(e["value"]) <= deal["price"] * (1 + tol)]
        if ok:
            found = max((parse_ts(e.get("found_at")) for e in ok), default=None,
                        key=lambda x: x or datetime.min.replace(tzinfo=timezone.utc))
            if found:
                self.stats["match"] += 1
                return "match", iso(found)
        prev = parse_ts(deal.get("found_at"))
        newer_higher = [e for e in same
                        if float(e["value"]) > deal["price"] * (1 + tol)
                        and (not prev or (parse_ts(e.get("found_at")) or prev) > prev)]
        if newer_higher:
            self.stats["higher"] += 1
            return "higher", None
        self.stats["none"] += 1
        return "none", None

    def is_fresh(self, deal: dict, now: datetime | None = None) -> str | None:
        """found_at si el viaje se vio hace menos de max_age_hours; si no, None."""
        status, found_at = self.check(deal, now)
        if status == "match" and age_hours(found_at, now) <= self.fcfg["max_age_hours"]:
            return found_at
        return None


def revalidate(conn, checker: Checker, cfg: dict, now: datetime | None = None) -> list[int]:
    """Revisa las ofertas activas y marca como terminadas las que ya no se
    pueden respaldar. Devuelve los ids que terminaron en esta corrida."""
    now = now or datetime.now(timezone.utc)
    fcfg = cfg["freshness"]
    rows = conn.execute(
        """SELECT * FROM deals WHERE status='active'
           AND published_at >= datetime('now', ?)""",
        (f"-{cfg['deals']['show_days']} days",)).fetchall()
    expired = []
    for r in rows:
        d = dict(r)
        reason = None
        dep = parse_ts((d["departure_at"] or "")[:10] + "T00:00:00Z")
        if dep and dep - now < timedelta(days=fcfg["min_days_before_departure"]):
            reason = "salida"
        else:
            status, found_at = checker.check(d, now)
            if status == "match":
                best = max(filter(None, [d.get("found_at"), found_at]), key=lambda s: parse_ts(s))
                conn.execute("UPDATE deals SET found_at=?, last_checked_at=? WHERE id=?",
                             (best, iso(now), d["id"]))
                d["found_at"] = best
            elif status == "higher":
                reason = "subio"
            a = age_hours(d.get("found_at"), now)
            if not reason and (a is None or a > fcfg["stale_hours"]):
                reason = "sin_confirmar"
        if reason:
            conn.execute(
                "UPDATE deals SET status='expired', expired_at=?, expire_reason=? WHERE id=?",
                (iso(now), reason, d["id"]))
            expired.append(d["id"])
    conn.commit()
    return expired
