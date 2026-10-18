"""Compiled level geometry and base graphics, shared independently of instances."""

from dataclasses import dataclass, replace
from .graphics import map_cells


@dataclass(frozen=True)
class Terrain:
    tiles: tuple
    cells: tuple
    walkability: tuple[bytes, ...]
    blocks_sight: tuple[bytes, ...]
    no_occluders: bool

    @classmethod
    def compile(cls, store, definition, object_states=None):
        from .doors import door_placements, door_category

        tiles = [list(row) for row in definition.tiles]
        walkability = [list(row) for row in definition.walkability]
        sight = [list(row) for row in definition.blocks_sight]
        for p in door_placements(store, definition):
            tile = store.get(door_category(store, p.ref), p.ref)
            candidates = (p.ref.split(":")[0] + ":floor", "base:floor")
            tiles[p.y][p.x] = (
                tiles[p.y][p.x]
                if tiles[p.y][p.x] and tiles[p.y][p.x] != p.ref
                else tile.brush.underlay
                or next(
                    (ref for ref in candidates if ("tiles", ref) in store.documents),
                    None,
                )
            )
            walkability[p.y][p.x] = True
            sight[p.y][p.x] = False
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
        # Object geometry is compiled once; authored masks remain independent.
        for p in definition.objects:
            obj = store.resolve("objects", p)
            state = (object_states or {}).get(p.id)
            if obj.illusion and state and state.activation_on:
                continue
            walkability[p.y][p.x] = walkability[p.y][p.x] and obj.walkable
            sight[p.y][p.x] = sight[p.y][p.x] or obj.blocks_sight
        blocks = tuple(bytes(row) for row in sight)
        return cls(
            tuple(tuple(row) for row in tiles),
            tuple(
                tuple(row) for row in map_cells(store, definition, tiles, object_states)
            ),
            tuple(bytes(row) for row in walkability),
            blocks,
            not any(any(row) for row in blocks),
        )

    def with_doors(self, doors):
        movement, sight = {}, {}
        for instance in doors:
            p, door = instance.placement, instance.door
            movement.setdefault(p.y, bytearray(self.walkability[p.y]))[p.x] = (
                door.passable
            )
            sight.setdefault(p.y, bytearray(self.blocks_sight[p.y]))[p.x] = door.opaque
        walkability, blocks = list(self.walkability), list(self.blocks_sight)
        for y, row in movement.items():
            walkability[y] = bytes(row)
        for y, row in sight.items():
            blocks[y] = bytes(row)
        return replace(
            self,
            walkability=tuple(walkability),
            blocks_sight=tuple(blocks),
            no_occluders=not any(any(row) for row in blocks),
        )
