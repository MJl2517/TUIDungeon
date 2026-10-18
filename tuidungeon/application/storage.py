"""Atomic item ownership changes shared by the terminal and browser clients."""

from ..domain.storage import item_stacks
from ..domain.keys import key_matches


class StorageCommands:
    def nearby_containers(self, *, include_closed=False):
        level = self.state.level
        if not level:
            return []
        p = self.state.position
        return [
            container
            for dx, dy in (
                (0, 0),
                (0, -1),
                (0, 1),
                (-1, 0),
                (1, 0),
                (-1, -1),
                (1, -1),
                (-1, 1),
                (1, 1),
            )
            for container in level.index("containers").at(p.x + dx, p.y + dy)
            if self._within_reach(container.placement)
            and (
                not getattr(container.definition, "light_fixture", None)
                or include_closed
                and container.locked
            )
            and (
                include_closed
                or container.spec.open_tool is None
                and not container.locked
            )
        ]

    def open_container(self, identifier):
        from .engine import ActionResult

        container = next(
            (
                c
                for c in self.nearby_containers(include_closed=True)
                if c.placement.id == identifier
            ),
            None,
        )
        if (
            not container
            or self.active_craft
            or self.lockpick_attempt
            or self.state.hero.hp <= 0
        ):
            return ActionResult(False, 0, "Контейнер недоступен.")
        if container.locked:
            return ActionResult(False, 0, "Контейнер заперт. Сначала откройте замок.")
        if container.spec.open_tool:
            if not any(
                i.usable and container.spec.open_tool in i.tags
                for i in self.state.hero.inventory
            ):
                return ActionResult(
                    False,
                    0,
                    "Закрытый ящик: нужна исправная монтировка или разберите мебель.",
                )
            container.spec = container.spec.model_copy(update={"open_tool": None})
            self._set_container_opened(container, True)
            self._advance(1)
            return ActionResult(True, 1, "Ящик открыт монтировкой.")
        self._set_container_opened(container, True)
        return ActionResult(True, 0, "Контейнер открыт.")

    def _set_container_opened(self, container, opened):
        if container.opened != opened:
            container.opened = opened
            self.state.level.container_visual_version += 1

    def close_container(self, identifier):
        from .engine import ActionResult

        container = self.storage_at(identifier)
        if (
            not container
            or not container.opened
            or self.active_craft
            or self.lockpick_attempt
            or self.state.hero.hp <= 0
        ):
            return ActionResult(False, 0, "Контейнер недоступен.")
        self._set_container_opened(container, False)
        return ActionResult(True, 0, "Контейнер закрыт.")

    def interact_container_lock(self, identifier, action):
        from ..domain.doors import LockpickAttempt
        from ..domain.equipment import find_lockpicks

        container = next(
            (
                c
                for c in self.nearby_containers(include_closed=True)
                if c.placement.id == identifier
            ),
            None,
        )
        if (
            not container
            or not container.locked
            or self.lockpick_attempt
            or self.active_craft
            or self.state.hero.hp <= 0
        ):
            return self._door_result(False, 0, "Замок контейнера недоступен.")
        if action == "unlock_container_key":
            if not any(
                key_matches(i, container.lock, "container", self.state.level.ref)
                for i in self.state.hero.inventory
            ):
                return self._door_result(
                    False,
                    0,
                    "Нужен уникальный ключ именно от этого контейнера."
                    if container.lock.key_code
                    else "Нужен подходящий ключ контейнера или ключ для контейнеров с этого уровня.",
                )
            container.lock.locked = False
            return self._finish_door(
                container, "use_key", "Ключ открывает замок контейнера."
            )
        if action == "pick_container_lock":
            if find_lockpicks(self.state.hero.inventory) is None:
                return self._door_result(
                    False, 0, "Нужны исправные воровские инструменты."
                )
            self.lockpick_attempt = LockpickAttempt(
                identifier, total=container.lock.lock_turns, target_kind="container"
            )
            if container.lock.lock_turns == 1:
                return self.advance_lockpick()
            return self._door_result(
                True, 0, "Взлом: Space — следующий ход, Backspace — отменить."
            )
        return self._door_result(False, 0, "Неизвестное действие с замком.")

    def storage_at(self, placement_id):
        return next(
            (c for c in self.nearby_containers() if c.placement.id == placement_id),
            None,
        )

    def storage_transfer_denial(
        self, container, items, *, deposit=False, free_weight=None
    ):
        """Read-only eligibility shared by commands and the two-pane browser."""
        from ..domain.item_sizes import fits_size, SIZE_LABELS

        hero = self.state.hero
        if self.lockpick_attempt or self.active_craft or hero.hp <= 0:
            return "Сейчас нельзя перемещать вещи."
        if container is None:
            return "Контейнер недоступен: подойдите к нему."
        if deposit and not container.spec.personal:
            return "Класть вещи можно только в личный контейнер."
        oversized = (
            next(
                (
                    item
                    for item in items
                    if not fits_size(item.size, container.spec.max_item_size)
                ),
                None,
            )
            if deposit
            else None
        )
        if oversized:
            return f"Предмет слишком большой ({SIZE_LABELS[oversized.size].lower()}). Предел контейнера: {SIZE_LABELS[container.spec.max_item_size].lower()}."
        if free_weight is None:
            current = container.weight if deposit else hero.carried_weight
            maximum = container.spec.capacity if deposit else hero.max_carry_weight
            free_weight = maximum - current
        if sum(item.weight for item in items) > free_weight + 1e-9:
            return "Недостаточно свободной нагрузки у получателя."
        return None

    def transfer_storage(self, placement_id, item_id, quantity=1, *, deposit=False):
        from .engine import ActionResult

        def denied(message):
            return ActionResult(False, 0, message)

        hero = self.state.hero
        if self.lockpick_attempt or self.active_craft or hero.hp <= 0:
            return denied("Сейчас нельзя перемещать вещи.")
        container = self.storage_at(placement_id)
        if container is None:
            return denied("Контейнер недоступен: подойдите к нему.")
        if type(deposit) is not bool or type(quantity) is not int or quantity < 1:
            return denied("Неверное количество предметов.")
        if deposit and not container.spec.personal:
            return denied("Класть вещи можно только в личный контейнер.")
        source = hero.inventory if deposit else container.items
        target = container.items if deposit else hero.inventory
        stack = next(
            (s for s in item_stacks(source) if s.first.instance_id == item_id), None
        )
        if stack is None or quantity > stack.quantity:
            return denied("Предмет или указанное количество отсутствует.")
        moved = stack.items[:quantity]
        if reason := self.storage_transfer_denial(container, moved, deposit=deposit):
            return denied(reason)
        # Check everything before mutating either inventory. Preserve IDs and
        # all resources; a stored object is never equipped or burning.
        ids = {item.instance_id for item in moved}
        source[:] = [item for item in source if item.instance_id not in ids]
        for item in moved:
            item.bind_key(self.state.level.ref, self.state.level.definition.name)
            if deposit:
                item.equipped = item.lit = False
            target.append(item)
        verb = "Положено" if deposit else "Взято"
        self.refresh_quests()
        message = f"{verb}: {moved[0].name} x{quantity}."
        self.events.append(
            dict(
                kind="storage",
                placement=placement_id,
                message=message,
                quantity=quantity,
                deposit=deposit,
            )
        )
        return ActionResult(True, 0, message)
