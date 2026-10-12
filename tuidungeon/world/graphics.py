"""Shared color cell composition. A transparent background preserves lower layers."""

from ..content.schemas import ArtDocument, Cell
from functools import lru_cache


class MapCell(Cell):
    """Runtime appearance identity; authored art still uses plain Cell."""

    visual_ref: str


@lru_cache(maxsize=4096)
def glyph_cell(char, foreground=7, background=None, visual_ref=None, symbol=None):
    if visual_ref:
        return MapCell(
            char=char,
            foreground=foreground,
            background=background,
            visual_ref=visual_ref,
            symbol=symbol,
        )
    return Cell(char=char, foreground=foreground, background=background, symbol=symbol)


def visual_cell(store, definition, visual_ref=None, state=None, background=None):
    from ..content.symbols import appearance

    char, symbol = appearance(store.documents, definition, state)
    get = (
        definition.get
        if isinstance(definition, dict)
        else lambda k, d=None: getattr(definition, k, d)
    )
    return glyph_cell(
        char,
        get("foreground", 7),
        get("background") if get("background") is not None else background,
        visual_ref,
        symbol,
    )


def overlay(lower: Cell | None, upper: Cell | None):
    if upper is None:
        return lower
    return upper.model_copy(
        update={
            "background": upper.background
            if upper.background is not None
            else (lower.background if lower else None)
        }
    )


def compose(art: ArtDocument):
    cells = [[None for _ in range(art.width)] for _ in range(art.height)]
    for layer in art.layers:
        if not layer.visible:
            continue
        for y, row in enumerate(layer.cells):
            for x, cell in enumerate(row):
                cells[y][x] = overlay(cells[y][x], cell)
    return cells


def import_txt(text, identifier="imported", name="Импорт TXT"):
    lines = text.splitlines() or [" "]
    width = max(1, max(map(len, lines)))
    height = len(lines)
    return ArtDocument.model_validate(
        {
            "id": identifier,
            "name": name,
            "width": width,
            "height": height,
            "layers": [
                {
                    "id": "base",
                    "name": "Основной",
                    "cells": [
                        [
                            {"char": c, "foreground": 7, "background": None}
                            for c in line.ljust(width)
                        ]
                        for line in lines
                    ],
                }
            ],
        }
    )


def export_txt(art):
    return (
        "\n".join("".join(c.char if c else " " for c in row) for row in compose(art))
        + "\n"
    )


def map_cells(store, definition, tiles=None):
    blank = Cell()
    palette = {None: blank}
    cells = [[blank] * definition.width for _ in range(definition.height)]
    for y, row in enumerate(tiles if tiles is not None else definition.tiles):
        for x, ref in enumerate(row):
            if ref:
                if ref not in palette:
                    tile = store.get("tiles", ref)
                    palette[ref] = visual_cell(store, tile, "tiles/" + ref)
                cells[y][x] = palette[ref]
    for placement in definition.objects:
        obj = store.resolve("objects", placement)
        cells[placement.y][placement.x] = overlay(
            cells[placement.y][placement.x],
            visual_cell(store, obj, "objects/" + placement.ref),
        )
    for placement in definition.decorations:
        from ..content.placements import resolve_placement

        art = compose(resolve_placement(store.documents, "art", placement))
        for y, row in enumerate(art):
            for x, cell in enumerate(row):
                if (
                    placement.y + y < definition.height
                    and placement.x + x < definition.width
                ):
                    cells[placement.y + y][placement.x + x] = overlay(
                        cells[placement.y + y][placement.x + x],
                        visual_cell(store, cell) if cell else None,
                    )
    return cells
