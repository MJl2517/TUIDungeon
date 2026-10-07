from copy import copy
from uuid import uuid4
from threading import RLock
from ..application.factories import SessionFactory
from ..application.engine import Action


class TestSession:
    def __init__(self, store, options):
        snapshot = copy(store)
        snapshot.documents = dict(store.documents)
        self.lock = RLock()
        self.factory = SessionFactory(snapshot)
        self.options = options
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
        return {
            "id": self.id,
            "map": level.ref,
            "width": state.dungeon.width,
            "height": state.dungeon.height,
            "cells": [
                [c.model_dump() if c else None for c in row]
                for row in level.render_cells(state)
            ],
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
                        {"id": c.id, "text": c.text} for c in p.challenge.choices
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
            "log": list(self.log),
            "events": self.engine.events[-100:],
        }
