"""Versioned JSON saves, atomic writes and reconstruction from content definitions."""

import json
from pathlib import Path
import random
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .engine import Engine
from .factories import SessionFactory, prepare_test_wizard
from ..content.catalog import default_catalog
from ..domain.actors import Hero, Monster
from ..domain.challenges import TextChallenge
from ..domain.equipment import Equipment
from ..domain.stats import Stats
from ..world.clock import GameClock
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement, ItemPlacement
from ..domain.doors import Door, LockpickAttempt, Material, MATERIALS
from ..content.compiler import compile_definition
from ..content.schemas import (
    EquipmentDocument,
    MonsterDocument,
    StorageSpec,
    DamageDefenses,
)
from ..domain.damage import DamageProfile
from ..content.migrations import migrate_map, equipment_alias, legacy_item_template


DEFAULT_SAVE = Path(__file__).resolve().parents[2] / "saves" / "quicksave.json"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ItemRecord(Record):
    template: dict | None = None
    definition: str
    instance_id: str
    durability: int | None = Field(default=None, ge=0)
    charges: int | None = Field(default=None, ge=0)
    equipped: bool
    fuel_minutes: int | None = Field(default=None, ge=0)
    lit: bool = False


class ActorRecord(Record):
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
    door_id: str
    progress: int = Field(ge=0, le=9)
    total: Literal[10] = 10


class OilRecord(Record):
    position: tuple[int, int]
    turns: int = Field(ge=1, le=5)


class ContainerRecord(Record):
    instance_id: str
    items: list[ItemRecord]
    personal: bool
    capacity: float = Field(gt=0, le=1000000, allow_inf_nan=False)


class LevelRecord(Record):
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
    return ItemRecord(
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
        instance_id=actor.instance_id,
        name=actor.name,
        stats=actor.stats.values,
        hp=actor.hp,
        max_hp=actor.max_hp,
        level=getattr(actor, "level", 1),
        gold=actor.gold,
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
    item = Equipment.create(definition)
    item.template = record.template
    for name in ("durability", "charges"):
        value, maximum = getattr(record, name), getattr(item.definition, name)
        if (
            name == "durability"
            and value is None
            and maximum is not None
            and item.definition.weapon_damage
        ):
            value = maximum  # Earlier scenery weapons had no durability.
        if (
            name == "durability"
            and record.definition == "crowbar"
            and value is None
            and maximum == 5
        ):
            value = maximum  # Saves from before crowbars had durability.
        if (
            name == "durability"
            and record.definition in ("thieves_tools", "base:thieves_tools")
            and maximum == 10
            and value is not None
            and 10 < value <= 20
        ):
            value = maximum  # Original thieves' tools had a maximum of 20.
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
        "gold",
        "experience",
        "spell_slots",
        "racial_uses",
        "conditions",
        "sneaking",
    ):
        setattr(actor, name, getattr(record, name))
    if isinstance(actor, Hero):
        actor.level = record.level
    actor.inventory = [restore_item(i, catalog) for i in record.inventory]
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
        levels = []
        for entry in states:
            level = entry.level
            levels.append(
                LevelRecord(
                    containers={
                        c.placement.id: ContainerRecord(
                            instance_id=c.instance_id,
                            items=[item_record(i) for i in c.items],
                            personal=c.spec.personal,
                            capacity=c.spec.capacity,
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
                    definition=level.definition.model_dump(mode="json")
                    if level
                    else None,
                    rows=entry.dungeon.rows,
                    position=(entry.position.x, entry.position.y),
                    monsters=[
                        MonsterRecord(
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
                    points={p.placement.id: p.challenge.completed for p in level.points}
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
                    )
                    if instance.door.material == "stone":
                        instance.door.opened = instance.door.locked = False
                    instance.instance_id = data.instance_id
            saved_rows = saved.rows
            if state.level and saved.doors is None:
                rows = [list(row) for row in saved_rows]
                for instance in state.level.doors:
                    p = instance.placement
                    rows[p.y][p.x] = "."
                saved_rows = tuple("".join(row) for row in rows)
            if state.dungeon.rows != saved_rows or not state.dungeon.walkable(
                state.position
            ):
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
                )
                for p in saved.monsters
            ]
            level = state.level
            if level:
                if saved.containers is not None:
                    if set(saved.containers) != {
                        c.placement.id for c in level.containers
                    }:
                        raise ValueError("Размещения контейнеров изменились")
                    for container in level.containers:
                        data = saved.containers[container.placement.id]
                        container.spec = StorageSpec(
                            personal=data.personal, capacity=data.capacity
                        )
                        items = [restore_item(i, catalog) for i in data.items]
                        if (
                            any(i.equipped or i.lit for i in items)
                            or sum(i.weight for i in items)
                            > container.spec.capacity + 1e-9
                        ):
                            raise ValueError("Недопустимое содержимое контейнера")
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
                for p in level.traps:
                    p.triggered = saved.traps[p.placement.id]
                for p in level.points:
                    p.challenge.completed = saved.points[p.placement.id]
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
            occupied = {state.position}
            for placement in state.monsters:
                if not state.dungeon.walkable(placement.position):
                    raise ValueError("Недопустимая позиция монстра")
                if placement.monster.hp > 0:
                    if placement.position in occupied:
                        raise ValueError("Существа занимают одну клетку")
                    occupied.add(placement.position)
            states.append(state)

        item_ids = [item.instance_id for item in hero.inventory]
        item_ids += [item.instance_id for state in states for _, item in state.items]
        item_ids += [
            item.instance_id
            for state in states
            for placement in state.monsters
            for item in placement.monster.inventory
        ]
        item_ids += [
            item.instance_id
            for state in states
            if state.level
            for container in state.level.containers
            for item in container.items
        ]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Предмет присутствует в нескольких местах")

        def tuples(value):
            return tuple(tuples(v) for v in value) if isinstance(value, list) else value

        rng = random.Random()
        rng.setstate(tuples(record.rng))
        engine = Engine(states[record.current], rng)
        engine.levels = {s.level.ref: s for s in states if s.level}
        from ..world.magic import MagicPlacement
        from ..domain.spellcasting import world_spell_parameters
        from .magic import world_spells

        magic_ids = set()
        for saved in record.magic_effects:
            params = world_spell_parameters.validate(saved.kind, saved.params)
            handler = world_spells.handlers.get(saved.kind)
            spell = next((s for s in hero.known_spells if s.id == saved.spell_id), None)
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
            instance = engine._door(attempt.door_id)
            if (
                not engine._door_available(instance)
                or not instance.door.locked
                or instance.door.passable
                or instance.door.lock_turns != attempt.total
            ):
                raise ValueError("Недопустимый процесс взлома")
            engine.lockpick_attempt = attempt
        engine.discard_consumed_lights()
        for key, completed in record.challenges.items():
            challenge = TextChallenge(catalog.challenges[key], engine.actions.effects)
            challenge.completed = completed
            engine.challenges[key] = challenge
        return engine
