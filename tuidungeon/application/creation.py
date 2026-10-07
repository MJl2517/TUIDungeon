"""Character creation state machine, also usable without curses."""

from enum import Enum, auto

from ..content.catalog import ContentCatalog, default_catalog
from ..domain.actors import Hero
from ..domain.definitions import ClassDefinition, RaceDefinition
from ..domain.rules import Ability, AbilityRoll, Dice
from ..domain.stats import Stats


class CreationStep(Enum):
    RACE = auto()
    CLASS = auto()
    ROLL = auto()
    DISTRIBUTE = auto()
    CONFIRM = auto()


class CharacterCreation:
    PAGE_SIZE = 6

    def __init__(self, dice: Dice, catalog: ContentCatalog | None = None):
        self.dice = dice
        self.catalog = catalog or default_catalog()
        if not self.catalog.races or not self.catalog.classes:
            raise ValueError("Для создания героя нужны расы и классы")
        self.step = CreationStep.RACE
        self.race: RaceDefinition | None = None
        self.character_class: ClassDefinition | None = None
        self.selection_page = 0
        self.rolls: tuple[AbilityRoll, ...] = ()
        # Indices, rather than values, preserve distinct dice results even on ties.
        self.assignments: list[int] = []

    def reroll(self) -> None:
        self.rolls = self.dice.abilities()
        self.assignments.clear()
        self.step = CreationStep.ROLL

    def preview(self) -> Hero:
        if (
            self.race is None
            or self.character_class is None
            or len(self.assignments) != len(Ability)
        ):
            raise ValueError("Создание героя ещё не завершено")
        stats = Stats(tuple(self.rolls[index].total for index in self.assignments))
        return Hero.create(self.race, self.character_class, stats, catalog=self.catalog)

    @property
    def options(self) -> tuple[RaceDefinition | ClassDefinition, ...]:
        if self.step is CreationStep.RACE:
            return self.catalog.ordered_races
        if self.step is CreationStep.CLASS:
            return self.catalog.ordered_classes
        return ()

    @property
    def page_count(self) -> int:
        return max(1, (len(self.options) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

    @property
    def visible_options(self) -> tuple[RaceDefinition | ClassDefinition, ...]:
        start = self.selection_page * self.PAGE_SIZE
        return self.options[start : start + self.PAGE_SIZE]

    def select(self, number: int) -> Hero | None:
        if self.step in (CreationStep.RACE, CreationStep.CLASS):
            if number == 8:
                self.selection_page = max(0, self.selection_page - 1)
            elif number == 9:
                self.selection_page = min(self.page_count - 1, self.selection_page + 1)
            elif 1 <= number <= len(self.visible_options):
                selected = self.visible_options[number - 1]
                self.selection_page = 0
                if self.step is CreationStep.RACE:
                    self.race = selected
                    self.step = CreationStep.CLASS
                else:
                    self.character_class = selected
                    self.reroll()
        elif self.step is CreationStep.ROLL:
            if number == 1:
                self.reroll()
            elif number == 2:
                self.assignments.clear()
                self.step = CreationStep.DISTRIBUTE
        elif self.step is CreationStep.DISTRIBUTE:
            index = number - 1
            if 0 <= index < len(self.rolls) and index not in self.assignments:
                self.assignments.append(index)
                if len(self.assignments) == len(Ability):
                    self.step = CreationStep.CONFIRM
        elif self.step is CreationStep.CONFIRM:
            if number == 1:
                return self.preview()
            if number == 2:
                self.reroll()
        return None

    def back(self) -> None:
        self.selection_page = 0
        if self.step is CreationStep.CLASS:
            self.step = CreationStep.RACE
        elif self.step is CreationStep.ROLL:
            self.step = CreationStep.CLASS
        elif self.step is CreationStep.DISTRIBUTE:
            if self.assignments:
                self.assignments.pop()
            else:
                self.step = CreationStep.ROLL
        elif self.step is CreationStep.CONFIRM:
            self.assignments.pop()
            self.step = CreationStep.DISTRIBUTE
