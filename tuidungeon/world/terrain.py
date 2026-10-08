"""Compiled level geometry and base graphics, shared independently of instances."""

from dataclasses import dataclass
from .graphics import map_cells


@dataclass(frozen=True)
class Terrain:
    tiles: tuple
    cells: tuple
    walkability: tuple[bytes, ...]
    blocks_sight: tuple[bytes, ...]
    no_occluders: bool

    @classmethod
    def compile(cls, store, definition):
        tiles = [list(row) for row in definition.tiles]
        # Compatibility for old brushes: normalize only generated object placements.
        # Source maps stay intact, and the base graphic never depends on picked-up loot.
        for p in definition.equipment:
            ref = tiles[p.y][p.x]
            if not ref or not p.id.startswith("tile_equipment_"):
                continue
            tile = store.get("tiles", ref)
            if tile.brush.item != p.ref:
                continue
            underlay = tile.brush.underlay
            if underlay is None:
                candidate = ref.split(":")[0] + ":floor"
                if ("tiles", candidate) in store.documents:
                    underlay = candidate
            tiles[p.y][p.x] = underlay
        blocks = tuple(bytes(row) for row in definition.blocks_sight)
        return cls(
            tuple(tuple(row) for row in tiles),
            tuple(tuple(row) for row in map_cells(store, definition, tiles)),
            tuple(bytes(row) for row in definition.walkability),
            blocks,
            not any(any(row) for row in blocks),
        )
