"""Build independent runtime objects from validated content; only factories read packs."""

import random
from ..content.catalog import ContentCatalog, default_catalog
from ..content.packs import runtime_key
from ..domain.actors import Hero, Monster
from ..domain.stats import Stats
from ..domain.equipment import Equipment
from ..domain.challenges import TextChallenge
from ..domain.effects import EffectRegistry
from ..world.level import Level, TrapInstance, PointInstance
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement
from ..presentation.art import map_cells


def create_test_hero(catalog: ContentCatalog | None = None) -> Hero:
    """A fixed starter hero; custom catalogs fall back to their first definitions."""
    catalog = catalog or default_catalog()
    if not catalog.races or not catalog.classes:
        raise ValueError("Для тестового героя нужны расы и классы")
    race = catalog.races.get("human") or catalog.ordered_races[0]
    character_class = catalog.classes.get("warrior") or catalog.ordered_classes[0]
    return Hero.create(
        race, character_class, Stats((14, 12, 13, 10, 10, 8)), catalog=catalog
    )


class SessionFactory:
    def __init__(self, store):
        self.store = store
        self.catalog = store.runtime_catalog()

    def hero(
        self,
        race="base:human",
        character_class="base:warrior",
        scores=(14, 12, 13, 10, 10, 8),
        background=None,
    ):
        self.store.get("races", race)
        self.store.get("classes", character_class)
        if background:
            self.store.get("backgrounds", background)
        hero = Hero.create(
            runtime_key(race),
            runtime_key(character_class),
            Stats(tuple(scores)),
            catalog=self.catalog,
            background=runtime_key(background) if background else None,
        )
        return hero

    def state(self, map_ref, hero):
        definition = self.store.get("maps", map_ref)
        rows = tuple(
            "".join("." if c else "#" for c in row) for row in definition.walkability
        )
        state = GameState(
            hero, DungeonMap(rows), Position(definition.spawn.x, definition.spawn.y)
        )
        level = Level(
            map_ref, definition, self.store, map_cells(self.store, definition)
        )
        effects = EffectRegistry.default()
        for p in definition.traps:
            level.traps.append(TrapInstance(p, self.store.get("traps", p.ref)))
        for p in definition.points_of_interest:
            point = self.store.get("points_of_interest", p.ref)
            challenge = TextChallenge(
                self.catalog.challenges[runtime_key(point.challenge)], effects
            )
            level.points.append(PointInstance(p, point, challenge))
        for p in definition.equipment:
            level.items.append(
                (p, Equipment.create(self.catalog.equipment[runtime_key(p.ref)]))
            )
        for p in definition.monsters:
            monster = Monster.create(runtime_key(p.ref), catalog=self.catalog)
            monster.definition_ref = p.ref
            state.monsters.append(MonsterPlacement(monster, Position(p.x, p.y)))
        state.level = level
        return state

    def session(
        self,
        map_ref,
        race="base:human",
        character_class="base:warrior",
        seed=0,
        scores=(14, 12, 13, 10, 10, 8),
        background=None,
    ):
        from .engine import Engine

        return Engine(
            self.state(map_ref, self.hero(race, character_class, scores, background)),
            random.Random(seed),
        )
