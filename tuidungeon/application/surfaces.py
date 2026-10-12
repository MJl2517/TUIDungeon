"""Timed cell coatings and fire commands, independent of input and rendering."""

from ..world.maps import Position
from ..domain.damage import validate_damage


class SurfaceCommands:
    def _inside(self, target):
        return (
            isinstance(target, Position)
            and 0 <= target.x < self.state.dungeon.width
            and 0 <= target.y < self.state.dungeon.height
        )

    def _consume_portion(self, item):
        if item.charges is not None:
            item.charges -= 1
        if item.charges is None or item.charges == 0:
            item.equipped = item.lit = False
            self.state.hero.inventory.remove(item)

    def throw_oil_at(self, item, target):
        from .engine import ActionResult

        state = self.state
        if (
            self.lockpick_attempt
            or state.hero.hp <= 0
            or not any(i is item for i in state.hero.inventory)
            or "lamp_oil" not in item.tags
            or not self._inside(target)
        ):
            return ActionResult(False, 0, "Нужны масло в инвентаре и клетка на карте.")
        distance = abs(target.x - state.position.x) + abs(target.y - state.position.y)
        if distance > self.throw_range or not self._clear_throw_path(
            target, allow_target_door=True
        ):
            return ActionResult(
                False, 0, f"Бросок закрыт преградой или дальше {self.throw_range} кл."
            )
        self._consume_portion(item)
        # The throwing action advances a turn; five *subsequent* turns remain.
        state.oil[target] = 6
        doors = state.level.index("doors").at(target.x, target.y) if state.level else ()
        burst = any(d.door.burning for d in doors)
        if burst:
            self.damage_cell(target, 0, "fire")
        expired = self._advance(1)
        message = (
            "Масло вспыхнуло: дополнительно 5 урона огнём."
            if burst
            else "Клетка покрыта маслом на 5 ходов. Поджог: дополнительно 5 урона огнём."
        )
        return ActionResult(
            True, 1, message + (" " + " ".join(expired) if expired else "")
        )

    def damage_cell(
        self,
        target,
        amount,
        kind="physical",
        *,
        source_tags=(),
        ignite=False,
        outcomes=None,
    ):
        """Apply damage without spending time; fire consumes oil once per cell.

        Commands own their time cost. Future attacks can reuse this entry point
        without duplicating oil rules or accidentally advancing two turns.
        """
        if not self._inside(target) or amount < 0:
            raise ValueError("Недопустимая клетка или урон")
        door_kind = kind
        if kind == "pickaxe":
            source_tags = {*source_tags, "pickaxe"}
        kind = "bludgeoning" if kind in ("physical", "pickaxe") else kind
        validate_damage(amount, kind, allow_untyped=False)
        state = self.state
        bonus = 5 if kind == "fire" and target in state.oil else 0
        if bonus:
            del state.oil[target]
            self.events.append(
                dict(
                    kind="oil",
                    x=target.x,
                    y=target.y,
                    amount=5,
                    message="Масло вспыхнуло: +5 урона огнём, покрытие исчезло.",
                )
            )
        damage = amount + bonus
        actual = self.damage_world_objects(target, damage, kind)
        if kind == "fire" and (ignite or bonus):
            self.ignite_world_objects(target)
        if state.level:
            for instance in state.level.index("doors").at(target.x, target.y):
                actual += instance.door.take_damage(
                    damage, door_kind, source_tags=source_tags
                )
                if kind == "fire" and (ignite or bonus):
                    instance.door.ignite()
        self.collect_door_remains()
        for p in state.actor_index.at(target.x, target.y):
            applied = self._damage_creature(p.monster, damage, kind, outcomes)
            actual += applied
            p.monster.check_concentration(applied, self.dice)
        if target == state.position:
            applied = self._damage_creature(state.hero, damage, kind, outcomes)
            actual += applied
            check = state.hero.check_concentration(applied, self.dice)
            if check:
                self.events.append(
                    dict(
                        kind="concentration",
                        roll=check.roll,
                        total=check.total,
                        difficulty=check.difficulty,
                        success=check.success,
                        message="Проверка концентрации.",
                    )
                )
        for _, item in state.item_index.at(target.x, target.y):
            before = item.durability
            item.wear(damage)
            if before is not None:
                actual += before - item.durability
        return actual

    @staticmethod
    def _damage_creature(creature, damage, kind, outcomes):
        from ..domain.effects import EffectOutcome

        result = creature.receive_damage(damage, kind)
        if outcomes is not None:
            outcomes.append(
                EffectOutcome(
                    "damage",
                    result.applied_amount,
                    target=creature,
                    damage_type=kind,
                    raw_amount=result.raw_amount,
                    resolved_amount=result.resolved_amount,
                    response=result.response,
                )
            )
        return result.applied_amount

    def ignite_cell(self, item, target):
        from .engine import ActionResult

        state = self.state
        if (
            self.lockpick_attempt
            or self.active_craft
            or state.hero.hp <= 0
            or item is None
            or not any(i is item for i in state.hero.inventory)
            or not item.can_ignite
        ):
            return ActionResult(
                False,
                0,
                "Нужен исправный предмет с тегом «поджог»: кремень и кресало, горящий факел в руке или огненное оружие в руке.",
            )
        if (
            not self._inside(target)
            or max(abs(target.x - state.position.x), abs(target.y - state.position.y))
            != 1
        ):
            return ActionResult(
                False, 0, "Поджечь можно только одну из 8 соседних клеток."
            )
        if not self._clear_throw_path(target, allow_target_door=True):
            return ActionResult(False, 0, "Поджог преграждает стена.")
        camp = next(
            (
                o
                for o in self.world_objects()
                if (o.placement.x, o.placement.y) == (target.x, target.y)
                and getattr(o.definition, "campfire", None)
            ),
            None,
        )
        fire_lit = bool(camp and not camp.state.lit and camp.state.fuel_minutes)
        if fire_lit:
            camp.state.lit = True
        doors = state.level.index("doors").at(target.x, target.y) if state.level else ()
        ignited = any(d.door.ignite() for d in doors)
        object_lit = self.ignite_world_objects(target)
        oiled = target in state.oil
        if not ignited and not oiled and not fire_lit and not object_lit:
            return ActionResult(
                False,
                0,
                "Здесь нечего поджигать: нужны костёр с топливом, горючий объект, деревянная дверь или масло.",
            )
        damage = self.damage_cell(target, 0, "fire") if oiled else 0
        message = (
            "Костёр зажжён."
            if fire_lit
            else "Дверь загорелась: 5 урона в минуту."
            if ignited
            else "Объект загорелся: 5 урона огнём за минуту."
            if object_lit
            else "Масло подожжено."
        )
        if oiled:
            message += f" Масло сгорело: +5 урона огнём (нанесено {damage})."
        self.events.append(dict(kind="fire", x=target.x, y=target.y, message=message))
        expired = self._advance(1)
        return ActionResult(
            True, 1, message + (" " + " ".join(expired) if expired else "")
        )

    @staticmethod
    def advance_surfaces(states):
        for state in states:
            state.oil = {p: turns - 1 for p, turns in state.oil.items() if turns > 1}
