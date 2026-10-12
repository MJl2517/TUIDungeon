"""Liquid handling, campfires and target operations reuse the crafting turn loop."""

from uuid import uuid4
from ..content.schemas import Placement
from ..domain.liquids import LIQUID_NAMES, WATER_KINDS, PORTION_WEIGHT, portion_text
from ..world.maps import Position
from ..world.objects import ObjectState


class WorkshopCommands:
    def owned_vessel(self, identifier):
        return next(
            (
                i
                for i in self.state.hero.inventory
                if i.instance_id == identifier
                and i.definition.vessel
                and i.usable
                and not i.equipped
            ),
            None,
        )

    def vessel_choices(self, item):
        if not item or not item.definition.vessel or not item.usable or item.equipped:
            return []
        choices = []
        if item.liquid_portions < item.definition.vessel.capacity_portions:
            for obj in self.nearby_world_objects():
                source = getattr(obj.definition, "water_source", None)
                if source and item.liquid_kind in (None, source.kind):
                    choices.append(
                        dict(
                            label="Набрать: " + obj.definition.name,
                            action="fill",
                            target=obj.placement.id,
                        )
                    )
        if item.liquid_portions:
            choices.append(dict(label="Вылить всё", action="empty"))
            for other in self.state.hero.inventory:
                if other is item or not other.usable or other.equipped:
                    continue
                if (
                    other.definition.vessel
                    and other.liquid_kind in (None, item.liquid_kind)
                    and other.liquid_portions
                    < other.definition.vessel.capacity_portions
                ):
                    choices.append(
                        dict(
                            label="Перелить: " + other.name,
                            action="pour",
                            target=other.instance_id,
                        )
                    )
                if (
                    other.contaminated
                    and item.liquid_kind in ("clean_water", "holy_water")
                    and item.liquid_portions >= 1
                ):
                    choices.append(
                        dict(
                            label="Промыть: " + other.name,
                            action="wash",
                            target=other.instance_id,
                        )
                    )
            choices.append(dict(label="Вылить на клетку", action="splash"))
        return choices

    def water_action(
        self, identifier, action, *, target=None, position=None, portions=None
    ):
        hero = self.state.hero
        item = self.owned_vessel(identifier)
        if self.active_craft or self.lockpick_attempt or hero.hp <= 0 or item is None:
            return self._craft_result(
                False,
                "Нужен доступный сосуд в инвентаре; сначала приостановите работу.",
            )
        if portions is not None and (type(portions) is not int or portions <= 0):
            return self._craft_result(
                False, "Количество порций должно быть целым положительным числом."
            )
        vessel = item.definition.vessel
        message = ""
        if action == "fill":
            source = next(
                (
                    o
                    for o in self.nearby_world_objects()
                    if o.placement.id == target
                    and getattr(o.definition, "water_source", None)
                ),
                None,
            )
            if not source:
                return self._craft_result(
                    False, "Нужен соседний видимый источник жидкости."
                )
            kind = source.definition.water_source.kind
            if item.liquid_kind and (item.liquid_kind != kind or item.liquid_effects):
                return self._craft_result(False, "Разные жидкости нельзя смешивать.")
            amount = min(
                portions or vessel.capacity_portions,
                vessel.capacity_portions - item.liquid_portions,
            )
            remaining = source.state.water_portions
            if remaining is None:
                remaining = source.definition.water_source.portions
            if remaining is not None:
                amount = min(amount, remaining)
            if amount <= 0:
                return self._craft_result(False, "Сосуд полон.")
            if (
                hero.carried_weight + amount * PORTION_WEIGHT
                > hero.max_carry_weight + 1e-9
            ):
                return self._craft_result(False, "Жидкость превысит переносимый вес.")
            item.liquid_kind = kind
            item.liquid_portions += amount
            if remaining is not None:
                source.state.water_portions = remaining - amount
                if source.state.water_portions == 0:
                    self._remove_world_object(source, [])
            message = f"Набрано: {LIQUID_NAMES[kind]}, {portion_text(amount)}."
        elif action == "pour":
            other = self.owned_vessel(target)
            if other is None or other is item or not item.liquid_portions:
                return self._craft_result(False, "Выберите другой доступный сосуд.")
            if other.liquid_kind and (
                other.liquid_kind != item.liquid_kind
                or other.liquid_effects != item.liquid_effects
            ):
                return self._craft_result(False, "Разные жидкости нельзя смешивать.")
            amount = min(
                portions or item.liquid_portions,
                item.liquid_portions,
                other.definition.vessel.capacity_portions - other.liquid_portions,
            )
            if amount <= 0:
                return self._craft_result(False, "В принимающем сосуде нет места.")
            other.liquid_kind = item.liquid_kind
            other.liquid_effects = item.liquid_effects
            other.liquid_portions += amount
            self._spend_liquid(item, amount)
            message = f"Перелито {portion_text(amount)}."
        elif action == "empty":
            if not item.liquid_portions:
                return self._craft_result(False, "Сосуд уже пуст.")
            amount = min(portions or item.liquid_portions, item.liquid_portions)
            self._spend_liquid(item, amount)
            message = f"Вылито {portion_text(amount)}; тара сохранена."
        elif action == "drink":
            return self.use_item(item)
        elif action == "wash":
            other = next(
                (
                    i
                    for i in hero.inventory
                    if i.instance_id == target
                    and i.usable
                    and not i.equipped
                    and i.contaminated
                ),
                None,
            )
            if (
                other is None
                or item.liquid_kind not in ("clean_water", "holy_water")
                or item.liquid_portions < 1
            ):
                return self._craft_result(
                    False, "Нужны загрязнённый предмет и 1 порция чистой воды."
                )
            other.contaminated = False
            self._spend_liquid(item, 1)
            message = "Предмет очищен."
        elif action == "splash":
            if denial := self.light_denial():
                return denial
            if (
                item.liquid_portions < 1
                or position is None
                or not self._inside(position)
            ):
                return self._craft_result(
                    False, "Нужны 1 порция жидкости и соседняя клетка."
                )
            p = self.state.position
            if (
                max(abs(p.x - position.x), abs(p.y - position.y)) > 1
                or not self.lighting.at(position)
                or not self._clear_throw_path(position, allow_target_door=True)
            ):
                return self._craft_result(False, "Клетка должна быть рядом и видна.")
            if item.liquid_kind in WATER_KINDS:
                self._water_cell(position)
            message = f"Вылито на клетку: {LIQUID_NAMES[item.liquid_kind]}, 1 порция; тара сохранена."
            self._spend_liquid(item, 1)
        else:
            return self._craft_result(False, "Неизвестное действие с жидкостью.")
        self._advance(1)
        return self._craft_result(True, message, 1)

    @staticmethod
    def _spend_liquid(item, amount):
        from ..domain.liquids import spend_liquid

        spend_liquid(item, amount)

    def _water_cell(self, p):
        changed = False
        for obj in self.world_objects():
            if (obj.placement.x, obj.placement.y) == (p.x, p.y) and obj.state.burning:
                obj.state.burning = False
                changed = True
            if (
                (obj.placement.x, obj.placement.y) == (p.x, p.y)
                and getattr(obj.definition, "campfire", None)
                and obj.state.lit
            ):
                obj.state.lit = False
                changed = True
        if self.state.level:
            for d in self.state.level.index("doors").at(p.x, p.y):
                if d.door.burning:
                    d.door.burning = False
                    changed = True
            ref = self.state.level.definition.tiles[p.y][p.x]
            if ref and "soil" in self.state.level.store.get("tiles", ref).tags:
                mud = next(
                    (
                        r
                        for (c, r), d in self.state.level.store.documents.items()
                        if c == "tiles"
                        and "mud" in d.tags
                        and d.walkable
                        and not d.blocks_sight
                        and not any(
                            (
                                d.brush.door,
                                d.brush.item,
                                d.brush.trap,
                                d.brush.interaction,
                                d.brush.transition,
                                d.brush.light,
                            )
                        )
                    ),
                    None,
                )
                if mud:
                    self.replace_surface(p, mud)
                    changed = True
        return changed

    def fill_at_source(self, identifier):
        source = self.world_object(identifier)
        kind = (
            source.definition.water_source.kind
            if source and getattr(source.definition, "water_source", None)
            else None
        )
        vessel = next(
            (
                i
                for i in self.state.hero.inventory
                if i.definition.vessel
                and i.usable
                and not i.equipped
                and i.liquid_kind in (None, kind)
                and i.liquid_portions < i.definition.vessel.capacity_portions
            ),
            None,
        )
        return self.water_action(
            vessel.instance_id if vessel else None, "fill", target=identifier
        )

    def campfire_action(self, identifier, action):
        obj = self.world_object(identifier)
        if self._world_ready(obj) and (denial := self.light_denial()):
            return denial
        if (
            self.active_craft
            or self.lockpick_attempt
            or not self._world_ready(obj)
            or not getattr(obj.definition, "campfire", None)
        ):
            return self._craft_result(
                False, "Нужен соседний видимый костёр; сначала приостановите работу."
            )
        state, spec = obj.state, obj.definition.campfire
        if action == "extinguish":
            if not state.lit:
                return self._craft_result(False, "Костёр уже потушен.")
            state.lit = False
            message = "Костёр потушен; оставшееся топливо сохранено."
        elif action == "ignite":
            if (
                state.lit
                or not state.fuel_minutes
                or not any(i.can_ignite for i in self.state.hero.inventory)
            ):
                return self._craft_result(
                    False, "Нужны топливо и действующий источник зажигания."
                )
            state.lit = True
            message = "Костёр зажжён."
        elif action == "refuel":
            fuel = next(
                (
                    i
                    for i in self.state.hero.inventory
                    if i.usable
                    and not i.equipped
                    and not i.definition.weapon_damage
                    and i.category == "materials"
                    and spec.fuel_tag in i.tags
                ),
                None,
            )
            if not fuel or state.fuel_minutes + spec.fuel_minutes > 100000:
                return self._craft_result(
                    False, "Нет подходящего топлива или костёр переполнен."
                )
            self.state.hero.inventory.remove(fuel)
            state.fuel_minutes += spec.fuel_minutes
            message = f"Добавлено топлива: {spec.fuel_minutes} мин."
        else:
            return self._craft_result(False, "Неизвестное действие с костром.")
        self._advance(1)
        return self._craft_result(True, message, 1)

    def campfire_lights(self):
        return tuple(
            (
                Position(o.placement.x, o.placement.y),
                o.definition.campfire.radius,
                o.definition.campfire.bright_radius,
            )
            for o in self.world_objects()
            if getattr(o.definition, "campfire", None)
            and o.state.lit
            and o.state.fuel_minutes
        ) + tuple(
            (Position(o.placement.x, o.placement.y), 3, 1)
            for o in self.world_objects()
            if o.state.burning
        )

    def advance_campfires(self, states, minutes):
        for state in states:
            if not state.level:
                continue
            for obj in state.level.object_states.values():
                if obj.lit:
                    obj.fuel_minutes = max(0, obj.fuel_minutes - minutes)
                    if not obj.fuel_minutes:
                        obj.lit = False

    def craft_targets(self, operation):
        if operation.kind == "repair_object":
            return [
                dict(
                    id=o.placement.id,
                    name=o.definition.name,
                    description=f"Прочность: {o.state.hp}/{o.definition.destruction.max_hp}",
                )
                for o in self.nearby_world_objects()
                if getattr(o.definition, "destruction", None)
                and o.state.hp < o.definition.destruction.max_hp
                and (
                    not operation.target_tags
                    or set(operation.target_tags).intersection(o.definition.tags)
                )
                and not o.state.total
                and not o.state.burning
            ]
        from ..domain.crafting import operation_target_matches

        return [
            dict(
                id=i.instance_id,
                name=i.name,
                description=f"Масса: {i.weight:g} кг"
                + (
                    f" · прочность {i.durability}/{i.definition.durability}"
                    if i.durability is not None
                    else ""
                ),
            )
            for i in self.state.hero.inventory
            if operation_target_matches(operation, i)
            and not i.equipped
            and not i.lit
            and not i.glow
        ]

    def craft_destinations(self):
        p = self.state.position
        return [
            dict(x=p.x + dx, y=p.y + dy)
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if (dx or dy) and self._world_destination(Position(p.x + dx, p.y + dy))
        ]

    def assess_operation(self, assessment, *, work=None, target=None, destination=None):
        op = assessment.recipe.operation
        if not op:
            return
        if op.ignition:
            assessment.require(
                "Наличие: источник зажигания",
                any(i.can_ignite for i in self.state.hero.inventory),
                "Нужен действующий источник зажигания.",
            )
        if op.kind in ("place_object", "place_trap"):
            assessment.destinations = self.craft_destinations()
            chosen = work.destination if work else destination
            if chosen is None and assessment.destinations:
                chosen = (
                    assessment.destinations[0]["x"],
                    assessment.destinations[0]["y"],
                )
            assessment.destination = chosen
            assessment.require(
                "Свободная доступная соседняя клетка пола",
                chosen and self._world_destination(Position(*chosen)),
                "Нужна свободная доступная соседняя клетка пола.",
            )
            if not self.state.level or (work and work.map_ref != self.state.level.ref):
                assessment.reasons.append("Работа привязана к исходной локации.")
            return
        assessment.targets = self.craft_targets(op)
        if work and work.target:
            from ..domain.crafting import operation_target_matches

            assessment.target = work.target
            assessment.require(
                "Подходящий предмет в работе",
                operation_target_matches(op, work.target),
                "Предмет больше не подходит для работы.",
            )
        else:
            identifier = (work.target_object or work.target_id) if work else target
            if identifier is None and assessment.targets:
                identifier = assessment.targets[0]["id"]
            found = next((t for t in assessment.targets if t["id"] == identifier), None)
            assessment.require(
                "Наличие: подходящий предмет или объект для работы",
                found,
                "Нет подходящего предмета или объекта для работы.",
            )
            if found and op.kind == "repair_object":
                assessment.target_object = identifier
            elif found:
                assessment.target = next(
                    i for i in self.state.hero.inventory if i.instance_id == identifier
                )
        if (
            op.kind == "repair_object"
            and work
            and (not self.state.level or self.state.level.ref != work.map_ref)
        ):
            assessment.reasons.append("Ремонт привязан к исходной локации.")

    def release_repair_target(self, work):
        if (
            work.target
            and work.recipe.operation
            and work.recipe.operation.kind
            in ("repair_item", "coat_weapon", "appraise_item")
        ):
            self.state.hero.inventory.append(work.target)
            work.target = None

    def finish_operation(self, work):
        op = work.recipe.operation
        if not op:
            return []
        if op.kind == "liquid":
            if op.liquid_result:
                work.target.liquid_kind = op.liquid_result
                work.target.liquid_effects = ()
            else:
                self._spend_liquid(work.target, op.portions)
        elif op.kind == "repair_item":
            work.target.repair(op.repair_amount)
        elif op.kind == "repair_object":
            self.repair_world_object(work.target_object, op.repair_amount)
        elif op.kind == "appraise_item":
            work.target.appraised = True
        elif op.kind == "coat_weapon":
            work.target.poison_damage = op.poison_damage
        elif op.kind == "place_trap":
            from ..world.level import TrapInstance

            level = self.state.level
            x, y = work.destination
            placement = Placement(
                id="built_trap_" + uuid4().hex, ref=op.place_trap, x=x, y=y
            )
            level.definition = level.definition.model_copy(
                update={"traps": [*level.definition.traps, placement]}
            )
            definition = level.store.resolve("traps", placement)
            level.traps.append(TrapInstance(placement, definition, discovered=True))
        elif op.kind == "place_object":
            level = self.state.level
            x, y = work.destination
            placement = Placement(
                id="built_" + uuid4().hex, ref=op.place_object, x=x, y=y
            )
            # One ordinary placement on the floor; source pack documents stay immutable.
            level.definition = level.definition.model_copy(
                update={"objects": [*level.definition.objects, placement]}
            )
            definition = level.store.resolve("objects", placement)
            state = ObjectState(
                hp=definition.destruction.max_hp if definition.destruction else None
            )
            if definition.campfire and op.ignition:
                state.fuel_minutes = definition.campfire.fuel_minutes
                state.lit = True
            level.object_states[placement.id] = state
        return [work.target] if work.target else []
