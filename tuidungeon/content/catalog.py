"""Typed JSON catalog with structural and cross-reference validation."""

from dataclasses import dataclass, field
from functools import lru_cache
import json
import math
from pathlib import Path
import re

from ..domain.definitions import (
    ActionDefinition,
    BackgroundDefinition,
    ChallengeChoice,
    ChallengeDefinition,
    CheckAid,
    ClassDefinition,
    DiceExpression,
    EffectSpec,
    EquipmentDefinition,
    MonsterDefinition,
    RaceDefinition,
    Spell,
)
from ..domain.rules import Ability
from ..domain.stats import Stats


DEFAULT_ROOT = Path(__file__).parent / "data"
ACTION_KINDS = frozenset(
    {"attack", "dodge", "stealth", "magic", "influence", "special"}
)
EFFECT_KINDS = frozenset({"damage", "heal", "gold", "experience", "condition"})
PASSIVE_KINDS = frozenset({"armor_class", "armor_bonus"})


class ContentError(ValueError):
    """Invalid content with a filename and field in the error message."""


def identifier(value, label="id") -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[a-z][a-z0-9_]*(?::[a-z][a-z0-9_]*)?", value) is None
    ):
        raise ContentError(f"{label}: нужен идентификатор вида goblin_scout")
    return value


def text(value, label, *, empty=False, multiline=False) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or any(ord(c) < 32 and (not multiline or c not in "\n\r\t") for c in value)
    ):
        raise ContentError(f"{label}: нужна печатная строка")
    return value


def integer(value, label, minimum=None, maximum=None) -> int:
    if (
        type(value) is not int
        or (minimum is not None and value < minimum)
        or (maximum is not None and value > maximum)
    ):
        raise ContentError(f"{label}: недопустимое целое число {value!r}")
    return value


def number(value, label, minimum=0) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ContentError(f"{label}: нужно конечное число >= {minimum}")
    return float(value)


def boolean(value, label) -> bool:
    if type(value) is not bool:
        raise ContentError(f"{label}: нужно true или false")
    return value


def sequence(value, label) -> list:
    if not isinstance(value, list):
        raise ContentError(f"{label}: нужен массив")
    return value


def names(value, label) -> tuple[str, ...]:
    return tuple(identifier(entry, label) for entry in sequence(value, label))


def fields(value, allowed, required=()):
    if not isinstance(value, dict):
        raise ContentError("Ожидается JSON-объект")
    unknown, missing = set(value) - set(allowed), set(required) - set(value)
    if unknown:
        raise ContentError(f"Неизвестные поля: {', '.join(sorted(unknown))}")
    if missing:
        raise ContentError(f"Не хватает полей: {', '.join(sorted(missing))}")
    return value


def ability(value) -> Ability:
    try:
        return Ability[value.upper()]
    except (KeyError, AttributeError):
        raise ContentError(f"Неизвестная характеристика: {value!r}") from None


def bonuses(value) -> tuple[int, ...]:
    fields(value, [entry.name.lower() for entry in Ability])
    return tuple(
        integer(value.get(entry.name.lower(), 0), "ability_bonuses")
        for entry in Ability
    )


def slots(value) -> tuple[tuple[int, int], ...]:
    fields(value, [str(level) for level in range(1, 10)])
    return tuple(
        (int(level), integer(count, "spell_slots", 0))
        for level, count in sorted(value.items())
    )


def expression(value) -> DiceExpression | None:
    if value is None:
        return None
    return DiceExpression.parse(text(value, "dice"))


def effect(value, kinds) -> EffectSpec:
    fields(
        value, {"kind", "amount", "dice", "condition", "duration", "params"}, {"kind"}
    )
    kind = identifier(value["kind"], "effect.kind")
    if kind not in kinds:
        raise ContentError(f"Неизвестная механика эффекта: {kind}")
    condition = value.get("condition", "")
    if kind == "condition":
        condition = identifier(condition, "condition")
    elif condition:
        raise ContentError("condition допустимо только для эффекта condition")
    dice = expression(value.get("dice"))
    if dice is not None and kind not in {"damage", "heal", "gold", "experience"}:
        raise ContentError(f"Эффект {kind} не поддерживает dice")
    return EffectSpec(
        kind,
        integer(value.get("amount", 0), "amount", 0),
        dice,
        condition,
        integer(value.get("duration", 1), "duration", 1),
        value.get("params", {}),
    )


def action(value, action_kinds, effect_kinds) -> ActionDefinition:
    fields(
        value,
        {
            "id",
            "name",
            "kind",
            "ability",
            "bonus",
            "damage",
            "effects",
            "difficulty",
            "description",
        },
        {"id", "name", "kind"},
    )
    kind = identifier(value["kind"], "action.kind")
    if kind not in action_kinds:
        raise ContentError(f"Неизвестная механика действия: {kind}")
    return ActionDefinition(
        identifier(value["id"]),
        text(value["name"], "name"),
        kind,
        ability(value.get("ability", "strength")),
        integer(value.get("bonus", 0), "bonus"),
        expression(value.get("damage")),
        tuple(
            effect(entry, effect_kinds)
            for entry in sequence(value.get("effects", []), "effects")
        ),
        integer(value.get("difficulty", 10), "difficulty", 0),
        text(value.get("description", ""), "description", empty=True, multiline=True),
    )


def no_duplicate_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContentError(f"Повторное поле JSON: {key}")
        result[key] = value
    return result


@dataclass
class ContentCatalog:
    equipment: dict[str, EquipmentDefinition] = field(default_factory=dict)
    spells: dict[str, Spell] = field(default_factory=dict)
    actions: dict[str, ActionDefinition] = field(default_factory=dict)
    races: dict[str, RaceDefinition] = field(default_factory=dict)
    classes: dict[str, ClassDefinition] = field(default_factory=dict)
    backgrounds: dict[str, BackgroundDefinition] = field(default_factory=dict)
    monsters: dict[str, MonsterDefinition] = field(default_factory=dict)
    challenges: dict[str, ChallengeDefinition] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        root: Path | str | None = None,
        *,
        action_kinds=ACTION_KINDS,
        effect_kinds=EFFECT_KINDS,
    ) -> "ContentCatalog":
        root = Path(root) if root is not None else DEFAULT_ROOT
        if not root.is_dir():
            raise ContentError(f"Каталог контента не найден: {root}")
        result = cls()
        sources = {}
        for category in result.__dataclass_fields__:
            target = getattr(result, category)
            for path in sorted((root / category).rglob("*.json")):
                try:
                    raw = json.loads(
                        path.read_text(encoding="utf-8"),
                        object_pairs_hook=no_duplicate_fields,
                    )
                    if not isinstance(raw, dict):
                        raise ContentError("В файле должен быть один объект")
                    version = integer(raw.pop("schema_version", None), "schema_version")
                    if version != 1:
                        raise ContentError(
                            f"Неподдерживаемая schema_version: {version}"
                        )
                    definition = result._parse(
                        category, raw, action_kinds, effect_kinds
                    )
                    if definition.id in target:
                        raise ContentError(
                            f"Повторный id в {category}: {definition.id}"
                        )
                    target[definition.id] = definition
                    sources[(category, definition.id)] = path
                except (ValueError, KeyError, TypeError, OSError) as error:
                    raise ContentError(f"{path}: {error}") from error
        result._validate_references(sources)
        return result

    def _parse(self, category, value, action_kinds, effect_kinds):
        if category == "actions":
            return action(value, action_kinds, effect_kinds)
        definition_type = {
            "equipment": EquipmentDefinition,
            "spells": Spell,
            "races": RaceDefinition,
            "classes": ClassDefinition,
            "backgrounds": BackgroundDefinition,
            "monsters": MonsterDefinition,
            "challenges": ChallengeDefinition,
        }[category]
        fields(value, definition_type.__dataclass_fields__, {"id", "name"})
        data = dict(value)
        data["id"] = identifier(data["id"])
        data["name"] = text(data["name"], "name")
        if "description" in data:
            data["description"] = text(
                data["description"], "description", empty=True, multiline=True
            )
        if "order" in data:
            data["order"] = integer(data["order"], "order", 0)
        for key in ("tags",):
            if key in data:
                data[key] = frozenset(names(data[key], key))
        for key in ("starting_items", "inventory", "spells", "actions"):
            if key in data:
                data[key] = names(data[key], key)
                if key in ("spells", "actions") and len(set(data[key])) != len(
                    data[key]
                ):
                    raise ContentError(f"{key}: повторные ссылки")
        if "ability_bonuses" in data:
            data["ability_bonuses"] = bonuses(data["ability_bonuses"])
        if "spell_slots" in data:
            data["spell_slots"] = slots(data["spell_slots"])
        if category == "equipment":
            data["weight"] = number(data.get("weight", 0), "weight")
            for key in ("durability", "charges"):
                if data.get(key) is not None:
                    data[key] = integer(data[key], key, 1)
            if data.get("slot") is not None:
                data["slot"] = identifier(data["slot"], "slot")
            data["weapon_damage"] = expression(data.get("weapon_damage"))
            data["weapon_ability"] = ability(data.get("weapon_ability", "strength"))
            data["properties"] = tuple(
                effect(entry, effect_kinds | PASSIVE_KINDS)
                for entry in sequence(data.get("properties", []), "properties")
            )
            aids = []
            for entry in sequence(data.get("check_aids", []), "check_aids"):
                fields(entry, {"check_tag", "mode"}, {"check_tag", "mode"})
                if entry["mode"] not in ("advantage", "automatic"):
                    raise ContentError("check_aids.mode: нужно advantage или automatic")
                aids.append(
                    CheckAid(identifier(entry["check_tag"], "check_tag"), entry["mode"])
                )
            data["check_aids"] = tuple(aids)
        elif category == "spells":
            data["level"] = integer(data.get("level"), "level", 0, 9)
            if data.get("target", "self") not in ("self", "other", "any"):
                raise ContentError("target: нужно self, other или any")
            data["effects"] = tuple(
                effect(entry, effect_kinds)
                for entry in sequence(data.get("effects", []), "effects")
            )
        elif category == "races":
            for key in ("hp_per_level", "racial_uses", "speed"):
                if key in data:
                    data[key] = integer(data[key], key, 0)
            if data.get("racial_spell") is not None:
                data["racial_spell"] = identifier(data["racial_spell"], "racial_spell")
            if bool(data.get("racial_spell")) != bool(data.get("racial_uses", 0)):
                raise ContentError(
                    "racial_spell и положительное racial_uses должны задаваться вместе"
                )
        elif category == "classes":
            data["hit_points"] = integer(data.get("hit_points"), "hit_points", 1)
            data["carry_per_strength"] = number(
                data.get("carry_per_strength", 5), "carry_per_strength", 0.01
            )
        elif category == "monsters":
            raw_stats = data.get("stats")
            fields(
                raw_stats,
                [entry.name.lower() for entry in Ability],
                [entry.name.lower() for entry in Ability],
            )
            data["stats"] = Stats(
                tuple(
                    integer(raw_stats[entry.name.lower()], "stats", 1)
                    for entry in Ability
                )
            )
            for key, minimum in (
                ("hit_points", 1),
                ("armor_class", 0),
                ("speed", 0),
                ("initiative_bonus", None),
            ):
                data[key] = integer(
                    data.get(key, 0 if key == "initiative_bonus" else None),
                    key,
                    minimum,
                )
            data["special_actions"] = tuple(
                action(entry, action_kinds, effect_kinds)
                for entry in sequence(
                    data.get("special_actions", []), "special_actions"
                )
            )
            action_ids = list(data.get("actions", ())) + [
                entry.id for entry in data["special_actions"]
            ]
            if len(action_ids) != len(set(action_ids)):
                raise ContentError("Повторные id действий монстра")
            if data.get("art") is not None:
                data["art"] = identifier(data["art"], "art")
        elif category == "challenges":
            data["text"] = text(data.get("text"), "text", multiline=True)
            data["repeatable"] = boolean(data.get("repeatable", False), "repeatable")
            choices = []
            for entry in sequence(data.get("choices"), "choices"):
                fields(entry, ChallengeChoice.__dataclass_fields__, {"id", "text"})
                choice = dict(entry)
                choice["id"] = identifier(choice["id"])
                choice["text"] = text(choice["text"], "choice.text", multiline=True)
                choice["ability"] = (
                    ability(choice["ability"])
                    if choice.get("ability") is not None
                    else None
                )
                choice["difficulty"] = integer(
                    choice.get("difficulty", 10), "difficulty", 0
                )
                choice["minutes"] = integer(choice.get("minutes", 1), "minutes", 0)
                if "check_tag" in choice:
                    choice["check_tag"] = identifier(choice["check_tag"], "check_tag")
                for key in ("required_tags", "advantage_tags", "automatic_tags"):
                    choice[key] = frozenset(names(choice.get(key, []), key))
                for key in ("success", "failure"):
                    choice[key] = tuple(
                        effect(effect_data, effect_kinds)
                        for effect_data in sequence(choice.get(key, []), key)
                    )
                choices.append(ChallengeChoice(**choice))
            if not choices or len({choice.id for choice in choices}) != len(choices):
                raise ContentError("Нужны непустые варианты с уникальными id")
            data["choices"] = tuple(choices)
        return definition_type(**data)

    def _validate_references(self, sources):
        def require(category, content_id, owner_category, owner_id, label):
            if content_id not in getattr(self, category):
                path = sources[(owner_category, owner_id)]
                raise ContentError(
                    f"{path}: {label}: неизвестный id {content_id!r} в {category}"
                )

        for category in ("classes", "backgrounds", "monsters"):
            for definition in getattr(self, category).values():
                for item_id in getattr(definition, "starting_items", ()) + getattr(
                    definition, "inventory", ()
                ):
                    require("equipment", item_id, category, definition.id, "inventory")
                for spell_id in getattr(definition, "spells", ()):
                    require("spells", spell_id, category, definition.id, "spells")
                for action_id in getattr(definition, "actions", ()):
                    require("actions", action_id, category, definition.id, "actions")
        for race in self.races.values():
            if race.racial_spell:
                require("spells", race.racial_spell, "races", race.id, "racial_spell")

    @property
    def ordered_races(self) -> tuple[RaceDefinition, ...]:
        return tuple(
            sorted(self.races.values(), key=lambda entry: (entry.order, entry.id))
        )

    @property
    def ordered_classes(self) -> tuple[ClassDefinition, ...]:
        return tuple(
            sorted(self.classes.values(), key=lambda entry: (entry.order, entry.id))
        )


@lru_cache(maxsize=1)
def default_catalog() -> ContentCatalog:
    return ContentCatalog.load()
