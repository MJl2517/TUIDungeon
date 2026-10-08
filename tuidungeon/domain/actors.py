"""Common abstract character and concrete player/monster implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

from .actions import ActionContext, ActionOutcome, ActionRegistry, SpellSource
from .definitions import (
    ActionDefinition,
    BackgroundDefinition,
    ClassDefinition,
    MonsterDefinition,
    RaceDefinition,
    Spell,
)
from .effects import EffectRegistry
from .equipment import Equipment
from .rules import Ability, CharacterClass, Dice, Race
from .stats import Stats
from .collections import TrackedList

if TYPE_CHECKING:
    from ..content.catalog import ContentCatalog


@dataclass(kw_only=True)
class Character(ABC):
    id: str
    name: str
    stats: Stats
    max_hp: int
    hp: int
    base_armor_class: int | None = None
    speed: int = 1
    initiative_bonus: int = 0
    carry_per_strength: float = 5
    inventory: list[Equipment] = field(default_factory=list)
    class_spells: tuple[Spell, ...] = ()
    racial_spell: Spell | None = None
    max_spell_slots: dict[int, int] = field(default_factory=dict)
    spell_slots: dict[int, int] = field(default_factory=dict)
    max_racial_uses: int = 0
    racial_uses: int = 0
    gold: int = 0
    experience: int = 0
    innate_tags: frozenset[str] = frozenset()
    conditions: dict[str, int] = field(default_factory=dict)
    sneaking: bool = False
    instance_id: str = field(default_factory=lambda: str(uuid4()), compare=False)

    def __setattr__(self, name, value):
        if name == "inventory" and not isinstance(value, TrackedList):
            value = TrackedList(value)
        super().__setattr__(name, value)

    @property
    def light_items(self):
        key = (id(self.inventory), self.inventory.version)
        if getattr(self, "_lights_key", None) != key:
            self._light_items = tuple(i for i in self.inventory if i.definition.light)
            self._lights_key = key
        return self._light_items

    @property
    @abstractmethod
    def available_actions(self) -> tuple[ActionDefinition, ...]:
        """Actions offered by this character's class or monster template."""

    @property
    def modifiers(self) -> dict[Ability, int]:
        return {ability: self.stats.modifier(ability) for ability in Ability}

    @property
    def armor_class(self) -> int:
        base = (
            self.base_armor_class
            if self.base_armor_class is not None
            else 10 + self.stats.modifier(Ability.DEXTERITY)
        )
        overrides, bonus = [], 0
        for item in self.inventory:
            if item.equipped and item.usable:
                for prop in item.definition.properties:
                    if prop.kind == "armor_class":
                        overrides.append(prop.amount)
                    elif prop.kind == "armor_bonus":
                        bonus += prop.amount
        return max(overrides, default=base) + bonus

    @property
    def initiative(self) -> int:
        return self.stats.modifier(Ability.DEXTERITY) + self.initiative_bonus

    def roll_initiative(self, dice: Dice) -> int:
        return dice.check(
            self.stats.score(Ability.DEXTERITY),
            0,
            bonus=self.initiative_bonus,
            advantage=self.sneaking,
        ).total

    @property
    def max_carry_weight(self) -> float:
        return self.stats.score(Ability.STRENGTH) * self.carry_per_strength

    @property
    def carried_weight(self) -> float:
        return sum(item.weight for item in self.inventory)

    @property
    def overloaded(self) -> bool:
        return self.carried_weight > self.max_carry_weight

    @property
    def tags(self) -> frozenset[str]:
        return self.innate_tags.union(*(item.tags for item in self.inventory))

    @property
    def known_spells(self) -> tuple[Spell, ...]:
        spells = list(self.class_spells)
        if self.racial_spell and self.racial_spell not in spells:
            spells.append(self.racial_spell)
        return tuple(spells)

    def consume_class_slot(self, spell_id: str) -> bool:
        spell = next(
            (spell for spell in self.class_spells if spell.id == spell_id), None
        )
        if spell is None:
            return False
        if spell.level == 0:
            return True
        if self.spell_slots.get(spell.level, 0) < 1:
            return False
        self.spell_slots[spell.level] -= 1
        return True

    def consume_racial_spell(self) -> bool:
        if self.racial_spell is None or self.racial_uses < 1:
            return False
        self.racial_uses -= 1
        return True

    def restore_after_rest(self) -> None:
        self.hp = self.max_hp
        self.spell_slots = self.max_spell_slots.copy()
        self.racial_uses = self.max_racial_uses
        self.conditions.clear()
        self.sneaking = False

    def take_damage(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Урон должен быть неотрицательным")
        actual = min(self.hp, amount)
        self.hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Лечение должно быть неотрицательным")
        actual = min(self.max_hp - self.hp, amount)
        self.hp += actual
        return actual

    def end_turn(self) -> None:
        self.conditions = {
            name: turns - 1 for name, turns in self.conditions.items() if turns > 1
        }

    @property
    def hands_used(self) -> int:
        return sum(item.hands for item in self.inventory if item.equipped)

    def can_equip(self, item: Equipment) -> bool:
        if (
            not any(owned is item for owned in self.inventory)
            or not item.usable
            or item.definition.slot is None
        ):
            return False
        occupied = sum(
            owned.hands
            for owned in self.inventory
            if owned.equipped
            and owned is not item
            and not (
                item.definition.slot != "hand"
                and owned.definition.slot == item.definition.slot
            )
        )
        return occupied + item.hands <= 2

    def equip(self, item: Equipment) -> bool:
        if not self.can_equip(item):
            return False
        for owned in self.inventory:
            if (
                item.definition.slot != "hand"
                and owned.definition.slot == item.definition.slot
            ):
                owned.equipped = False
                owned.lit = False
        item.equipped = True
        return True

    def unequip(self, item: Equipment) -> bool:
        if not any(owned is item for owned in self.inventory):
            return False
        item.equipped = False
        item.lit = False
        return True

    def use_item(
        self,
        item: Equipment,
        dice: Dice,
        target: "Character | None" = None,
        effects: EffectRegistry | None = None,
    ) -> ActionOutcome:
        if self.hp <= 0:
            return ActionOutcome(False, False, "Персонаж без сознания.")
        if not any(owned is item for owned in self.inventory) or not item.usable:
            return ActionOutcome(False, False, "Предмет недоступен.")
        active = tuple(
            prop
            for prop in item.definition.properties
            if prop.kind not in {"armor_class", "armor_bonus"}
        )
        if not active:
            return ActionOutcome(False, False, "У предмета нет применяемого свойства.")
        result = (effects or EffectRegistry.default()).apply_all(
            active, target or self, dice
        )
        if item.charges is not None:
            item.charges -= 1
        return ActionOutcome(True, True, f"Использовано: {item.name}.", effects=result)

    def perform(
        self,
        action_id: str,
        context: ActionContext,
        registry: ActionRegistry | None = None,
    ) -> ActionOutcome:
        definition = next(
            (entry for entry in self.available_actions if entry.id == action_id), None
        )
        if definition is None:
            return ActionOutcome(False, False, "Это действие недоступно персонажу.")
        return (registry or ActionRegistry.default()).execute(definition, self, context)

    def attack(
        self, target: "Character", dice: Dice, *, action_id="attack", weapon_id=None
    ) -> ActionOutcome:
        return self.perform(action_id, ActionContext(dice, target, weapon_id=weapon_id))

    def dodge(self, dice: Dice) -> ActionOutcome:
        return self.perform("dodge", ActionContext(dice))

    def stealth(self, dice: Dice, difficulty: int) -> ActionOutcome:
        return self.perform("stealth", ActionContext(dice, difficulty=difficulty))

    def cast(
        self,
        spell_id: str,
        dice: Dice,
        target: "Character | None" = None,
        *,
        source: SpellSource = SpellSource.CLASS,
    ) -> ActionOutcome:
        return self.perform(
            "magic", ActionContext(dice, target, spell_id=spell_id, spell_source=source)
        )

    def influence(
        self, dice: Dice, difficulty: int, target: "Character | None" = None
    ) -> ActionOutcome:
        return self.perform(
            "influence", ActionContext(dice, target, difficulty=difficulty)
        )


@dataclass(kw_only=True)
class Hero(Character):
    race: RaceDefinition
    character_class: ClassDefinition
    catalog: "ContentCatalog" = field(repr=False, compare=False)
    level: int = 1
    background: BackgroundDefinition | None = None

    @classmethod
    def create(
        cls,
        race: Race | RaceDefinition | str,
        character_class: CharacterClass | ClassDefinition | str,
        base_stats: Stats,
        *,
        catalog: "ContentCatalog | None" = None,
        background: BackgroundDefinition | str | None = None,
    ) -> "Hero":
        from ..content.catalog import default_catalog

        catalog = catalog or default_catalog()
        if isinstance(race, Race):
            race = catalog.races[race.name.lower()]
        elif isinstance(race, str):
            race = catalog.races[race]
        if isinstance(character_class, CharacterClass):
            character_class = catalog.classes[character_class.name.lower()]
        elif isinstance(character_class, str):
            character_class = catalog.classes[character_class]
        if isinstance(background, str):
            background = catalog.backgrounds[background]
        if (
            background
            and background.classes
            and character_class.id not in background.classes
        ):
            raise ValueError("Предыстория недоступна выбранному классу")
        stats = base_stats.with_bonuses(race.ability_bonuses)
        if background:
            stats = stats.with_bonuses(background.ability_bonuses)
        max_hp = max(
            1,
            character_class.hit_points
            + stats.modifier(Ability.CONSTITUTION)
            + race.hp_per_level,
        )
        racial_spell = catalog.spells[race.racial_spell] if race.racial_spell else None
        slots = dict(character_class.spell_slots)
        item_ids = character_class.starting_items + (
            background.starting_items if background else ()
        )
        hero = cls(
            id="hero",
            name=character_class.name,
            race=race,
            character_class=character_class,
            stats=stats,
            max_hp=max_hp,
            hp=max_hp,
            catalog=catalog,
            background=background,
            speed=race.speed,
            carry_per_strength=character_class.carry_per_strength,
            inventory=[
                Equipment.create(catalog.equipment[item_id]) for item_id in item_ids
            ],
            class_spells=tuple(
                catalog.spells[spell_id] for spell_id in character_class.spells
            ),
            racial_spell=racial_spell,
            max_spell_slots=slots.copy(),
            spell_slots=slots.copy(),
            max_racial_uses=race.racial_uses,
            racial_uses=race.racial_uses,
            innate_tags=background.tags if background else frozenset(),
        )
        for item in hero.inventory:
            if item.definition.slot and not item.definition.light:
                hero.equip(item)
        return hero

    @property
    def available_actions(self) -> tuple[ActionDefinition, ...]:
        return tuple(
            self.catalog.actions[action_id]
            for action_id in self.character_class.actions
        )


@dataclass(kw_only=True)
class Monster(Character):
    definition_ref: str | None = None
    definition: MonsterDefinition
    catalog: "ContentCatalog" = field(repr=False, compare=False)

    @classmethod
    def create(
        cls, monster_id: str, *, catalog: "ContentCatalog | None" = None
    ) -> "Monster":
        from ..content.catalog import default_catalog

        catalog = catalog or default_catalog()
        definition = catalog.monsters[monster_id]
        slots = dict(definition.spell_slots)
        monster = cls(
            id=definition.id,
            name=definition.name,
            definition=definition,
            catalog=catalog,
            definition_ref=definition.id
            if ":" in definition.id
            else f"base:{definition.id}",
            stats=definition.stats,
            max_hp=definition.hit_points,
            hp=definition.hit_points,
            base_armor_class=definition.armor_class,
            speed=definition.speed,
            initiative_bonus=definition.initiative_bonus,
            innate_tags=definition.tags,
            inventory=[
                Equipment.create(catalog.equipment[item_id])
                for item_id in definition.inventory
            ],
            class_spells=tuple(
                catalog.spells[spell_id] for spell_id in definition.spells
            ),
            max_spell_slots=slots.copy(),
            spell_slots=slots.copy(),
        )
        for item in monster.inventory:
            if item.definition.slot and not item.definition.light:
                monster.equip(item)
        return monster

    @property
    def available_actions(self) -> tuple[ActionDefinition, ...]:
        return (
            tuple(
                self.catalog.actions[action_id] for action_id in self.definition.actions
            )
            + self.definition.special_actions
        )

    @property
    def special_actions(self) -> tuple[ActionDefinition, ...]:
        return self.definition.special_actions
