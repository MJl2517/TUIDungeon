"""Session-owned placements; authored documents never contain runtime state."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4
from ..domain.challenges import TextChallenge
from .terrain import Terrain
from .doors import DoorInstance
from .storage import StorageInstance
from .spatial import CellIndex
from ..domain.collections import TrackedList
from ..domain.equipment import Equipment
from ..content.schemas import MapDocument, Placement, TrapDocument, PointDocument

if TYPE_CHECKING:
    from ..content.compiler import ContentSnapshot
    from .state import ItemPlacement


@dataclass
class TrapInstance:
    placement: Placement
    definition: TrapDocument
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    triggered: bool = False


@dataclass
class PointInstance:
    placement: Placement
    definition: PointDocument
    challenge: TextChallenge
    instance_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Level:
    ref: str
    definition: MapDocument
    store: ContentSnapshot
    traps: list[TrapInstance] = field(default_factory=list)
    points: list[PointInstance] = field(default_factory=list)
    doors: list[DoorInstance] = field(default_factory=list)
    containers: list[StorageInstance] = field(default_factory=list)
    items: list[tuple[Placement | ItemPlacement, Equipment]] = field(
        default_factory=list
    )

    def __setattr__(self, name, value):
        if name in (
            "traps",
            "points",
            "items",
            "doors",
            "containers",
        ) and not isinstance(value, TrackedList):
            value = TrackedList(value)
        super().__setattr__(name, value)

    def index(self, name):
        indexes = self.__dict__.setdefault("_indexes", {})
        if name not in indexes:
            indexes[name] = CellIndex(lambda p: (p.placement.x, p.placement.y))
        return indexes[name].synchronize(getattr(self, name))

    @property
    def terrain(self):
        if getattr(self, "_terrain_definition", None) is not self.definition:
            self._base_terrain = (
                self.store.terrain(self.ref)
                if self.store.get("maps", self.ref) is self.definition
                else Terrain.compile(self.store, self.definition)
            )
            self._terrain_definition = self.definition
            self._door_geometry_key = None
        key = (
            id(self.doors),
            self.doors.version,
            tuple(
                (p.placement.x, p.placement.y, p.door.geometry_key) for p in self.doors
            ),
        )
        if getattr(self, "_door_geometry_key", None) != key:
            self._terrain = (
                self._base_terrain.with_doors(self.doors)
                if self.doors
                else self._base_terrain
            )
            self._door_geometry_key = key
        return self._terrain

    @property
    def static_lights(self):
        """Compile author-defined light once, including per-instance overrides."""
        from .maps import Position

        if getattr(self, "_lights_definition", None) is not self.definition:
            explicit = {(p.x, p.y) for p in self.definition.lights}
            sources = []
            for category in ("objects", "traps", "points_of_interest"):
                for p in getattr(self.definition, category):
                    doc = self.store.resolve(category, p)
                    light = doc.brush.light if category == "objects" else doc.map_light
                    if light and (p.x, p.y) not in explicit:
                        sources.append((Position(p.x, p.y), light))
            self._static_lights = tuple(sources)
            self._lights_definition = self.definition
        return self._static_lights

    @property
    def cells(self):
        return self.terrain.cells

    def nearby(self, position):
        index = self.index("points")
        points = [
            p
            for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
            for p in index.at(position.x + dx, position.y + dy)
        ]
        # Preserve authored ordering for numbered interaction menus.
        return sorted(points, key=lambda p: self._point_order[p.placement.id])

    def nearby_doors(self, position):
        index = self.index("doors")
        return [
            door
            for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
            for door in index.at(position.x + dx, position.y + dy)
        ]

    @property
    def _point_order(self):
        key = (id(self.points), self.points.version)
        if getattr(self, "_order_key", None) != key:
            self._order = {p.placement.id: i for i, p in enumerate(self.points)}
            self._order_key = key
        return self._order

    def render_cells(self, state, viewport=None):
        from .graphics import glyph_cell

        x, y, width, height = viewport or (
            0,
            0,
            state.dungeon.width,
            state.dungeon.height,
        )
        cells = [list(row[x : x + width]) for row in self.cells[y : y + height]]

        def draw(definition, p):
            if isinstance(definition, dict):
                cells[p.y - y][p.x - x] = glyph_cell(
                    definition["glyph"],
                    definition["foreground"],
                    definition["background"],
                )
            else:
                cells[p.y - y][p.x - x] = glyph_cell(
                    definition.glyph, definition.foreground, definition.background
                )

        for trap in self.index("traps").region(x, y, width, height):
            if not trap.definition.hidden or trap.triggered:
                draw(trap.definition, trap.placement)
        for point in self.index("points").region(x, y, width, height):
            draw(point.definition, point.placement)
        for instance in self.index("doors").region(x, y, width, height):
            p, door = instance.placement, instance.door
            if not door.destroyed:
                cells[p.y - y][p.x - x] = glyph_cell(door.glyph, door.display_color())
        for placement, item in state.item_index.region(x, y, width, height):
            draw(item.template or self.store.get("equipment", placement.ref), placement)
        for monster in state.actor_index.region(x, y, width, height):
            if monster.monster.hp > 0:
                ref = getattr(monster.monster, "definition_ref", None)
                if ref:
                    draw(
                        monster.monster.template or self.store.get("monsters", ref),
                        monster.position,
                    )
        p = state.position
        if x <= p.x < x + width and y <= p.y < y + height:
            cells[p.y - y][p.x - x] = glyph_cell(
                "@", 244 if state.hero.sneaking else 15
            )
        return cells
