from functools import lru_cache
from dataclasses import asdict
from ..domain.value_types import FrozenDict
from uuid import uuid4
from threading import RLock
from ..application.factories import SessionFactory
from ..application.engine import Action
from ..world.maps import Position
from ..domain.storage import item_stacks


def stack_payload(items):
    return [
        dict(
            id=s.first.instance_id,
            name=s.first.name,
            label=s.label,
            quantity=s.quantity,
            weight=s.weight,
            unit_weight=s.first.weight,
            durability=s.first.durability,
            max_durability=s.first.definition.durability,
            charges=s.first.charges,
            fuel_minutes=s.first.fuel_minutes,
            equipped=s.first.equipped,
            glow=asdict(s.first.glow) if s.first.glow else None,
            tags=sorted(s.first.definition.tags | s.first.effect_tags),
        )
        for s in item_stacks(items)
    ]


@lru_cache(maxsize=4096)
def cell_payload(cell):
    return FrozenDict(cell.model_dump()) if cell else None


class TestSession:
    def __init__(self, store, options):
        snapshot = store.snapshot()
        self.lock = RLock()
        self.factory = SessionFactory(snapshot)
        self.options = dict(options)
        self.viewport_width = self.options.pop("viewport_width", None)
        self.viewport_height = self.options.pop("viewport_height", None)
        if (self.viewport_width is None) != (self.viewport_height is None):
            raise ValueError("Для камеры нужны ширина и высота")
        if self.viewport_width is not None and any(
            type(n) is not int or not 1 <= n <= 256
            for n in (self.viewport_width, self.viewport_height)
        ):
            raise ValueError("Размеры камеры должны быть от 1 до 256")
        self.id = str(uuid4())
        self.reset()

    def reset(self):
        with self.lock:
            self._reset()

    def _reset(self):
        self.engine = self.factory.session(**self.options)
        self.log = []

    def command(
        self,
        command,
        placement=None,
        choice=None,
        x=None,
        y=None,
        item=None,
        quantity=1,
        deposit=False,
        spell_id=None,
        source="class",
        option=None,
    ):
        with self.lock:
            return self._command(
                command,
                placement,
                choice,
                x,
                y,
                item,
                quantity,
                deposit,
                spell_id,
                source,
                option,
            )

    def _command(
        self,
        command,
        placement=None,
        choice=None,
        x=None,
        y=None,
        item=None,
        quantity=1,
        deposit=False,
        spell_id=None,
        source="class",
        option=None,
    ):
        if self.engine.lockpick_attempt and command not in (
            "lockpick_step",
            "lockpick_cancel",
        ):
            raise ValueError("Сначала завершите или отмените взлом")
        bindings = {
            "w": Action.NORTH,
            "s": Action.SOUTH,
            "a": Action.WEST,
            "d": Action.EAST,
            "wait": Action.WAIT,
            "rest": Action.REST,
            "short_rest": Action.SHORT_REST,
        }
        if command == "cast":
            from ..domain.actions import SpellSource
            from ..content.packs import runtime_key

            target = (
                next(
                    (
                        i
                        for i in self.engine.state.hero.inventory
                        if i.instance_id == item
                    ),
                    None,
                )
                if item
                else Position(x, y)
                if type(x) is int and type(y) is int
                else None
            )
            result = self.engine.cast_spell(
                runtime_key(spell_id) if spell_id else "",
                SpellSource(source),
                target,
                option=option,
            )
        elif command == "hand":
            result = self.engine.use_magic_hand(
                Position(x, y) if type(x) is int and type(y) is int else None
            )
        elif command == "storage_transfer":
            result = self.engine.transfer_storage(
                placement, item, quantity, deposit=deposit
            )
        elif command == "lockpick_step":
            result = self.engine.advance_lockpick()
        elif command == "lockpick_cancel":
            result = self.engine.cancel_lockpick()
        elif command == "interact":
            result = self.engine.interact(placement, choice)
        elif command in ("equip", "unequip", "throw", "ignite"):
            item = next(
                (
                    i
                    for i in self.engine.state.hero.inventory
                    if i.instance_id == placement
                ),
                None,
            )
            if item is None:
                raise ValueError("Предмет отсутствует в инвентаре")
            if command in ("throw", "ignite"):
                if type(x) is not int or type(y) is not int:
                    raise ValueError("Выберите клетку цели")
                target = Position(x, y)
                if not self.engine._inside(target):
                    raise ValueError("Цель за пределами карты")
                result = (
                    self.engine.ignite_cell(item, target)
                    if command == "ignite"
                    else self.engine.place_item(item, target, throwing=True)
                )
            else:
                result = self.engine.manage_equipment(item, command == "equip")
        elif command == "pickup":
            result = self.engine.pickup_item()
        elif command in bindings:
            result = self.engine.apply(bindings[command])
        else:
            raise ValueError("Неизвестная команда")
        self.log.append(
            {
                "performed": result.performed,
                "minutes": getattr(result, "minutes", int(result.performed)),
                "message": result.message,
            }
        )
        self.log = self.log[-100:]
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        self.engine.sync_magic()
        state = self.engine.state
        hero = state.hero
        level = state.level
        width = min(self.viewport_width or state.dungeon.width, state.dungeon.width)
        height = min(self.viewport_height or state.dungeon.height, state.dungeon.height)
        x = max(0, min(state.position.x - width // 2, state.dungeon.width - width))
        y = max(0, min(state.position.y - height // 2, state.dungeon.height - height))
        region = (x, y, width, height)
        light = self.engine.lighting
        return {
            "lockpick": vars(self.engine.lockpick_attempt).copy()
            if self.engine.lockpick_attempt
            else None,
            "id": self.id,
            "map": level.ref,
            "width": state.dungeon.width,
            "height": state.dungeon.height,
            "viewport": {"x": x, "y": y, "width": width, "height": height},
            "cells": [
                [cell_payload(c) for c in row]
                for row in self.engine.render_cells(region)
            ],
            "lighting": [row[x : x + width] for row in light.cells[y : y + height]],
            "position": {"x": state.position.x, "y": state.position.y},
            "turns": state.turns,
            "oil": [dict(x=p.x, y=p.y, turns=t) for p, t in state.oil.items()],
            "clock": {
                "day": state.clock.day,
                "hour": state.clock.hour,
                "minute": state.clock.minute,
                "elapsed": state.clock.elapsed_minutes,
                "time_of_day": state.clock.time_of_day,
            },
            "hero": {
                "carried_weight": hero.carried_weight,
                "max_carry_weight": hero.max_carry_weight,
                "stacks": stack_payload(hero.inventory),
                "name": hero.name,
                "hp": hero.hp,
                "max_hp": hero.max_hp,
                "armor_class": hero.armor_class,
                "gold": hero.gold,
                "experience": hero.experience,
                "spell_slots": dict(hero.spell_slots),
                "racial_uses": hero.racial_uses,
                "cantrip_uses": hero.cantrip_uses,
                "max_cantrip_uses": hero.max_cantrip_uses,
                "concentrating": bool(hero.concentration_id),
                "hand_active": bool(self.engine.active_hand),
                "spells": [
                    dict(
                        id=s.id,
                        source=source,
                        name=s.name,
                        level=s.level,
                        target=s.target,
                        range=s.range,
                        modes=s.modes,
                        world_effect=s.world_effect,
                        description=s.description,
                        pending_effects=s.pending_effects,
                        item_targets=[
                            item.instance_id for item in self.engine.spell_item_targets(s)
                        ],
                    )
                    for s, source in [(s, "class") for s in hero.class_spells]
                    + ([(hero.racial_spell, "racial")] if hero.racial_spell else [])
                ],
                "conditions": dict(hero.conditions),
                "hands_used": hero.hands_used,
                "inventory": [
                    {
                        "id": i.instance_id,
                        "name": i.name,
                        "equipped": i.equipped,
                        "ignition_source": i.ignition_source,
                        "can_ignite": i.can_ignite,
                        "throwable": bool(i.tags & {"lamp_oil", "acid"}),
                        "slot": i.definition.slot,
                        "hands": i.hands,
                        "light": bool(i.definition.light),
                        "lit": i.lit,
                        "fuel_minutes": i.fuel_minutes,
                        "charges": i.charges,
                        "durability": i.durability,
                        "max_durability": i.definition.durability,
                        "glow": asdict(i.glow) if i.glow else None,
                        "tags": sorted(i.definition.tags | i.effect_tags),
                    }
                    for i in hero.inventory
                ],
            },
            "traps": [
                {"id": t.placement.id, "triggered": t.triggered} for t in level.traps
            ],
            "containers": [
                dict(
                    id=c.placement.id,
                    name=c.definition.name,
                    personal=c.spec.personal,
                    capacity=c.spec.capacity,
                    weight=c.weight,
                    items=stack_payload(c.items),
                )
                for c in self.engine.nearby_containers()
            ],
            "points": [
                {"id": p.placement.id, "completed": p.challenge.completed}
                for p in level.points
            ],
            "doors": [
                dict(
                    id=d.placement.id,
                    x=d.placement.x,
                    y=d.placement.y,
                    material=d.door.material,
                    opened=d.door.opened,
                    locked=d.door.locked,
                    hp=d.door.hp,
                    max_hp=d.door.max_hp,
                    burning=d.door.burning,
                    corroding=d.door.corroding,
                    bent=d.door.bent,
                )
                for d in level.doors
            ],
            "nearby": [
                {
                    "id": p.placement.id,
                    "name": p.definition.name,
                    "text": p.challenge.text,
                    "completed": p.challenge.completed,
                    "choices": [
                        {"id": c.id, "text": c.text}
                        for c in p.challenge.available_choices(hero)
                    ],
                }
                for p in self.engine.nearby_points()
            ],
            "monsters": [
                {
                    "id": p.monster.instance_id,
                    "definition": p.monster.definition_ref,
                    "hp": p.monster.hp,
                    "x": p.position.x,
                    "y": p.position.y,
                }
                for p in state.monsters
            ],
            "ground": [
                {"id": p.id, "name": item.name, "x": p.x, "y": p.y}
                for p, item in state.items
            ],
            "log": list(self.log),
            "events": self.engine.events[-100:],
        }
