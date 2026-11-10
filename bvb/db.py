import sqlite3

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    origin TEXT, destination TEXT, depart_month TEXT,
    price REAL, airline TEXT, departure_at TEXT, return_at TEXT,
    transfers INTEGER, link TEXT,
    found_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_obs_route ON observations(origin, destination, found_at);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE,
    origin TEXT, destination TEXT, depart_month TEXT,
    price REAL, baseline REAL, airline TEXT,
    departure_at TEXT, return_at TEXT, transfers INTEGER, link TEXT,
    copy_web TEXT, copy_social TEXT,
    published_at TEXT DEFAULT (datetime('now')),
    telegram_sent INTEGER DEFAULT 0
);
"""


def connect(path=DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
