"""Atomic item ownership changes shared by the terminal and browser clients."""

from ..domain.storage import item_stacks


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
            and not getattr(container.definition, "light_fixture", None)
            and (include_closed or container.spec.open_tool is None)
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
            self._advance(1)
            return ActionResult(True, 1, "Ящик открыт монтировкой.")
        return ActionResult(True, 0, "Контейнер открыт.")

    def storage_at(self, placement_id):
        return next(
            (c for c in self.nearby_containers() if c.placement.id == placement_id),
            None,
        )

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
        weight = sum(item.weight for item in moved)
        current = container.weight if deposit else hero.carried_weight
        maximum = container.spec.capacity if deposit else hero.max_carry_weight
        if current + weight > maximum + 1e-9:
            return denied("Недостаточно свободной нагрузки у получателя.")
        # Check everything before mutating either inventory. Preserve IDs and
        # all resources; a stored object is never equipped or burning.
        ids = {item.instance_id for item in moved}
        source[:] = [item for item in source if item.instance_id not in ids]
        for item in moved:
            if deposit:
                item.equipped = item.lit = False
            target.append(item)
        verb = "Положено" if deposit else "Взято"
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
