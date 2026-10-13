"""Thumbnails, palettes, perceptual hashes and color math (Pillow + numpy only)."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 120_000_000  # allow big posters, still refuse decompression bombs


@dataclass
class ThumbResult:
    data: bytes  # webp
    width: int
    height: int
    src_width: int
    src_height: int
    colors: list[list]  # [[hex, fraction], ...]
    dhash: str
    hist: np.ndarray  # 64-bin color histogram (for the fallback vibe vector)


def _open(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    try:
        img.seek(0)  # first frame of GIF/animated WebP
    except EOFError:
        pass
    img.load()
    return img


def process_image(data: bytes, max_size: int = 360) -> ThumbResult:
    img = _open(data)
    src_w, src_h = img.size
    img = ImageOps.exif_transpose(img)
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    img.thumbnail((max_size, max_size * 3), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80, method=4)
    rgb = _flatten(img)
    return ThumbResult(
        data=buf.getvalue(), width=img.width, height=img.height, src_width=src_w, src_height=src_h,
        colors=palette(img), dhash=dhash(rgb), hist=color_hist(img),
    )


def _flatten(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def _opaque_pixels(img: Image.Image, size: int = 64) -> np.ndarray:
    small = img.copy()
    small.thumbnail((size, size))
    arr = np.asarray(small.convert("RGBA"), dtype=np.uint8).reshape(-1, 4)
    opaque = arr[arr[:, 3] > 32][:, :3]
    if len(opaque) == 0:
        opaque = arr[:, :3]
    return opaque


def palette(img: Image.Image, n: int = 5) -> list[list]:
    px = _opaque_pixels(img)
    if len(px) == 0:
        return []
    strip = Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8), "RGB")
    q = strip.quantize(colors=n + 3, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    merged: list[list] = []  # [hex, count]; fold near-identical shades together
    for count, idx in counts:
        hexv = rgb_to_hex(tuple(pal[idx * 3: idx * 3 + 3]))
        for m in merged:
            if delta_e(m[0], hexv) < 10:
                m[1] += count
                break
        else:
            merged.append([hexv, count])
    merged.sort(key=lambda m: -m[1])
    return [[h, round(c / total, 3)] for h, c in merged[:n]]


def dhash(img: Image.Image, size: int = 8) -> str:
    g = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def informative_hash(h: str | None) -> bool:
    """Flat images (solid colors, blank frames) all share the same dHash — don't treat those as duplicates."""
    if not h:
        return False
    try:
        bits = bin(int(h, 16)).count("1")
    except ValueError:
        return False
    return 6 <= bits <= 58


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def color_hist(img: Image.Image, bins: int = 4) -> np.ndarray:
    px = _opaque_pixels(img, 48).astype(np.int32)
    idx = (px[:, 0] * bins // 256) * bins * bins + (px[:, 1] * bins // 256) * bins + (px[:, 2] * bins // 256)
    hist = np.bincount(idx, minlength=bins ** 3).astype(np.float32)
    hist = np.sqrt(hist / max(hist.sum(), 1.0))
    norm = np.linalg.norm(hist)
    return hist / norm if norm else hist


def hist_for_colors(hexes: list[str], bins: int = 4) -> np.ndarray:
    """A synthetic histogram for 'red'/'teal' style color intents in queries."""
    hist = np.zeros(bins ** 3, dtype=np.float32)
    for h in hexes:
        r, g, b = hex_to_rgb(h)
        hist[(r * bins // 256) * bins * bins + (g * bins // 256) * bins + (b * bins // 256)] += 1.0
    norm = np.linalg.norm(hist)
    return hist / norm if norm else hist


# -- color math ---------------------------------------------------------------

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, c))) for c in rgb))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (128, 128, 128)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return (128, 128, 128)


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: str, b: str) -> float:
    la, aa, ba = rgb_to_lab(hex_to_rgb(a))
    lb, ab, bb = rgb_to_lab(hex_to_rgb(b))
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def color_match(colors: list | None, target_hex: str) -> float:
    """0..1: how much of the palette is close to the target color."""
    if not colors:
        return 0.0
    score = 0.0
    for item in colors:
        try:
            hexv, frac = item[0], float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        d = delta_e(hexv, target_hex)
        score += frac * math.exp(-(d / 22.0) ** 2)
    return min(1.0, score * 1.6)


def palette_similarity(a: list | None, b: list | None) -> float:
    if not a or not b:
        return 0.0
    return sum(float(fa) * color_match(b, ha) for ha, fa in a) / max(sum(float(f) for _, f in a), 1e-6)


def render_font_specimen(font_path: str, text: str = "Aa Bb Cc", size: int = 360) -> bytes | None:
    """Thumbnail for local font files (import-folder)."""
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.truetype(font_path, 72)
    except Exception:
        return None
    img = Image.new("RGB", (size, int(size * 0.6)), (246, 244, 239))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    scale = min((size * 0.86) / max(w, 1), (size * 0.4) / max(h, 1), 1.0)
    if scale < 1.0:
        font = ImageFont.truetype(font_path, max(10, int(72 * scale)))
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (img.height - h) / 2 - bbox[1]), text, font=font, fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=85)
    return buf.getvalue()
