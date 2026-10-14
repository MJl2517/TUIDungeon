"""Character creation state machine, also usable without curses."""

from enum import Enum, auto
from dataclasses import dataclass

from ..content.catalog import ContentCatalog, default_catalog
from ..domain.actors import Hero
from ..domain.definitions import ClassDefinition, RaceDefinition, BackgroundDefinition
from ..domain.rules import Ability, AbilityRoll, Dice
from ..domain.stats import Stats
from ..domain.skills import SKILLS, starting_skills


class CreationStep(Enum):
    RACE = auto()
    CLASS = auto()
    BACKGROUND = auto()
    SKILLS = auto()
    BONUS_SKILLS = auto()
    EXPERTISE = auto()
    ROLL = auto()
    DISTRIBUTE = auto()
    CANTRIPS = auto()
    CONFIRM = auto()


@dataclass(frozen=True)
class CreationButton:
    number: int
    label: str


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
        self.background: BackgroundDefinition | None = None
        self.cursor = 0
        self.selection_page = 0
        self.rolls: tuple[AbilityRoll, ...] = ()
        # Indices, rather than values, preserve distinct dice results even on ties.
        self.assignments: list[int] = []
        self.cantrips: list[str] = []
        self.skills: list[str] = []
        self.extra_skills: list[str] = []
        self.expertise: list[str] = []

    @property
    def skill_steps(self):
        return (CreationStep.SKILLS, CreationStep.BONUS_SKILLS, CreationStep.EXPERTISE)

    def skill_count(self, step):
        if not self.character_class or not self.race:
            return 0
        return {
            CreationStep.SKILLS: self.character_class.skills_known,
            CreationStep.BONUS_SKILLS: starting_skills(
                self.race, self.character_class, self.background
            )[2],
            CreationStep.EXPERTISE: self.character_class.expertise_count,
        }.get(step, 0)

    def selected_skills(self, step):
        return {
            CreationStep.SKILLS: self.skills,
            CreationStep.BONUS_SKILLS: self.extra_skills,
            CreationStep.EXPERTISE: self.expertise,
        }[step]

    @property
    def known_skills(self):
        fixed = starting_skills(self.race, self.character_class, self.background)[0]
        return fixed | set(self.skills) | set(self.extra_skills)

    @property
    def steps(self):
        return tuple(
            s
            for s in CreationStep
            if (s not in self.skill_steps or self.skill_count(s))
            and (
                s is not CreationStep.CANTRIPS
                or self.character_class
                and self.character_class.cantrips_known
            )
        )

    def reroll(self) -> None:
        self.rolls = self.dice.abilities()
        self.assignments.clear()
        self.step = CreationStep.ROLL
        self.cursor = 1

    def preview(self) -> Hero:
        if (
            self.race is None
            or self.character_class is None
            or len(self.assignments) != len(Ability)
        ):
            raise ValueError("Создание героя ещё не завершено")
        stats = Stats(tuple(self.rolls[index].total for index in self.assignments))
        return Hero.create(
            self.race,
            self.character_class,
            stats,
            catalog=self.catalog,
            background=self.background,
            cantrips=tuple(self.cantrips)
            if len(self.cantrips) == self.character_class.cantrips_known
            else None,
            skills=self.skills,
            extra_skills=self.extra_skills,
            expertise=self.expertise,
        )

    @property
    def options(
        self,
    ) -> tuple[RaceDefinition | ClassDefinition | BackgroundDefinition, ...]:
        if self.step is CreationStep.RACE:
            return self.catalog.ordered_races
        if self.step is CreationStep.CLASS:
            return self.catalog.ordered_classes
        if self.step is CreationStep.CANTRIPS:
            return tuple(
                self.catalog.spells[s] for s in self.character_class.cantrip_choices
            )
        if self.step in self.skill_steps:
            fixed, choices, _ = starting_skills(
                self.race, self.character_class, self.background
            )
            ids = (
                choices
                if self.step is CreationStep.SKILLS
                else [s for s in SKILLS if s in self.known_skills]
                if self.step is CreationStep.EXPERTISE
                else [s for s in SKILLS if s not in fixed | set(self.skills)]
            )
            return tuple(SKILLS[s] for s in ids)
        if self.step is CreationStep.BACKGROUND and self.character_class:
            return tuple(
                background
                for background in sorted(
                    self.catalog.backgrounds.values(), key=lambda b: b.id
                )
                if self.character_class.id in background.classes
            )
        return ()

    @property
    def page_count(self) -> int:
        return max(1, (len(self.options) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

    @property
    def visible_options(
        self,
    ) -> tuple[RaceDefinition | ClassDefinition | BackgroundDefinition, ...]:
        start = self.selection_page * self.PAGE_SIZE
        return self.options[start : start + self.PAGE_SIZE]

    @property
    def buttons(self) -> tuple[CreationButton, ...]:
        if self.step in (
            CreationStep.RACE,
            CreationStep.CLASS,
            CreationStep.BACKGROUND,
            CreationStep.CANTRIPS,
            *self.skill_steps,
        ):
            buttons = [
                CreationButton(
                    i,
                    (
                        (
                            "[*] "
                            if option.id
                            in (
                                self.cantrips
                                if self.step is CreationStep.CANTRIPS
                                else self.selected_skills(self.step)
                            )
                            else "[ ] "
                        )
                        if self.step is CreationStep.CANTRIPS
                        or self.step in self.skill_steps
                        else ""
                    )
                    + option.name,
                )
                for i, option in enumerate(self.visible_options, 1)
            ]
            if self.step is CreationStep.BACKGROUND and not self.options:
                buttons = [CreationButton(1, "Продолжить без предыстории")]
            if self.step is CreationStep.CANTRIPS:
                buttons.append(
                    CreationButton(
                        7,
                        f"Продолжить ({len(self.cantrips)}/{self.character_class.cantrips_known})",
                    )
                )
            if self.step in self.skill_steps:
                buttons.append(
                    CreationButton(
                        7,
                        f"Продолжить ({len(self.selected_skills(self.step))}/{self.skill_count(self.step)})",
                    )
                )
            if self.page_count > 1:
                if self.selection_page > 0:
                    buttons.append(CreationButton(8, "Предыдущая страница"))
                if self.selection_page < self.page_count - 1:
                    buttons.append(CreationButton(9, "Следующая страница"))
        elif self.step is CreationStep.ROLL:
            buttons = [
                CreationButton(1, "Перебросить весь набор"),
                CreationButton(2, "Распределить результаты"),
            ]
        elif self.step is CreationStep.DISTRIBUTE:
            buttons = [
                CreationButton(i + 1, f"Значение {roll.total} (бросок {i + 1})")
                for i, roll in enumerate(self.rolls)
                if i not in self.assignments
            ]
        else:
            buttons = [
                CreationButton(1, "Начать приключение"),
                CreationButton(2, "Перебросить характеристики"),
            ]
        return tuple(buttons + [CreationButton(0, "Назад")])

    @property
    def focused_button(self) -> CreationButton:
        return self.buttons[min(self.cursor, len(self.buttons) - 1)]

    @property
    def focused_option(self):
        number = self.focused_button.number
        return (
            self.visible_options[number - 1]
            if 1 <= number <= len(self.visible_options)
            else None
        )

    def move(self, direction: int):
        self.cursor = (self.cursor + direction) % len(self.buttons)

    def change_page(self, direction: int):
        self.selection_page = max(
            0, min(self.page_count - 1, self.selection_page + direction)
        )
        self.cursor = 0

    def select(self, number: int) -> Hero | None:
        if self.step in (
            CreationStep.RACE,
            CreationStep.CLASS,
            CreationStep.BACKGROUND,
            CreationStep.CANTRIPS,
            *self.skill_steps,
        ):
            if number == 8:
                self.change_page(-1)
            elif number == 9:
                self.change_page(1)
            elif number == 7 and self.step is CreationStep.CANTRIPS:
                if len(self.cantrips) == self.character_class.cantrips_known:
                    self.step = CreationStep.CONFIRM
                    self.cursor = 0
            elif number == 7 and self.step in self.skill_steps:
                if len(self.selected_skills(self.step)) == self.skill_count(self.step):
                    self.advance_skill_step(self.step)
            elif (
                self.step is CreationStep.BACKGROUND
                and not self.options
                and number == 1
            ):
                self.background = None
                self.accept_background()
            elif 1 <= number <= len(self.visible_options):
                selected = self.visible_options[number - 1]
                if self.step in self.skill_steps:
                    chosen = self.selected_skills(self.step)
                    if selected.id in chosen:
                        chosen.remove(selected.id)
                    elif len(chosen) < self.skill_count(self.step):
                        chosen.append(selected.id)
                    if self.step is not CreationStep.EXPERTISE:
                        self.expertise.clear()
                    if self.step is CreationStep.SKILLS:
                        self.extra_skills.clear()
                    return None
                if self.step is CreationStep.CANTRIPS:
                    if selected.id in self.cantrips:
                        self.cantrips.remove(selected.id)
                    elif len(self.cantrips) < self.character_class.cantrips_known:
                        self.cantrips.append(selected.id)
                    return None
                self.selection_page = 0
                self.cursor = 0
                if self.step is CreationStep.RACE:
                    self.race = selected
                    self.step = CreationStep.CLASS
                elif self.step is CreationStep.CLASS:
                    self.character_class = selected
                    self.cantrips.clear()
                    self.background = None
                    self.step = CreationStep.BACKGROUND
                else:
                    self.background = selected
                    self.accept_background()
        elif self.step is CreationStep.ROLL:
            if number == 1:
                self.reroll()
            elif number == 2:
                self.assignments.clear()
                self.step = CreationStep.DISTRIBUTE
                self.cursor = 0
        elif self.step is CreationStep.DISTRIBUTE:
            index = number - 1
            if 0 <= index < len(self.rolls) and index not in self.assignments:
                self.assignments.append(index)
                if len(self.assignments) == len(Ability):
                    self.step = (
                        CreationStep.CANTRIPS
                        if self.character_class.cantrips_known
                        else CreationStep.CONFIRM
                    )
                self.cursor = 0
        elif self.step is CreationStep.CONFIRM:
            if number == 1:
                return self.preview()
            if number == 2:
                self.reroll()
        return None

    def accept_background(self):
        self.assignments.clear()
        self.skills.clear()
        self.extra_skills.clear()
        self.expertise.clear()
        self.advance_skill_step(CreationStep.BACKGROUND)

    def advance_skill_step(self, previous):
        remaining = [
            s
            for s in self.skill_steps
            if self.skill_count(s) and s.value > previous.value
        ]
        self.cursor = self.selection_page = 0
        if remaining:
            self.step = remaining[0]
            return
        if not self.rolls:
            self.reroll()
        else:
            self.step = CreationStep.ROLL
            self.cursor = 1

    def back(self) -> None:
        self.selection_page = 0
        self.cursor = 0
        if self.step is CreationStep.CLASS:
            self.step = CreationStep.RACE
        elif self.step is CreationStep.ROLL:
            self.step = next(
                (s for s in reversed(self.skill_steps) if self.skill_count(s)),
                CreationStep.BACKGROUND,
            )
        elif self.step in self.skill_steps:
            self.step = next(
                (
                    s
                    for s in reversed(self.skill_steps)
                    if s.value < self.step.value and self.skill_count(s)
                ),
                CreationStep.BACKGROUND,
            )
        elif self.step is CreationStep.BACKGROUND:
            self.step = CreationStep.CLASS
        elif self.step is CreationStep.DISTRIBUTE:
            if self.assignments:
                self.assignments.pop()
            else:
                self.step = CreationStep.ROLL
        elif self.step is CreationStep.CONFIRM:
            if self.character_class.cantrips_known:
                self.step = CreationStep.CANTRIPS
            else:
                self.assignments.pop()
                self.step = CreationStep.DISTRIBUTE
        elif self.step is CreationStep.CANTRIPS:
            self.assignments.pop()
            self.step = CreationStep.DISTRIBUTE
