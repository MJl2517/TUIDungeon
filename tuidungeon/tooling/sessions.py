from functools import lru_cache
from ..domain.value_types import FrozenDict
from uuid import uuid4
from threading import RLock
from ..application.factories import SessionFactory
from ..application.engine import Action


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

    def command(self, command, placement=None, choice=None):
        with self.lock:
            return self._command(command, placement, choice)

    def _command(self, command, placement=None, choice=None):
        bindings = {
            "w": Action.NORTH,
            "s": Action.SOUTH,
            "a": Action.WEST,
            "d": Action.EAST,
            "wait": Action.WAIT,
            "rest": Action.REST,
        }
        if command == "interact":
            result = self.engine.interact(placement, choice)
        elif command in ("equip", "unequip"):
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
                "minutes": result.minutes,
                "message": result.message,
            }
        )
        self.log = self.log[-100:]
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
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
            "clock": {
                "day": state.clock.day,
                "hour": state.clock.hour,
                "minute": state.clock.minute,
                "elapsed": state.clock.elapsed_minutes,
                "time_of_day": state.clock.time_of_day,
            },
            "hero": {
                "name": hero.name,
                "hp": hero.hp,
                "max_hp": hero.max_hp,
                "armor_class": hero.armor_class,
                "gold": hero.gold,
                "experience": hero.experience,
                "spell_slots": dict(hero.spell_slots),
                "racial_uses": hero.racial_uses,
                "conditions": dict(hero.conditions),
                "hands_used": hero.hands_used,
                "inventory": [
                    {
                        "id": i.instance_id,
                        "name": i.name,
                        "equipped": i.equipped,
                        "slot": i.definition.slot,
                        "hands": i.hands,
                        "light": bool(i.definition.light),
                        "lit": i.lit,
                        "fuel_minutes": i.fuel_minutes,
                        "charges": i.charges,
                    }
                    for i in hero.inventory
                ],
            },
            "traps": [
                {"id": t.placement.id, "triggered": t.triggered} for t in level.traps
            ],
            "points": [
                {"id": p.placement.id, "completed": p.challenge.completed}
                for p in level.points
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
