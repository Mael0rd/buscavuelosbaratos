"""Imágenes para compartir (Open Graph, 1200x630): la vista previa que muestran
WhatsApp, Facebook, X, Telegram y LinkedIn cuando alguien comparte un enlace.

Se generan en cada corrida con Pillow, sin servicios externos:
  - una por oferta (destino grande, precio, fechas, bandera de origen)
  - una por país, una por ciudad de origen y una general para el resto.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import ROOT, STATIC_DIR
from .copywriter import fmt_date, fmt_stops

W, H = 1200, 630
FONTS = ROOT / "assets" / "fonts"
NAVY = (20, 33, 61)
ORANGE = (232, 93, 4)
WHITE = (255, 255, 255)
SOFT = (255, 255, 255, 215)

# Mismos degradados que las tarjetas de la web (.tone-0 … .tone-5)
TONES = [
    [(217, 119, 6), (234, 88, 12), (190, 18, 60)],
    [(3, 105, 161), (67, 56, 202), (30, 41, 59)],
    [(6, 182, 212), (20, 184, 166), (37, 99, 235)],
    [(5, 150, 105), (13, 148, 136), (19, 78, 74)],
    [(147, 51, 234), (192, 38, 211), (76, 29, 149)],
    [(180, 83, 9), (146, 64, 14), (68, 64, 60)],
]

_font_cache: dict = {}


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _font_cache:
        path = FONTS / f"Inter-{weight}.otf"
        try:
            _font_cache[key] = ImageFont.truetype(str(path), size)
        except OSError:  # sin la fuente, una genérica (no rompe la corrida)
            _font_cache[key] = ImageFont.load_default(size)
    return _font_cache[key]


def gradient(colors: list[tuple]) -> Image.Image:
    """Degradado diagonal de 3 colores + oscurecido abajo para que el texto se lea."""
    small = Image.new("RGB", (W // 10, H // 10))
    px = small.load()
    sw, sh = small.size
    for y in range(sh):
        for x in range(sw):
            t = (x / sw * 0.7 + y / sh * 0.3)
            if t < 0.5:
                a, b, k = colors[0], colors[1], t / 0.5
            else:
                a, b, k = colors[1], colors[2], (t - 0.5) / 0.5
            shade = 1 - 0.35 * (y / sh)
            px[x, y] = tuple(int((a[i] + (b[i] - a[i]) * k) * shade) for i in range(3))
    return small.resize((W, H), Image.BICUBIC)


def fit(draw, text: str, weight: str, max_size: int, max_w: int, min_size: int = 40):
    """Fuente más grande (hasta max_size) con la que el texto cabe en max_w."""
    size = max_size
    while size > min_size:
        f = font(weight, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return font(weight, min_size)


def ellipsize(draw, text: str, f, max_w: int) -> str:
    if draw.textlength(text, font=f) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def brand(draw, x: int = 64, y: int = 52):
    f = font("ExtraBold", 38)
    draw.text((x, y), "Busca Vuelos ", font=f, fill=WHITE)
    w = draw.textlength("Busca Vuelos ", font=f)
    draw.text((x + w, y), "Baratos", font=f, fill=(255, 196, 140))
    return f


def paste_flag(img, cc: str, x: int, y: int, h: int = 42) -> int:
    """Pega la bandera (PNG de static/flags) y devuelve el ancho usado."""
    p = STATIC_DIR / "flags" / f"{(cc or '').lower()}.png"
    if not cc or not p.exists():
        return 0
    flag = Image.open(p).convert("RGBA")
    flag = flag.resize((int(flag.width * h / flag.height), h), Image.LANCZOS)
    mask = Image.new("L", flag.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, flag.width - 1, h - 1), radius=6, fill=255)
    img.paste(flag, (x, y), mask)
    return flag.width


def pill(draw, x: int, y: int, text: str, f, fill=ORANGE, color=WHITE, pad_x: int = 34, pad_y: int = 18):
    w = draw.textlength(text, font=f)
    asc, desc = f.getmetrics()
    box = (x, y, x + w + 2 * pad_x, y + asc + desc + 2 * pad_y)
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    draw.text((x + pad_x, y + pad_y), text, font=f, fill=color)
    return box


def save(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=84, optimize=True, progressive=True)


# ---------- imágenes ----------
def deal_tone(d: dict) -> int:
    return d["tone"] if d.get("tone") is not None else sum(map(ord, d.get("destination") or "")) % len(TONES)


def deal_image(d: dict, cc: str, path: Path, ended: bool = False):
    """Imagen de la oferta. ended=True: en gris, precio tachado y sello 'OFERTA TERMINADA'."""
    img = gradient(TONES[deal_tone(d)])
    if ended:
        img = Image.blend(img, img.convert("L").convert("RGB"), 0.85)
    draw = ImageDraw.Draw(img, "RGBA")
    brand(draw)

    # Origen con bandera
    y = 150
    fw = paste_flag(img, cc, 64, y + 4)
    f_small = font("Medium", 38)
    origin = f"Desde {d['origin_name']} ({d['origin']})"
    draw.text((64 + (fw + 16 if fw else 0), y), ellipsize(draw, origin, f_small, 1000), font=f_small, fill=SOFT)

    # Destino grande
    dest = d["dest_name"]
    f_dest = fit(draw, dest, "ExtraBold", 132, W - 128, 64)
    draw.text((60, 205), dest, font=f_dest, fill=WHITE)
    if d.get("dest_country") and d["dest_country"] != dest:
        draw.text((64, 205 + f_dest.size + 18), d["dest_country"], font=font("Medium", 36), fill=SOFT)

    # Precio + detalles
    box = pill(draw, 64, 440, f"${d['price']:.0f}", font("ExtraBold", 76), fill=WHITE, color=(194, 65, 12))
    x = box[2] + 30
    draw.text((x, 452), "ida y vuelta", font=font("Bold", 36), fill=WHITE)
    dates = fmt_date(d.get("departure_at", ""))
    if d.get("return_at"):
        dates += f" – {fmt_date(d['return_at'])}"
    detail = f"{dates} · {fmt_stops(d.get('transfers'))}"
    draw.text((x, 500), ellipsize(draw, detail, font("Medium", 32), W - x - 64), font=font("Medium", 32), fill=SOFT)

    if ended:
        mid = (box[1] + box[3]) // 2
        draw.line((box[0] + 18, mid + 6, box[2] - 18, mid - 6), fill=(190, 18, 60), width=8)
        f = font("ExtraBold", 50)
        tw = int(draw.textlength("OFERTA TERMINADA", font=f))
        sw, sh = tw + 80, 112
        stamp = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle((4, 4, sw - 5, sh - 5), radius=18, fill=(190, 18, 60, 240), outline=WHITE, width=5)
        sd.text((40, 26), "OFERTA TERMINADA", font=f, fill=WHITE)
        stamp = stamp.rotate(8, expand=True, resample=Image.BICUBIC)
        img.paste(stamp, (W - stamp.width - 40, 40), stamp)
    elif d.get("verify_status") == "ok":
        draw.text((64, 572), "✓ Precio verificado en Google Flights", font=font("Bold", 28), fill=(220, 255, 236))
    save(img, path)


def deal_image_bytes(d: dict, cc: str, ended: bool = False) -> bytes | None:
    """La imagen en memoria (para Telegram). None si no se pudo generar."""
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "o.jpg"
            deal_image(d, cc, p, ended=ended)
            return p.read_bytes()
    except Exception as e:  # noqa: BLE001 — sin imagen se publica como texto
        print(f"[imagen] no se pudo generar: {e}")
        return None


def page_image(title: str, subtitle: str, path: Path, cc: str = "", tone: int = 1, kicker: str = ""):
    img = gradient(TONES[tone % len(TONES)])
    draw = ImageDraw.Draw(img, "RGBA")
    brand(draw)
    y = 160
    if kicker or cc:
        fw = paste_flag(img, cc, 64, y + 4)
        if kicker:
            draw.text((64 + (fw + 16 if fw else 0), y), kicker, font=font("Medium", 38), fill=SOFT)
        y += 70
    # Título en hasta 2 líneas
    words, lines, cur = title.split(), [], ""
    f = font("ExtraBold", 92)
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= W - 128 or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
        f = fit(draw, max(lines, key=len), "ExtraBold", 92, W - 128, 56)
    for line in lines:
        draw.text((60, y), line, font=f, fill=WHITE)
        y += int(f.size * 1.12)
    if subtitle:
        draw.text((64, y + 10), ellipsize(draw, subtitle, font("Medium", 36), W - 128),
                  font=font("Medium", 36), fill=SOFT)
        y += 60
    pill(draw, 64, min(max(y + 28, 500), 545), "Ofertas verificadas · cada hora", font("Bold", 30), fill=WHITE, color=NAVY, pad_x=26, pad_y=14)
    save(img, path)


# ---------- imagen vertical para redes (Threads / Instagram) ----------
SW, SH = 1080, 1350  # 4:5: el formato que más pantalla ocupa en el feed del celular
MONTHS_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_photo_cache: dict = {}


def photo_url(url: str) -> str:
    """Foto de Unsplash recortada a 1080x1350 (vacío si no hay foto)."""
    if not url or "images.unsplash.com" not in url:
        return ""
    return url.split("?")[0] + f"?auto=format&fit=crop&q=75&w={SW}&h={SH}"


def fetch_photo(url: str) -> Image.Image | None:
    """Descarga la foto del destino (una vez por corrida). None si falla: se usa el degradado."""
    if not url:
        return None
    if url not in _photo_cache:
        import io
        import requests
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            _photo_cache[url] = Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            print(f"[imagen] sin foto ({e.__class__.__name__}); se usa el degradado")
            _photo_cache[url] = None
    return _photo_cache[url]


def short_dates(dep: str, ret: str = "") -> str:
    """'3–17 feb', '28 feb – 6 mar'."""
    def p(s):
        return int(s[8:10]), int(s[5:7])
    if not dep or len(dep) < 10:
        return ""
    d1, m1 = p(dep)
    if not ret or len(ret) < 10:
        return f"{d1} {MONTHS_SHORT[m1 - 1]}"
    d2, m2 = p(ret)
    if m1 == m2:
        return f"{d1}–{d2} {MONTHS_SHORT[m1 - 1]}"
    return f"{d1} {MONTHS_SHORT[m1 - 1]} – {d2} {MONTHS_SHORT[m2 - 1]}"


def _cover(photo: Image.Image) -> Image.Image:
    """Recorta la foto para llenar 1080x1350 sin deformarla."""
    k = max(SW / photo.width, SH / photo.height)
    p = photo.resize((int(photo.width * k) + 1, int(photo.height * k) + 1), Image.LANCZOS)
    x, y = (p.width - SW) // 2, (p.height - SH) // 2
    return p.crop((x, y, x + SW, y + SH))


def _shade(img: Image.Image) -> Image.Image:
    """Oscurece arriba (marca y origen) y sobre todo abajo (precio), dejando ver la foto al centro."""
    ov = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    px = ov.load()
    for y in range(SH):
        t = y / SH
        a = 160 * max(0.0, 1 - t / 0.28) + 245 * max(0.0, (t - 0.36) / 0.64) ** 0.75
        a = int(min(240, a))
        for x in range(0, SW, 1):
            px[x, y] = (8, 12, 24, a)
    return Image.alpha_composite(img.convert("RGBA"), ov)


def social_image(d: dict, cc: str, path: Path, photo: Image.Image | None = None):
    """Imagen vertical de la oferta: foto del destino, descuento, precio antes/ahora, fechas."""
    from .copywriter import savings_pct
    if photo is not None:
        img = _shade(_cover(photo))
    else:
        base = gradient(TONES[deal_tone(d)]).resize((SW, SH), Image.BICUBIC)
        img = _shade(base)
    draw = ImageDraw.Draw(img, "RGBA")
    M = 72
    brand(draw, M, 64)

    # Descuento: el gancho principal, arriba a la derecha
    ahorro = savings_pct(d)
    if ahorro >= 10:
        f = font("ExtraBold", 64)
        t = f"−{ahorro}%"
        tw = draw.textlength(t, font=f)
        box = (SW - M - tw - 56, 46, SW - M, 46 + 64 + 52)
        draw.rounded_rectangle(box, radius=26, fill=ORANGE)
        draw.text((box[0] + 28, box[1] + 22), t, font=f, fill=WHITE)

    # Origen con bandera
    y = 190
    fw = paste_flag(img, cc, M, y + 6, h=46)
    fo = font("Bold", 44)
    origin = f"Desde {d['origin_name']} ({d['origin']})"
    draw.text((M + (fw + 18 if fw else 0), y), ellipsize(draw, origin, fo, SW - 2 * M - fw - 18), font=fo, fill=WHITE)

    # Bloque inferior (se arma de abajo hacia arriba para que nunca se salga)
    price = d.get("live_price") or d["price"]
    f_foot, f_ver, f_det = font("Bold", 32), font("Bold", 36), font("Medium", 44)
    y_foot = SH - 64
    draw.text((M, y_foot), "buscavuelosbaratos.com", font=f_foot, fill=(255, 255, 255, 190))
    y = y_foot - 28
    if d.get("verify_status") == "ok":
        y -= 46
        draw.text((M, y), "✓ Precio verificado en Google Flights", font=f_ver, fill=(170, 255, 205))
    y -= 66
    detail = f"{short_dates(d.get('departure_at', ''), d.get('return_at', ''))} · {fmt_stops(d.get('transfers'))}"
    draw.text((M, y), detail, font=f_det, fill=WHITE)

    f_price = font("ExtraBold", 104)
    asc, desc = f_price.getmetrics()
    pill_h = asc + desc + 32
    y -= pill_h + 30
    box = pill(draw, M, y, f"${price:.0f}", f_price, fill=WHITE, color=(194, 65, 12), pad_x=40, pad_y=16)
    draw.text((box[2] + 28, (box[1] + box[3]) // 2 - 30), "ida y vuelta", font=font("Bold", 46), fill=WHITE)

    if ahorro >= 10 and d.get("baseline"):
        fa = font("Bold", 44)
        y -= 72
        antes = f"Normal: ${d['baseline']:.0f}"
        draw.text((M, y), antes, font=fa, fill=(255, 255, 255, 200))
        x0 = M + draw.textlength("Normal: ", font=fa)
        x1 = M + draw.textlength(antes, font=fa)
        draw.line((x0 - 4, y + 30, x1 + 4, y + 30), fill=(255, 120, 90), width=6)

    dest = d["dest_name"]
    if d.get("dest_country") and d["dest_country"] != dest:
        y -= 80
        draw.text((M, y), d["dest_country"], font=font("Medium", 46), fill=SOFT)
    f_dest = fit(draw, dest, "ExtraBold", 150, SW - 2 * M, 72)
    y -= int(f_dest.size * 1.12)
    draw.text((M - 4, y), dest, font=f_dest, fill=WHITE)
    save(img, path)
