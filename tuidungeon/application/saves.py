"""Versioned JSON saves, atomic writes and reconstruction from content definitions."""

import json
from pathlib import Path
import random
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .engine import Engine
from .factories import SessionFactory
from ..content.catalog import default_catalog
from ..domain.actors import Hero, Monster
from ..domain.challenges import TextChallenge
from ..domain.equipment import Equipment
from ..domain.stats import Stats
from ..world.clock import GameClock
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement


DEFAULT_SAVE = Path(__file__).resolve().parents[2] / "saves" / "quicksave.json"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ItemRecord(Record):
    definition: str
    instance_id: str
    durability: int | None = Field(default=None, ge=0)
    charges: int | None = Field(default=None, ge=0)
    equipped: bool


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


class MonsterRecord(Record):
    definition: str
    position: tuple[int, int]
    actor: ActorRecord


class LevelRecord(Record):
    ref: str | None
    # Full authored definition detects maps edited since the save.
    definition: dict | None
    rows: tuple[str, ...]
    position: tuple[int, int]
    monsters: list[MonsterRecord]
    traps: dict[str, bool]
    points: dict[str, bool]
    items: dict[str, ItemRecord]


class SaveRecord(Record):
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
        definition=item.id,
        instance_id=item.instance_id,
        durability=item.durability,
        charges=item.charges,
        equipped=item.equipped,
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
    )


def restore_item(record, catalog):
    item = Equipment.create(catalog.equipment[record.definition])
    for name in ("durability", "charges"):
        value, maximum = getattr(record, name), getattr(item.definition, name)
        if (value is None) != (maximum is None) or (
            value is not None and value > maximum
        ):
            raise ValueError("Ресурс предмета не соответствует шаблону")
        setattr(item, name, value)
    item.equipped, item.instance_id = record.equipped, record.instance_id
    return item


def restore_actor(actor, record, catalog):
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
    return actor


class SaveRepository:
    def __init__(self, path=DEFAULT_SAVE):
        self.path = Path(path)

    def save(self, engine):
        state, hero = engine.state, engine.state.hero
        states = list(engine.levels.values()) if engine.levels else [state]
        levels = []
        for entry in states:
            level = entry.level
            levels.append(
                LevelRecord(
                    ref=level.ref if level else None,
                    definition=level.definition.model_dump(mode="json")
                    if level
                    else None,
                    rows=entry.dungeon.rows,
                    position=(entry.position.x, entry.position.y),
                    monsters=[
                        MonsterRecord(
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
                    items={p.id: item_record(i) for p, i in level.items}
                    if level
                    else {},
                )
            )
        record = SaveRecord(
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
        restore_actor(hero, record.hero, catalog)
        clock = GameClock(record.elapsed_minutes)
        states = []
        for saved in record.levels:
            if saved.ref:
                if store is None:
                    from ..content.packs import PackStore

                    store = PackStore()
                state = SessionFactory(store).state(saved.ref, hero)
                if state.level.definition.model_dump(mode="json") != saved.definition:
                    raise ValueError("Карта изменена после сохранения")
            else:
                state = GameState(
                    hero, DungeonMap(saved.rows), Position(*saved.position)
                )
            state.position = Position(*saved.position)
            if state.dungeon.rows != saved.rows or not state.dungeon.walkable(
                state.position
            ):
                raise ValueError("Недопустимая карта или позиция героя")
            state.clock, state.turns = clock, record.turns
            state.monsters = [
                MonsterPlacement(
                    restore_actor(
                        Monster.create(p.definition, catalog=catalog), p.actor, catalog
                    ),
                    Position(*p.position),
                )
                for p in saved.monsters
            ]
            level = state.level
            if level:
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
                placements = {p.id: p for p, _ in level.items}
                level.items = [
                    (placements[key], restore_item(item, catalog))
                    for key, item in saved.items.items()
                ]
            occupied = {state.position}
            for placement in state.monsters:
                if not state.dungeon.walkable(placement.position):
                    raise ValueError("Недопустимая позиция монстра")
                if placement.monster.hp > 0:
                    if placement.position in occupied:
                        raise ValueError("Существа занимают одну клетку")
                    occupied.add(placement.position)
            states.append(state)

        def tuples(value):
            return tuple(tuples(v) for v in value) if isinstance(value, list) else value

        rng = random.Random()
        rng.setstate(tuples(record.rng))
        engine = Engine(states[record.current], rng)
        engine.levels = {s.level.ref: s for s in states if s.level}
        for key, completed in record.challenges.items():
            challenge = TextChallenge(catalog.challenges[key], engine.actions.effects)
            challenge.completed = completed
            engine.challenges[key] = challenge
        return engine
