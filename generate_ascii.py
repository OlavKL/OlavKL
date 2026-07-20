"""
Generates an ASCII-art portrait from assets/profile.png.

Approach:
- Load the photo, convert to grayscale.
- Crop/pad to a target character-grid aspect ratio (monospace cells are
  taller than they are wide, so we compensate ~0.5 for the vertical step).
- Map luminance to a ramp of characters from dark -> light.
- Apply mild contrast/gamma so mid-tones separate cleanly at low resolution.
- Write the result to ascii_portrait.txt (one line per row) for the HTML
  build script to embed inside a <pre> block.
"""

from PIL import Image, ImageOps, ImageFilter
import os

SRC = os.path.join(os.path.dirname(__file__), "assets", "profile.png")
OUT = os.path.join(os.path.dirname(__file__), "ascii_portrait.txt")

# Character count across the portrait (columns). Rows derive from aspect ratio.
COLS = 96

# Ramp from darkest -> lightest. Kept short and clean for a crisp, modern look
# rather than a dense "old-school" ASCII-art ramp.
RAMP = " .:-=+*#%@"


def load_and_prepare(path: str) -> Image.Image:
    img = Image.open(path)

    # Flatten onto a white background before dropping alpha, since the
    # source has a transparent (not opaque white) backdrop.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    gray = ImageOps.grayscale(img)

    # Autocontrast to spread the tonal range, then a gamma lift so mid-tone
    # facial features (eyes, nose, mouth shading) separate more clearly once
    # downsampled to a small character grid.
    gray = ImageOps.autocontrast(gray, cutoff=0.5)
    gamma = 0.8
    lut = [int(255 * ((i / 255) ** gamma)) for i in range(256)]
    gray = gray.point(lut)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))
    return gray


def resize_for_grid(gray: Image.Image, cols: int) -> Image.Image:
    w, h = gray.size
    # Monospace character cells are roughly 2x taller than wide, so we
    # under-sample rows to keep the portrait's proportions correct.
    cell_aspect = 0.52
    rows = max(1, round((h / w) * cols * cell_aspect))
    return gray.resize((cols, rows), Image.LANCZOS)


def to_ascii(gray_small: Image.Image, ramp: str) -> str:
    pixels = list(gray_small.getdata())
    w, h = gray_small.size
    n = len(ramp) - 1
    lines = []
    for y in range(h):
        row = pixels[y * w:(y + 1) * w]
        line = "".join(ramp[int((255 - p) / 255 * n)] for p in row)
        lines.append(line)
    return "\n".join(lines)


def main():
    gray = load_and_prepare(SRC)
    small = resize_for_grid(gray, COLS)
    art = to_ascii(small, RAMP)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(art)
    print(f"Wrote {OUT}")
    print(art)


if __name__ == "__main__":
    main()
