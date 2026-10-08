"""Rebuild the bundled font atlas: pip install Pillow, then run this file."""

import json
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import tcod.tileset

ROOT = Path(__file__).resolve().parents[1] / "assets" / "fonts"
WIDTH, HEIGHT, COLUMNS, FONT_SIZE = 12, 24, 128, 20
NAMES = ("DejaVuSansMono.ttf", "DejaVuSans.ttf", "NotoSansSymbols2-Regular.ttf")


def build():
    sources = []
    for name in NAMES:
        font = tcod.tileset.load_truetype_font(ROOT / name, WIDTH, HEIGHT)
        sources.append((name, set(font)))
    codepoints = sorted(set().union(*(coverage for _, coverage in sources)))
    rows = ceil(len(codepoints) / COLUMNS)
    atlas = Image.new("RGBA", (WIDTH * COLUMNS, HEIGHT * rows))
    for index, codepoint in enumerate(codepoints):
        char = chr(codepoint)
        name = next(name for name, coverage in sources if codepoint in coverage)
        size = FONT_SIZE
        while True:
            font = ImageFont.truetype(str(ROOT / name), size)
            left, top, right, bottom = font.getbbox(char)
            if (right - left <= WIDTH and bottom - top <= HEIGHT) or size == 1:
                break
            size -= 1
        tile = Image.new("RGBA", (WIDTH, HEIGHT))
        # Normal text shares a baseline; fallback symbols fit into the same cell.
        x = (WIDTH - (right - left)) // 2 - left
        y = (
            0
            if name == NAMES[0] and size == FONT_SIZE and 0 <= top <= bottom <= HEIGHT
            else (HEIGHT - (bottom - top)) // 2 - top
        )
        ImageDraw.Draw(tile).text((x, y), char, font=font, fill=(255, 255, 255, 255))
        atlas.paste(tile, ((index % COLUMNS) * WIDTH, (index // COLUMNS) * HEIGHT))
    atlas.save(ROOT / "glyphs.png", optimize=True)
    (ROOT / "glyphs.json").write_text(
        json.dumps({"columns": COLUMNS, "rows": rows, "codepoints": codepoints}),
        encoding="utf-8",
    )
    print(f"Built {len(codepoints)} glyphs, {WIDTH}x{HEIGHT} cells")


if __name__ == "__main__":
    build()
