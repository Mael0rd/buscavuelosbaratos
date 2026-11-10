import sqlite3

from .config import DATA_DIR, DB_PATH

SCHEMA = """
-- Precio mínimo visto cada día por ruta (origen-destino): base para la mediana
CREATE TABLE IF NOT EXISTS prices_daily (
    origin TEXT, destination TEXT, day TEXT, min_price REAL,
    PRIMARY KEY (origin, destination, day)
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE,
    country TEXT, flag TEXT,
    origin TEXT, origin_name TEXT, origin_airport TEXT,
    destination TEXT, dest_name TEXT, dest_country TEXT, destination_airport TEXT,
    price REAL, baseline REAL, threshold REAL, score REAL,
    airline TEXT, airline_name TEXT,
    departure_at TEXT, return_at TEXT, transfers INTEGER, link TEXT,
    copy_web TEXT, copy_social TEXT,
    published_at TEXT DEFAULT (datetime('now')),
    telegram_sent INTEGER DEFAULT 0   -- 0 pendiente, 1 enviado, 2 omitido
);
CREATE INDEX IF NOT EXISTS idx_deals_route ON deals(origin, destination, published_at);

-- Avisos enviados por alerta (para no repetir)
CREATE TABLE IF NOT EXISTS alert_log (
    sub_id INTEGER, price REAL, sent_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alert_log ON alert_log(sub_id, sent_at);
"""


def connect(path=DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
