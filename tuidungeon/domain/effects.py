"""Registered effects shared by spells, items, special actions and challenges."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from .definitions import EffectSpec
from .rules import Dice

if TYPE_CHECKING:
    from .actors import Character


@dataclass(frozen=True)
class EffectOutcome:
    kind: str
    amount: int = 0
    condition: str = ""
    target: "Character | None" = field(default=None, repr=False, compare=False)


class EffectHandler(ABC):
    @abstractmethod
    def apply(
        self, effect: EffectSpec, target: "Character", dice: Dice
    ) -> EffectOutcome:
        """Apply one validated effect and return its actual result."""


class DamageEffect(EffectHandler):
    def apply(self, effect, target, dice):
        amount = effect.amount + (effect.dice.roll(dice) if effect.dice else 0)
        return EffectOutcome("damage", target.take_damage(amount))


class HealingEffect(EffectHandler):
    def apply(self, effect, target, dice):
        amount = effect.amount + (effect.dice.roll(dice) if effect.dice else 0)
        return EffectOutcome("heal", target.heal(amount))


class RewardEffect(EffectHandler):
    def apply(self, effect, target, dice):
        amount = effect.amount + (effect.dice.roll(dice) if effect.dice else 0)
        setattr(target, effect.kind, getattr(target, effect.kind) + amount)
        return EffectOutcome(effect.kind, amount)


class ConditionEffect(EffectHandler):
    def apply(self, effect, target, dice):
        target.conditions[effect.condition] = max(
            effect.duration, target.conditions.get(effect.condition, 0)
        )
        return EffectOutcome("condition", condition=effect.condition)


class EffectRegistry:
    def __init__(self):
        self.handlers: dict[str, EffectHandler] = {}

    def register(self, kind: str, handler: EffectHandler) -> None:
        if kind in self.handlers:
            raise ValueError(f"Эффект уже зарегистрирован: {kind}")
        self.handlers[kind] = handler

    def validate(self, effects: tuple[EffectSpec, ...]) -> None:
        for effect in effects:
            if effect.kind not in self.handlers:
                raise ValueError(f"Нет обработчика эффекта: {effect.kind}")

    def apply_all(
        self, effects: tuple[EffectSpec, ...], target: "Character", dice: Dice
    ) -> tuple[EffectOutcome, ...]:
        self.validate(effects)  # Reject unsupported mechanics before any mutation.
        return tuple(
            replace(
                self.handlers[effect.kind].apply(effect, target, dice), target=target
            )
            for effect in effects
        )

    @classmethod
    def default(cls) -> "EffectRegistry":
        registry = cls()
        for kind, handler in (
            ("damage", DamageEffect()),
            ("heal", HealingEffect()),
            ("gold", RewardEffect()),
            ("experience", RewardEffect()),
            ("condition", ConditionEffect()),
        ):
            registry.register(kind, handler)
        from .mechanics import mechanics

        return mechanics.extend(registry)
