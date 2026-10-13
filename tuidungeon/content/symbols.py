"""Shared one-cell visual resolution. Legacy glyphs remain readable."""

from functools import lru_cache
import struct
import zlib

SIZE = 16
DOOR_STATES = ("closed", "locked", "open", "bent")


def glyph_ref(char):
    return f"base:glyph_{ord(char):04x}"


def symbol_ref(documents, definition, state=None):
    get = (
        definition.get
        if isinstance(definition, dict)
        else lambda k, d=None: getattr(definition, k, d)
    )
    if state is None and (storage := get("storage")):
        state = (
            storage.get("state", "closed")
            if isinstance(storage, dict)
            else storage.state
        )
    ref = get("state_symbols", {}).get(state) if state else None
    ref = ref or get("symbol")
    if not ref:
        ref = glyph_ref(get("glyph", get("char", "?")))
    return ref if ("symbols", ref) in documents else None


def appearance(documents, definition, state=None):
    ref = symbol_ref(documents, definition, state)
    if ref:
        return documents["symbols", ref].glyph, ref
    get = (
        definition.get
        if isinstance(definition, dict)
        else lambda k, d=None: getattr(definition, k, d)
    )
    return get("glyph", get("char", "?")), None


def resolve_text(store, text, pack="base"):
    """Register printable typed characters once, including new TXT imports."""
    from .schemas import SymbolDocument, valid_glyph
    from .packs import ContentError
    import json
    from pathlib import Path
    import tcod.tileset
    import numpy as np

    if pack not in store.manifests:
        raise ContentError("Выберите существующий пакет для символов")

    def dependencies(identifier):
        result = {identifier}
        for dep in store.manifests[identifier].dependencies:
            result.update(dependencies(dep))
        return result

    accessible = dependencies(pack)
    chars = set(text) - {"\n", "\r"}
    for char in chars:
        valid_glyph(char)
    root = Path(__file__).resolve().parents[2] / "assets/fonts"
    result = {}
    font = None
    for char in sorted(chars):
        ref = glyph_ref(char)
        if "base" not in accessible or ("symbols", ref) not in store.documents:
            ref = pack + ":" + ref.split(":")[1]
        if ("symbols", ref) not in store.documents:
            if font is None:
                meta = json.loads((root / "glyphs.json").read_text())
                font = tcod.tileset.load_tilesheet(
                    root / "glyphs.png",
                    meta["columns"],
                    meta["rows"],
                    meta["codepoints"],
                )
            tile = font[ord(char)] if ord(char) in font else font[ord("?")]
            yy = np.arange(16) * font.tile_height // 16
            xx = np.arange(16) * font.tile_width // 16
            pixels = [
                "".join("1" if a > 127 else "0" for a in row)
                for row in tile[yy[:, None], xx, 3]
            ]
            doc = SymbolDocument(
                id=ref.split(":")[1],
                name=f"Текстовый знак {char!r} (U+{ord(char):04X})",
                glyph=char,
                group="Текстовые знаки",
                pixels=pixels,
                reviewed=True,
            )
            store.save("symbols", ref, doc.model_dump(mode="json"), None)
        result[char] = ref
    return result


def bind_legacy_visuals(store, raw, pack):
    """Studio writes library links even when an older client submits text signs."""

    def signs(value):
        if isinstance(value, dict):
            if not value.get("symbol"):
                sign = value.get("glyph", value.get("char"))
                if sign is not None:
                    yield sign
            for nested in value.values():
                yield from signs(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from signs(nested)

    refs = resolve_text(store, "".join(set(signs(raw))), pack)

    def bind(value):
        if isinstance(value, list):
            return [bind(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: bind(v) for k, v in value.items()}
        sign = result.get("glyph", result.get("char"))
        if sign is not None and not result.get("symbol"):
            result["symbol"] = refs[sign]
        return result

    return bind(raw)


def png_bytes(rows, scale=1):
    """Portable RGBA PNG export; no imaging package or display is needed."""
    height, width = len(rows), len(rows[0])
    data = b"".join(
        b"\0" + b"".join(pixel * scale for pixel in row)
        for row in rows
        for _ in range(scale)
    )

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width * scale, height * scale, 8, 6, 0, 0, 0),
        )
        + chunk(b"IDAT", zlib.compress(data))
        + chunk(b"IEND", b"")
    )


@lru_cache(maxsize=4096)
def mask_rgba(pixels):
    return [
        [b"\xff\xff\xff\xff" if c == "1" else b"\0\0\0\0" for c in row]
        for row in pixels
    ]
