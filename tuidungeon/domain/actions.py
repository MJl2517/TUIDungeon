"""OO action strategies. JSON supplies parameters, registered classes execute them."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .definitions import ActionDefinition, DiceExpression, EffectSpec
from .effects import EffectOutcome, EffectRegistry
from .rules import CheckResult, Dice

if TYPE_CHECKING:
    from .actors import Character


class SpellSource(Enum):
    CLASS = "class"
    RACIAL = "racial"


@dataclass(frozen=True)
class ActionContext:
    dice: Dice
    target: "Character | None" = None
    difficulty: int | None = None
    spell_id: str | None = None
    spell_source: SpellSource = SpellSource.CLASS
    weapon_id: str | None = None
    mode: str = "combat"
    targets: tuple = ()


@dataclass(frozen=True)
class ActionOutcome:
    performed: bool
    success: bool
    message: str
    check: CheckResult | None = None
    effects: tuple[EffectOutcome, ...] = ()


class CharacterAction(ABC):
    @abstractmethod
    def execute(
        self,
        definition: ActionDefinition,
        actor: "Character",
        context: ActionContext,
        effects: EffectRegistry,
    ) -> ActionOutcome:
        """Execute an action independently of the map or terminal."""


class AttackAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        target = context.target
        if target is None or target is actor or target.hp <= 0:
            return ActionOutcome(False, False, "Нужна живая цель атаки.")
        ability, damage, damage_type = (
            definition.ability,
            definition.damage,
            definition.damage_type,
        )
        if damage is None:
            weapons = [
                item
                for item in actor.inventory
                if item.usable and item.equipped and item.definition.weapon_damage
            ]
            weapon = (
                next((item for item in weapons if item.id == context.weapon_id), None)
                if context.weapon_id
                else next(iter(weapons), None)
            )
            if context.weapon_id and weapon is None:
                return ActionOutcome(False, False, "Оружие не найдено или недоступно.")
            if weapon:
                ability, damage = (
                    weapon.definition.weapon_ability,
                    weapon.definition.weapon_damage,
                )
                damage_type = weapon.damage_type
            else:
                damage = DiceExpression(1, 4)
                damage_type = "bludgeoning"
        check = context.dice.check(
            actor.stats.score(ability),
            target.armor_class,
            bonus=definition.bonus,
            advantage="hidden" in actor.conditions,
            disadvantage="dodging" in target.conditions,
        )
        if not check.success:
            return ActionOutcome(True, False, "Атака не попала.", check)
        amount = max(0, damage.roll(context.dice) + actor.stats.modifier(ability))
        outcome = effects.apply_all(
            (EffectSpec("damage", amount, damage_type=damage_type),)
            + definition.effects,
            target,
            context.dice,
        )
        return ActionOutcome(True, True, "Атака попала.", check, outcome)


class DodgeAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        result = effects.apply_all(
            (EffectSpec("condition", condition="dodging"),) + definition.effects,
            actor,
            context.dice,
        )
        return ActionOutcome(True, True, "Персонаж уклоняется.", effects=result)


class StealthAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        difficulty = (
            context.difficulty
            if context.difficulty is not None
            else definition.difficulty
        )
        check = context.dice.check(
            actor.stats.score(definition.ability), difficulty, bonus=definition.bonus
        )
        if not check.success:
            return ActionOutcome(True, False, "Не удалось скрыться.", check)
        result = effects.apply_all(
            (EffectSpec("condition", condition="hidden"),) + definition.effects,
            actor,
            context.dice,
        )
        return ActionOutcome(True, True, "Персонаж скрылся.", check, result)


class InfluenceAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        difficulty = (
            context.difficulty
            if context.difficulty is not None
            else definition.difficulty
        )
        check = context.dice.check(
            actor.stats.score(definition.ability), difficulty, bonus=definition.bonus
        )
        if not check.success:
            return ActionOutcome(True, False, "Влияние не удалось.", check)
        result = effects.apply_all(
            definition.effects, context.target or actor, context.dice
        )
        return ActionOutcome(True, True, "Проверка влияния пройдена.", check, result)


class MagicAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        if context.spell_source is SpellSource.CLASS:
            spell = next(
                (spell for spell in actor.class_spells if spell.id == context.spell_id),
                None,
            )
            available = spell is not None and (
                actor.cantrip_uses > 0
                if spell.level == 0
                else actor.spell_slots.get(spell.level, 0) > 0
            )
        elif context.spell_source is SpellSource.RACIAL:
            spell = (
                actor.racial_spell
                if actor.racial_spell and actor.racial_spell.id == context.spell_id
                else None
            )
            available = spell is not None and (
                actor.cantrip_uses > 0 if spell.level == 0 else actor.racial_uses > 0
            )
        else:
            return ActionOutcome(False, False, "Неизвестный источник магии.")
        if not available:
            return ActionOutcome(False, False, "Заклинание или ресурс недоступны.")
        if context.mode not in spell.modes:
            return ActionOutcome(
                False, False, "Это заклинание недоступно в этом режиме."
            )
        if spell.target == "item" or not spell.effects:
            return ActionOutcome(
                False, False, "Нужна карта/предмет или механика будущего боя."
            )
        target = context.target or actor
        if (spell.target == "other" and target is actor) or (
            spell.target == "self" and target is not actor
        ):
            return ActionOutcome(False, False, "Неподходящая цель заклинания.")
        targets = context.targets or (target,)
        if (
            len(targets) > spell.max_targets
            or len({id(t) for t in targets}) != len(targets)
            or any(
                t.hp <= 0
                or (spell.target == "other" and t is actor)
                or (spell.target == "self" and t is not actor)
                for t in targets
            )
        ):
            return ActionOutcome(False, False, "Недопустимый набор целей.")
        effects.validate(spell.effects)
        if context.spell_source is SpellSource.RACIAL:
            actor.consume_racial_spell()
        else:
            actor.consume_class_slot(spell.id)
        result, checks = [], []
        for target in targets:
            check, hit = spell_check(actor, target, spell, context.dice)
            if check:
                checks.append(check)
            if hit:
                result.extend(
                    effects.apply_all(
                        scaled_spell_effects(spell, actor, target), target, context.dice
                    )
                )
        message = f"Применено: {spell.name}."
        if checks:
            message += (
                " "
                + "; ".join(
                    f"d20 {c.roll} + {c.modifier} = {c.total} против {c.difficulty}"
                    for c in checks
                )
                + "."
            )
        if spell.pending_effects:
            message += " Пока не реализовано: " + "; ".join(spell.pending_effects) + "."
        return ActionOutcome(
            True, bool(result), message, checks[0] if checks else None, tuple(result)
        )


def spell_check(actor, target, spell, dice):
    if spell.resolution == "attack":
        check = dice.check(
            actor.stats.score(actor.spellcasting_ability),
            target.armor_class,
            bonus=actor.proficiency_bonus,
        )
        return check, check.success
    if spell.resolution == "save":
        check = dice.check(target.stats.score(spell.save_ability), actor.spell_save_dc)
        return check, not check.success
    return None, True


def scaled_spell_effects(spell, actor, target):
    from dataclasses import replace
    from .spellcasting import scaling_multiplier

    multiplier = (
        scaling_multiplier(getattr(actor, "level", 1)) if spell.cantrip_scaling else 1
    )
    result = []
    for effect in spell.effects:
        expression = (
            spell.wounded_dice
            if effect.kind == "damage"
            and spell.wounded_dice
            and target.hp < target.max_hp
            else effect.dice
        )
        if expression and effect.kind == "damage":
            expression = replace(expression, count=expression.count * multiplier)
        result.append(replace(effect, dice=expression))
    return tuple(result)


class SpecialAction(CharacterAction):
    def execute(self, definition, actor, context, effects):
        target = context.target or actor
        check = None
        if context.difficulty is not None:
            check = context.dice.check(
                actor.stats.score(definition.ability),
                context.difficulty,
                bonus=definition.bonus,
            )
            if not check.success:
                return ActionOutcome(True, False, "Особое действие не удалось.", check)
        result = effects.apply_all(definition.effects, target, context.dice)
        return ActionOutcome(True, True, definition.name, check, result)


class ActionRegistry:
    def __init__(self, effects: EffectRegistry | None = None):
        self.effects = effects or EffectRegistry.default()
        self.handlers: dict[str, CharacterAction] = {}

    def register(self, kind: str, handler: CharacterAction) -> None:
        if kind in self.handlers:
            raise ValueError(f"Действие уже зарегистрировано: {kind}")
        self.handlers[kind] = handler

    def execute(
        self, definition: ActionDefinition, actor: "Character", context: ActionContext
    ) -> ActionOutcome:
        if actor.hp <= 0:
            return ActionOutcome(False, False, "Персонаж без сознания.")
        if definition.kind not in self.handlers:
            raise ValueError(f"Нет обработчика действия: {definition.kind}")
        self.effects.validate(definition.effects)
        return self.handlers[definition.kind].execute(
            definition, actor, context, self.effects
        )

    @classmethod
    def default(cls, effects: EffectRegistry | None = None) -> "ActionRegistry":
        registry = cls(effects)
        for kind, handler in (
            ("attack", AttackAction()),
            ("dodge", DodgeAction()),
            ("stealth", StealthAction()),
            ("magic", MagicAction()),
            ("influence", InfluenceAction()),
            ("special", SpecialAction()),
        ):
            registry.register(kind, handler)
        return registry
