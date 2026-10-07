"""Shared color cell composition. A transparent background preserves lower layers."""

from ..content.schemas import ArtDocument, Cell


def overlay(lower: Cell | None, upper: Cell | None):
    if upper is None:
        return lower
    return Cell(
        char=upper.char,
        foreground=upper.foreground,
        background=upper.background
        if upper.background is not None
        else (lower.background if lower else None),
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


def map_cells(store, definition):
    cells = [
        [Cell() for _ in range(definition.width)] for _ in range(definition.height)
    ]
    for y, row in enumerate(definition.tiles):
        for x, ref in enumerate(row):
            if ref:
                tile = store.get("tiles", ref)
                cells[y][x] = Cell(
                    char=tile.glyph,
                    foreground=tile.foreground,
                    background=tile.background,
                )
    for placement in definition.decorations:
        art = compose(store.get("art", placement.ref))
        for y, row in enumerate(art):
            for x, cell in enumerate(row):
                if (
                    placement.y + y < definition.height
                    and placement.x + x < definition.width
                ):
                    cells[placement.y + y][placement.x + x] = overlay(
                        cells[placement.y + y][placement.x + x], cell
                    )
    return cells
