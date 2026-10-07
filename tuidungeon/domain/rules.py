"""Dice and character rules. No terminal dependencies."""

from dataclasses import dataclass
from enum import Enum
import random


class Ability(Enum):
    STRENGTH = "Сила"
    DEXTERITY = "Ловкость"
    CONSTITUTION = "Телосложение"
    INTELLIGENCE = "Интеллект"
    WISDOM = "Мудрость"
    CHARISMA = "Харизма"


class Race(Enum):
    HUMAN = "Человек"
    DWARF = "Дварф"
    ELF = "Эльф"


class CharacterClass(Enum):
    WARRIOR = "Воин"
    WIZARD = "Волшебник"
    ROGUE = "Плут"


def modifier(score: int) -> int:
    return (score - 10) // 2


@dataclass(frozen=True)
class AbilityRoll:
    dice: tuple[int, ...]
    discarded: int
    total: int


@dataclass(frozen=True)
class CheckResult:
    roll: int
    modifier: int
    difficulty: int
    rolls: tuple[int, ...] = ()
    advantage: bool = False
    disadvantage: bool = False

    @property
    def total(self) -> int:
        return self.roll + self.modifier

    @property
    def success(self) -> bool:
        return self.total >= self.difficulty


class Dice:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def roll(self, count: int, sides: int) -> tuple[int, ...]:
        if count < 1 or sides < 2:
            raise ValueError("Нужен хотя бы один кубик с двумя или более гранями")
        return tuple(self.rng.randint(1, sides) for _ in range(count))

    def abilities(self) -> tuple[AbilityRoll, ...]:
        result = []
        for _ in Ability:
            rolled = self.roll(4, 6)
            discarded = min(rolled)
            result.append(AbilityRoll(rolled, discarded, sum(rolled) - discarded))
        return tuple(result)

    def check(
        self,
        score: int,
        difficulty: int,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
        bonus: int = 0,
    ) -> CheckResult:
        advantage, disadvantage = (
            advantage and not disadvantage,
            disadvantage and not advantage,
        )
        rolled = self.roll(2 if advantage or disadvantage else 1, 20)
        selected = (
            max(rolled) if advantage else min(rolled) if disadvantage else rolled[0]
        )
        return CheckResult(
            selected,
            modifier(score) + bonus,
            difficulty,
            rolled,
            advantage,
            disadvantage,
        )
