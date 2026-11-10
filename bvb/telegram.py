import requests

from .config import env


def send(text: str) -> bool:
    token, channel = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHANNEL")
    if not token or not channel:
        print("[telegram] sin credenciales, se omite")
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel, "text": text, "disable_web_page_preview": False},
        timeout=20,
    )
    if not r.ok:
        print(f"[telegram] error {r.status_code}: {r.text[:200]}")
    return r.ok


def publish_pending(conn, site_url: str) -> int:
    if not env("TELEGRAM_BOT_TOKEN") or not env("TELEGRAM_CHANNEL"):
        print("[telegram] sin credenciales, se omite")
        return 0
    rows = conn.execute(
        "SELECT * FROM deals WHERE telegram_sent=0 ORDER BY published_at"
    ).fetchall()
    sent = 0
    for row in rows:
        text = row["copy_social"] + f"\n🔎 Más ofertas: {site_url}"
        if send(text):
            conn.execute("UPDATE deals SET telegram_sent=1 WHERE id=?", (row["id"],))
            sent += 1
    conn.commit()
    return sent
