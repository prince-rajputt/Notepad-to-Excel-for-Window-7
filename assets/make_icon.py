"""Generate assets/app_icon.ico for Taaza News Excel Sync.

Regenerate with:  python assets/make_icon.py

The icon is deliberately unlike the older single-workbook app's default
PyInstaller icon so the two can be told apart in the Start menu, on the
desktop and in the taskbar when both are installed side by side.
"""
import os

from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")

BREAKING_RED = (198, 40, 40, 255)
DEEP_RED = (150, 25, 25, 255)
BAND_YELLOW = (255, 214, 0, 255)
WHITE = (255, 255, 255, 255)


def _font(size):
    """A bold sans face, falling back through the usual Windows candidates."""
    for name in ("arialbd.ttf", "seguisb.ttf", "segoeuib.ttf", "calibrib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_centered(draw, box, text, font, fill):
    left, top, right, bottom = box
    t_left, t_top, t_right, t_bottom = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (t_right - t_left)) / 2 - t_left
    y = top + (bottom - top - (t_bottom - t_top)) / 2 - t_top
    draw.text((x, y), text, font=font, fill=fill)


def render(size):
    # Render at 4x and downsample so the small sizes stay clean.
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(s * 0.20)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=BREAKING_RED)
    # Subtle darker lower half for a bit of depth.
    draw.rounded_rectangle(
        [0, int(s * 0.55), s - 1, s - 1], radius=radius, fill=DEEP_RED
    )
    draw.rectangle([0, int(s * 0.55), s - 1, int(s * 0.66)], fill=DEEP_RED)

    # Yellow ticker band - echoes the yellow header row of the workbooks.
    band_top = int(s * 0.62)
    band_bottom = int(s * 0.80)
    draw.rectangle([int(s * 0.10), band_top, int(s * 0.90), band_bottom], fill=BAND_YELLOW)

    # "T" mark above the band.
    _draw_centered(
        draw,
        (0, int(s * 0.06), s, band_top),
        "T",
        _font(int(s * 0.52)),
        WHITE,
    )

    # Three ticker dashes inside the band, standing in for scrolling text.
    dash_y0 = band_top + int((band_bottom - band_top) * 0.34)
    dash_y1 = band_top + int((band_bottom - band_top) * 0.66)
    x = int(s * 0.17)
    for width_frac in (0.26, 0.18, 0.13):
        w = int(s * width_frac)
        draw.rectangle([x, dash_y0, x + w, dash_y1], fill=DEEP_RED)
        x += w + int(s * 0.045)

    return img.resize((size, size), Image.LANCZOS)


def main():
    images = [render(size) for size in SIZES]
    images[-1].save(OUT_PATH, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Wrote {OUT_PATH} ({', '.join(f'{s}x{s}' for s in SIZES)})")


if __name__ == "__main__":
    main()
