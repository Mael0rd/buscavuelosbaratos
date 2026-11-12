"""Publica en Telegram un post de ejemplo (la mejor oferta activa de un país, con imagen)
y diagnostica el canal: si el bot es miembro/administrador y si puede publicar y editar.
No cambia el historial (la oferta puede volver a salir normalmente).

Uso:  python -m bvb.post_example costa-rica [general|pais]
"""
import sys
from datetime import datetime, timezone

from . import ogimage, telegram
from .config import env, load_config
from .db import connect
from .site import active_deals


def diagnose(chat: str) -> bool:
    print(f"— Revisando {chat}")
    info = telegram._call("getChat", {"chat_id": chat})
    if not info:
        print("  ✗ Telegram no encuentra ese canal o el bot no tiene acceso: revisa el @ de la variable.")
        return False
    print(f"  canal: {info.get('title')} (@{info.get('username')}) · tipo {info.get('type')}")
    me = telegram._call("getMe", {}) or {}
    m = telegram._call("getChatMember", {"chat_id": chat, "user_id": me.get("id")}) or {}
    status = m.get("status")
    print(f"  bot @{me.get('username')}: {status or 'desconocido'}")
    if status != "administrator":
        print("  ✗ El bot no es administrador: agrégalo en el canal → Administradores, con 'Publicar mensajes'.")
        return False
    print(f"  publicar: {'sí' if m.get('can_post_messages') else 'NO'} · editar: {'sí' if m.get('can_edit_messages') else 'NO'}")
    return bool(m.get("can_post_messages"))


def main(country: str, target: str = "pais") -> None:
    cfg = load_config()
    if country not in cfg["countries"]:
        raise SystemExit(f"País desconocido: {country}. Opciones: {', '.join(cfg['countries'])}")
    if not env("TELEGRAM_BOT_TOKEN"):
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN.")
    chat = telegram.country_channels(cfg).get(country) if target == "pais" else env("TELEGRAM_CHANNEL")
    if not chat:
        raise SystemExit(f"No hay canal configurado ({telegram.channel_var(country) if target == 'pais' else 'TELEGRAM_CHANNEL'}).")
    if not diagnose(chat):
        raise SystemExit(1)

    cname = cfg["countries"][country]["name"]
    deals = [d for d in active_deals(connect(), cfg) if d["country"] == country]
    if not deals:
        text = (f"✅ Canal de {cname} conectado. Aquí publicaremos los vuelos baratos verificados "
                f"desde {cname}.")
        ok = telegram.send(text, {"inline_keyboard": [[{"text": "Ver ofertas",
                                  "url": f"https://{cfg['site']['domain']}/pais/{country}"}]]}, chat_id=chat)
        print(text)
    else:
        d = deals[0]
        text, markup = telegram.build_message(d, f"https://{cfg['site']['domain']}", cname,
                                              datetime.now(timezone.utc))
        photo = ogimage.deal_image_bytes(d, cfg["countries"][country].get("cc", ""))
        ok = (photo and telegram.send_photo(photo, text, markup, chat)) or telegram.send(text, markup, chat_id=chat)
        print(text)
        print(f"\nOferta: {d['origin_name']} → {d['dest_name']} ${d['price']:.0f} · {'con imagen' if photo else 'solo texto'}")
    if not ok:
        raise SystemExit("Telegram rechazó el mensaje (revisa el error de arriba).")
    print(f"\n✓ Publicado en {chat}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "costa-rica", sys.argv[2] if len(sys.argv) > 2 else "pais")
