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
def deal_image(d: dict, cc: str, path: Path):
    img = gradient(TONES[d.get("tone", 0) % len(TONES)])
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

    if d.get("verify_status") == "ok":
        draw.text((64, 572), "✓ Precio verificado en Google Flights", font=font("Bold", 28), fill=(220, 255, 236))
    save(img, path)


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
