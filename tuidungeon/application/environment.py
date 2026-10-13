"""World work uses the same turn, light and pause controls as crafting."""

from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
from ..content.schemas import Placement
from ..world.maps import Position
from ..world.objects import (
    WorldObject,
    ObjectState,
    FurnitureCargo,
    RegrowingObject,
    WORK_NAMES,
    WORK_RESULTS,
)
from ..world.state import ItemPlacement
from ..domain.equipment import Equipment
from ..domain.damage import DamageProfile
from ..domain.rules import Ability


class EnvironmentCommands:
    def can_long_rest(self):
        p = self.state.position
        cells = {
            (p.x, p.y),
            (p.x - 1, p.y),
            (p.x + 1, p.y),
            (p.x, p.y - 1),
            (p.x, p.y + 1),
        }
        if self.state.level and any(
            (o.x, o.y) in cells
            and "rest_spot" in self.state.level.store.resolve(category, o).tags
            and self._clear_throw_path(Position(o.x, o.y), allow_target_door=True)
            for category in ("objects", "points_of_interest")
            for o in getattr(self.state.level.definition, category)
        ):
            return True
        return any(
            (o.x, o.y) in cells
            and "rest_spot" in item.tags
            and self._clear_throw_path(Position(o.x, o.y), allow_target_door=True)
            for o, item in self.state.items
        )

    def fixture_action(self, identifier, action):
        target = self.world_object(identifier)
        if self._world_ready(target) and (denial := self.light_denial()):
            return denial
        fixture = getattr(target.definition, "light_fixture", None) if target else None
        if (
            action not in {"take_light", "mount_light"}
            or not fixture
            or not self._world_ready(target)
            or self.active_craft
            or self.lockpick_attempt
        ):
            return self._craft_result(False, "Подставка недоступна.")
        container = next(
            c for c in self.state.level.containers if c.placement.id == identifier
        )
        if container.locked:
            return self._craft_result(
                False, "Контейнер заперт. Сначала откройте замок."
            )
        if action == "take_light":
            if not container.items:
                return self._craft_result(False, "Подставка пуста.")
            item = container.items[0]
            if (
                self.state.hero.carried_weight + item.weight
                > self.state.hero.max_carry_weight + 1e-9
            ):
                return self._craft_result(False, "Недостаточно переносимого веса.")
            container.items.remove(item)
            item.equipped = item.lit = False
            self.state.hero.inventory.append(item)
            if not fixture.stays_when_empty:
                self._detach_world(target)
            message = "Подобрано: " + item.name + "."
        else:
            item = next(
                (
                    i
                    for i in self.state.hero.inventory
                    if i.usable
                    and (i.id if ":" in i.id else "base:" + i.id) == fixture.item
                    and i.definition.light
                    and i.fuel_minutes > 0
                ),
                None,
            )
            if container.items or not item:
                return self._craft_result(
                    False,
                    "Нужны пустая подставка и подходящий источник света с топливом.",
                )
            self.state.hero.inventory.remove(item)
            item.equipped, item.lit = False, True
            container.items.append(item)
            message = "Установлено: " + item.name + "."
        self._advance(1)
        return self._craft_result(True, message, 1)

    def collect_corpses(self, states):
        """Move possessions once; the dead actor remains recorded for old saves."""
        for state in states:
            level = state.level
            if not level:
                continue
            for index, placement in enumerate(state.monsters):
                actor = placement.monster
                if actor.hp > 0 or placement.corpse_created:
                    continue
                ref = (
                    "base:skeleton_remains"
                    if "undead" in actor.innate_tags
                    else "base:corpse"
                    if "humanoid" in actor.innate_tags
                    else "base:carcass"
                )
                if ("objects", ref) not in level.store.documents:
                    continue
                p = Placement(
                    id="corpse_" + uuid4().hex,
                    ref=ref,
                    x=placement.position.x,
                    y=placement.position.y,
                    overrides={
                        "name": "Останки: " + actor.name,
                        "description": "Здесь лежат останки существа: "
                        + actor.name
                        + ". Можно обыскать.",
                    },
                )
                definition = level.store.resolve("objects", p)
                for item in actor.inventory:
                    item.equipped = item.lit = False
                self._attach_world_object(
                    level,
                    "objects",
                    p,
                    definition,
                    ObjectState(
                        hp=definition.destruction.max_hp
                        if definition.destruction
                        else None
                    ),
                    items=actor.inventory,
                )
                actor.inventory.clear()
                state.monsters[index] = replace(placement, corpse_created=True)

    def world_objects(self):
        level = self.state.level
        if not level:
            return []
        # Placements are immutable; map edits replace the document. Runtime HP,
        # fuel and discovery remain live and are deliberately not cached.
        if getattr(level, "_world_definitions_source", None) is not level.definition:
            level._world_definitions = {
                (category, p.id): level.store.resolve(category, p)
                for category in ("objects", "points_of_interest", "traps")
                for p in getattr(level.definition, category)
            }
            level._world_definitions_source = level.definition
        result = []
        containers = {c.placement.id: c for c in level.containers}
        for category in ("objects", "points_of_interest", "traps"):
            originals = {
                p.placement.id: p
                for p in getattr(
                    level, "points" if category == "points_of_interest" else "traps", []
                )
            }
            for p in getattr(level.definition, category):
                d = level._world_definitions[category, p.id]
                original = originals.get(p.id) if category != "objects" else None
                if category == "traps":
                    if not (d.dismantle or d.disarm) or (
                        d.hidden and not (original.discovered or original.triggered)
                    ):
                        continue
                    maximum = None
                else:
                    if not (
                        d.destruction
                        or d.movable
                        or getattr(d, "light_fixture", None)
                        or getattr(d, "water_source", None)
                        or getattr(d, "campfire", None)
                    ):
                        continue
                    maximum = d.destruction.max_hp if d.destruction else None
                state = level.object_states.get(p.id)
                if state is None:
                    state = level.object_states[p.id] = ObjectState(hp=maximum)
                result.append(
                    WorldObject(category, p, d, state, original, containers.get(p.id))
                )
        return result

    def world_object(self, identifier):
        return next(
            (o for o in self.world_objects() if o.placement.id == identifier), None
        )

    def world_work_target(self, identifier):
        """Doors share dismantling progress, but retain their own HP and commands."""
        target = self.world_object(identifier)
        if target is not None:
            return target
        instance = self._door(identifier)
        spec = getattr(instance.definition, "destruction", None) if instance else None
        if not instance or instance.door.destroyed or not spec or not spec.dismantle:
            return None
        state = self.state.level.object_states.setdefault(identifier, ObjectState())
        return WorldObject(
            "doors", instance.placement, instance.definition, state, instance
        )

    def _within_reach(self, placement, distance=1):
        p = Position(placement.x, placement.y)
        hero = self.state.position
        return (
            self._inside(p)
            and max(abs(p.x - hero.x), abs(p.y - hero.y)) <= distance
            and self._clear_throw_path(p, allow_target_door=True)
        )

    def nearby_world_objects(self):
        p = self.state.position
        return [
            o
            for o in self.world_objects()
            if (
                self._within_reach(o.placement)
                or (
                    "pole_reachable" in o.definition.tags
                    and (abs(o.placement.x - p.x), abs(o.placement.y - p.y))
                    in ((2, 0), (0, 2))
                    and self.state.walkable(
                        Position((o.placement.x + p.x) // 2, (o.placement.y + p.y) // 2)
                    )
                    and self._within_reach(o.placement, distance=2)
                    and any(
                        i.usable and i.equipped and "pole" in i.tags
                        for i in self.state.hero.inventory
                    )
                )
            )
        ]

    def world_workpiece(self, identifier):
        target = self.world_work_target(identifier.removeprefix("world:"))
        if target is None or not target.state.total:
            return None
        work = SimpleNamespace(
            recipe=SimpleNamespace(
                name=(WORK_NAMES[target.dismantle.verb] + ": ") + target.definition.name
            ),
            progress=target.state.progress,
            total=target.state.total,
        )
        return SimpleNamespace(
            name=work.recipe.name,
            work=work,
            instance_id=identifier,
            weight=target.definition.weight if target.category != "traps" else 0,
        )

    def _world_ready(self, target):
        return (
            target is not None
            and self.state.hero.hp > 0
            and not self.lockpick_attempt
            and (
                self._within_reach(target.placement)
                if target.category == "doors"
                else any(
                    o.placement.id == target.placement.id
                    for o in self.nearby_world_objects()
                )
            )
            and bool(
                self.state.level.definition.tiles[target.placement.y][
                    target.placement.x
                ]
            )
        )

    def ignite_world_objects(self, p):
        ignited = False
        for target in self.world_objects():
            if (
                target.category != "traps"
                and target.definition.destruction
                and not getattr(target.definition, "campfire", None)
                and "flammable" in target.definition.tags
                and (target.placement.x, target.placement.y) == (p.x, p.y)
                and not target.state.burning
            ):
                target.state.burning = True
                ignited = True
        return ignited

    def advance_world_fires(self, states, minutes):
        original = self.state
        for state in states:
            active = self.active_craft
            try:
                self.state = state
                for target in list(self.world_objects()):
                    if target.state.burning:
                        self.damage_world_objects(
                            Position(target.placement.x, target.placement.y),
                            5 * minutes,
                            "fire",
                        )
            finally:
                self.state = original
                if state is not original:
                    self.active_craft = active

    def dismantle_ready(self, target):
        if not target or not target.dismantle or target.state.burning:
            return False
        if target.category == "doors" and (
            target.original.door.burning or target.original.brace
        ):
            return False
        if not all(self.has_work_tool([tag]) for tag in target.furniture_tools):
            return False
        tools = target.dismantle.tools
        return (
            not tools
            or self.has_work_tool(
                tools, held=target.dismantle.verb in {"harvest", "chop"}
            )
        ) and not (
            target.category == "traps"
            and target.definition.disarm
            and not target.original.disabled
        )

    def has_work_tool(self, requirements, *, held=False):
        return any(
            item.usable
            and (not held or item.equipped and item.definition.hands > 0)
            and (
                set(requirements).intersection(item.tags)
                or item.definition.weapon_damage
                and item.definition.damage_type in requirements
            )
            for item in self.state.hero.inventory
        )

    def disarm_trap(self, identifier):
        target = self.world_object(identifier)
        if self._world_ready(target) and (denial := self.light_denial()):
            return denial
        if (
            self.active_craft
            or not self._world_ready(target)
            or target.category != "traps"
            or not target.definition.disarm
            or target.original.disabled
        ):
            return self._craft_result(
                False, "Нужна соседняя видимая действующая ловушка и свет."
            )
        tools = target.dismantle.tools if target.dismantle else []
        if tools and not any(
            i.usable and set(tools).intersection(i.tags)
            for i in self.state.hero.inventory
        ):
            return self._craft_result(
                False, "Нет исправного инструмента: " + " / ".join(tools)
            )
        spec = target.definition.disarm
        check = self.dice.check(
            self.state.hero.stats.score(Ability[spec.ability.upper()]), spec.difficulty
        )
        if check.success:
            target.original.disabled = True
        else:
            from ..content.catalog import effect
            from ..domain.mechanics import mechanics

            self.actions.effects.apply_all(
                tuple(
                    effect(e.model_dump(mode="json"), set(mechanics.entries))
                    for e in target.definition.failure
                ),
                self.state.hero,
                self.dice,
            )
            target.original.triggered = target.original.discovered = True
        self._advance(1)
        return self._craft_result(
            True,
            f"Обезвреживание: {check.total}/{spec.difficulty}. "
            + ("Успех." if check.success else "Провал; ловушка сработала."),
            1,
        )

    def start_dismantle(self, identifier):
        target = self.world_work_target(identifier)
        if self._world_ready(target) and (
            denial := self.light_denial(2 if target.is_furniture else 1)
        ):
            return denial
        if self._world_ready(target) and target.dismantle:
            missing = [
                tag for tag in target.furniture_tools if not self.has_work_tool([tag])
            ]
            if missing:
                from ..domain.tags import TAG_LABELS

                return self._craft_result(
                    False,
                    "Для разбора нужны: "
                    + ", ".join(TAG_LABELS[tag] for tag in missing)
                    + ". Владение инструментом не требуется.",
                )
        if (
            self._world_ready(target)
            and target.dismantle
            and target.dismantle.verb in {"harvest", "chop"}
            and target.dismantle.tools
            and not self.has_work_tool(target.dismantle.tools, held=True)
        ):
            return self._craft_result(
                False, "Для сбора или рубки возьмите в руки подходящий инструмент."
            )
        if (
            self.active_craft
            or not self._world_ready(target)
            or not self.dismantle_ready(target)
        ):
            return self._craft_result(
                False,
                "Работа недоступна: нужны свет, соседний видимый объект, подходящий инструмент; ловушку сначала обезвредьте.",
            )
        state, spec = target.state, target.dismantle
        if not state.total:
            fast = spec.fast_tool and any(
                i.usable and spec.fast_tool in i.tags for i in self.state.hero.inventory
            )
            state.total = spec.fast_turns if fast else spec.turns
            state.fast_tool = spec.fast_tool if fast else None
        if state.fast_tool and not any(
            i.usable and state.fast_tool in i.tags for i in self.state.hero.inventory
        ):
            return self._craft_result(
                False, "Нет инструмента для выбранного способа разбора."
            )
        self.active_craft = "world:" + identifier
        return self._craft_result(
            True,
            WORK_NAMES[spec.verb] + ": →/Space — ход, Esc — пауза.",
        )

    def advance_world_work(self):
        target = self.world_work_target(self.active_craft.removeprefix("world:"))
        if self._world_ready(target) and (
            denial := self.light_denial(2 if target.is_furniture else 1)
        ):
            self.active_craft = None
            return denial
        if (
            not self._world_ready(target)
            or not self.dismantle_ready(target)
            or (
                target.state.fast_tool
                and not any(
                    i.usable and target.state.fast_tool in i.tags
                    for i in self.state.hero.inventory
                )
            )
        ):
            self.active_craft = None
            return self._craft_result(
                False,
                "Работа приостановлена: проверьте инструмент в руках и остальные условия.",
            )
        self._advance(1)
        if self.world_work_target(target.placement.id) is None:
            self.active_craft = None
            return self._craft_result(True, "Работа прервана: объект разрушен.", 1)
        target.state.progress += 1
        if target.state.progress >= target.state.total:
            loot = list(target.dismantle.loot)
            if self.has_work_tool(target.dismantle.bonus_tools):
                loot.extend(target.dismantle.bonus_loot)
            loot = self.furniture_hardware_loot(target, loot)
            self._remove_world_object(
                target, loot, harvested=target.dismantle.verb == "harvest"
            )
            self.active_craft = None
            return self._craft_result(
                True,
                WORK_RESULTS[target.dismantle.verb]
                + ": "
                + target.definition.name
                + ". Материалы на земле.",
                1,
            )
        if self.light_denial(2 if target.is_furniture else 1):
            self.active_craft = None
        return self._craft_result(
            True,
            f"{WORK_NAMES[target.dismantle.verb]}: {target.state.progress}/{target.state.total}.",
            1,
        )

    def _ground(self, items, p):
        for item in items:
            self.state.items.append(
                (ItemPlacement(item.instance_id, self.item_ref(item), p.x, p.y), item)
            )

    def _loot(self, rows):
        return [
            Equipment.create(self.catalog.equipment[r.item.removeprefix("base:")])
            for r in rows
            for _ in range(r.quantity)
        ]

    def _detach_world(self, target, *, level=None):
        level, identifier = level or self.state.level, target.placement.id
        if target.category == "doors":
            level.doors[:] = [d for d in level.doors if d.placement.id != identifier]
            level.door_loot.discard(identifier)
        level.object_states.pop(identifier, None)
        level.definition = level.definition.model_copy(
            update={
                target.category: [
                    p
                    for p in getattr(level.definition, target.category)
                    if p.id != identifier
                ],
                "transitions": [
                    p
                    for p in level.definition.transitions
                    if p.id != identifier + "_transition"
                ],
            }
        )
        container = next(
            (c for c in level.containers if c.placement.id == identifier), None
        )
        level.containers[:] = [c for c in level.containers if c is not container]
        if target.category in ("traps", "points_of_interest"):
            key = "traps" if target.category == "traps" else "points"
            getattr(level, key)[:] = [
                p for p in getattr(level, key) if p.placement.id != identifier
            ]
        return list(
            container.items
        ) if container else [], container.snapshot_spec() if container else None

    def _remove_world_object(self, target, loot, *, harvested=False):
        level = self.state.level
        # Destroying a young plant cancels its adult's recovery.
        level.regrowing_objects[:] = [
            pending
            for pending in level.regrowing_objects
            if pending.sprout_id != target.placement.id
        ]
        recovery = (
            target.definition.destruction.regrow_minutes
            if target.category != "traps" and target.definition.destruction
            else None
        )
        if recovery:
            sprout_ref = target.definition.destruction.regrow_as if harvested else None
            sprout = (
                Placement(
                    id="sprout_" + uuid4().hex,
                    ref=sprout_ref,
                    x=target.placement.x,
                    y=target.placement.y,
                )
                if sprout_ref
                else None
            )
            level.regrowing_objects.append(
                RegrowingObject(
                    category=target.category,
                    placement=target.placement,
                    ready_at=self.state.clock.elapsed_minutes + recovery,
                    sprout_id=sprout.id if sprout else None,
                    completed=target.completed,
                    transitions=[
                        p
                        for p in level.definition.transitions
                        if p.id == target.placement.id + "_transition"
                    ],
                )
            )
        contents, _ = self._detach_world(target)
        if recovery and sprout:
            definition = level.store.resolve("objects", sprout)
            self._attach_world_object(
                level,
                "objects",
                sprout,
                definition,
                ObjectState(
                    hp=definition.destruction.max_hp if definition.destruction else None
                ),
            )
        items = self._loot(loot)
        if harvested and getattr(target.definition, "poisonous", False):
            from ..content.compiler import compile_definition
            from ..content.schemas import EquipmentDocument

            raw = level.store.get("equipment", "base:poison_herb").model_dump(
                mode="json"
            )
            raw.update(
                name=target.definition.name,
                description="Собранный цветок.",
                glyph=target.definition.glyph,
                symbol=target.definition.symbol,
                foreground=target.definition.foreground,
                category="consumables",
                charges=1,
                properties=[
                    {"kind": "condition", "condition": "poisoned", "duration": 5}
                ],
            )
            definition = compile_definition(
                "equipment", "base:poison_herb", EquipmentDocument.model_validate(raw)
            )
            items = [Equipment.create(definition) for _ in items]
            for item in items:
                item.template = raw
        self._ground([*contents, *items], target.placement)
        if self.active_craft == "world:" + target.placement.id:
            self.active_craft = None

    def advance_regrowth(self, states):
        now = self.state.clock.elapsed_minutes
        for state in states:
            level = state.level
            if not level or not level.regrowing_objects:
                continue
            occupied = Counter(
                (p.x, p.y)
                for category in ("objects", "points_of_interest", "traps", "doors")
                for p in getattr(level.definition, category)
            )
            occupied.update(
                (m.position.x, m.position.y) for m in state.monsters if m.monster.hp > 0
            )
            if state is self.state:
                occupied[(state.position.x, state.position.y)] += 1
            for pending in list(level.regrowing_objects):
                p = pending.placement
                sprout = next(
                    (s for s in level.definition.objects if s.id == pending.sprout_id),
                    None,
                )
                if (
                    now < pending.ready_at
                    or occupied[p.x, p.y] > (1 if sprout else 0)
                    or not state.walkable(Position(p.x, p.y))
                ):
                    continue
                if sprout:
                    self._detach_world(
                        SimpleNamespace(category="objects", placement=sprout),
                        level=level,
                    )
                    occupied[p.x, p.y] -= 1
                definition = level.store.resolve(pending.category, p)
                self._attach_world_object(
                    level,
                    pending.category,
                    p,
                    definition,
                    ObjectState(hp=definition.destruction.max_hp),
                    completed=pending.completed,
                )
                if pending.transitions:
                    level.definition = level.definition.model_copy(
                        update={
                            "transitions": [
                                *level.definition.transitions,
                                *pending.transitions,
                            ]
                        }
                    )
                level.regrowing_objects.remove(pending)
                occupied[p.x, p.y] += 1

    def _world_destination(self, p, source=None):
        level, hero = self.state.level, self.state.position
        if (
            not level
            or p == hero
            or (
                source is not None
                and any(
                    o.placement.id == source
                    and (o.placement.x, o.placement.y) == (p.x, p.y)
                    for o in self.world_objects()
                )
            )
            or not max(abs(p.x - hero.x), abs(p.y - hero.y)) == 1
            or not self.state.walkable(p)
        ):
            return False
        if (
            not level.definition.tiles[p.y][p.x]
            or not self.lighting.at(p)
            or not self.lighting.level_at(p)
        ):
            return False
        if (
            p.x != hero.x
            and p.y != hero.y
            and not (
                self.state.walkable(Position(hero.x, p.y))
                and self.state.walkable(Position(p.x, hero.y))
            )
        ):
            return False
        occupied = [
            e
            for key in (
                "objects",
                "points_of_interest",
                "traps",
                "doors",
                "transitions",
            )
            for e in getattr(level.definition, key)
        ]
        return (
            not any(e.x == p.x and e.y == p.y and e.id != source for e in occupied)
            and not self.state.item_index.at(p.x, p.y)
            and not any(m.monster.hp > 0 for m in self.state.actor_index.at(p.x, p.y))
        )

    def move_furniture(self, identifier, p):
        target = self.world_object(identifier)
        if self._world_ready(target) and (denial := self.light_denial()):
            return denial
        if (
            self.active_craft
            or not self._world_ready(target)
            or target.category == "traps"
            or target.state.burning
            or not target.definition.movable
            or not self._world_destination(p, identifier)
        ):
            return self._craft_result(
                False,
                "Мебель нельзя передвинуть: нужна свободная доступная соседняя клетка пола.",
            )
        level = self.state.level
        moved = target.placement.model_copy(update={"x": p.x, "y": p.y})
        level.definition = level.definition.model_copy(
            update={
                target.category: [
                    moved if e.id == identifier else e
                    for e in getattr(level.definition, target.category)
                ]
            }
        )
        for key in ("points", "containers"):
            entries = getattr(level, key)
            for entry in entries:
                if entry.placement.id == identifier:
                    entry.placement = moved
            entries[:] = list(entries)
        self._advance(1)
        return self._craft_result(
            True, "Передвинуто: " + target.definition.name + ".", 1
        )

    def lift_furniture(self, identifier):
        target = self.world_object(identifier)
        if self._world_ready(target) and (denial := self.light_denial()):
            return denial
        if (
            self.active_craft
            or not self._world_ready(target)
            or target.category == "traps"
            or target.state.burning
            or not target.definition.movable
        ):
            return self._craft_result(False, "Эту мебель нельзя поднять.")
        container = next(
            (c for c in self.state.level.containers if c.placement.id == identifier),
            None,
        )
        weight = target.definition.weight + (container.weight if container else 0)
        if (
            self.state.hero.carried_weight + weight
            > self.state.hero.max_carry_weight + 1e-9
        ):
            return self._craft_result(
                False, "Недостаточно переносимого веса для мебели и её содержимого."
            )
        target.state.lit = False
        contents, spec = self._detach_world(target)
        item = Equipment.create(self.catalog.equipment["packed_furniture"])
        item.furniture = FurnitureCargo(
            target.category,
            target.placement,
            target.definition,
            target.state,
            contents,
            bool(target.original and target.original.completed),
            spec,
        )
        self.state.hero.inventory.append(item)
        self._advance(1)
        return self._craft_result(True, "Поднято: " + item.name + ".", 1)

    def place_furniture(self, item, p):
        if denial := self.light_denial():
            return denial
        if (
            self.active_craft
            or self.lockpick_attempt
            or self.state.hero.hp <= 0
            or item is None
            or item not in self.state.hero.inventory
            or not item.furniture
            or not self._world_destination(p)
        ):
            return self._craft_result(
                False, "Нужна свободная доступная соседняя клетка пола."
            )
        from ..content.placements import property_difference

        cargo, level = item.furniture, self.state.level
        used = {
            e.id
            for key in (
                "objects",
                "points_of_interest",
                "traps",
                "doors",
                "transitions",
                "lights",
                "equipment",
                "monsters",
                "decorations",
            )
            for e in getattr(level.definition, key)
        }
        identifier = cargo.placement.id
        if identifier in used or any(
            r.placement.id == identifier for r in level.regrowing_objects
        ):
            identifier = "placed_" + uuid4().hex
        base = level.store.get(cargo.category, cargo.placement.ref)
        placement = Placement(
            id=identifier,
            ref=cargo.placement.ref,
            x=p.x,
            y=p.y,
            overrides=property_difference(
                base.model_dump(mode="json"), cargo.definition.model_dump(mode="json")
            ),
            challenge_overrides=cargo.placement.challenge_overrides,
        )
        self._attach_world_object(
            level,
            cargo.category,
            placement,
            cargo.definition,
            cargo.state,
            items=cargo.items,
            completed=cargo.completed,
            container_spec=cargo.container_spec,
        )
        self.state.hero.inventory.remove(item)
        self._advance(1)
        return self._craft_result(True, "Поставлено: " + cargo.definition.name + ".", 1)

    def _attach_world_object(
        self,
        level,
        category,
        placement,
        definition,
        state,
        *,
        items=(),
        completed=False,
        container_spec=None,
    ):
        from ..world.storage import StorageInstance
        from ..world.level import PointInstance
        from ..domain.challenges import TextChallenge
        from ..content.compiler import compile_definition
        from ..content.placements import resolve_challenge

        if getattr(getattr(definition, "brush", None), "door", None):
            from ..world.doors import DoorInstance
            from ..domain.doors import Door

            category = "doors"
            level.doors.append(
                DoorInstance(
                    placement, definition, Door.from_spec(definition.brush.door)
                )
            )
        level.definition = level.definition.model_copy(
            update={category: [*getattr(level.definition, category), placement]}
        )
        level.object_states[placement.id] = (
            ObjectState() if category == "doors" else state
        )
        if category == "points_of_interest":
            doc = resolve_challenge(level.store.documents, definition, placement)
            challenge = (
                TextChallenge(
                    compile_definition("challenges", definition.challenge, doc),
                    self.actions.effects,
                )
                if doc
                else None
            )
            if challenge:
                challenge.completed = completed
            level.points.append(PointInstance(placement, definition, challenge))
        if definition.storage:
            level.containers.append(
                StorageInstance(
                    placement,
                    definition,
                    container_spec or definition.storage,
                    items=list(items),
                )
            )

    def furniture_hardware_loot(self, target, loot, *, destroyed=False):
        """Fittings survive careful dismantling; destruction recovers them half the time."""
        if (
            not target.is_furniture
            or "wooden" not in target.definition.tags
            or "furniture_hardware" not in self.catalog.equipment
        ):
            return loot
        from ..content.schemas import RecipeOutput

        ref = "base:furniture_hardware"
        quantity = next(
            (
                entry.quantity
                for entry in (target.dismantle.loot if target.dismantle else [])
                if entry.item == ref
            ),
            1,
        )
        if not destroyed:
            return (
                loot
                if any(entry.item == ref for entry in loot)
                else [*loot, RecipeOutput(item=ref, quantity=quantity)]
            )
        # Fittings are a separate find, not the half-sized wood/cloth salvage budget.
        result = [entry for entry in loot if entry.item != ref]
        if self.dice.roll(1, 100)[0] <= 50:
            result.append(RecipeOutput(item=ref, quantity=quantity))
        return result

    def damage_world_objects(self, p, amount, kind):
        actual = 0
        for target in self.world_objects():
            if (
                target.category == "traps"
                or (target.placement.x, target.placement.y) != (p.x, p.y)
                or not target.definition.destruction
            ):
                continue
            spec = target.definition.destruction
            profile = DamageProfile(
                **{
                    k: frozenset(getattr(spec.damage_profile, k))
                    for k in ("resistances", "vulnerabilities", "immunities")
                }
            )
            damage = min(target.state.hp, profile.resolve(amount, kind).resolved_amount)
            target.state.hp -= damage
            actual += damage
            if target.state.hp == 0:
                remains = spec.remains
                if target.is_furniture and target.dismantle:
                    # Broken furniture salvages at most half of each dismantled material.
                    budget = {}
                    for loot in target.dismantle.loot:
                        budget[loot.item] = budget.get(loot.item, 0) + loot.quantity
                    budget = {ref: quantity // 2 for ref, quantity in budget.items()}
                    remains = []
                    for loot in spec.remains:
                        quantity = min(loot.quantity, budget.get(loot.item, 0))
                        if quantity:
                            remains.append(
                                loot.model_copy(update={"quantity": quantity})
                            )
                            budget[loot.item] -= quantity
                self._remove_world_object(
                    target,
                    self.furniture_hardware_loot(target, remains, destroyed=True),
                )
        return actual

    def replace_surface(self, p, ref):
        """Apply a finished construction result; callers own work and material costs."""
        from ..content.schemas import MapDocument
        from ..world.maps import DungeonMap

        if not self.state.level or not self._inside(p):
            raise ValueError("Недопустимая клетка поверхности")
        level = self.state.level
        tile = level.store.get("tiles", ref)
        if (
            not tile.walkable
            or tile.blocks_sight
            or any(
                (
                    tile.brush.door,
                    tile.brush.item,
                    tile.brush.trap,
                    tile.brush.interaction,
                    tile.brush.transition,
                    tile.brush.light,
                )
            )
        ):
            raise ValueError(
                "Основанием должна быть проходимая поверхность без объектов"
            )
        raw = level.definition.model_dump(mode="json")
        raw["tiles"][p.y][p.x] = ref
        raw["tile_mirrors"][p.y][p.x] = False
        raw["walkability"][p.y][p.x] = tile.walkable
        raw["blocks_sight"][p.y][p.x] = tile.blocks_sight
        level.definition = MapDocument.model_validate(raw)
        masks = [list(row) for row in level.definition.walkability]
        for door in level.doors:
            masks[door.placement.y][door.placement.x] = True
        self.state.dungeon = DungeonMap(
            tuple("".join("." if c else "#" for c in row) for row in masks)
        )

    def repair_world_object(self, identifier, amount):
        # State operation for repair recipes; not exposed as a free player action.
        target = self.world_object(identifier)
        if (
            target is None
            or target.state.hp is None
            or type(amount) is not int
            or amount < 0
        ):
            raise ValueError("Недопустимый ремонт объекта")
        before = target.state.hp
        target.state.hp = min(target.definition.destruction.max_hp, before + amount)
        return target.state.hp - before

    def collect_door_remains(self):
        for state in self.levels.values() if self.levels else (self.state,):
            level = state.level
            if not level:
                continue
            for door in level.doors:
                if not door.door.destroyed or door.placement.id in level.door_loot:
                    continue
                level.door_loot.add(door.placement.id)
                level.object_states.pop(door.placement.id, None)
                if door.brace:
                    item = door.brace
                    door.brace = None
                    state.items.append(
                        (
                            ItemPlacement(
                                item.instance_id,
                                self.item_ref(item),
                                door.placement.x,
                                door.placement.y,
                            ),
                            item,
                        )
                    )
                remains = getattr(door.definition, "door_remains", [])
                if remains:
                    for item in self._loot(remains):
                        state.items.append(
                            (
                                ItemPlacement(
                                    item.instance_id,
                                    self.item_ref(item),
                                    door.placement.x,
                                    door.placement.y,
                                ),
                                item,
                            )
                        )

    def discover_traps(self):
        if denial := self.light_denial():
            return denial
        if (
            self.active_craft
            or self.lockpick_attempt
            or self.state.hero.hp <= 0
            or not self.state.level
        ):
            return self._craft_result(False, "Сейчас поиск невозможен.")
        found = 0
        for trap in self.state.level.traps:
            p = Position(trap.placement.x, trap.placement.y)
            if (
                max(abs(p.x - self.state.position.x), abs(p.y - self.state.position.y))
                <= 1
                and self.lighting.at(p)
                and self.lighting.level_at(p)
                and not trap.discovered
            ):
                check = self.dice.check(
                    self.state.hero.stats.score(Ability.WISDOM),
                    trap.definition.difficulty,
                )
                if check.success:
                    trap.discovered = True
                    found += 1
        self._advance(1)
        return self._craft_result(
            True, f"Осмотр окрестностей завершён. Найдено ловушек: {found}.", 1
        )

    def interact_world(self, identifier, choice):
        if choice in ("take_light", "mount_light"):
            return self.fixture_action(identifier, choice)
        if choice == "ignite_object":
            target = self.world_object(identifier)
            if target is None:
                return self._craft_result(False, "Объект недоступен.")
            source = next((i for i in self.state.hero.inventory if i.can_ignite), None)
            return self.ignite_cell(
                source, Position(target.placement.x, target.placement.y)
            )
        if choice == "disarm":
            return self.disarm_trap(identifier)
        if choice == "dismantle":
            return self.start_dismantle(identifier)
        if choice == "lift":
            return self.lift_furniture(identifier)
        target = self.world_object(identifier)
        if not self._world_ready(target) or self.active_craft:
            return self._craft_result(False, "Объект недоступен.")
        if choice != "break_object" and (denial := self.light_denial()):
            return denial
        if choice == "break_object" and not getattr(
            target.definition, "attackable", True
        ):
            return self._craft_result(
                False,
                "Этот объект нельзя атаковать. Используйте доступные взаимодействия.",
            )
        if (
            choice == "break_object"
            and target.category != "traps"
            and target.definition.destruction
        ):
            weapon = next(
                (
                    i
                    for i in self.state.hero.inventory
                    if i.equipped and i.usable and i.definition.weapon_damage
                ),
                None,
            )
            amount = max(
                1,
                (weapon.definition.weapon_damage.roll(self.dice) if weapon else 1)
                + self.state.hero.stats.modifier(Ability.STRENGTH),
            )
            applied = self.damage_cell(
                Position(target.placement.x, target.placement.y),
                amount,
                weapon.damage_type if weapon else "bludgeoning",
            )
            if weapon:
                weapon.wear(1)
            self._advance(1)
            return self._craft_result(True, f"Урон окружению: {applied}.", 1)
        return self._craft_result(False, "Выберите соседнюю клетку для мебели.")
