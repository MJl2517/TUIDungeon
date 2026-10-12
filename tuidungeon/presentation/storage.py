"""Two-pane inventory exchange, shared by curses and the SDL cell renderer."""

from dataclasses import dataclass, field

from ..domain.storage import item_stacks


@dataclass
class StorageBrowser:
    container_id: str | None = None
    side: int = 1
    selected: list[int] = field(default_factory=lambda: [0, 0])
    pending: tuple[int, str, int] | None = None
    quantity: int = 1

    def open(self, container_id):
        self.container_id = container_id
        self.side, self.selected, self.pending = 1, [0, 0], None

    def stacks(self, engine):
        container = engine.storage_at(self.container_id)
        return [
            item_stacks(engine.state.hero.inventory),
            item_stacks(container.items) if container else [],
        ]

    def handle(self, controller, key):
        from .tui import View

        engine = controller.engine
        container = engine.storage_at(self.container_id)
        if container is None:
            controller.view = View.EXPLORE
            controller.message = "Контейнер больше недоступен."
            return
        if key == "f4" and not self.pending:
            point = next(
                (
                    p
                    for p in engine.state.level.points
                    if p.placement.id == self.container_id
                ),
                None,
            )
            if point and point.available_choices(engine.state.hero):
                controller.point_id = self.container_id
                controller.view = View.INTERACTION
            return
        if key in ("escape", "backspace"):
            if self.pending:
                self.pending = None
            else:
                controller.view = View.EXPLORE
            return
        if self.pending:
            maximum = self.pending[2]
            if key in ("left", "a", "down", "s"):
                self.quantity = max(1, self.quantity - 1)
            elif key in ("right", "d", "up", "w"):
                self.quantity = min(maximum, self.quantity + 1)
            elif key in ("home", "pageup"):
                self.quantity = 1
            elif key in ("end", "pagedown"):
                self.quantity = maximum
            elif key in ("enter", "f5"):
                side, item_id, _ = self.pending
                result = engine.transfer_storage(
                    self.container_id, item_id, self.quantity, deposit=side == 0
                )
                controller.message = result.message
                if result.performed:
                    self.pending = None
            return
        stacks = self.stacks(engine)
        if key in ("tab", "left", "right", "a", "d"):
            self.side = 1 - self.side if key == "tab" else int(key in ("right", "d"))
        elif key in ("up", "down", "w", "s", "pageup", "pagedown", "home", "end"):
            count = len(stacks[self.side])
            shift = (
                -1
                if key in ("up", "w")
                else 1
                if key in ("down", "s")
                else -8
                if key == "pageup"
                else 8
            )
            value = (
                0
                if key == "home"
                else count - 1
                if key == "end"
                else self.selected[self.side] + shift
            )
            self.selected[self.side] = max(0, min(count - 1, value))
        elif key in ("enter", "f5"):
            if self.side == 0 and not container.spec.personal:
                controller.message = "Лутовый контейнер: вещи можно только забирать."
                return
            options = stacks[self.side]
            index = min(self.selected[self.side], len(options) - 1)
            if index < 0:
                return
            stack = options[index]
            if stack.quantity > 1:
                self.pending = (self.side, stack.first.instance_id, stack.quantity)
                self.quantity = 1
            else:
                result = engine.transfer_storage(
                    self.container_id, stack.first.instance_id, deposit=self.side == 0
                )
                controller.message = result.message


def storage_layout(controller, width, height):
    from .tui import Rect

    browser, engine = controller.storage, controller.engine
    container = engine.storage_at(browser.container_id)
    w, h = min(116, width - 4), min(32, height - 2)
    rect = Rect((width - w) // 2, (height - h) // 2, w, h)
    if not container:
        return "Контейнер", rect, ["Контейнер недоступен. Backspace: закрыть"], []
    column = (w - 5) // 2
    pair = lambda a, b: a[:column].ljust(column) + " | " + b[:column].ljust(column)
    hero = engine.state.hero
    rows = [
        pair(
            "[ Инвентарь ]" if browser.side == 0 else "Инвентарь",
            "[ Контейнер ]" if browser.side == 1 else "Контейнер",
        )
    ]
    rows.append("-" * column + "-+-" + "-" * column)
    stacks = browser.stacks(engine)
    count = h - 11
    windows, offsets = [], []
    for side, options in enumerate(stacks):
        browser.selected[side] = max(0, min(browser.selected[side], len(options) - 1))
        offset = max(0, browser.selected[side] - count + 1)
        offsets.append(offset)
        windows.append(options[offset : offset + count])
    for i in range(count):
        labels = []
        for side in (0, 1):
            active = (
                browser.side == side and browser.selected[side] == i + offsets[side]
            )
            label = (
                windows[side][i].label
                if i < len(windows[side])
                else "(пусто)"
                if not stacks[side] and i == 0
                else ""
            )
            labels.append(("> " if active and label else "  ") + label)
        rows.append(pair(*labels))
    rows += [
        "-" * column + "-+-" + "-" * column,
        pair(
            f"Вес: {hero.carried_weight:g}/{hero.max_carry_weight:g} кг",
            f"Вес: {container.weight:g}/{container.spec.capacity:g} кг",
        ),
        "Личный: можно класть и забирать; не обновляется."
        if container.spec.personal
        else "Лутовый: можно только забирать.",
    ]
    if browser.pending:
        maximum = browser.pending[2]
        used = round(20 * browser.quantity / maximum)
        rows += [
            f"Количество: {browser.quantity}/{maximum} ["
            + "#" * used
            + "-" * (20 - used)
            + "]",
            "←/→: количество | Home/End: 1/всё | Enter: перенос",
        ]
    else:
        rows += [
            "Tab / ←→: колонка | ↑↓: предмет | Enter / F5: перенос",
            "Если вещей несколько — выбор количества ползунком.",
        ]
    point = next(
        (
            p
            for p in engine.state.level.points
            if p.placement.id == browser.container_id
        ),
        None,
    )
    event_hint = (
        " | F4: событие"
        if point and point.available_choices(hero) and not browser.pending
        else ""
    )
    rows += [
        controller.message,
        "Backspace / Esc: "
        + ("отменить количество" if browser.pending else "закрыть")
        + event_hint,
    ]
    return container.definition.name, rect, rows, offsets


def storage_click(controller, x, y, width, height):
    _, rect, rows, offsets = storage_layout(controller, width, height)
    browser = controller.storage
    row = y - rect.y - 1
    column = (rect.width - 5) // 2
    local_x = x - rect.x - 2
    if browser.pending:
        slider_row = len(rows) - 4
        if row == slider_row and rect.x < x < rect.x + rect.width - 1:
            start = rows[slider_row].index("[") + 1
            fraction = max(0, min(1, (local_x - start) / 19))
            browser.quantity = 1 + round(fraction * (browser.pending[2] - 1))
        return True
    if 2 <= row < rect.height - 9 and 0 <= local_x < 2 * column + 3:
        side = int(local_x >= column + 3)
        index = row - 2 + offsets[side]
        if index < len(browser.stacks(controller.engine)[side]):
            browser.side, browser.selected[side] = side, index
    return True
