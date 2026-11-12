-- Alertas de rutas (Telegram o correo)
CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL,                 -- 'telegram' | 'email'
  address TEXT NOT NULL,                 -- chat_id o correo
  origin TEXT NOT NULL,
  origin_name TEXT,
  destination TEXT NOT NULL,
  dest_name TEXT,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | active | removed
  token TEXT NOT NULL UNIQUE,            -- para confirmar / darse de baja
  created_at TEXT DEFAULT (datetime('now')),
  confirmed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_sub ON subscriptions(channel, address, origin, destination);

-- Estado de la conversación con el bot (pregunta origen -> destino)
CREATE TABLE IF NOT EXISTS bot_state (
  chat_id TEXT PRIMARY KEY,
  step TEXT,
  origin TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Valores privados que el buscador necesita guardar entre corridas (p. ej. el token
-- de Threads, que se renueva cada pocas semanas). Solo con la clave de administrador.
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT DEFAULT (datetime('now'))
);
