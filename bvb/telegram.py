import requests

from .config import env


def send(text: str) -> bool:
    r = requests.post(
        f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/sendMessage",
        json={"chat_id": env("TELEGRAM_CHANNEL"), "text": text},
        timeout=20,
    )
    if not r.ok:
        print(f"[telegram] error {r.status_code}: {r.text[:200]}")
    return r.ok


def publish_pending(conn, site_url: str, max_per_run: int) -> int:
    """Publica las mejores ofertas nuevas (hasta max_per_run). El resto queda
    solo en la web, para no saturar el canal."""
    if not env("TELEGRAM_BOT_TOKEN") or not env("TELEGRAM_CHANNEL"):
        print("[telegram] sin credenciales, se omite")
        return 0
    # Pendientes viejas (p. ej. de antes de conectar Telegram) no se envían
    conn.execute("""UPDATE deals SET telegram_sent=2
                    WHERE telegram_sent=0 AND published_at < datetime('now', '-1 day')""")
    rows = conn.execute(
        "SELECT * FROM deals WHERE telegram_sent=0 ORDER BY score ASC").fetchall()
    sent = 0
    for i, row in enumerate(rows):
        if i >= max_per_run:
            conn.execute("UPDATE deals SET telegram_sent=2 WHERE id=?", (row["id"],))
            continue
        text = row["copy_social"] + f"\n🔎 Más ofertas desde tu país: {site_url}/pais/{row['country']}.html"
        if send(text):
            conn.execute("UPDATE deals SET telegram_sent=1 WHERE id=?", (row["id"],))
            sent += 1
    conn.commit()
    return sent
