"""World placements and complete exploration state."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING
from pydantic import field_validator
from ..content.schemas import StrictModel, ReadingText, Ref, LocalId, title_text

if TYPE_CHECKING:
    from .level import Level

from ..domain.actors import Hero, Monster
from ..domain.equipment import Equipment
from ..domain.collections import TrackedList
from .spatial import CellIndex
from .clock import GameClock
from .maps import DungeonMap, Position


class ReadNote(StrictModel):
    map_ref: Ref
    placement_id: LocalId
    location: str
    text: ReadingText
    _location = field_validator("location")(title_text)


@dataclass(frozen=True)
class MonsterPlacement:
    monster: Monster
    position: Position
    corpse_created: bool = False


@dataclass(frozen=True)
class ItemPlacement:
    id: str
    ref: str
    x: int
    y: int


@dataclass
class GameState:
    hero: Hero
    dungeon: DungeonMap
    position: Position
    clock: GameClock = field(default_factory=GameClock)
    turns: int = 0
    monsters: list[MonsterPlacement] = field(default_factory=list)
    level: "Level | None" = None
    ground_items: list[tuple[ItemPlacement, Equipment]] = field(default_factory=list)
    # Session-owned surfaces; keys may include walls and other blocked cells.
    oil: dict[Position, int] = field(default_factory=dict)

    def walkable(self, position):
        if self.level:
            if self.level.index("npcs").at(position.x, position.y):
                return False
            return bool(
                0 <= position.x < self.dungeon.width
                and 0 <= position.y < self.dungeon.height
                and self.level.terrain.walkability[position.y][position.x]
            )
        return self.dungeon.walkable(position)

    def __setattr__(self, name, value):
        if name in ("monsters", "ground_items") and not isinstance(value, TrackedList):
            value = TrackedList(value)
        super().__setattr__(name, value)

    @property
    def actor_index(self):
        if not hasattr(self, "_actor_index"):
            self._actor_index = CellIndex(lambda p: (p.position.x, p.position.y))
        return self._actor_index.synchronize(self.monsters)

    @property
    def item_index(self):
        if not hasattr(self, "_item_index"):
            self._item_index = CellIndex(lambda entry: (entry[0].x, entry[0].y))
        return self._item_index.synchronize(self.items)

    def move_monster(self, placement, target):
        if (
            not self.walkable(target)
            or target == self.position
            or any(
                p.monster.hp > 0 and p is not placement
                for p in self.actor_index.at(target.x, target.y)
            )
        ):
            raise ValueError("Для монстра нужна свободная клетка пола")
        index = next(i for i, p in enumerate(self.monsters) if p is placement)
        updated = replace(placement, position=target)
        self.monsters[index] = updated
        return updated

    def light_sources(self, *, shining=True):
        sources = [(self.position, i) for i in self.hero.light_items if i.equipped]
        sources.extend((Position(p.x, p.y), i) for p, i in self.item_index.lights)
        for placement in self.monsters:
            sources.extend(
                (placement.position, i)
                for i in placement.monster.light_items
                if i.equipped
            )
        if self.level:
            sources.extend(
                (Position(c.placement.x, c.placement.y), i)
                for c in self.level.containers
                if getattr(c.definition, "light_fixture", None)
                for i in c.items
                if i.definition.light
            )
        return tuple((p, i) for p, i in sources if (i.shining if shining else i.lit))

    @property
    def items(self):
        return self.level.items if self.level else self.ground_items

    def __post_init__(self) -> None:
        if not self.dungeon.walkable(self.position):
            raise ValueError("Герой должен начинать на проходимой клетке")
        occupied = {self.position}
        for placement in self.monsters:
            if (
                not self.dungeon.walkable(placement.position)
                or placement.position in occupied
            ):
                raise ValueError("Монстр должен находиться на свободной клетке пола")
            occupied.add(placement.position)
