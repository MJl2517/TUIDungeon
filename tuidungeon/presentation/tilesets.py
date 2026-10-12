"""Optional map graphics; UI text and terminal rendering keep their own font."""

import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]
APPEARANCE_PATH = ROOT / "saves" / "appearance.json"
MAP_STYLES = {"text": "Текст", "symbols": "Символы"}
SPRITE_START = 0x100000


def load_map_style(path=APPEARANCE_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        style = data.get("map_style") if isinstance(data, dict) else None
        if style == "kenney_1bit":
            style = "symbols"
        return style if isinstance(style, str) and style in MAP_STYLES else "text"
    except (OSError, ValueError):
        return "text"


def save_map_style(style, path=APPEARANCE_PATH):
    if style == "kenney_1bit":
        style = "symbols"
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
    """Compatibility entrypoint; the pack library now owns all assignments."""
    from ..content.packs import PackStore

    return load_symbol_tileset(font, PackStore().documents)


def load_symbol_tileset(font, documents):
    """Build a pinned atlas once for the loaded content snapshot."""
    import numpy as np
    import tcod.tileset
    from ..content.symbols import glyph_ref, symbol_ref

    tileset = tcod.tileset.Tileset(16, 16)
    y = np.arange(16) * font.tile_height // 16
    x = np.arange(16) * font.tile_width // 16
    for codepoint in font:
        tileset[codepoint] = font[codepoint][y[:, None], x]
    mapping = {}
    for (category, ref), doc in sorted(documents.items()):
        if category != "symbols":
            continue
        code = SPRITE_START + len(mapping)
        if code > 0x10FFFD:
            raise ValueError("Превышен размер атласа символов")
        pixels = np.zeros((16, 16, 4), dtype=np.uint8)
        pixels[:, :, :3] = 255
        pixels[:, :, 3] = [[255 if c == "1" else 0 for c in row] for row in doc.pixels]
        tileset[code] = pixels
        mapping[ref] = chr(code)
    for codepoint in font:
        if codepoint != ord(" ") and glyph_ref(chr(codepoint)) in mapping:
            mapping[("glyph", chr(codepoint))] = mapping[glyph_ref(chr(codepoint))]
    for (category, ref), doc in documents.items():
        if category != "symbols" and hasattr(doc, "glyph"):
            target = symbol_ref(documents, doc)
            if target in mapping:
                mapping[category + "/" + ref] = mapping[target]
    if "base:hero" in mapping:
        mapping["hero"] = mapping["base:hero"]
    return tileset, mapping
