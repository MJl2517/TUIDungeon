"""Ability scores shared by heroes, monsters and NPCs."""

from dataclasses import dataclass

from .rules import Ability, modifier


@dataclass(frozen=True)
class Stats:
    values: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(Ability) or any(
            type(value) is not int or value < 1 for value in self.values
        ):
            raise ValueError("Требуются шесть положительных целых характеристик")

    def score(self, ability: Ability) -> int:
        return self.values[list(Ability).index(ability)]

    def modifier(self, ability: Ability) -> int:
        return modifier(self.score(ability))

    def with_bonuses(self, bonuses: tuple[int, ...]) -> "Stats":
        if len(bonuses) != len(Ability):
            raise ValueError("Нужны бонусы для всех шести характеристик")
        return Stats(tuple(value + bonus for value, bonus in zip(self.values, bonuses)))
