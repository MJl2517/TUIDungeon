"""Immutable content definitions; runtime state is kept in actors and equipment."""

from dataclasses import dataclass, field
import re

from .liquids import VesselDefinition
from .rules import Ability
from .stats import Stats
from .value_types import freeze
from .damage import DamageProfile, DamageType, validate_damage
from .item_sizes import ItemSize, ITEM_SIZES


@dataclass(frozen=True)
class DiceExpression:
    count: int
    sides: int
    bonus: int = 0

    @classmethod
    def parse(cls, text: str) -> "DiceExpression":
        match = re.fullmatch(r"([1-9][0-9]*)d([1-9][0-9]*)([+-][0-9]+)?", text)
        if match is None:
            raise ValueError("Бросок должен иметь вид 1d6 или 2d4+2")
        count, sides, bonus = int(match[1]), int(match[2]), int(match[3] or 0)
        if count > 100 or not 2 <= sides <= 1000:
            raise ValueError("Бросок: до 100 кубиков, от 2 до 1000 граней")
        return cls(count, sides, bonus)

    def roll(self, dice) -> int:
        return max(0, sum(dice.roll(self.count, self.sides)) + self.bonus)


@dataclass(frozen=True)
class EffectSpec:
    kind: str
    amount: int = 0
    dice: DiceExpression | None = None
    condition: str = ""
    duration: int = 1
    params: dict = field(default_factory=dict)
    damage_type: DamageType | None = None

    def __post_init__(self):
        validate_damage(0, self.damage_type)
        if self.kind != "damage" and self.damage_type is not None:
            raise ValueError("damage_type допустимо только для damage")
        object.__setattr__(self, "params", freeze(self.params))


@dataclass(frozen=True)
class ActionDefinition:
    id: str
    name: str
    kind: str
    ability: Ability = Ability.STRENGTH
    bonus: int = 0
    damage: DiceExpression | None = None
    effects: tuple[EffectSpec, ...] = ()
    difficulty: int = 10
    description: str = ""
    damage_type: DamageType = "bludgeoning"
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CheckAid:
    check_tag: str
    mode: str


@dataclass(frozen=True)
class LightDefinition:
    radius: int = 6
    bright_radius: int = 3
    burn_minutes: int = 60
    fuel_tag: str | None = None


@dataclass(frozen=True)
class EquipmentDefinition:
    id: str
    name: str
    weight: float = 0
    tags: frozenset[str] = frozenset()
    durability: int | None = None
    slot: str | None = None
    properties: tuple[EffectSpec, ...] = ()
    check_aids: tuple[CheckAid, ...] = ()
    weapon_damage: DiceExpression | None = None
    weapon_ability: Ability = Ability.STRENGTH
    charges: int | None = None
    description: str = ""
    category: str | None = None
    hands: int = 0
    light: LightDefinition | None = None
    vessel: VesselDefinition | None = None
    damage_type: DamageType = "bludgeoning"
    damage_profile: DamageProfile = DamageProfile()
    value_gold: int | None = None
    cast_spell: str | None = None
    spell_bonus: int = 0
    reading: object | None = None
    size: ItemSize = "medium"

    def __post_init__(self):
        if self.size not in ITEM_SIZES:
            raise ValueError("Размер предмета: small, medium или large")
        if "lockpicks" in self.tags and self.durability is None:
            object.__setattr__(self, "durability", 10)
        elif "tool" in self.tags and "lockpicks" not in self.tags:
            object.__setattr__(self, "durability", None)


@dataclass(frozen=True)
class Spell:
    id: str
    name: str
    level: int
    effects: tuple[EffectSpec, ...] = ()
    target: str = "self"
    description: str = ""
    school: str = "evocation"
    modes: tuple[str, ...] = ("combat", "exploration")
    range: int = 6
    resolution: str = "automatic"
    save_ability: Ability | None = None
    cantrip_scaling: bool = False
    wounded_dice: DiceExpression | None = None
    max_targets: int = 1
    world_effect: str | None = None
    world_parameters: dict = field(default_factory=dict)
    concentration: bool = False
    pending_effects: tuple[str, ...] = ()
    tags: frozenset[str] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "world_parameters", freeze(self.world_parameters))


@dataclass(frozen=True)
class RaceDefinition:
    id: str
    name: str
    ability_bonuses: tuple[int, ...] = (0,) * 6
    hp_per_level: int = 0
    racial_spell: str | None = None
    racial_uses: int = 0
    speed: int = 1
    order: int = 0
    description: str = ""
    damage_profile: DamageProfile = DamageProfile()

    tags: frozenset[str] = frozenset()
    skills: tuple[str, ...] = ()

    @property
    def value(self) -> str:
        return self.name


@dataclass(frozen=True)
class ClassDefinition:
    id: str
    name: str
    hit_points: int
    starting_items: tuple[str, ...] = ()
    spells: tuple[str, ...] = ()
    spell_slots: tuple[tuple[int, int], ...] = ()
    actions: tuple[str, ...] = ()
    carry_per_strength: float = 5
    order: int = 0
    description: str = ""
    damage_profile: DamageProfile = DamageProfile()
    spellcasting_ability: Ability = Ability.INTELLIGENCE
    cantrip_choices: tuple[str, ...] = ()
    cantrips_known: int = 0
    skill_choices: tuple[str, ...] = ()
    skills_known: int = 0
    expertise_count: int = 0

    tool_proficiencies: frozenset[str] = frozenset()
    starting_recipes: tuple[str, ...] = ()
    tool_expertise: frozenset[str] = frozenset()

    @property
    def value(self) -> str:
        return self.name


@dataclass(frozen=True)
class BackgroundDefinition:
    id: str
    name: str
    ability_bonuses: tuple[int, ...] = (0,) * 6
    starting_items: tuple[str, ...] = ()
    tags: frozenset[str] = frozenset()
    description: str = ""
    classes: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()

    tool_proficiencies: frozenset[str] = frozenset()
    starting_recipes: tuple[str, ...] = ()
    tool_expertise: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MonsterDefinition:
    id: str
    name: str
    stats: Stats
    hit_points: int
    armor_class: int
    speed: int
    initiative_bonus: int = 0
    actions: tuple[str, ...] = ()
    special_actions: tuple[ActionDefinition, ...] = ()
    inventory: tuple[str, ...] = ()
    spells: tuple[str, ...] = ()
    spell_slots: tuple[tuple[int, int], ...] = ()
    tags: frozenset[str] = frozenset()
    art: str | None = None
    description: str = ""
    damage_profile: DamageProfile = DamageProfile()
    spellcasting_ability: Ability = Ability.INTELLIGENCE


@dataclass(frozen=True)
class ChallengeChoice:
    id: str
    text: str
    ability: Ability | None = None
    difficulty: int = 10
    check_tag: str = ""
    required_tags: frozenset[str] = frozenset()
    advantage_tags: frozenset[str] = frozenset()
    automatic_tags: frozenset[str] = frozenset()
    success: tuple[EffectSpec, ...] = ()
    failure: tuple[EffectSpec, ...] = ()
    minutes: int = 1
    visible_tags: frozenset[str] = frozenset()
    skill: str | None = None
    tool: str | None = None


@dataclass(frozen=True)
class ChallengeDefinition:
    id: str
    name: str
    text: str
    choices: tuple[ChallengeChoice, ...]
    repeatable: bool = False
