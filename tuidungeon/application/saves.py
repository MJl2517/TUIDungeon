"""Versioned JSON saves, atomic writes and reconstruction from content definitions."""

import json
from pathlib import Path
import random
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from .engine import Engine
from .factories import SessionFactory, prepare_test_wizard
from ..content.catalog import default_catalog
from ..domain.actors import Hero, Monster
from ..domain.challenges import TextChallenge
from ..domain.equipment import Equipment
from ..domain.item_sizes import ItemSize, fits_size
from ..domain.stats import Stats
from ..world.clock import GameClock
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement, ItemPlacement, ReadNote
from ..domain.doors import Door, LockpickAttempt, Material, MATERIALS
from ..content.compiler import compile_definition
from ..content.schemas import (
    MapDocument,
    Placement,
    RecipeDocument,
    Ref,
    LocalId,
    EquipmentDocument,
    MonsterDocument,
    StorageSpec,
    DamageDefenses,
    Effect,
)
from ..world.objects import ObjectState, FurnitureCargo, RegrowingObject
from ..domain.skills import SkillId
from ..content.schemas import MODELS
from ..domain.damage import DamageProfile
from ..content.migrations import migrate_map, equipment_alias, legacy_item_template


DEFAULT_SAVE = Path(__file__).resolve().parents[2] / "saves" / "quicksave.json"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WorkRecord(Record):
    recipe_ref: Ref
    recipe: RecipeDocument
    variant: int = Field(ge=0)
    progress: int = Field(ge=0)
    ingredients: list["ItemRecord"] = Field(max_length=1000)
    target: "ItemRecord | None" = None
    target_id: str | None = None
    target_object: str | None = None
    map_ref: Ref | None = None
    destination: tuple[int, int] | None = None

    @field_validator("destination", mode="before")
    @classmethod
    def json_coordinate(cls, value):
        # Legacy item conversion exposes nested JSON arrays to strict Python validation.
        return tuple(value) if isinstance(value, list) else value


class FurnitureRecord(Record):
    category: Literal["objects", "points_of_interest"]
    placement: Placement
    definition: dict
    state: ObjectState
    items: list["ItemRecord"] = Field(default_factory=list, max_length=10000)
    completed: bool = False
    container_spec: StorageSpec | None = None


class ItemRecord(Record):
    @model_validator(mode="before")
    @classmethod
    def legacy_liquids(cls, value):
        if isinstance(value, dict) and "liquid_ml" in value:
            from ..domain.liquids import legacy_portions, migrate_vessel

            data = dict(value)
            amount = data.pop("liquid_ml")
            if "liquid_portions" in data:
                raise ValueError("Нельзя смешивать старые объёмы и порции")
            template = data.get("template") or {}
            vessel = template.get("vessel") if isinstance(template, dict) else None
            if isinstance(vessel, dict) and "capacity_ml" in vessel:
                data["liquid_portions"] = migrate_vessel(
                    dict(vessel, initial_ml=amount), template.get("id")
                )["initial_portions"]
            else:
                data["liquid_portions"] = legacy_portions(
                    amount, data.get("definition")
                )
            return data
        return value

    poison_damage: int = Field(default=0, ge=0, le=100)
    appraised: bool = False
    liquid_effects: list[Effect] = Field(default_factory=list, max_length=32)
    liquid_kind: str | None = None
    liquid_portions: int = Field(default=0, ge=0, le=100000, strict=True)
    contaminated: bool = False
    furniture: FurnitureRecord | None = None
    work: WorkRecord | None = None
    template: dict | None = None
    definition: str
    instance_id: str
    durability: int | None = Field(default=None, ge=0)
    charges: int | None = Field(default=None, ge=0)
    equipped: bool
    fuel_minutes: int | None = Field(default=None, ge=0)
    lit: bool = False


FurnitureRecord.model_rebuild()
ItemRecord.model_rebuild()
WorkRecord.model_rebuild()


class ActorRecord(Record):
    skill_proficiencies: list[SkillId] | None = None
    expertise: list[SkillId] | None = None
    tool_proficiencies: list[LocalId] | None = None
    tool_expertise: list[LocalId] | None = None
    known_recipes: list[Ref] | None = None
    instance_id: str
    name: str
    stats: tuple[int, int, int, int, int, int]
    hp: int = Field(ge=0)
    max_hp: int = Field(ge=1)
    level: int = Field(default=1, ge=1)
    gold: int = Field(ge=0)
    experience: int = Field(ge=0)
    spell_slots: dict[int, int]
    racial_uses: int = Field(ge=0)
    conditions: dict[str, int]
    sneaking: bool
    inventory: list[ItemRecord]
    damage_profile: DamageDefenses | None = None
    cantrips: list[str] | None = None
    cantrip_uses: int | None = Field(default=None, ge=0)
    concentration_id: str | None = None


class MonsterRecord(Record):
    corpse_created: bool = False
    template: dict | None = None
    definition: str
    position: tuple[int, int]
    actor: ActorRecord


class GroundItemRecord(Record):
    id: str
    ref: str
    position: tuple[int, int]
    item: ItemRecord


class DoorRecord(Record):
    instance_id: str
    material: Material
    opened: bool
    locked: bool
    max_hp: int = Field(ge=1)
    hp: int = Field(ge=0)
    bent: bool = False
    burning: bool = False
    corroding: bool = False
    burn_turns: int = Field(default=0, ge=0)


class LockpickRecord(Record):
    target_kind: Literal["door", "container"] = "door"
    door_id: str
    progress: int = Field(ge=0, le=9)
    total: Literal[10] = 10


class OilRecord(Record):
    position: tuple[int, int]
    turns: int = Field(ge=1, le=5)


class ContainerRecord(Record):
    opened: bool | None = None
    locked: bool | None = None
    max_item_size: ItemSize = "large"
    open_tool: LocalId | None = None
    instance_id: str
    items: list[ItemRecord]
    personal: bool
    capacity: float = Field(gt=0, le=1000000, allow_inf_nan=False)


class LevelRecord(Record):
    regrowing_objects: list[RegrowingObject] = Field(default_factory=list)
    world: MapDocument | None = None
    object_states: dict[str, ObjectState] = Field(default_factory=dict)
    door_braces: dict[str, ItemRecord] = Field(default_factory=dict)
    disabled_traps: list[str] = Field(default_factory=list)
    discovered_traps: list[str] = Field(default_factory=list)
    door_loot: list[str] | None = None
    containers: dict[str, ContainerRecord] | None = None
    oil: list[OilRecord] = Field(default_factory=list)
    doors: dict[str, DoorRecord] | None = None
    ref: str | None
    # Full authored definition detects maps edited since the save.
    definition: dict | None
    rows: tuple[str, ...]
    position: tuple[int, int]
    monsters: list[MonsterRecord]
    traps: dict[str, bool]
    points: dict[str, bool]
    items: dict[str, ItemRecord]
    # None identifies saves made before runtime ground placements were supported.
    ground_items: list[GroundItemRecord] | None = None


class MagicRecord(Record):
    scroll_definition: str | None = None
    spell_id: str
    instance_id: str
    kind: str
    turns: int = Field(ge=1, le=1001)
    map_ref: str | None = None
    position: tuple[int, int] | None = None
    item_id: str | None = None
    concentration: bool = False
    params: dict = Field(default_factory=dict)


class SaveRecord(Record):
    active_craft: str | None = None
    read_notes: list[ReadNote] = Field(default_factory=list)
    test_profile: Literal["wizard"] | None = None
    magic_effects: list[MagicRecord] = Field(default_factory=list)
    lockpick: LockpickRecord | None = None
    version: Literal[1] = 1
    race: str
    character_class: str
    background: str | None
    hero: ActorRecord
    elapsed_minutes: int = Field(ge=0)
    turns: int = Field(ge=0)
    current: int = Field(ge=0)
    levels: list[LevelRecord] = Field(min_length=1)
    challenges: dict[str, bool]
    rng: list


def item_record(item):
    from ..domain.liquids import liquid_effect_records

    return ItemRecord(
        furniture=FurnitureRecord(
            category=item.furniture.category,
            placement=item.furniture.placement,
            definition=item.furniture.definition.model_dump(mode="json"),
            state=item.furniture.state,
            items=[item_record(i) for i in item.furniture.items],
            completed=item.furniture.completed,
            container_spec=item.furniture.container_spec,
        )
        if item.furniture
        else None,
        work=WorkRecord(
            recipe_ref=item.work.recipe_ref,
            recipe=item.work.recipe,
            variant=item.work.variant,
            progress=item.work.progress,
            ingredients=[item_record(i) for i in item.work.ingredients],
            target=item_record(item.work.target) if item.work.target else None,
            target_id=item.work.target_id,
            target_object=item.work.target_object,
            map_ref=item.work.map_ref,
            destination=item.work.destination,
        )
        if item.work
        else None,
        poison_damage=item.poison_damage,
        appraised=item.appraised,
        liquid_kind=item.liquid_kind,
        liquid_portions=item.liquid_portions,
        contaminated=item.contaminated,
        liquid_effects=liquid_effect_records(item),
        template=item.template,
        definition=item.id,
        instance_id=item.instance_id,
        durability=item.durability,
        charges=item.charges,
        equipped=item.equipped,
        fuel_minutes=item.fuel_minutes,
        lit=item.lit,
    )


def actor_record(actor):
    return ActorRecord(
        skill_proficiencies=sorted(actor.skill_proficiencies),
        expertise=sorted(actor.expertise),
        tool_expertise=sorted(actor.tool_expertise)
        if isinstance(actor, Hero)
        else None,
        tool_proficiencies=sorted(actor.tool_proficiencies)
        if isinstance(actor, Hero)
        else None,
        known_recipes=sorted(actor.known_recipes) if isinstance(actor, Hero) else None,
        instance_id=actor.instance_id,
        name=actor.name,
        stats=actor.stats.values,
        hp=actor.hp,
        max_hp=actor.max_hp,
        level=getattr(actor, "level", 1),
        gold=0,  # Currency lives in inventory; this field reads older saves only.
        experience=actor.experience,
        spell_slots=actor.spell_slots,
        racial_uses=actor.racial_uses,
        conditions=actor.conditions,
        sneaking=actor.sneaking,
        inventory=[item_record(i) for i in actor.inventory],
        cantrips=[s.id for s in actor.class_spells if s.level == 0],
        cantrip_uses=actor.cantrip_uses,
        concentration_id=actor.concentration_id,
        damage_profile=DamageDefenses(
            **{
                name: sorted(getattr(actor.innate_damage_profile, name))
                for name in ("resistances", "vulnerabilities", "immunities")
            }
        ),
    )


def restore_item(record, catalog):
    record = record.model_copy(deep=True)
    record.template = legacy_item_template(record.definition, record.template)
    record.definition = equipment_alias(record.definition)
    definition = catalog.equipment[record.definition]
    if record.template is not None:
        doc = EquipmentDocument.model_validate(record.template)
        if doc.id != record.definition.split(":")[-1]:
            raise ValueError("Шаблон предмета не соответствует ссылке")
        definition = compile_definition("equipment", record.definition, doc)
    if definition.cast_spell:
        spell = catalog.spells.get(definition.cast_spell)
        if not spell or not spell.world_effect or "exploration" not in spell.modes:
            raise ValueError("Неизвестное или неподдерживаемое заклинание свитка")
    if definition.reading and any(
        r not in catalog.recipes for r in definition.reading.learn_recipes
    ):
        raise ValueError("Неизвестный рецепт в тексте предмета")
    item = Equipment.create(definition)
    item.template = record.template
    for name in ("durability", "charges"):
        value, maximum = getattr(record, name), getattr(item.definition, name)
        if name == "durability" and "tool" in definition.tags and maximum is None:
            value = None  # Old damaged/broken tools become unbreakable.
        if (
            name == "durability"
            and value is None
            and maximum is not None
            and (item.definition.weapon_damage or "lockpicks" in definition.tags)
        ):
            value = maximum  # Earlier scenery weapons and lockpicks had no durability.
        if (value is None) != (maximum is None) or (
            value is not None and value > maximum
        ):
            raise ValueError("Ресурс предмета не соответствует шаблону")
        setattr(item, name, value)
    item.equipped, item.instance_id = record.equipped, record.instance_id
    if record.fuel_minutes is not None:
        maximum = item.definition.light.burn_minutes if item.definition.light else 0
        if record.fuel_minutes > maximum or (
            record.lit and (not record.fuel_minutes or item.broken)
        ):
            raise ValueError("Недопустимый запас топлива или состояние света")
        item.fuel_minutes = record.fuel_minutes
    if record.lit and not item.definition.light:
        raise ValueError("Предмет не является источником света")
    item.lit = record.lit
    from ..domain.liquids import LIQUID_NAMES

    if {"liquid_portions", "liquid_kind"}.intersection(record.model_fields_set):
        item.liquid_kind, item.liquid_portions = (
            record.liquid_kind,
            record.liquid_portions,
        )
    elif definition.vessel and record.charges == 0:
        item.liquid_kind, item.liquid_portions = None, 0
    if (
        bool(item.liquid_portions) != bool(item.liquid_kind)
        or (item.liquid_kind and item.liquid_kind not in LIQUID_NAMES)
        or (
            item.liquid_portions
            and (
                not definition.vessel
                or item.liquid_portions > definition.vessel.capacity_portions
            )
        )
    ):
        raise ValueError("Недопустимое содержимое сосуда")
    if "liquid_effects" in record.model_fields_set:
        from ..content.catalog import effect
        from ..domain.mechanics import mechanics

        item.liquid_effects = tuple(
            effect(e.model_dump(mode="json"), set(mechanics.entries))
            for e in record.liquid_effects
        )
    if not item.liquid_portions:
        if record.liquid_effects:
            raise ValueError("Пустая тара не содержит эффектов жидкости")
        item.liquid_effects = ()
    if record.poison_damage and (
        not definition.weapon_damage
        or definition.damage_type not in ("piercing", "slashing")
        or record.work
        or record.furniture
    ):
        raise ValueError("Яд допустим только на подходящем оружии")
    if record.appraised and definition.value_gold is None:
        raise ValueError("Предмет не подлежит оценке")
    item.appraised = record.appraised
    item.poison_damage = record.poison_damage
    item.contaminated = record.contaminated
    if record.furniture:
        cargo = record.furniture
        doc = MODELS[cargo.category].model_validate(cargo.definition)
        if (
            item.id != "packed_furniture"
            or record.work
            or item.equipped
            or item.lit
            or not doc.movable
            or doc.id != cargo.placement.ref.split(":", 1)[1]
        ):
            raise ValueError("Недопустимая переносимая мебель")
        from ..world.objects import validate_object_state

        validate_object_state(cargo.state, doc, cargo.category)
        items = [restore_item(i, catalog) for i in cargo.items]
        spec = cargo.container_spec or doc.storage
        if (
            any(i.equipped or i.lit for i in items)
            or (items and spec is None)
            or (spec and sum(i.weight for i in items) > spec.capacity + 1e-9)
            or (spec and any(not fits_size(i.size, spec.max_item_size) for i in items))
        ):
            raise ValueError("Недопустимое содержимое переносимой мебели")
        item.furniture = FurnitureCargo(
            cargo.category,
            cargo.placement,
            doc,
            cargo.state,
            items,
            cargo.completed,
            spec,
        )
    if record.work:
        from collections import Counter
        from ..domain.crafting import CraftWork, ingredient_choices

        saved = record.work
        if (
            item.id != "craft_workpiece"
            or item.equipped
            or item.lit
            or saved.recipe.id != saved.recipe_ref.split(":")[-1]
            or saved.variant >= len(saved.recipe.variants)
        ):
            raise ValueError("Недопустимая заготовка")
        variant = saved.recipe.variants[saved.variant]
        if saved.progress >= variant.turns or any(
            i.work or i.equipped or i.lit for i in saved.ingredients
        ):
            raise ValueError("Недопустимый прогресс или вложения заготовки")
        inputs = [restore_item(i, catalog) for i in saved.ingredients]
        counts = Counter(i.id if ":" in i.id else "base:" + i.id for i in inputs)
        if (
            sum(r.quantity for r in variant.ingredients) != len(inputs)
            or ingredient_choices(variant.ingredients, counts) is None
            or any(
                r.item.removeprefix("base:") not in catalog.equipment
                for r in (
                    variant.result
                    if variant.result is not None
                    else saved.recipe.result
                )
            )
        ):
            raise ValueError("Вложения или результат не соответствуют рецепту")
        if any(r not in catalog.recipes for r in saved.recipe.learn_recipes) or any(
            s.removeprefix("base:") not in catalog.spells for s in variant.spells
        ):
            raise ValueError("Неизвестные знания в заготовке")
        target = restore_item(saved.target, catalog) if saved.target else None
        op = saved.recipe.operation
        from ..domain.crafting import operation_target_matches

        if target and (
            not op
            or not operation_target_matches(op, target)
            or saved.target_id != target.instance_id
        ):
            raise ValueError("Недопустимый предмет на обработке")
        if op:
            if op.kind in ("liquid", "repair_item", "coat_weapon", "appraise_item"):
                if (
                    not saved.target_id
                    or saved.target_object
                    or saved.destination
                    or (op.kind == "liquid" and not target)
                ):
                    raise ValueError("Отсутствует предмет на обработке")
            elif op.kind == "repair_object":
                if (
                    not saved.target_object
                    or not saved.map_ref
                    or target
                    or saved.target_id
                    or saved.destination
                ):
                    raise ValueError("Недопустимый объект ремонта")
            elif (
                not saved.destination
                or not saved.map_ref
                or min(saved.destination) < 0
                or target
                or saved.target_id
                or saved.target_object
            ):
                raise ValueError("Недопустимое место строительства")
        elif target or saved.target_id or saved.target_object or saved.destination:
            raise ValueError("Обычная заготовка не может содержать целевую операцию")
        item.work = CraftWork(
            saved.recipe_ref,
            saved.recipe,
            saved.variant,
            inputs,
            saved.progress,
            target=target,
            target_id=saved.target_id,
            target_object=saved.target_object,
            map_ref=saved.map_ref,
            destination=saved.destination,
        )
    return item


def restore_monster(record, catalog):
    definition = catalog.monsters[record.definition]
    if record.template is not None:
        doc = MonsterDocument.model_validate(record.template)
        if doc.id != record.definition.split(":")[-1]:
            raise ValueError("Шаблон существа не соответствует ссылке")
        definition = compile_definition("monsters", record.definition, doc)
    monster = Monster.create(record.definition, catalog=catalog, definition=definition)
    monster.template = record.template
    return monster


def restore_actor(actor, record, catalog):
    if record.cantrips is not None:
        if len(record.cantrips) != len(set(record.cantrips)) or any(
            s not in catalog.spells or catalog.spells[s].level != 0
            for s in record.cantrips
        ):
            raise ValueError("Недопустимые сохранённые заговоры")
        if isinstance(actor, Hero) and actor.test_profile == "wizard":
            expected = {s.id for s in catalog.spells.values() if s.level == 0}
            if set(record.cantrips) != expected:
                raise ValueError("Неполный набор заговоров тестового волшебника")
        elif isinstance(actor, Hero):
            fixed = {
                s for s in actor.character_class.spells if catalog.spells[s].level == 0
            }
            chosen = set(record.cantrips) - fixed
            if (
                not fixed.issubset(record.cantrips)
                or len(chosen) != actor.character_class.cantrips_known
                or any(s not in actor.character_class.cantrip_choices for s in chosen)
            ):
                raise ValueError("Выбор заговоров не соответствует классу")
        actor.class_spells = tuple(
            s for s in actor.class_spells if s.level != 0
        ) + tuple(catalog.spells[s] for s in record.cantrips)
    if record.damage_profile is not None:
        actor.innate_damage_profile = DamageProfile(
            **record.damage_profile.model_dump()
        )
    if record.hp > record.max_hp or record.racial_uses > actor.max_racial_uses:
        raise ValueError("Недопустимое здоровье или расовый ресурс")
    if set(record.spell_slots) != set(actor.max_spell_slots) or any(
        not 0 <= count <= actor.max_spell_slots[level]
        for level, count in record.spell_slots.items()
    ):
        raise ValueError("Недопустимые ячейки заклинаний")
    if any(value <= 0 for value in record.conditions.values()):
        raise ValueError("Недопустимая длительность состояния")
    actor.stats = Stats(record.stats)
    actor.cantrip_uses = (
        actor.max_cantrip_uses if record.cantrip_uses is None else record.cantrip_uses
    )
    if actor.cantrip_uses > actor.max_cantrip_uses:
        raise ValueError("Недопустимый запас заговоров")
    actor.concentration_id = record.concentration_id
    for name in (
        "instance_id",
        "name",
        "hp",
        "max_hp",
        "experience",
        "spell_slots",
        "racial_uses",
        "conditions",
        "sneaking",
    ):
        setattr(actor, name, getattr(record, name))
    if isinstance(actor, Hero):
        if record.level > 20:
            raise ValueError("Уровень героя должен быть от 1 до 20")
        actor.level = record.level
        if record.skill_proficiencies is not None:
            actor.skill_proficiencies = set(record.skill_proficiencies)
        if record.expertise is not None:
            actor.expertise = set(record.expertise)
        if not actor.expertise.issubset(actor.skill_proficiencies):
            raise ValueError("Экспертиза требует владения навыком")
        if record.tool_proficiencies is not None:
            actor.tool_proficiencies = set(record.tool_proficiencies)
        if record.tool_expertise is not None:
            actor.tool_expertise = set(record.tool_expertise)
        if not actor.tool_expertise.issubset(actor.tool_proficiencies):
            raise ValueError("Экспертиза инструмента требует отдельного владения им")
        if record.known_recipes is not None:
            if not set(record.known_recipes).issubset(catalog.recipes):
                raise ValueError("Недопустимые сохранённые рецепты")
            actor.known_recipes = set(record.known_recipes)
    actor.inventory = [restore_item(i, catalog) for i in record.inventory]
    if record.gold:
        actor.gold += record.gold
    slots = [
        i.definition.slot
        for i in actor.inventory
        if i.equipped and i.definition.slot != "hand"
    ]
    if (
        actor.hands_used > 2
        or len(slots) != len(set(slots))
        or any(i.lit and not i.equipped for i in actor.inventory)
    ):
        raise ValueError("Недопустимое снаряжение в руках")
    return actor


class SaveRepository:
    def __init__(self, path=DEFAULT_SAVE):
        self.path = Path(path)

    def save(self, engine):
        engine.sync_magic()
        engine.prune_magic_items()
        state, hero = engine.state, engine.state.hero
        states = list(engine.levels.values()) if engine.levels else [state]
        engine.collect_corpses(states)
        levels = []
        for entry in states:
            level = entry.level
            levels.append(
                LevelRecord(
                    world=level.definition
                    if level and level.definition is not level.authored_definition
                    else None,
                    object_states=level.object_states if level else {},
                    regrowing_objects=level.regrowing_objects if level else [],
                    door_braces={
                        d.placement.id: item_record(d.brace)
                        for d in level.doors
                        if d.brace
                    }
                    if level
                    else {},
                    disabled_traps=[p.placement.id for p in level.traps if p.disabled]
                    if level
                    else [],
                    discovered_traps=[
                        p.placement.id for p in level.traps if p.discovered
                    ]
                    if level
                    else [],
                    door_loot=sorted(level.door_loot) if level else [],
                    containers={
                        c.placement.id: ContainerRecord(
                            open_tool=c.spec.open_tool,
                            instance_id=c.instance_id,
                            items=[item_record(i) for i in c.items],
                            personal=c.spec.personal,
                            capacity=c.spec.capacity,
                            max_item_size=c.spec.max_item_size,
                            locked=c.lock.locked if c.lock else None,
                            opened=c.opened,
                        )
                        for c in level.containers
                    }
                    if level
                    else {},
                    oil=[
                        OilRecord(position=(p.x, p.y), turns=t)
                        for p, t in entry.oil.items()
                    ],
                    ref=level.ref if level else None,
                    definition=level.authored_definition.model_dump(mode="json")
                    if level
                    else None,
                    rows=entry.dungeon.rows,
                    position=(entry.position.x, entry.position.y),
                    monsters=[
                        MonsterRecord(
                            corpse_created=p.corpse_created,
                            template=p.monster.template,
                            definition=p.monster.id,
                            position=(p.position.x, p.position.y),
                            actor=actor_record(p.monster),
                        )
                        for p in entry.monsters
                    ],
                    traps={p.placement.id: p.triggered for p in level.traps}
                    if level
                    else {},
                    points={p.placement.id: p.completed for p in level.points}
                    if level
                    else {},
                    doors={
                        p.placement.id: DoorRecord(
                            instance_id=p.instance_id,
                            **{
                                name: getattr(p.door, name)
                                for name in DoorRecord.model_fields
                                if name != "instance_id"
                            },
                        )
                        for p in level.doors
                    }
                    if level
                    else {},
                    items={},
                    ground_items=[
                        GroundItemRecord(
                            id=p.id,
                            ref=p.ref,
                            position=(p.x, p.y),
                            item=item_record(item),
                        )
                        for p, item in entry.items
                    ],
                )
            )
        record = SaveRecord(
            active_craft=engine.active_craft,
            read_notes=list(engine.read_notes.values()),
            test_profile=hero.test_profile,
            magic_effects=[
                MagicRecord(
                    **{
                        **vars(m),
                        "position": (m.position.x, m.position.y)
                        if m.position
                        else None,
                    }
                )
                for m in engine.magic_effects
            ],
            lockpick=LockpickRecord(**vars(engine.lockpick_attempt))
            if engine.lockpick_attempt
            else None,
            race=hero.race.id,
            character_class=hero.character_class.id,
            background=hero.background.id if hero.background else None,
            hero=actor_record(hero),
            elapsed_minutes=state.clock.elapsed_minutes,
            turns=state.turns,
            current=next(i for i, s in enumerate(states) if s is state),
            levels=levels,
            challenges={key: c.completed for key, c in engine.challenges.items()},
            rng=json.loads(json.dumps(engine.dice.rng.getstate())),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".save-",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(record.model_dump_json(indent=2))
            temporary.replace(self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def load(self, catalog=None, store=None):
        # No pickle or executable data. Build a separate session before replacing UI state.
        record = SaveRecord.model_validate_json(self.path.read_text(encoding="utf-8"))
        catalog = catalog or (store.runtime_catalog() if store else default_catalog())
        hero = Hero.create(
            record.race,
            record.character_class,
            Stats((10,) * 6),
            catalog=catalog,
            background=record.background,
        )
        if record.test_profile == "wizard":
            prepare_test_wizard(hero)
        restore_actor(hero, record.hero, catalog)
        clock = GameClock(record.elapsed_minutes)
        states = []
        for saved in record.levels:
            if saved.ref:
                if store is None:
                    from ..content.packs import PackStore

                    store = PackStore()
                state = SessionFactory(store).state(saved.ref, hero)
                from ..content.schemas import MapDocument

                from ..content.placements import normalized_map

                if normalized_map(
                    state.level.definition, store.documents
                ) != normalized_map(
                    MapDocument.model_validate(migrate_map(saved.definition)),
                    store.documents,
                ):
                    raise ValueError("Карта изменена после сохранения")
                if saved.world:
                    saved.world = MapDocument.model_validate(
                        migrate_map(saved.world.model_dump(mode="json"))
                    )
                    authored = state.level.definition
                    mutable = {
                        "objects",
                        "points_of_interest",
                        "traps",
                        "tiles",
                        "walkability",
                        "blocks_sight",
                        "transitions",
                        "doors",
                    }
                    if saved.world.model_dump(exclude=mutable) != authored.model_dump(
                        exclude=mutable
                    ):
                        raise ValueError("Недопустимые изменения карты в сохранении")
                    state = SessionFactory(store).state(
                        saved.ref, hero, definition=saved.world
                    )
                    state.level.authored_definition = authored
                state.level.object_states = saved.object_states
                state.level.regrowing_objects = saved.regrowing_objects
                used_ids = {
                    p.id
                    for category in (
                        "objects",
                        "points_of_interest",
                        "traps",
                        "doors",
                        "equipment",
                        "monsters",
                        "transitions",
                        "lights",
                        "decorations",
                    )
                    for p in getattr(state.level.definition, category)
                }
                sprout_ids = set()
                for pending in saved.regrowing_objects:
                    p = pending.placement
                    if p.id in used_ids or not (
                        0 <= p.x < state.level.definition.width
                        and 0 <= p.y < state.level.definition.height
                    ):
                        raise ValueError(
                            "Недопустимое размещение восстанавливаемого объекта"
                        )
                    used_ids.add(p.id)
                    definition = state.level.store.resolve(pending.category, p)
                    if (
                        not definition.destruction
                        or not definition.destruction.regrow_minutes
                    ):
                        raise ValueError("Объект не поддерживает восстановление")
                    if pending.sprout_id:
                        sprout = next(
                            (
                                s
                                for s in state.level.definition.objects
                                if s.id == pending.sprout_id
                            ),
                            None,
                        )
                        if (
                            pending.sprout_id in sprout_ids
                            or sprout is None
                            or sprout.ref != definition.destruction.regrow_as
                            or (sprout.x, sprout.y) != (p.x, p.y)
                        ):
                            raise ValueError("Недопустимое молодое растение")
                        sprout_ids.add(pending.sprout_id)
                    for transition in pending.transitions:
                        if (
                            transition.id != p.id + "_transition"
                            or (transition.x, transition.y) != (p.x, p.y)
                            or transition.id in used_ids
                        ):
                            raise ValueError(
                                "Недопустимый переход восстанавливаемого объекта"
                            )
                        state.level.store.get("maps", transition.target)
                        used_ids.add(transition.id)
                state.level.door_loot = set(saved.door_loot or [])
            else:
                state = GameState(
                    hero, DungeonMap(saved.rows), Position(*saved.position)
                )
            state.position = Position(*saved.position)
            if state.level and saved.doors is not None:
                if set(saved.doors) != {d.placement.id for d in state.level.doors}:
                    raise ValueError("Размещения дверей изменились")
                for instance in state.level.doors:
                    data = saved.doors[instance.placement.id]
                    original = instance.door
                    transformed = (
                        original.material == "adamantine" and data.material == "stone"
                    )
                    if (
                        data.material != original.material
                        and not transformed
                        or data.max_hp
                        != (
                            MATERIALS["stone"].hit_points
                            if transformed
                            else original.max_hp
                        )
                        or data.hp > data.max_hp
                        or data.bent
                        and data.material != "bars"
                        or data.burning
                        and (data.material != "wood" or data.hp == 0)
                        or data.corroding
                        and (data.material not in ("steel", "bars") or data.hp == 0)
                    ):
                        raise ValueError("Недопустимое состояние двери")
                    instance.door = Door(
                        **data.model_dump(exclude={"instance_id"}),
                        lock_quality=original.lock_quality,
                        lock_complexity=original.lock_complexity,
                        transmits_light=original.transmits_light,
                        openable=original.openable,
                        force_allowed=original.force_allowed,
                        bend_difficulty=original.bend_difficulty,
                        foreground=original.foreground,
                        key_tag=original.key_tag,
                    )
                    if instance.door.material == "stone":
                        instance.door.opened = instance.door.locked = False
                    instance.instance_id = data.instance_id
            if saved.door_braces:
                if not state.level or not set(saved.door_braces).issubset(
                    d.placement.id for d in state.level.doors
                ):
                    raise ValueError("Неизвестная дверь с подпоркой")
                for instance in state.level.doors:
                    if instance.placement.id in saved.door_braces:
                        item = restore_item(
                            saved.door_braces[instance.placement.id], catalog
                        )
                        if (
                            not item.usable
                            or item.equipped
                            or item.lit
                            or "door_brace" not in item.tags
                            or instance.door.destroyed
                            or instance.door.material == "stone"
                        ):
                            raise ValueError("Недопустимая подпорка")
                        instance.brace = item
            saved_rows = saved.rows
            if state.level and saved.doors is None:
                rows = [list(row) for row in saved_rows]
                for instance in state.level.doors:
                    p = instance.placement
                    rows[p.y][p.x] = "."
                saved_rows = tuple("".join(row) for row in rows)
            if state.dungeon.rows != saved_rows and saved.world is None and state.level:
                from ..world.terrain import Terrain

                legacy = Terrain.compile(
                    state.level.store, state.level.authored_definition
                )
                if saved_rows == tuple(
                    "".join("." if c else "#" for c in row)
                    for row in legacy.walkability
                ):
                    saved_rows = state.dungeon.rows
            if state.dungeon.rows != saved_rows or not state.walkable(state.position):
                raise ValueError("Недопустимая карта или позиция героя")
            state.clock, state.turns = clock, record.turns
            for coating in saved.oil:
                p = Position(*coating.position)
                if (
                    not 0 <= p.x < state.dungeon.width
                    or not 0 <= p.y < state.dungeon.height
                    or p in state.oil
                ):
                    raise ValueError("Недопустимое покрытие маслом")
                state.oil[p] = coating.turns
            state.monsters = [
                MonsterPlacement(
                    restore_actor(restore_monster(p, catalog), p.actor, catalog),
                    Position(*p.position),
                    corpse_created=p.corpse_created,
                )
                for p in saved.monsters
            ]
            level = state.level
            if level:
                if saved.containers is not None:
                    containers = {c.placement.id: c for c in level.containers}
                    new_remains = {
                        identifier
                        for identifier, c in containers.items()
                        if "remains" in c.definition.tags
                        and not c.spec.contents
                        and (
                            c.placement.ref
                            in {
                                "base:wolf_remains",
                                "base:snake_remains",
                                "base:spider_remains",
                            }
                            or saved.definition["tiles"][c.placement.y][c.placement.x]
                            == c.placement.ref
                        )
                    }
                    new_remains.update(
                        identifier
                        for identifier, c in containers.items()
                        if getattr(c.definition, "light_fixture", None)
                        and c.placement.ref
                        in {
                            "base:torch_wall",
                            "base:torch_decor",
                            "base:lantern",
                            "base:candle",
                        }
                    )
                    if set(saved.containers) - containers.keys() or (
                        containers.keys() - saved.containers.keys() - new_remains
                    ):
                        raise ValueError("Размещения контейнеров изменились")
                    for container in level.containers:
                        if container.placement.id not in saved.containers:
                            continue  # Older remains had no container or contents.
                        data = saved.containers[container.placement.id]
                        if data.opened is not None:
                            container.opened = data.opened
                        if data.locked is not None:
                            if container.lock is None:
                                raise ValueError(
                                    "Сохранён замок у контейнера без замка"
                                )
                            container.lock.locked = data.locked
                        elif "locked" not in data.model_fields_set and container.lock:
                            container.lock.locked = (
                                False  # Older saves had freely accessible containers.
                            )
                        container.spec = container.spec.model_copy(
                            update={
                                "personal": data.personal,
                                "capacity": data.capacity,
                                "max_item_size": data.max_item_size
                                if "max_item_size" in data.model_fields_set
                                else container.spec.max_item_size,
                                "open_tool": data.open_tool
                                if "open_tool" in data.model_fields_set
                                else container.spec.open_tool,
                            }
                        )
                        items = [restore_item(i, catalog) for i in data.items]
                        if (
                            any(
                                i.equipped
                                or (
                                    i.lit
                                    and not getattr(
                                        container.definition, "light_fixture", None
                                    )
                                )
                                for i in items
                            )
                            or sum(i.weight for i in items)
                            > container.spec.capacity + 1e-9
                            or any(
                                not fits_size(i.size, container.spec.max_item_size)
                                for i in items
                            )
                        ):
                            raise ValueError("Недопустимое содержимое контейнера")
                        fixture = getattr(container.definition, "light_fixture", None)
                        if fixture and (
                            len(items) > 1
                            or any(
                                (i.id if ":" in i.id else "base:" + i.id)
                                != fixture.item
                                or not i.definition.light
                                for i in items
                            )
                        ):
                            raise ValueError("Недопустимый источник света в подставке")
                        container.items[:] = items
                        container.instance_id = data.instance_id
                for p in state.monsters:
                    p.monster.definition_ref = (
                        p.monster.id if ":" in p.monster.id else "base:" + p.monster.id
                    )
                if set(saved.traps) != {p.placement.id for p in level.traps} or set(
                    saved.points
                ) != {p.placement.id for p in level.points}:
                    raise ValueError("Размещения карты изменились")
                if len(saved.disabled_traps) != len(
                    set(saved.disabled_traps)
                ) or not set(saved.disabled_traps).issubset(saved.traps):
                    raise ValueError("Недопустимые обезвреженные ловушки")
                for p in level.traps:
                    p.disabled = p.placement.id in saved.disabled_traps
                    p.triggered = saved.traps[p.placement.id]
                    p.discovered = p.placement.id in saved.discovered_traps
                for p in level.points:
                    if p.challenge:
                        p.challenge.completed = saved.points[p.placement.id]
                    elif saved.points[p.placement.id]:
                        raise ValueError(
                            "У записки нет состояния завершённого испытания"
                        )
                if saved.ground_items is None:
                    placements = {p.id: p for p, _ in level.items}
                    level.items = [
                        (placements[key], restore_item(item, catalog))
                        for key, item in saved.items.items()
                    ]
            if saved.ground_items is not None:
                restored = []
                placement_ids = set()
                for entry in saved.ground_items:
                    position = Position(*entry.position)
                    if (
                        not state.dungeon.walkable(position)
                        or entry.id in placement_ids
                    ):
                        raise ValueError("Недопустимое размещение предмета")
                    item = restore_item(entry.item, catalog)
                    expected = item.id if ":" in item.id else "base:" + item.id
                    if equipment_alias(entry.ref) != expected:
                        raise ValueError("Ссылка предмета не соответствует шаблону")
                    placement_ids.add(entry.id)
                    restored.append(
                        (ItemPlacement(entry.id, expected, *entry.position), item)
                    )
                state.items[:] = restored
            if state.level:
                from ..world.objects import validate_object_state

                for category in ("objects", "points_of_interest", "traps", "doors"):
                    for placement in getattr(state.level.definition, category):
                        if placement.id in state.level.object_states:
                            validate_object_state(
                                state.level.object_states[placement.id],
                                state.level.store.resolve(
                                    "objects" if category == "doors" else category,
                                    placement,
                                ),
                                category,
                            )
                if saved.door_loot is None:
                    state.level.door_loot.update(
                        d.placement.id for d in state.level.doors if d.door.destroyed
                    )
            occupied = {state.position}
            for placement in state.monsters:
                if placement.corpse_created and (
                    placement.monster.hp > 0 or placement.monster.inventory
                ):
                    raise ValueError("Недопустимое состояние останков существа")
                if not state.dungeon.walkable(placement.position):
                    raise ValueError("Недопустимая позиция монстра")
                if placement.monster.hp > 0:
                    if placement.position in occupied:
                        raise ValueError("Существа занимают одну клетку")
                    occupied.add(placement.position)
            states.append(state)

        all_items = [
            *hero.inventory,
            *(
                d.brace
                for state in states
                if state.level
                for d in state.level.doors
                if d.brace
            ),
            *(item for state in states for _, item in state.items),
            *(
                item
                for state in states
                for placement in state.monsters
                for item in placement.monster.inventory
            ),
            *(
                item
                for state in states
                if state.level
                for container in state.level.containers
                for item in container.items
            ),
        ]

        def contents(items):
            for item in items:
                yield item
                if item.work:
                    yield from contents(item.work.ingredients)
                    if item.work.target:
                        yield from contents([item.work.target])
                if item.furniture:
                    yield from contents(item.furniture.items)

        for item in contents(all_items):
            if (
                item.work
                and item.work.recipe.operation
                and item.work.recipe.operation.place_trap
                and store is not None
            ):
                store.get("traps", item.work.recipe.operation.place_trap)
            if item.furniture and store is not None:
                store.get(item.furniture.category, item.furniture.placement.ref)
            if (
                item.work
                and item.work.recipe.operation
                and item.work.recipe.operation.place_object
                and store is not None
            ):
                obj = store.get("objects", item.work.recipe.operation.place_object)
                if (
                    obj.storage
                    or obj.brush.transition
                    or (item.work.recipe.operation.ignition and not obj.campfire)
                ):
                    raise ValueError("Недопустимый шаблон создаваемого объекта")

        # Every nested item has one owner, including reserved vessels and repair targets.
        item_ids = [i.instance_id for i in contents(all_items)]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Предмет присутствует в нескольких местах")

        def tuples(value):
            return tuple(tuples(v) for v in value) if isinstance(value, list) else value

        rng = random.Random()
        rng.setstate(tuples(record.rng))
        engine = Engine(states[record.current], rng)
        for note in record.read_notes:
            key = note.map_ref, note.placement_id
            if key in engine.read_notes:
                raise ValueError("Повторная запись в журнале")
            engine.read_notes[key] = note
        engine.levels = {s.level.ref: s for s in states if s.level}
        for item in list(hero.inventory):
            if item.work:
                engine.release_repair_target(item.work)
        from ..world.magic import MagicPlacement
        from ..domain.spellcasting import world_spell_parameters
        from .magic import world_spells

        magic_ids = set()
        for saved in record.magic_effects:
            params = world_spell_parameters.validate(saved.kind, saved.params)
            handler = world_spells.handlers.get(saved.kind)
            if saved.scroll_definition:
                scroll = catalog.equipment.get(saved.scroll_definition)
                if (
                    not scroll
                    or scroll.cast_spell != saved.spell_id
                    or scroll.charges is None
                ):
                    raise ValueError("Недопустимый источник магического эффекта")
                spell = catalog.spells.get(saved.spell_id)
            else:
                spell = next(
                    (s for s in hero.known_spells if s.id == saved.spell_id), None
                )
            if (
                not handler
                or not handler.persistent
                or saved.instance_id in magic_ids
                or saved.turns > params.duration
                or spell is None
                or spell.world_effect != saved.kind
            ):
                raise ValueError("Недопустимый временный магический эффект")
            if saved.kind == "light":
                if saved.item_id not in item_ids or saved.position is not None:
                    raise ValueError("У света нет предмета")
            else:
                level_state = (
                    engine.levels.get(saved.map_ref)
                    if saved.map_ref
                    else next((s for s in states if not s.level), None)
                )
                if (
                    level_state is None
                    or saved.position is None
                    or saved.item_id is not None
                    or not (
                        0 <= saved.position[0] < level_state.dungeon.width
                        and 0 <= saved.position[1] < level_state.dungeon.height
                    )
                ):
                    raise ValueError("Магический эффект находится за пределами карты")
            if saved.concentration != spell.concentration:
                raise ValueError("Неправильный тип концентрации")
            magic_ids.add(saved.instance_id)
            engine.magic_effects.append(
                MagicPlacement(
                    **{
                        **saved.model_dump(),
                        "position": Position(*saved.position)
                        if saved.position
                        else None,
                    }
                )
            )
        if hero.concentration_id and not any(
            m.instance_id == hero.concentration_id and m.concentration
            for m in engine.magic_effects
        ):
            raise ValueError("Концентрация не соответствует эффекту")
        engine.sync_magic()
        if not engine.state.walkable(engine.state.position):
            raise ValueError("Герой находится в закрытой двери")
        if record.lockpick:
            attempt = LockpickAttempt(**record.lockpick.model_dump())
            target = engine.lockpick_target(attempt)
            if target is None or target[1].lock_turns != attempt.total:
                raise ValueError("Недопустимый процесс взлома")
            engine.lockpick_attempt = attempt
        if record.active_craft:
            if engine.lockpick_attempt or engine.workpiece(record.active_craft) is None:
                raise ValueError("Недопустимая текущая работа")
            # Load safely paused so a dark location never traps the player in a job.
            engine.active_craft = None
        engine.discard_consumed_lights()
        engine.collect_corpses(list(engine.levels.values()))
        for key, completed in record.challenges.items():
            challenge = TextChallenge(catalog.challenges[key], engine.actions.effects)
            challenge.completed = completed
            engine.challenges[key] = challenge
        return engine
