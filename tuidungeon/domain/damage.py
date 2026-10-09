"""Typed damage and immutable defenses, independent of combat and rendering."""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, get_args

DamageType = Literal[
    "bludgeoning",
    "piercing",
    "slashing",
    "acid",
    "cold",
    "fire",
    "lightning",
    "thunder",
    "force",
    "necrotic",
    "psychic",
    "radiant",
    "poison",
]
DamageSelector = Literal[
    "bludgeoning",
    "piercing",
    "slashing",
    "acid",
    "cold",
    "fire",
    "lightning",
    "thunder",
    "force",
    "necrotic",
    "psychic",
    "radiant",
    "poison",
    "physical",
    "elemental",
    "mystic",
    "toxic",
]
DAMAGE_TYPES = frozenset(get_args(DamageType))
DAMAGE_GROUPS = {
    "physical": frozenset({"bludgeoning", "piercing", "slashing"}),
    "elemental": frozenset({"acid", "cold", "fire", "lightning", "thunder"}),
    "mystic": frozenset({"force", "necrotic", "psychic", "radiant"}),
    "toxic": frozenset({"poison"}),
}
DAMAGE_LABELS = {
    "bludgeoning": "Дробящий",
    "piercing": "Колющий",
    "slashing": "Рубящий",
    "acid": "Кислота",
    "cold": "Холод",
    "fire": "Огонь",
    "lightning": "Электрический",
    "thunder": "Громовой",
    "force": "Силовой",
    "necrotic": "Некротический",
    "psychic": "Психический",
    "radiant": "Лучистый",
    "poison": "Ядовитый",
    "physical": "Физический (все 3 типа)",
    "elemental": "Элементальный (все 5 типов)",
    "mystic": "Мистический (все 4 типа)",
    "toxic": "Токсический (яд)",
}


def validate_damage(amount, damage_type, *, allow_untyped=True):
    if type(amount) is not int or amount < 0:
        raise ValueError("Урон должен быть целым неотрицательным числом")
    if damage_type is None and not allow_untyped:
        raise ValueError("Нужен один из 13 типов урона")
    if damage_type is not None and (
        not isinstance(damage_type, str) or damage_type not in DAMAGE_TYPES
    ):
        raise ValueError(f"Неизвестный тип урона: {damage_type}")


def expand(selectors):
    result = set()
    for selector in selectors:
        if selector in DAMAGE_TYPES:
            result.add(selector)
        elif selector in DAMAGE_GROUPS:
            result.update(DAMAGE_GROUPS[selector])
        else:
            raise ValueError(f"Неизвестный тип или группа урона: {selector}")
    return frozenset(result)


@dataclass(frozen=True)
class DamageProfile:
    resistances: frozenset[str] = frozenset()
    vulnerabilities: frozenset[str] = frozenset()
    immunities: frozenset[str] = frozenset()
    _expanded: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        values = []
        for name in ("resistances", "vulnerabilities", "immunities"):
            selectors = frozenset(getattr(self, name))
            object.__setattr__(self, name, selectors)
            values.append(expand(selectors))
        object.__setattr__(self, "_expanded", tuple(values))

    def merge(self, *others):
        return merged_profiles((self, *others)) if others else self

    def resolve(self, amount: int, damage_type: DamageType | None = None):
        validate_damage(amount, damage_type)
        resistance, vulnerability, immunity = self._expanded
        response = "normal"
        result = amount
        if damage_type in immunity:
            result, response = 0, "immune"
        elif damage_type in resistance and damage_type in vulnerability:
            response = "cancelled"
        elif damage_type in resistance:
            result, response = amount // 2, "resistant"
        elif damage_type in vulnerability:
            result, response = amount * 2, "vulnerable"
        return DamageResult(damage_type, amount, result, response)


@dataclass(frozen=True)
class DamageResult:
    damage_type: DamageType | None
    raw_amount: int
    resolved_amount: int
    response: str
    applied_amount: int = 0


@lru_cache(maxsize=1024)
def merged_profiles(profiles):
    return DamageProfile(
        **{
            name: frozenset().union(*(getattr(p, name) for p in profiles))
            for name in ("resistances", "vulnerabilities", "immunities")
        }
    )


def profile_details(profile):
    return [
        f"{label}: {', '.join(DAMAGE_LABELS[s] for s in sorted(getattr(profile, name)))}."
        for name, label in (
            ("resistances", "Сопротивления ×½"),
            ("vulnerabilities", "Уязвимости ×2"),
            ("immunities", "Иммунитеты"),
        )
        if getattr(profile, name)
    ]
