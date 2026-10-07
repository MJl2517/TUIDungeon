"""Compatibility imports for the original prototype API."""

from .content.catalog import default_catalog
from .domain.actors import Character, Hero, Monster
from .domain.definitions import Spell
from .domain.equipment import Equipment as Item
from .domain.stats import Stats
from .world.clock import GameClock
from .world.maps import DungeonMap, Position
from .world.state import GameState

MAGIC_MISSILE = default_catalog().spells["magic_missile"]
DETECT_MAGIC = default_catalog().spells["detect_magic"]

__all__ = [
    "Character",
    "Hero",
    "Monster",
    "Spell",
    "Item",
    "Stats",
    "GameClock",
    "DungeonMap",
    "Position",
    "GameState",
]
