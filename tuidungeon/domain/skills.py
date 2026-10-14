"""The 18 SRD 5.2.1 skills and shared character-creation selection rules."""

from dataclasses import dataclass
from typing import Literal
from .rules import Ability

SkillId = Literal[
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
]


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    ability: Ability


SKILLS = {
    key: Skill(key, name, Ability[ability.upper()])
    for key, name, ability in (
        ("acrobatics", "Акробатика", "dexterity"),
        ("animal_handling", "Уход за животными", "wisdom"),
        ("arcana", "Магия", "intelligence"),
        ("athletics", "Атлетика", "strength"),
        ("deception", "Обман", "charisma"),
        ("history", "История", "intelligence"),
        ("insight", "Проницательность", "wisdom"),
        ("intimidation", "Запугивание", "charisma"),
        ("investigation", "Расследование", "intelligence"),
        ("medicine", "Медицина", "wisdom"),
        ("nature", "Природа", "intelligence"),
        ("perception", "Внимательность", "wisdom"),
        ("performance", "Выступление", "charisma"),
        ("persuasion", "Убеждение", "charisma"),
        ("religion", "Религия", "intelligence"),
        ("sleight_of_hand", "Ловкость рук", "dexterity"),
        ("stealth", "Скрытность", "dexterity"),
        ("survival", "Выживание", "wisdom"),
    )
}
ALIASES = {skill.name.casefold(): key for key, skill in SKILLS.items()}
ALIASES.update(
    {
        "анализ": "investigation",
        "обращение с животными": "animal_handling",
        "восприятие": "perception",
    }
)


def skill_id(value):
    key = ALIASES.get(value.casefold(), value) if isinstance(value, str) else value
    if not isinstance(key, str) or key not in SKILLS:
        raise ValueError(f"Неизвестный навык: {value}")
    return key


def skill_list(values):
    if not isinstance(values, (list, tuple)):
        raise ValueError("Нужен список навыков")
    result = [skill_id(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError("Навыки не должны повторяться")
    return result


def starting_skills(race, character_class, background):
    grants = (*race.skills, *(background.skills if background else ()))
    known = set(grants)
    choices = [s for s in character_class.skill_choices if s not in known]
    if len(choices) < character_class.skills_known:
        choices += [s for s in SKILLS if s not in known and s not in choices]
    return known, choices, len(grants) - len(known)


def select_skills(choices, count, selected=None):
    selected = list(choices[:count]) if selected is None else skill_list(selected)
    if len(selected) != count or not set(selected).issubset(choices):
        raise ValueError(f"Выберите {count} различных доступных навыков")
    return set(selected)
