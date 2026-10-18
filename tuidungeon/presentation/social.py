"""Two-column NPC, shop and quest windows shared by both renderers."""

from dataclasses import dataclass, field
import textwrap

from ..domain.storage import item_stacks
from .inventory import item_details


@dataclass
class SocialBrowser:
    npc_id: str | None = None
    selected: list[int] = field(default_factory=lambda: [0, 0])
    side: int = 1
    answer: str = ""
    scroll: int = 0
    pending: tuple | None = None
    quantity: int = 1
    hits: list = field(default_factory=list)

    def open(self, controller, identifier):
        from .tui import View

        result = controller.engine.open_dialogue(identifier)
        controller.message = result.message
        if result.performed:
            self.npc_id, self.answer = identifier, result.message
            self.selected, self.scroll, self.pending = [0, 0], 0, None
            controller.view = View.DIALOGUE

    def stacks(self, engine):
        npc = engine.npc_at(self.npc_id)
        return [
            item_stacks([i for i in items if i.id not in ("gold", "base:gold")])
            for items in (engine.state.hero.inventory, npc.items)
        ]

    def handle(self, c, key):
        from .tui import View

        e = c.engine
        if key in ("escape", "backspace"):
            if self.pending:
                self.pending = None
            elif c.view is View.TRADE:
                c.view = View.DIALOGUE
                self.selected, self.scroll = [0, 0], 0
            elif c.view is View.QUESTS:
                c.view, c.notebook_section = View.NOTEBOOK, None
            else:
                c.view, c.point_id = View.EXPLORE, None
            return
        if c.view is not View.QUESTS:
            _, error = e.social_access(self.npc_id)
            if error:
                c.message, c.view = error, View.EXPLORE
                return
        if c.view is View.TRADE:
            if self.pending:
                if key in ("left", "down", "right", "up", "home", "end"):
                    self.quantity = (
                        1
                        if key == "home"
                        else self.pending[2]
                        if key == "end"
                        else max(
                            1,
                            min(
                                self.pending[2],
                                self.quantity + (1 if key in ("right", "up") else -1),
                            ),
                        )
                    )
                elif key == "enter":
                    side, item_id, _ = self.pending
                    result = e.trade(
                        self.npc_id, item_id, self.quantity, selling=side == 0
                    )
                    c.message = result.message
                    if result.performed:
                        self.pending = None
                return
            if key in ("left", "right", "tab"):
                self.side = 1 - self.side if key == "tab" else int(key == "right")
            stacks = self.stacks(e)[self.side]
            self.selected[self.side] = min(
                self.selected[self.side], max(0, len(stacks) - 1)
            )
            if key in ("up", "down"):
                self.selected[self.side] = max(
                    0,
                    min(
                        len(stacks) - 1,
                        self.selected[self.side] + (1 if key == "down" else -1),
                    ),
                )
            elif key == "enter" and stacks:
                stack = stacks[self.selected[self.side]]
                self.pending, self.quantity = (
                    (self.side, stack.first.instance_id, stack.quantity),
                    1,
                )
            return
        options = (
            list(e.quests)
            if c.view is View.QUESTS
            else list(e.dialogue_choices(self.npc_id))
        )
        if key in ("up", "down", "home", "end"):
            self.selected[0] = (
                0
                if key == "home"
                else max(0, len(options) - 1)
                if key == "end"
                else max(
                    0,
                    min(
                        len(options) - 1,
                        self.selected[0] + (1 if key == "down" else -1),
                    ),
                )
            )
            self.scroll = 0
        elif key in ("pageup", "pagedown", "left", "right"):
            self.scroll = max(
                0, self.scroll + (8 if key in ("pagedown", "right") else -8)
            )
        elif key == "enter" and options and c.view is View.DIALOGUE:
            choice = options[min(self.selected[0], len(options) - 1)]
            if choice.id == "trade":
                if denial := e.light_denial():
                    c.message = self.answer = denial.message
                else:
                    c.view = View.TRADE
                    self.selected, self.side, self.pending = [0, 0], 1, None
                    if not self.stacks(e)[1]:
                        self.side = 0
            else:
                result = e.choose_dialogue(self.npc_id, choice.id)
                c.message = self.answer = result.message
                self.scroll = 0


def social_layout(c, width, height):
    from .tui import Rect, View

    b, e = c.social, c.engine
    w, h = min(124, width - 4), min(36, height - 2)
    rect = Rect((width - w) // 2, (height - h) // 2, w, h)
    rows, b.hits = [], []
    npc = e.npc_at(b.npc_id)
    left_width = max(23, (w - 5) // 3)
    right_width = w - left_width - 5
    capacity = h - 7
    if c.view is View.TRADE:
        if not npc:
            return "Торговля", rect, ["NPC недоступен"], []
        left_width = (w - 5) // 2
        right_width = w - left_width - 5
        stacks = b.stacks(e)
        for side in (0, 1):
            b.selected[side] = min(b.selected[side], max(0, len(stacks[side]) - 1))
        rows = [
            f"Ваше золото: {e.state.hero.gold} | Золото NPC: {sum(i.id in ('gold', 'base:gold') for i in npc.items)}",
            *textwrap.wrap(e.bargain_text(npc), w - 4),
        ]
        rows.append("Ваши вещи".ljust(left_width) + " | Товары NPC")
        list_height = max(2, h - 14)
        offsets = [max(0, b.selected[s] - list_height + 1) for s in (0, 1)]
        for y in range(list_height):
            pair = []
            for side, col in ((0, left_width), (1, right_width)):
                index = offsets[side] + y
                label = ""
                if index < len(stacks[side]):
                    stack = stacks[side][index]
                    price = e.trade_price(npc, stack.first, selling=side == 0)
                    label = f"{'>' if b.side == side and b.selected[side] == index else ' '} {stack.first.name} ×{stack.quantity} | {price if price is not None else '—'} зол."
                    b.hits.append((len(rows), side, index))
                pair.append(label[:col].ljust(col))
            rows.append(pair[0] + " | " + pair[1])
        selected = stacks[b.side]
        index = min(b.selected[b.side], max(0, len(selected) - 1))
        if selected:
            item = selected[index].first
            details = item_details(item)
            state = [
                line
                for line in details
                if line.startswith(("Вес", "Стойкость:", "Прочность:", "Заряды:"))
            ]
            rows.extend([item.name[: w - 3], " | ".join(state)[: w - 3]])
            denial = e.trade_item_denial(item)
            rows.append((denial or item.definition.description)[: w - 3])
        if b.pending:
            stack = next(
                (
                    s
                    for s in stacks[b.pending[0]]
                    if s.first.instance_id == b.pending[1]
                ),
                None,
            )
            price = (
                e.trade_price(npc, stack.first, selling=b.pending[0] == 0)
                if stack
                else None
            )
            rows.append(
                f"Количество: {b.quantity}/{b.pending[2]} | Итого: {price * b.quantity if price is not None else '—'} зол. [−] [+] [Всё]"
            )
            rows.append("[Подтвердить] [Отмена] | ←→: количество | Home/End: 1/всё")
        else:
            rows.append("Tab / ←→: колонка | ↑↓: выбор | Enter: купить/продать")
        rows += [c.message[: w - 3], "Esc: отменить количество / вернуться к разговору"]
        return npc.definition.name + " — магазин", rect, rows, []
    if c.view is View.QUESTS:
        refs = list(e.quests)
        names = [
            ("V " if e.quest_status(r) == "completed" else "• ") + e.quest_def(r).name
            for r in refs
        ]
        b.selected[0] = min(b.selected[0], max(0, len(refs) - 1))
        text = e.quest_text(refs[b.selected[0]]) if refs else "Пока нет заданий."
        title = "Квесты — активные и завершённые"
    else:
        names = [x.text for x in e.dialogue_choices(b.npc_id)]
        b.selected[0] = min(b.selected[0], max(0, len(names) - 1))
        text = b.answer
        title = npc.definition.name if npc else "Разговор"
        if npc and npc.definition.trade:
            text += "\n\n" + e.bargain_text(npc)
    wrapped = [
        part
        for line in text.splitlines()
        for part in (textwrap.wrap(line, right_width) or [""])
    ]
    b.scroll = min(b.scroll, max(0, len(wrapped) - capacity))
    offset = max(0, b.selected[0] - capacity + 1)
    for y in range(capacity):
        i = offset + y
        left = (
            (("> " if i == b.selected[0] else "  ") + names[i])
            if i < len(names)
            else ""
        )
        right = wrapped[b.scroll + y] if b.scroll + y < len(wrapped) else ""
        rows.append(left[:left_width].ljust(left_width) + " | " + right)
        if i < len(names):
            b.hits.append((y, 0, i))
    rows += ["", "↑↓: вопрос/задание | Enter: выбрать | PgUp/PgDn: текст | Esc: назад"]
    return title, rect, rows, []


def social_click(c, x, y, width, height):
    from .tui import View

    _, rect, rows, _ = social_layout(c, width, height)
    row = y - rect.y - 1
    side = int(x >= rect.x + 2 + (rect.width - 5) // 2) if c.view is View.TRADE else 0
    if not (
        rect.x < x < rect.x + rect.width - 1 and rect.y < y < rect.y + rect.height - 1
    ):
        return False
    local_x = x - rect.x - 2
    if c.view is View.TRADE and c.social.pending:
        if 0 <= row < len(rows):
            for label, key in (
                ("[−]", "left"),
                ("[+]", "right"),
                ("[Всё]", "end"),
                ("[Подтвердить]", "enter"),
                ("[Отмена]", "escape"),
            ):
                start = rows[row].find(label)
                if start >= 0 and start <= local_x < start + len(label):
                    c.handle(key)
                    break
        return True
    if c.view is not View.TRADE and local_x >= max(23, (rect.width - 5) // 3):
        return True
    for hit_row, hit_side, index in c.social.hits:
        if hit_row == row and hit_side == side:
            c.social.side = side
            c.social.selected[side] = index
            c.handle("enter")
            break
    return True
