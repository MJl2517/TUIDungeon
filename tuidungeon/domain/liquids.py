"""Liquids use whole portions; carrying mass remains in kilograms."""

from dataclasses import dataclass
from typing import Literal

WaterKind = Literal[
    "clean_water",
    "dirty_water",
    "swamp_water",
    "salt_water",
    "poisoned_water",
    "holy_water",
]
LiquidKind = Literal[
    "clean_water",
    "dirty_water",
    "swamp_water",
    "salt_water",
    "poisoned_water",
    "holy_water",
    "healing_broth",
    "healing_potion",
    "antidote",
    "cactus_juice",
]
LIQUID_NAMES = dict(
    clean_water="Чистая вода",
    dirty_water="Грязная вода",
    swamp_water="Болотная вода",
    salt_water="Солёная вода",
    poisoned_water="Отравленная вода",
    holy_water="Святая вода",
    healing_broth="Лечебный отвар",
    healing_potion="Лечебное зелье",
    antidote="Противоядный отвар",
    cactus_juice="Сок кактуса",
)
WATER_KINDS = tuple(k for k in LIQUID_NAMES if k.endswith("water"))
PORTION_WEIGHT = 0.1
LEGACY_VESSELS = {
    "water_flask": (250, 1),
    "glass_flask": (500, 1),
    "healing_potion": (100, 1),
    "waterskin": (1000, 2),
    "cooking_pot": (500, 3),
    "clay_pot": (500, 3),
}


def portion_text(n):
    word = (
        "порция"
        if n % 10 == 1 and n % 100 != 11
        else "порции"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14
        else "порций"
    )
    return f"{n} {word}"


def legacy_portions(amount, identifier=None):
    if type(amount) is not int or amount < 0:
        raise ValueError("Недопустимый старый объём жидкости")
    old, new = LEGACY_VESSELS.get((identifier or "").removeprefix("base:"), (250, 1))
    if (
        identifier
        and (identifier.removeprefix("base:") in LEGACY_VESSELS)
        and amount > old
    ):
        raise ValueError("Старый объём превышает вместимость сосуда")
    return (amount * new + old - 1) // old


def migrate_vessel(raw, identifier=None):
    if not isinstance(raw, dict) or "capacity_ml" not in raw:
        return raw
    data = dict(raw)
    old = data.pop("capacity_ml")
    if type(old) is not int or old <= 0:
        raise ValueError("Недопустимая старая вместимость")
    if "capacity_portions" in data or "initial_portions" in data:
        raise ValueError("Нельзя смешивать старые объёмы и порции")
    data["capacity_portions"] = LEGACY_VESSELS.get(
        identifier, (old, max(1, (old + 249) // 250))
    )[1]
    initial = data.pop("initial_ml", 0)
    if type(initial) is not int or not 0 <= initial <= old:
        raise ValueError("Недопустимое старое содержимое сосуда")
    data["initial_portions"] = (initial * data["capacity_portions"] + old - 1) // old
    return data


@dataclass(frozen=True)
class VesselDefinition:
    capacity_portions: int = 1
    heat_safe: bool = False
    fragile: bool = False
    initial_kind: str | None = None
    initial_portions: int = 0


def spend_liquid(item, amount):
    if type(amount) is not int or not 0 < amount <= item.liquid_portions:
        raise ValueError("Недопустимое количество порций")
    item.liquid_portions -= amount
    if not item.liquid_portions:
        item.liquid_kind = None
        item.liquid_effects = ()


def drink_liquid(item, target, dice, effects):
    from .actions import ActionOutcome
    from .definitions import EffectSpec, DiceExpression

    if not item.liquid_portions:
        return ActionOutcome(False, False, "Сосуд пуст.")
    kind = item.liquid_kind
    specs = []
    if kind == "healing_potion":
        specs = [EffectSpec(kind="heal", dice=DiceExpression.parse("2d4+2"))]
    elif kind == "healing_broth":
        specs = [EffectSpec(kind="heal", amount=4)]
    elif kind == "antidote":
        target.conditions.pop("poisoned", None)
    elif kind in ("dirty_water", "swamp_water", "poisoned_water"):
        specs = [EffectSpec(kind="condition", condition="poisoned", duration=5)]
    outcomes = effects.apply_all(item.liquid_effects or specs, target, dice)
    amount = 1
    spend_liquid(item, amount)
    if item.charges is not None:
        item.charges = max(0, item.charges - 1)
    return ActionOutcome(
        True,
        True,
        f"Выпито: {LIQUID_NAMES[kind]}, 1 порция; тара сохранена.",
        effects=outcomes,
    )


def liquid_effect_records(item):
    from dataclasses import asdict

    result = []
    for e in item.liquid_effects:
        raw = asdict(e)
        raw["dice"] = (
            f"{e.dice.count}d{e.dice.sides}{e.dice.bonus:+d}" if e.dice else None
        )
        result.append(raw)
    return result
