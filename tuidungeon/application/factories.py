"""Build independent runtime objects from validated content; only factories read packs."""

import random
from ..content.catalog import ContentCatalog, default_catalog
from ..content.packs import runtime_key
from ..content.compiler import compile_definition
from ..content.placements import resolve_challenge
from ..domain.actors import Hero, Monster
from ..domain.stats import Stats
from ..domain.equipment import Equipment
from ..domain.challenges import TextChallenge
from ..domain.effects import EffectRegistry
from ..world.level import Level, TrapInstance, PointInstance
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement
from ..world.doors import DoorInstance, door_placements, door_category
from ..world.storage import StorageInstance
from ..domain.doors import Door


def create_test_hero(
    catalog: ContentCatalog | None = None, character_class: str | None = None
) -> Hero:
    """A fixed starter hero; custom catalogs fall back to their first definitions."""
    catalog = catalog or default_catalog()
    if not catalog.races or not catalog.classes:
        raise ValueError("Для тестового героя нужны расы и классы")
    if character_class is not None:
        if character_class not in catalog.classes:
            raise ValueError(f"Неизвестный тестовый класс: {character_class}")
        if character_class == "wizard":
            return create_test_wizard(catalog)
    race = catalog.races.get("human") or catalog.ordered_races[0]
    definition = (
        catalog.classes[character_class]
        if character_class is not None
        else catalog.classes.get("warrior") or catalog.ordered_classes[0]
    )
    return Hero.create(
        race, definition, Stats((14, 12, 13, 10, 10, 8)), catalog=catalog
    )


def prepare_test_wizard(hero: Hero) -> Hero:
    """Grant the developer spellbook without changing shared class definitions."""
    if hero.character_class.id != "wizard":
        raise ValueError("Для тестового волшебника нужен класс wizard")
    hero.test_profile = "wizard"
    hero.class_spells = tuple(hero.catalog.spells.values())
    hero.max_spell_slots = {
        level: max(10, hero.max_spell_slots.get(level, 0))
        for level in sorted({s.level for s in hero.class_spells if s.level > 0})
    }
    hero.restore_after_rest()
    return hero


def create_test_wizard(catalog: ContentCatalog | None = None) -> Hero:
    catalog = catalog or default_catalog()
    if not catalog.races or "wizard" not in catalog.classes:
        raise ValueError("Для тестового волшебника нужны раса и класс wizard")
    race = catalog.races.get("human") or catalog.ordered_races[0]
    return prepare_test_wizard(
        Hero.create(race, "wizard", Stats((10, 12, 14, 18, 12, 10)), catalog=catalog)
    )


class SessionFactory:
    def __init__(self, store):
        self.store = store.snapshot()
        self.catalog = self.store.runtime_catalog()

    def hero(
        self,
        race="base:human",
        character_class="base:warrior",
        scores=(14, 12, 13, 10, 10, 8),
        background=None,
        cantrips=None,
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
            cantrips=tuple(runtime_key(s) for s in cantrips)
            if cantrips is not None
            else None,
        )
        return hero

    def state(self, map_ref, hero, *, definition=None):
        restoring = definition is not None
        definition = definition or self.store.get("maps", map_ref)
        for item in hero.inventory:
            item.bind_key(map_ref, definition.name)
        level = Level(map_ref, definition, self.store)
        for p in door_placements(self.store, definition):
            tile = self.store.resolve(door_category(self.store, p.ref), p)
            if tile.brush.door is None:
                raise ValueError("Размещение двери должно ссылаться на тайл с door")
            level.doors.append(DoorInstance(p, tile, Door.from_spec(tile.brush.door)))
        # DungeonMap keeps underlying terrain; mutable doors are a separate overlay.
        level.terrain
        base = definition
        masks = [list(row) for row in base.walkability]
        for door in level.doors:
            masks[door.placement.y][door.placement.x] = True
        rows = tuple("".join("." if c else "#" for c in row) for row in masks)
        state = GameState(
            hero, DungeonMap(rows), Position(definition.spawn.x, definition.spawn.y)
        )
        if (
            not restoring
            and not level.terrain.walkability[state.position.y][state.position.x]
        ):
            raise ValueError("Старт героя закрыт объектом")
        effects = EffectRegistry.default()
        for p in definition.traps:
            level.traps.append(TrapInstance(p, self.store.resolve("traps", p)))
        for p in definition.points_of_interest:
            point = self.store.resolve("points_of_interest", p)
            challenge_document = resolve_challenge(self.store.documents, point, p)
            challenge = (
                TextChallenge(
                    compile_definition(
                        "challenges", point.challenge, challenge_document
                    )
                    if p.challenge_overrides
                    else self.catalog.challenges[runtime_key(point.challenge)],
                    effects,
                )
                if challenge_document is not None
                else None
            )
            level.points.append(PointInstance(p, point, challenge))
        for p in definition.equipment:
            item = Equipment.create(
                self.store.placement_definition("equipment", p),
                level_ref=map_ref,
                level_name=definition.name,
            )
            if p.overrides:
                item.template = self.store.resolve("equipment", p).model_dump(
                    mode="json"
                )
            if p.item_state:
                item.contaminated = p.item_state.contaminated
                if (
                    p.item_state.durability is not None
                    and item.definition.durability is not None
                ):
                    item.durability = p.item_state.durability
            level.items.append((p, item))
        for category in ("objects", "points_of_interest"):
            for p in getattr(definition, category):
                obj = self.store.resolve(category, p)
                if obj.storage is None:
                    continue
                container = StorageInstance(p, obj, obj.storage)
                for entry in obj.storage.contents:
                    item_definition = self.catalog.equipment[runtime_key(entry.item)]
                    template = None
                    if entry.key_code:
                        from ..content.placements import override_document

                        doc = override_document(
                            "equipment",
                            self.store.get("equipment", entry.item),
                            {"key_code": entry.key_code},
                        )
                        item_definition = compile_definition(
                            "equipment", entry.item, doc
                        )
                        template = doc.model_dump(mode="json")
                    for _ in range(entry.quantity):
                        item = Equipment.create(
                            item_definition,
                            level_ref=map_ref,
                            level_name=definition.name,
                        )
                        item.template = template
                        container.items.append(item)
                if container.weight > container.spec.capacity + 1e-9:
                    raise ValueError(
                        "Начальное содержимое превышает вместимость контейнера"
                    )
                from ..domain.item_sizes import fits_size

                if any(
                    not fits_size(i.size, container.spec.max_item_size)
                    for i in container.items
                ):
                    raise ValueError(
                        "Размер начального содержимого превышает предел контейнера"
                    )
                if getattr(obj, "light_fixture", None):
                    for item in container.items:
                        if item.definition.light:
                            item.fuel_minutes = item.definition.light.burn_minutes
                        item.lit = bool(item.definition.light and item.fuel_minutes)
                level.containers.append(container)
        for p in definition.monsters:
            if not restoring and not level.terrain.walkability[p.y][p.x]:
                raise ValueError("Существо размещено на непроходимой клетке")
            monster = Monster.create(
                runtime_key(p.ref),
                catalog=self.catalog,
                definition=self.store.placement_definition("monsters", p),
            )
            if p.overrides:
                monster.template = self.store.resolve("monsters", p).model_dump(
                    mode="json"
                )
            monster.definition_ref = p.ref
            for item in monster.inventory:
                item.bind_key(map_ref, definition.name)
            state.monsters.append(MonsterPlacement(monster, Position(p.x, p.y)))
        from ..world.npcs import NpcInstance

        for p in definition.npcs:
            if not level.terrain.walkability[p.y][p.x]:
                raise ValueError("NPC размещён на непроходимой клетке")
            npc = NpcInstance(p, self.store.resolve("npcs", p))
            if npc.definition.trade:
                stock = [(e.item, e.quantity) for e in npc.definition.trade.stock]
                stock.append(("base:gold", npc.definition.trade.gold))
                for ref, count in stock:
                    npc.items.extend(
                        Equipment.create(
                            self.catalog.equipment[runtime_key(ref)],
                            level_ref=map_ref,
                            level_name=definition.name,
                        )
                        for _ in range(count)
                    )
            level.npcs.append(npc)
        state.level = level
        if not restoring:
            from ..world.objects import schedule_growth

            for p in definition.objects:
                schedule_growth(
                    level,
                    p,
                    self.store.resolve("objects", p),
                    state.clock.elapsed_minutes,
                )
        return state

    def session(
        self,
        map_ref,
        race="base:human",
        character_class="base:warrior",
        seed=0,
        scores=(14, 12, 13, 10, 10, 8),
        background=None,
        cantrips=None,
    ):
        from .engine import Engine

        return Engine(
            self.state(
                map_ref, self.hero(race, character_class, scores, background, cantrips)
            ),
            random.Random(seed),
        )
