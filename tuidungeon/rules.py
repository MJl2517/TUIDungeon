"""Compatibility imports; new code uses tuidungeon.domain.rules."""

from .domain.rules import (
    Ability,
    AbilityRoll,
    CharacterClass,
    CheckResult,
    Dice,
    Race,
    modifier,
)

__all__ = [
    "Ability",
    "AbilityRoll",
    "CharacterClass",
    "CheckResult",
    "Dice",
    "Race",
    "modifier",
]
