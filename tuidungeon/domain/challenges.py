"""Abstract adventure situation and the standard data-driven text challenge."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .actors import Character
from .definitions import ChallengeChoice, ChallengeDefinition
from .effects import EffectOutcome, EffectRegistry
from .rules import CheckResult, Dice


@dataclass(frozen=True)
class ChallengeResult:
    performed: bool
    success: bool
    minutes: int
    message: str
    check: CheckResult | None = None
    effects: tuple[EffectOutcome, ...] = ()


class Challenge(ABC):
    @property
    @abstractmethod
    def text(self) -> str:
        """Narrative shown to the player."""

    @property
    @abstractmethod
    def choices(self) -> tuple[ChallengeChoice, ...]:
        """Available choices, requirements and consequences."""

    @abstractmethod
    def resolve(self, choice_id: str, actor: Character, dice: Dice) -> ChallengeResult:
        """Evaluate a choice and apply its consequences."""


class TextChallenge(Challenge):
    def __init__(
        self, definition: ChallengeDefinition, effects: EffectRegistry | None = None
    ):
        self.definition = definition
        self.effects = effects or EffectRegistry.default()
        self.completed = False

    @property
    def text(self) -> str:
        return self.definition.text

    @property
    def choices(self) -> tuple[ChallengeChoice, ...]:
        return self.definition.choices

    def resolve(self, choice_id: str, actor: Character, dice: Dice) -> ChallengeResult:
        if self.completed and not self.definition.repeatable:
            return ChallengeResult(False, False, 0, "Ситуация уже разрешена.")
        if actor.hp <= 0:
            return ChallengeResult(False, False, 0, "Персонаж без сознания.")
        choice = next((entry for entry in self.choices if entry.id == choice_id), None)
        if choice is None:
            return ChallengeResult(False, False, 0, "Неизвестный вариант действия.")
        if not choice.required_tags.issubset(actor.tags):
            return ChallengeResult(
                False, False, 0, "Не хватает необходимых инструментов или свойств."
            )
        self.effects.validate(choice.success + choice.failure)
        aids = (
            {item.check_support(choice.check_tag) for item in actor.inventory}
            if choice.check_tag
            else set()
        )
        automatic = bool(choice.automatic_tags & actor.tags) or "automatic" in aids
        advantage = bool(choice.advantage_tags & actor.tags) or "advantage" in aids
        check = None
        if choice.ability is not None and not automatic:
            check = dice.check(
                actor.stats.score(choice.ability),
                choice.difficulty,
                advantage=advantage,
            )
        success = check is None or check.success
        outcomes = self.effects.apply_all(
            choice.success if success else choice.failure, actor, dice
        )
        self.completed = True
        return ChallengeResult(
            True,
            success,
            choice.minutes,
            "Испытание пройдено." if success else "Проверка провалена.",
            check,
            outcomes,
        )
