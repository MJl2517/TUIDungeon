"""Common abstract character and concrete player/monster implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING
from uuid import uuid4
from math import fsum

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
from .damage import DamageProfile

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
    experience: int = 0
    innate_tags: frozenset[str] = frozenset()
    skill_proficiencies: set[str] = field(default_factory=set)
    expertise: set[str] = field(default_factory=set)
    conditions: dict[str, int] = field(default_factory=dict)
    sneaking: bool = False
    innate_damage_profile: DamageProfile = DamageProfile()
    spellcasting_ability: Ability = Ability.INTELLIGENCE
    cantrip_uses: int = 0
    concentration_id: str | None = None
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
    def gold(self) -> int:
        return sum(i.id in {"gold", "base:gold"} for i in self.inventory)

    @gold.setter
    def gold(self, amount: int):
        if type(amount) is not int or amount < 0:
            raise ValueError(
                "Количество золота должно быть целым неотрицательным числом"
            )
        difference = amount - self.gold
        if difference > 0:
            # ponytail: reuse item instances; counted stacks only if huge treasuries become a bottleneck.
            self.inventory.extend(
                Equipment.create(self.catalog.equipment["gold"])
                for _ in range(difference)
            )
        elif difference < 0:
            coins = [i for i in self.inventory if i.id in {"gold", "base:gold"}]
            removed = {i.instance_id for i in coins[:-difference]}
            self.inventory[:] = [
                i for i in self.inventory if i.instance_id not in removed
            ]

    @property
    def gold_weight(self) -> float:
        return self.gold / 100

    @property
    def carried_weight(self) -> float:
        return fsum(item.weight for item in self.inventory)

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
            return self.consume_cantrip()
        if self.spell_slots.get(spell.level, 0) < 1:
            return False
        self.spell_slots[spell.level] -= 1
        return True

    def consume_racial_spell(self) -> bool:
        if self.racial_spell and self.racial_spell.level == 0:
            return self.consume_cantrip()
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
        self.cantrip_uses = self.max_cantrip_uses
        self.concentration_id = None

    @property
    def max_cantrip_uses(self):
        return (
            self.stats.score(self.spellcasting_ability)
            if any(s.level == 0 for s in self.known_spells)
            else 0
        )

    @property
    def proficiency_bonus(self):
        return 2 + (max(1, getattr(self, "level", 1)) - 1) // 4

    def skill_bonus(self, skill, ability=None):
        from .skills import SKILLS, skill_id

        skill = skill_id(skill)
        multiplier = (
            2
            if skill in self.expertise
            else 1
            if skill in self.skill_proficiencies
            else 0
        )
        return (
            self.stats.modifier(ability or SKILLS[skill].ability)
            + multiplier * self.proficiency_bonus
        )

    def ability_check(
        self,
        dice,
        ability,
        difficulty,
        *,
        skill=None,
        tool=None,
        bonus=0,
        advantage=False,
        disadvantage=False,
    ):
        from .skills import skill_id

        skill = skill_id(skill) if skill is not None else None
        trained = skill in self.skill_proficiencies
        tool_trained = tool is not None and tool in getattr(
            self, "tool_proficiencies", ()
        )
        multiplier = (
            (2 if tool in getattr(self, "tool_expertise", ()) else int(tool_trained))
            if tool is not None
            else 2
            if skill in self.expertise
            else int(trained)
        )
        return dice.check(
            self.stats.score(ability),
            difficulty,
            bonus=bonus + multiplier * self.proficiency_bonus,
            advantage=advantage,
            disadvantage=disadvantage,
        )

    def passive_skill(self, skill, *, advantage=False, disadvantage=False):
        return (
            10
            + self.skill_bonus(skill)
            + (
                5
                if advantage and not disadvantage
                else -5
                if disadvantage and not advantage
                else 0
            )
        )

    @property
    def spell_attack_bonus(self):
        return (
            self.stats.modifier(self.spellcasting_ability)
            + self.proficiency_bonus
            + max(
                (
                    i.definition.spell_bonus
                    for i in self.inventory
                    if i.equipped and i.usable
                ),
                default=0,
            )
        )

    @property
    def spell_save_dc(self):
        return 8 + self.spell_attack_bonus

    def consume_cantrip(self):
        if self.cantrip_uses < 1:
            return False
        self.cantrip_uses -= 1
        return True

    def restore_cantrips_short(self):
        before = self.cantrip_uses
        self.cantrip_uses = min(
            self.max_cantrip_uses,
            before + max(0, self.stats.modifier(self.spellcasting_ability)),
        )
        return self.cantrip_uses - before

    @property
    def damage_profile(self) -> DamageProfile:
        return self.innate_damage_profile.merge(
            *(
                item.definition.damage_profile
                for item in self.inventory
                if item.equipped and item.usable
            )
        )

    def receive_damage(self, amount: int, damage_type=None):
        result = self.damage_profile.resolve(amount, damage_type)
        actual = min(self.hp, result.resolved_amount)
        self.hp -= actual
        if self.hp == 0:
            self.concentration_id = None
        return replace(result, applied_amount=actual)

    def check_concentration(self, damage, dice):
        if not self.concentration_id or damage <= 0:
            return None
        check = dice.check(self.stats.score(Ability.CONSTITUTION), max(10, damage // 2))
        if not check.success:
            self.concentration_id = None
        return check

    def take_damage(self, amount: int, damage_type=None) -> int:
        return self.receive_damage(amount, damage_type).applied_amount

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
        if item.definition.vessel:
            from .liquids import drink_liquid

            return drink_liquid(
                item, target or self, dice, effects or EffectRegistry.default()
            )
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
    test_profile: str | None = None
    tool_proficiencies: set[str] = field(default_factory=set)
    tool_expertise: set[str] = field(default_factory=set)
    known_recipes: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        race: Race | RaceDefinition | str,
        character_class: CharacterClass | ClassDefinition | str,
        base_stats: Stats,
        *,
        catalog: "ContentCatalog | None" = None,
        background: BackgroundDefinition | str | None = None,
        cantrips: tuple[str, ...] | None = None,
        skills=None,
        extra_skills=None,
        expertise=None,
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
        selected = (
            tuple(character_class.cantrip_choices[: character_class.cantrips_known])
            if cantrips is None
            else tuple(cantrips)
        )
        if (
            len(selected) != character_class.cantrips_known
            or len(set(selected)) != len(selected)
            or any(s not in character_class.cantrip_choices for s in selected)
        ):
            raise ValueError("Выберите нужное количество различных заговоров класса")
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
                catalog.spells[spell_id]
                for spell_id in dict.fromkeys(character_class.spells + selected)
            ),
            racial_spell=racial_spell,
            max_spell_slots=slots.copy(),
            spell_slots=slots.copy(),
            max_racial_uses=race.racial_uses,
            racial_uses=race.racial_uses,
            innate_tags=background.tags if background else frozenset(),
            innate_damage_profile=race.damage_profile.merge(
                character_class.damage_profile
            ),
            spellcasting_ability=character_class.spellcasting_ability,
        )
        hero.tool_expertise = set(character_class.tool_expertise) | (
            set(background.tool_expertise) if background else set()
        )
        hero.tool_proficiencies = (
            hero.tool_expertise
            | set(character_class.tool_proficiencies)
            | (set(background.tool_proficiencies) if background else set())
        )
        hero.known_recipes = (
            {
                ref
                for ref, r in catalog.recipes.items()
                if r.basic_known
                or set(r.learn_on_proficiency) & hero.tool_proficiencies
            }
            | set(character_class.starting_recipes)
            | (set(background.starting_recipes) if background else set())
        )
        hero.cantrip_uses = hero.max_cantrip_uses
        from .skills import SKILLS, starting_skills, select_skills

        known, choices, replacements = starting_skills(
            race, character_class, background
        )
        known |= select_skills(choices, character_class.skills_known, skills)
        known |= select_skills(
            [s for s in SKILLS if s not in known], replacements, extra_skills
        )
        hero.skill_proficiencies = known
        hero.expertise = select_skills(
            [s for s in SKILLS if s in known],
            character_class.expertise_count,
            expertise,
        )
        for item in hero.inventory:
            if item.definition.slot and not item.definition.light:
                hero.equip(item)
        return hero

    def learn_recipes(self, refs):
        refs = set(refs)
        if not refs <= self.catalog.recipes.keys():
            raise ValueError("Источник содержит неизвестный рецепт")
        learned = sorted(refs - self.known_recipes)
        self.known_recipes.update(refs)
        return learned

    def learn_tool_proficiency(self, tag):
        self.tool_proficiencies.add(tag)
        return self.learn_recipes(
            ref
            for ref, recipe in self.catalog.recipes.items()
            if tag in recipe.learn_on_proficiency
        )

    @property
    def available_actions(self) -> tuple[ActionDefinition, ...]:
        return tuple(
            self.catalog.actions[action_id]
            for action_id in self.character_class.actions
        )


@dataclass(kw_only=True)
class Monster(Character):
    definition_ref: str | None = None
    template: dict | None = field(default=None, repr=False, compare=False)
    definition: MonsterDefinition
    catalog: "ContentCatalog" = field(repr=False, compare=False)

    @classmethod
    def create(
        cls,
        monster_id: str,
        *,
        catalog: "ContentCatalog | None" = None,
        definition: MonsterDefinition | None = None,
    ) -> "Monster":
        from ..content.catalog import default_catalog

        catalog = catalog or default_catalog()
        definition = definition or catalog.monsters[monster_id]
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
            innate_damage_profile=definition.damage_profile,
            spellcasting_ability=definition.spellcasting_ability,
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
        monster.cantrip_uses = monster.max_cantrip_uses
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
