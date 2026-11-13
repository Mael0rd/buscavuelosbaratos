"""Acceso a la página de Facebook y al Instagram conectado con un token de usuario del sistema.

El usuario del sistema se crea en el portafolio empresarial (Business Manager →
Usuarios del sistema), con la app, la página y el perfil de Instagram asignados.
Su token NO vence, así que no hay que renovarlo. Va en el secret META_SYSTEM_TOKEN.
Permisos: instagram_basic, instagram_content_publish, pages_show_list,
pages_read_engagement y pages_manage_posts.

Del token se sacan: la página (su ID y su token de página, para publicar en Facebook)
y el ID de la cuenta de Instagram conectada a esa página (para publicar en Instagram).
"""
import requests

from .config import env

GRAPH = "https://graph.facebook.com/v21.0"
_cache: dict = {}


def session(page_hint: str = "") -> dict | None:
    """{token, page_id, page_name, page_token, ig_id, ig_username} o None si no hay token o no sirve."""
    token = env("META_SYSTEM_TOKEN").strip()
    if not token:
        return None
    if token in _cache:
        return _cache[token]
    try:
        r = requests.get(f"{GRAPH}/me/accounts", timeout=20, params={
            "fields": "id,name,username,access_token,instagram_business_account{id,username}",
            "access_token": token})
        pages = r.json().get("data", []) if r.ok else []
    except Exception:
        pages = []
    if not pages:
        print("[meta] ⚠ el token META_SYSTEM_TOKEN no ve ninguna página (¿falta asignar la página al "
              "usuario del sistema o el permiso pages_show_list?)")
        _cache[token] = None
        return None
    hint = page_hint.lower()
    page = next((p for p in pages if hint and hint in (p.get("username", "") + p.get("name", "")).lower()), pages[0])
    ig = page.get("instagram_business_account") or {}
    s = {"token": token, "page_id": page["id"], "page_name": page.get("name", ""),
         "page_token": page.get("access_token") or token,
         "ig_id": ig.get("id", ""), "ig_username": ig.get("username", "")}
    _cache[token] = s
    return s
