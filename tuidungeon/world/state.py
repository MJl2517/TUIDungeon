"""World placements and complete exploration state."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .level import Level

from ..domain.actors import Hero, Monster
from ..domain.equipment import Equipment
from ..domain.collections import TrackedList
from .spatial import CellIndex
from .clock import GameClock
from .maps import DungeonMap, Position


@dataclass(frozen=True)
class MonsterPlacement:
    monster: Monster
    position: Position


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
        if not self.dungeon.walkable(position):
            return False
        if self.level:
            return bool(self.level.terrain.walkability[position.y][position.x])
        return True

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
