"""Session-owned placements; authored documents never contain runtime state."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4
from ..domain.challenges import TextChallenge
from ..domain.definitions import ChallengeChoice
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
    discovered: bool = False
    disabled: bool = False


@dataclass
class PointInstance:
    placement: Placement
    definition: PointDocument
    challenge: TextChallenge | None
    instance_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def text(self):
        return (
            self.challenge.text
            if self.challenge
            and (not self.definition.storage or self.definition.storage.search_contents)
            else self.definition.description
        )

    @property
    def completed(self):
        return bool(self.challenge and self.challenge.completed)

    def available_choices(self, hero):
        choices = (
            self.challenge.available_choices(hero)
            if self.challenge
            and (not self.definition.storage or self.definition.storage.search_contents)
            else ()
        )
        if self.definition.learn_recipes:
            choices = (
                ChallengeChoice("study", "Изучить мастерскую", minutes=0),
                *choices,
            )
        if self.definition.reading:
            return (ChallengeChoice("read_note", "Прочесть", minutes=0), *choices)
        return choices


@dataclass
class Level:
    ref: str
    definition: MapDocument
    store: ContentSnapshot
    traps: list[TrapInstance] = field(default_factory=list)
    points: list[PointInstance] = field(default_factory=list)
    npcs: list = field(default_factory=list)
    doors: list[DoorInstance] = field(default_factory=list)
    containers: list[StorageInstance] = field(default_factory=list)
    items: list[tuple[Placement | ItemPlacement, Equipment]] = field(
        default_factory=list
    )

    object_states: dict = field(default_factory=dict)
    regrowing_objects: list = field(default_factory=list)
    door_loot: set = field(default_factory=set)
    container_visual_version: int = 0

    def __post_init__(self):
        self.authored_definition = self.definition

    def __setattr__(self, name, value):
        if name in (
            "traps",
            "points",
            "npcs",
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
        signal_key = tuple(
            (key, s.mechanism_on, s.activation_on)
            for key, s in self.object_states.items()
            if s.mechanism_on is not None or s.activation_on is not None
        )
        if (
            getattr(self, "_terrain_definition", None) is not self.definition
            or getattr(self, "_signal_key", None) != signal_key
        ):
            self._base_terrain = (
                self.store.terrain(self.ref)
                if not signal_key
                and self.store.get("maps", self.ref) is self.definition
                else Terrain.compile(self.store, self.definition, self.object_states)
            )
            self._signal_key = signal_key
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
                    if (
                        light
                        and not getattr(doc, "light_fixture", None)
                        and (p.x, p.y) not in explicit
                    ):
                        sources.append((p.id, Position(p.x, p.y), light))
            self._static_lights = tuple(sources)
            self._lights_definition = self.definition
        return tuple(
            (position, light)
            for identifier, position, light in self._static_lights
            if not (
                self.object_states.get(identifier)
                and self.object_states[identifier].activation_on is False
            )
        )

    @property
    def cells(self):
        return self.terrain.cells

    def nearby(self, position):
        index = self.index("points")
        points = [
            p
            for dx, dy in (
                (0, 0),
                (0, -1),
                (0, 1),
                (-1, 0),
                (1, 0),
                (-1, -1),
                (1, -1),
                (-1, 1),
                (1, 1),
            )
            for p in index.at(position.x + dx, position.y + dy)
        ]
        # Preserve authored ordering for numbered interaction menus.
        return sorted(points, key=lambda p: self._point_order[p.placement.id])

    def nearby_doors(self, position):
        index = self.index("doors")
        return [
            door
            for dx, dy in (
                (0, 0),
                (0, -1),
                (0, 1),
                (-1, 0),
                (1, 0),
                (-1, -1),
                (1, -1),
                (-1, 1),
                (1, 1),
            )
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
        from ..domain.doors import door_glyph
        from .graphics import glyph_cell, visual_cell
        from ..content.symbols import appearance

        x, y, width, height = viewport or (
            0,
            0,
            state.dungeon.width,
            state.dungeon.height,
        )
        cells = [list(row[x : x + width]) for row in self.cells[y : y + height]]

        def draw(definition, p, category, ref=None, visual_state=None):
            visual_ref = category + "/" + (ref or p.ref)
            cells[p.y - y][p.x - x] = visual_cell(
                self.store,
                definition,
                visual_ref,
                state=visual_state,
                background=cells[p.y - y][p.x - x].background,
            )

        for trap in self.index("traps").region(x, y, width, height):
            if not trap.definition.hidden or trap.triggered or trap.discovered:
                draw(trap.definition, trap.placement, "traps")
        for point in self.index("points").region(x, y, width, height):
            draw(point.definition, point.placement, "points_of_interest")
        for container in self.index("containers").region(x, y, width, height):
            fixture = getattr(container.definition, "light_fixture", None)
            if fixture and fixture.stays_when_empty and not container.items:
                p = container.placement
                cells[p.y - y][p.x - x] = glyph_cell("†", 8)
            elif container.definition.state_symbols:
                draw(
                    container.definition,
                    container.placement,
                    "objects"
                    if ("objects", container.placement.ref) in self.store.documents
                    else "points_of_interest",
                    visual_state="open" if container.opened else "closed",
                )
        for instance in self.index("doors").region(x, y, width, height):
            p, door = instance.placement, instance.door
            if not door.destroyed:
                definition = instance.definition
                if definition.brush.door.material != door.material:
                    definition = self.store.documents.get(
                        ("objects", "base:door_" + door.material), definition
                    )
                state_key = "open" if door.opened else "bent" if door.bent else "closed"
                visual = (
                    definition
                    if state_key in definition.state_symbols
                    or (state_key == "closed" and definition.symbol)
                    else {
                        "glyph": door_glyph(
                            door.opened, False, bent=door.bent, material=door.material
                        )
                    }
                )
                char, symbol = appearance(self.store.documents, visual, state_key)
                cells[p.y - y][p.x - x] = glyph_cell(
                    char
                    if symbol
                    else door_glyph(
                        door.opened, False, bent=door.bent, material=door.material
                    ),
                    door.display_color(),
                    visual_ref="door_"
                    + ("open" if door.opened else "bent" if door.bent else "closed"),
                    symbol=symbol,
                    mirror_x=definition.mirror_x,
                    rotation=definition.rotation,
                )

        from collections import Counter

        ground_items = list(state.item_index.region(x, y, width, height))
        coins = Counter(
            (p.x, p.y) for p, i in ground_items if i.id in {"gold", "base:gold"}
        )
        for placement, item in ground_items:
            definition = item.template or self.store.get("equipment", placement.ref)
            if item.id in {"gold", "base:gold"}:
                indicator = self.store.service_tile(
                    "coin_large"
                    if coins[placement.x, placement.y] > 10
                    else "coin_small",
                    self.ref.split(":")[0],
                )
                if indicator:
                    definition = indicator[1]
            draw(
                definition,
                placement,
                "equipment",
            )
        for npc in self.index("npcs").region(x, y, width, height):
            draw(npc.definition, npc.placement, "npcs")
        for monster in state.actor_index.region(x, y, width, height):
            if monster.monster.hp > 0:
                ref = getattr(monster.monster, "definition_ref", None)
                if ref:
                    draw(
                        monster.monster.template or self.store.get("monsters", ref),
                        monster.position,
                        "monsters",
                        ref,
                    )
        p = state.position
        if x <= p.x < x + width and y <= p.y < y + height:
            cells[p.y - y][p.x - x] = visual_cell(
                self.store,
                {
                    "glyph": "@",
                    "foreground": 244 if state.hero.sneaking else 15,
                    "symbol": "base:hero"
                    if ("symbols", "base:hero") in self.store.documents
                    else None,
                },
                "hero",
            )
        return cells
