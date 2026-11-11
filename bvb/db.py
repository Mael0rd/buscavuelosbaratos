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
    telegram_sent INTEGER DEFAULT 0,  -- (versión anterior; ya no se usa)
    status TEXT DEFAULT 'active', found_at TEXT, last_checked_at TEXT,
    expired_at TEXT, expire_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_deals_route ON deals(origin, destination, published_at);

-- Avisos enviados por alerta (para no repetir)
CREATE TABLE IF NOT EXISTS alert_log (
    sub_id INTEGER, price REAL, sent_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alert_log ON alert_log(sub_id, sent_at);

-- Posts publicados en Telegram (para cupos por canal y editar los que terminan)
CREATE TABLE IF NOT EXISTS telegram_posts (
    deal_id INTEGER, chat_id TEXT, message_id INTEGER,
    posted_at TEXT DEFAULT (datetime('now')),
    edited INTEGER DEFAULT 0          -- 1 marcado como terminado, 2 no se pudo editar
);
CREATE INDEX IF NOT EXISTS idx_tg_posts ON telegram_posts(chat_id, posted_at);
"""

# Columnas agregadas después de la primera versión (se crean si faltan)
MIGRATIONS = {
    "deals": {
        "status": "TEXT DEFAULT 'active'",   # active | expired
        "found_at": "TEXT",                  # cuándo se vio el precio (UTC, ISO)
        "last_checked_at": "TEXT",
        "expired_at": "TEXT",
        "expire_reason": "TEXT",             # subio | sin_confirmar | salida
    },
}


def connect(path=DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.commit()
    return conn
