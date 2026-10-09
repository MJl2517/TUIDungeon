"""Exploration door commands, shared by terminal and browser clients."""

from ..domain.doors import LockpickAttempt
from ..domain.equipment import find_lockpicks
from ..domain.rules import Ability
from ..world.maps import Position


class DoorCommands:
    lockpick_attempt = None

    def _door(self, identifier):
        level = self.state.level
        return (
            next((d for d in level.doors if d.placement.id == identifier), None)
            if level
            else None
        )

    def _door_available(self, instance, *, distance=1):
        if instance is None or self.state.hero.hp <= 0:
            return False
        p = instance.placement
        return (
            abs(p.x - self.state.position.x) + abs(p.y - self.state.position.y)
            <= distance
        )

    def _door_result(self, performed, minutes, message):
        from .engine import ActionResult

        return ActionResult(performed, minutes, message)

    def _finish_door(self, instance, action, message, *, minutes=1, check=None):
        event = dict(
            kind="door", placement=instance.placement.id, action=action, message=message
        )
        if check:
            event.update(
                roll=check.roll,
                rolls=list(check.rolls),
                total=check.total,
                difficulty=check.difficulty,
                success=check.success,
                advantage=check.advantage,
            )
        self.events.append(event)
        expired = self._advance(minutes) if minutes else []
        return self._door_result(
            True, minutes, message + (" " + " ".join(expired) if expired else "")
        )

    def interact_door(self, identifier, action):
        instance = self._door(identifier)
        if self.lockpick_attempt:
            return self._door_result(False, 0, "Сначала завершите или отмените взлом.")
        if not self._door_available(instance):
            return self._door_result(False, 0, "Подойдите к двери.")
        door, hero = instance.door, self.state.hero
        if door.destroyed or door.bent:
            return self._door_result(False, 0, "Проход уже свободен.")
        if door.material == "stone" and action != "attack":
            return self._door_result(
                False,
                0,
                "Каменную плиту можно только разрушить киркой или дробящими атаками.",
            )
        if action == "open":
            if door.opened or door.locked:
                return self._door_result(
                    False, 0, "Дверь уже открыта." if door.opened else "Дверь заперта."
                )
            door.opened = True
            return self._finish_door(instance, action, "Вы открываете дверь.")
        if action == "close":
            if not door.opened:
                return self._door_result(False, 0, "Дверь уже закрыта.")
            p = Position(instance.placement.x, instance.placement.y)
            if (
                self.state.position == p
                or self.state.item_index.at(p.x, p.y)
                or any(m.monster.hp > 0 for m in self.state.actor_index.at(p.x, p.y))
            ):
                return self._door_result(
                    False, 0, "Нельзя закрыть дверь: клетка занята."
                )
            door.opened = False
            return self._finish_door(instance, action, "Вы закрываете дверь.")
        if door.opened:
            return self._door_result(False, 0, "Дверь открыта.")
        if action == "pick":
            if not door.locked:
                return self._door_result(False, 0, "Замок не заперт.")
            if find_lockpicks(hero.inventory) is None:
                return self._door_result(
                    False,
                    0,
                    "Для взлома нужны исправные воровские инструменты в инвентаре.",
                )
            self.lockpick_attempt = LockpickAttempt(identifier, total=door.lock_turns)
            if door.lock_turns == 1:
                return self.advance_lockpick()
            return self._door_result(
                True, 0, "Взлом: Space — следующий ход, Backspace — отменить."
            )
        if action in ("force", "bend"):
            if action == "bend" and door.material != "bars":
                return self._door_result(False, 0, "Сгибать можно только прутья.")
            crowbar = (
                next(
                    (
                        i
                        for i in hero.inventory
                        if i.equipped and i.hands and i.usable and "lever" in i.tags
                    ),
                    None,
                )
                if action == "force"
                else None
            )
            difficulty = door.force_dc if action == "force" else 20
            check = self.dice.check(
                hero.stats.score(Ability.STRENGTH),
                difficulty,
                advantage=crowbar is not None,
            )
            if crowbar:
                crowbar.wear(1)
            if check.success:
                if action == "force":
                    door.force_open()
                else:
                    door.bent = True
            message = self._door_check_message(check) + (
                " Проход открыт." if check.success else " Дверь не поддалась."
            )
            if crowbar:
                message += (
                    f" Ломик: {crowbar.durability}/{crowbar.definition.durability}."
                )
                if crowbar.broken:
                    message += " Ломик сломан."
            return self._finish_door(instance, action, message, check=check)
        if action == "attack":
            weapons = [
                i
                for i in hero.inventory
                if i.equipped and i.usable and i.definition.weapon_damage
            ]
            weapon = next(
                (
                    i
                    for i in weapons
                    if door.material == "stone"
                    and ("pickaxe" in i.tags or i.damage_type == "bludgeoning")
                ),
                weapons[0] if weapons else None,
            )
            amount = max(
                1,
                (weapon.definition.weapon_damage.roll(self.dice) if weapon else 1)
                + hero.stats.modifier(Ability.STRENGTH),
            )
            kind = weapon.damage_type if weapon else "bludgeoning"
            source_tags = weapon.tags if weapon else ()
            ignite = weapon.can_ignite if weapon else False
            wear = sum(self.dice.roll(1, 4)) if weapon else 0
            if weapon:
                weapon.wear(wear)
            damage = self.damage_cell(
                Position(instance.placement.x, instance.placement.y),
                amount,
                kind,
                source_tags=source_tags,
                ignite=ignite,
            )
            message = f"Урон: {damage}. HP: {door.hp}/{door.max_hp}."
            if weapon:
                message += f" {weapon.name}: −{wear} прочности ({weapon.durability}/{weapon.definition.durability})."
                if weapon.broken:
                    message += " Оружие сломано."
            return self._finish_door(instance, action, message)
        if action == "ignite":
            source = next((i for i in hero.inventory if i.can_ignite), None)
            return self.ignite_cell(
                source, Position(instance.placement.x, instance.placement.y)
            )
        if action == "acid":
            item = next(
                (i for i in hero.inventory if "acid" in i.tags and i.usable), None
            )
            return self.throw_acid_at(instance, item)
        if action == "daylight":
            spell = next(
                (
                    s
                    for s in hero.class_spells
                    if s.id.removeprefix("base:") == "daylight" and s.level == 3
                ),
                None,
            )
            if (
                door.material != "adamantine"
                or hero.character_class.id.removeprefix("base:") != "wizard"
                or not spell
                or not hero.consume_class_slot(spell.id)
            ):
                return self._door_result(
                    False,
                    0,
                    "Нужны волшебник, известное заклинание «Дневной свет» и ячейка 3 уровня.",
                )
            door.daylight()
            return self._finish_door(
                instance,
                action,
                "Дневной свет превращает адамантиевую дверь в каменную плиту.",
            )
        return self._door_result(False, 0, "Неизвестное действие с дверью.")

    @staticmethod
    def _door_check_message(check):
        return (
            f"d20 {list(check.rolls)} + {check.modifier} = {check.total}, СЛ {check.difficulty}. "
            + ("Успех." if check.success else "Провал.")
        )

    def advance_lockpick(self):
        attempt = self.lockpick_attempt
        instance = self._door(attempt.door_id) if attempt else None
        if (
            not attempt
            or not self._door_available(instance)
            or not instance.door.locked
            or instance.door.passable
        ):
            self.lockpick_attempt = None
            return self._door_result(False, 0, "Взлом недоступен или прерван.")
        tools = find_lockpicks(self.state.hero.inventory)
        if tools is None:
            self.lockpick_attempt = None
            return self._door_result(
                False, 0, "Взлом прерван: нет исправных воровских инструментов."
            )
        attempt.progress += 1
        expired = self._advance(1)
        if self.state.hero.hp <= 0 or instance.door.destroyed:
            self.lockpick_attempt = None
            return self._door_result(True, 1, "Взлом прерван." + " ".join(expired))
        if attempt.progress < attempt.total:
            return self._door_result(
                True,
                1,
                f"Взлом: {attempt.progress}/{attempt.total}. Space — продолжить, Backspace — отменить.",
            )
        self.lockpick_attempt = None
        hero = self.state.hero
        check = self.dice.check(
            hero.stats.score(Ability.DEXTERITY),
            instance.door.lock_dc,
        )
        if check.success:
            instance.door.locked = False
        else:
            tools.wear(1)
        tool_message = (
            f" Воровские инструменты: {tools.durability}/{tools.definition.durability}."
            if tools.durability is not None
            else ""
        )
        if tools.broken:
            tool_message += " Воровские инструменты сломаны."
        result = self._finish_door(
            instance,
            "pick",
            self._door_check_message(check)
            + (" Замок открыт." if check.success else " Замок остался заперт.")
            + tool_message,
            minutes=0,
            check=check,
        )
        return self._door_result(
            True, 1, result.message + (" " + " ".join(expired) if expired else "")
        )

    def cancel_lockpick(self):
        if not self.lockpick_attempt:
            return self._door_result(False, 0, "Вы не взламываете замок.")
        self.lockpick_attempt = None
        return self._door_result(
            True, 0, "Взлом отменён. Потраченные ходы не возвращаются."
        )

    def damage_door(self, identifier, amount, kind="physical"):
        instance = self._door(identifier)
        if self.lockpick_attempt or not self._door_available(instance):
            return self._door_result(False, 0, "Дверь недоступна.")
        damage = self.damage_cell(
            Position(instance.placement.x, instance.placement.y), amount, kind
        )
        return self._finish_door(
            instance,
            "damage",
            f"Урон двери: {damage}. HP: {instance.door.hp}/{instance.door.max_hp}."
            + (" Дверь уничтожена." if instance.door.destroyed else ""),
        )

    def throw_acid_at(self, instance, item):
        hero = self.state.hero
        target = (
            Position(instance.placement.x, instance.placement.y) if instance else None
        )
        if (
            self.lockpick_attempt
            or not self._door_available(instance, distance=self.throw_range)
            or item is None
            or not any(i is item for i in hero.inventory)
            or "acid" not in item.tags
            or not item.usable
        ):
            return self._door_result(
                False, 0, "Нужна доступная дверь и кислота в инвентаре."
            )
        if not self._clear_throw_path(target, allow_target_door=True):
            return self._door_result(
                False, 0, "Бросок преграждает стена или другая дверь."
            )
        amount = (
            item.definition.weapon_damage.roll(self.dice)
            if item.definition.weapon_damage
            else sum(self.dice.roll(2, 6))
        )
        damage = instance.door.apply_acid(amount)
        if item.charges is None:
            hero.inventory.remove(item)
        else:
            item.charges -= 1
            if not item.charges:
                hero.inventory.remove(item)
        return self._finish_door(
            instance,
            "acid",
            f"Кислота: {damage} урона двери; сталь и прутья получают двойной урон. HP: {instance.door.hp}/{instance.door.max_hp}.",
        )

    def advance_doors(self, states, minutes):
        messages = []
        for state in states:
            if state.level:
                for instance in state.level.doors:
                    was_destroyed = instance.door.destroyed
                    instance.door.tick(minutes)
                    if not was_destroyed and instance.door.destroyed:
                        message = f"{instance.definition.name}: дверь уничтожена огнём или коррозией."
                        messages.append(message)
                        self.events.append(
                            dict(
                                kind="door",
                                placement=instance.placement.id,
                                message=message,
                            )
                        )
        return messages
