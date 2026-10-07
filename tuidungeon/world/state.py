"""World placements and complete exploration state."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .level import Level

from ..domain.actors import Hero, Monster
from .clock import GameClock
from .maps import DungeonMap, Position


@dataclass
class MonsterPlacement:
    monster: Monster
    position: Position


@dataclass
class GameState:
    hero: Hero
    dungeon: DungeonMap
    position: Position
    clock: GameClock = field(default_factory=GameClock)
    turns: int = 0
    monsters: list[MonsterPlacement] = field(default_factory=list)
    level: "Level | None" = None

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
