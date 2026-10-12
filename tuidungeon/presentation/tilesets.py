"""Optional map graphics; UI text and terminal rendering keep their own font."""

import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]
APPEARANCE_PATH = ROOT / "saves" / "appearance.json"
MAP_STYLES = {"text": "Текст", "kenney_1bit": "Kenney 1-Bit"}
SPRITE_START = 0x100000


def load_map_style(path=APPEARANCE_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        style = data.get("map_style") if isinstance(data, dict) else None
        return style if isinstance(style, str) and style in MAP_STYLES else "text"
    except (OSError, ValueError):
        return "text"


def save_map_style(style, path=APPEARANCE_PATH):
    if style not in MAP_STYLES:
        raise ValueError("Неизвестное оформление карты")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump({"map_style": style}, output)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def load_kenney_tileset(font):
    import numpy as np
    import tcod.tileset

    manifest = json.loads(
        (ROOT / "assets" / "tilesets" / "kenney_1bit.json").read_text(encoding="utf-8")
    )
    columns, rows = manifest["columns"], manifest["rows"]
    tileset = tcod.tileset.load_tilesheet(
        ROOT / "assets" / manifest["image"],
        columns,
        rows,
        range(SPRITE_START, SPRITE_START + columns * rows),
    )
    # Unmapped content keeps its normal glyph, fitted to the square map cell.
    y = np.arange(tileset.tile_height) * font.tile_height // tileset.tile_height
    x = np.arange(tileset.tile_width) * font.tile_width // tileset.tile_width
    for codepoint in font:
        if not SPRITE_START <= codepoint < SPRITE_START + columns * rows:
            tileset[codepoint] = font[codepoint][y[:, None], x]

    def sprite(coordinates):
        x, y = coordinates
        if not (0 <= x < columns and 0 <= y < rows):
            raise ValueError("Рисунок выходит за границы тайлсета")
        return chr(SPRITE_START + y * columns + x)

    mapping = {("glyph", char): sprite(xy) for char, xy in manifest["glyphs"].items()}
    mapping.update({ref: sprite(xy) for ref, xy in manifest["special"].items()})
    for category, entries in manifest["content"].items():
        mapping.update(
            {category + "/" + ref: sprite(xy) for ref, xy in entries.items()}
        )
    return tileset, mapping
