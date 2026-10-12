"""Two-column recipe browser; work progresses in the exploration HUD."""

from collections import Counter
from dataclasses import dataclass, field
import textwrap

from ..application.crafting import CRAFT_CATEGORIES
from ..domain.equipment import Equipment
from .inventory import item_details
from .menus import ActionMenu


def craft_turns(n):
    ending = (
        "ход"
        if n % 10 == 1 and n % 100 != 11
        else "хода"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14
        else "ходов"
    )
    return f"{n} {ending}"


@dataclass
class CraftBrowser:
    filter: str = "all"
    page: int = 0
    recipe_ref: str | None = None
    variant: int | None = None
    target: str | None = None
    destination: tuple[int, int] | None = None
    selection_key: tuple | None = None
    work_id: str | None = None
    query: str = ""
    editing: bool = False
    previous_query: str = ""
    selected: int = 0
    category: str | None = None
    _available_key: tuple | None = field(default=None, repr=False)
    _available_refs: set[str] = field(default_factory=set, repr=False)
    colors: list[tuple] = field(default_factory=list, repr=False)
    _detail_colors: dict[str, int] = field(default_factory=dict, repr=False)

    def open(self, item=None):
        self.filter, self.page, self.variant = "all", 0, None
        self.target = self.destination = self.selection_key = None
        self.query, self.editing, self.selected = "", False, 0
        self.category = self._available_key = None
        self.work_id = item.instance_id if item and item.work else None
        self.recipe_ref = item.work.recipe_ref if item and item.work else None

    def matching(self, engine):
        words = self.query.casefold().split()
        return [
            e
            for e in engine.craft_list()
            if all(
                word
                in (
                    e["name"]
                    + " "
                    + e["ref"]
                    + " "
                    + e["description"]
                    + " "
                    + CRAFT_CATEGORIES.get(e["category"], e["category"])
                ).casefold()
                for word in words
            )
        ]

    def categories(self, engine):
        return sorted(
            {e["category"] for e in self.matching(engine)},
            key=lambda c: (c != "basic", c),
        )

    def entries(self, engine):
        matching = self.matching(engine)
        categories = sorted(
            {e["category"] for e in matching}, key=lambda c: (c != "basic", c)
        )
        if self.category not in categories:
            selected = engine.catalog.recipes.get(self.recipe_ref)
            self.category = (
                selected.category
                if selected and selected.category in categories
                else categories[0]
                if categories
                else None
            )
        entries = [e for e in matching if e["category"] == self.category]
        state = engine.state
        key = (
            id(engine),
            self.category,
            self.filter,
            self.query,
            tuple(e["ref"] for e in entries),
            state.turns,
            state.position,
            id(state.level.definition) if state.level else None,
            len(engine.events),
            tuple(
                (
                    i.instance_id,
                    i.durability,
                    i.equipped,
                    i.lit,
                    i.liquid_kind,
                    i.liquid_portions,
                )
                for i in state.hero.inventory
            ),
        )
        if key != self._available_key:
            self._available_refs = {
                e["ref"] for e in entries if engine.assess_craft(e["ref"]).available
            }
            self._available_key = key
        for entry in entries:
            entry["available"] = entry["ref"] in self._available_refs
        if self.filter == "available":
            entries = [e for e in entries if e["available"]]
        return entries

    def rows(self, engine):
        rows = [(e["category"], e, 1) for e in self.entries(engine)]
        self.selected = max(0, min(self.selected, len(rows) - 1))
        return rows

    def filters(self, engine):
        return ["all", "available"]

    def assessment(self, engine, rows=None):
        if self.work_id:
            item = engine.workpiece(self.work_id)
            return (
                engine.assess_craft(
                    item.work.recipe_ref, item.work.variant, work=item.work
                )
                if item
                else None
            )
        rows = self.rows(engine) if rows is None else rows
        if not self.recipe_ref and rows and rows[self.selected][1]:
            self.recipe_ref = rows[self.selected][1]["ref"]
        key = (self.recipe_ref, self.variant)
        if key != self.selection_key:
            self.target = self.destination = None
            self.selection_key = key
        return (
            engine.assess_craft(
                self.recipe_ref,
                self.variant,
                target=self.target,
                destination=self.destination,
            )
            if self.recipe_ref
            else None
        )

    def details(self, engine, rows=None):
        self._detail_colors = {}
        a = self.assessment(engine, rows)
        if not a:
            return ["Выберите рецепт в списке слева."], [], []
        v = a.recipe.variants[a.variant]
        rows = [
            a.recipe.name,
            a.recipe.description,
        ]
        if self.work_id:
            item = engine.workpiece(self.work_id)
            rows += [
                f"Заготовка: {item.work.progress}/{item.work.total} · {item.weight:g} кг",
                "Вложено: "
                + ", ".join(
                    f"{name} x{n}"
                    for name, n in Counter(
                        i.name for i in item.work.ingredients
                    ).items()
                ),
            ]
        if not self.work_id:
            rows.append("Ингредиенты:")
            if not a.ingredients:
                rows.append("Не требуются.")
        for ingredient in a.ingredients:
            available, required = ingredient["available"], ingredient["required"]
            line = f"{required} {ingredient['chosen_name']} | у вас: {available}"
            rows.append(line)
            self._detail_colors[line] = (
                10 if available >= required else 11 if available else 9
            )
            if ingredient["name"] != ingredient["chosen_name"]:
                rows.append("  Варианты: " + ingredient["name"])
            rows.extend(
                f"  {source}: {n}"
                for source, n in Counter(
                    s["source"] for s in ingredient["sources"]
                ).items()
            )
        rows.append("Время изготовления:")
        rows.extend(
            f"{method.name}: {craft_turns(method.turns)}"
            + (" · выбран [B]" if n == a.variant else "")
            for n, method in enumerate(a.recipe.variants)
        )
        rows.append("Условия изготовления:")
        for condition in a.conditions:
            line = ("V " if condition["met"] else "X ") + condition["name"]
            rows.append(line)
            self._detail_colors[line] = 10 if condition["met"] else 9
        check = v.check or a.recipe.check
        if a.recipe.learn_recipes:
            rows.append(
                "Открывает: "
                + ", ".join(
                    engine.catalog.recipes[r].name for r in a.recipe.learn_recipes
                )
            )
        if check:
            rows.append(f"Рискованная работа: {check.ability}, СЛ {check.difficulty}")
        from ..application.crafting import operation_summary

        if a.recipe.operation:
            rows.append(operation_summary(a.recipe))
            if a.target:
                rows.append("Предмет [T]: " + a.target.name)
            elif a.target_object:
                rows.append(
                    "Объект [T]: "
                    + next(t["name"] for t in a.targets if t["id"] == a.target_object)
                )
            if a.destination:
                rows.append(f"Клетка [V]: {a.destination[0]}, {a.destination[1]}")
        rows += [
            reason
            for reason in a.reasons
            if not reason.startswith("Не хватает:")
            and not any(c["reason"] == reason for c in a.conditions)
        ]
        result = [operation_summary(a.recipe)] if a.recipe.operation else []
        for output in v.result if v.result is not None else a.recipe.result:
            item = Equipment.create(
                engine.catalog.equipment[output.item.removeprefix("base:")]
            )
            result += [
                f"{item.name} x{output.quantity}",
                f"Вес: {item.weight:g} кг/шт. · всего {item.weight * output.quantity:g} кг",
            ]
            result += [
                line
                for line in item_details(item, preview=True)[1:]
                if not line.startswith(("Вес:", "Надето:"))
            ]
        actions = (
            ["Продолжить", "Разобрать: вернуть материалы"]
            if self.work_id
            else ["Изготовить" if a.available else "Изготовить — недоступно"]
        )
        return rows, result, actions

    def content(self, controller):
        requirements, result, _ = self.details(controller.engine)
        return "Изготовление", requirements + ["Результат"] + result, []

    def handle(self, controller, key):
        from .tui import View

        engine = controller.engine
        self._available_key = None
        if self.editing:
            if key == "enter":
                self.editing = False
            elif key == "escape":
                self.query, self.editing = self.previous_query, False
            elif key == "backspace":
                self.query = self.query[:-1]
            elif len(key) == 1 and key.isprintable() and len(self.query) < 100:
                self.query += key
            self.selected, self.recipe_ref, self.variant, controller.page = (
                0,
                None,
                None,
                0,
            )
            return
        if key in ("escape", "backspace", "m", "q"):
            controller.view = controller.craft_return_view
            if key in ("m", "q"):
                controller._handle(key)
            return
        if key in ("f", "/"):
            self.previous_query, self.editing = self.query, True
            return
        if key == "tab":
            filters = self.filters(engine)
            self.filter = filters[(filters.index(self.filter) + 1) % len(filters)]
            (
                self.selected,
                self.recipe_ref,
                self.work_id,
                self.variant,
                controller.page,
            ) = 0, None, None, None, 0
            return
        if key in ("left", "right"):
            categories = self.categories(engine)
            self.entries(engine)
            if categories:
                self.category = categories[
                    (categories.index(self.category) + (1 if key == "right" else -1))
                    % len(categories)
                ]
            (
                self.selected,
                self.recipe_ref,
                self.work_id,
                self.variant,
                controller.page,
            ) = 0, None, None, None, 0
            return
        rows = self.rows(engine)
        if key in ("up", "down", "home", "end"):
            self.selected = max(
                0,
                min(
                    len(rows) - 1,
                    0
                    if key == "home"
                    else len(rows) - 1
                    if key == "end"
                    else self.selected + (1 if key == "down" else -1),
                ),
            )
            self.recipe_ref, self.work_id, self.variant, controller.page = (
                None,
                None,
                None,
                0,
            )
        elif key in ("pageup", "pagedown"):
            controller.page = max(0, controller.page + (1 if key == "pagedown" else -1))
        elif key == "b":
            a = self.assessment(engine)
            if a and not self.work_id:
                self.variant = (a.variant + 1) % len(a.recipe.variants)
                controller.page = 0
        elif key in ("t", "v") and not self.work_id:
            a = self.assessment(engine)
            if a and key == "t" and a.targets:
                current = a.target.instance_id if a.target else a.target_object
                ids = [t["id"] for t in a.targets]
                self.target = (
                    ids[(ids.index(current) + 1) % len(ids)]
                    if current in ids
                    else ids[0]
                )
            elif a and key == "v" and a.destinations:
                cells = [(p["x"], p["y"]) for p in a.destinations]
                self.destination = (
                    cells[(cells.index(a.destination) + 1) % len(cells)]
                    if a.destination in cells
                    else cells[0]
                )
        elif key in ("enter", "1"):
            a = self.assessment(engine)
            if not a:
                return
            result = (
                engine.resume_craft(self.work_id)
                if self.work_id
                else engine.start_craft(
                    a.ref,
                    a.variant,
                    target=a.target.instance_id if a.target else a.target_object,
                    destination=a.destination,
                )
            )
            controller.message = result.message
            if result.performed:
                self.work_id = engine.active_craft
                controller.view = View.EXPLORE
                controller.action_menu = ActionMenu.ROOT
        elif key == "2" and self.work_id:
            result = engine.cancel_craft(self.work_id)
            controller.message = result.message
            if result.performed:
                self.work_id = None


def craft_layout(controller, width, height):
    from .tui import Rect

    b, engine = controller.craft, controller.engine
    w, h = min(132, width - 4), min(40, height - 2)
    rect = Rect((width - w) // 2, (height - h) // 2, w, h)
    left = min(34, max(22, (w - 4) // 3))
    right = w - 7 - left
    pair = lambda a, z: a[:left].ljust(left) + " | " + z[:right]
    strength = engine.lighting.level_at(engine.state.position)
    light = ("тьма: крафт запрещён", "полутьма: базовые рецепты", "яркий свет")[
        strength
    ]
    options = b.rows(engine)
    categories = b.categories(engine)
    category = CRAFT_CATEGORIES.get(b.category, b.category or "Нет рецептов")
    title = "← " + category + " →"
    if categories:
        title += f" {categories.index(b.category) + 1}/{len(categories)}"
    rows = [
        pair("Поиск: " + b.query + ("_" if b.editing else " [F]"), "Свет: " + light),
        pair(
            title, "ТРЕБОВАНИЯ · " + ("Доступно" if b.filter == "available" else "Все")
        ),
        pair("-" * left, "-" * right),
    ]
    count = h - 9
    b.page = max(0, b.selected - count + 1)
    visible = options[b.page : b.page + count]
    requirements, result, actions = b.details(engine, options)
    wrap = lambda lines: [
        (part, b._detail_colors.get(line))
        for line in lines
        for part in (textwrap.wrap(line, right) or [""])
    ]
    requirements, result = wrap(requirements), wrap(result)
    top = max(4, count * 2 // 3)
    bottom = count - top - 1
    pages = max(
        1, (len(requirements) + top - 1) // top, (len(result) + bottom - 1) // bottom
    )
    controller.page = min(controller.page, pages - 1)
    req_page = min(controller.page, max(0, (len(requirements) - 1) // top))
    result_page = min(controller.page, max(0, (len(result) - 1) // bottom))
    detail = requirements[req_page * top : (req_page + 1) * top]
    detail += [("", None)] * (top - len(detail)) + [
        (f"РЕЗУЛЬТАТ · подробности {controller.page + 1}/{pages}", None)
    ]
    detail += result[result_page * bottom : (result_page + 1) * bottom]
    hits = [(1, "category", 0)]
    b.colors = []
    for i in range(count):
        label = ""
        if i < len(visible):
            category, recipe, number = visible[i]
            label = ("V " if recipe["available"] else "X ") + recipe["name"]
            label = ("> " if i + b.page == b.selected else "  ") + label
            b.colors.append(
                (
                    3 + i,
                    0,
                    label[:left],
                    10 if recipe["available"] else 9,
                    60 if i + b.page == b.selected else 4,
                )
            )
            hits.append((3 + i, "select", i + b.page))
        text, color = detail[i] if i < len(detail) else ("", None)
        rows.append(pair(label, text))
        if color:
            b.colors.append((3 + i, left + 3, text, color, 4))
    action_row = len(rows)
    rows += [
        pair(
            "↑↓: выбор · Enter: действие",
            " | ".join(f"{i + 1}) {a}" for i, a in enumerate(actions)),
        ),
        "←/→: категория · B: способ · F: поиск · Tab: доступность · PgUp/PgDn: текст",
        controller.message,
        "T: предмет · V: клетка · Esc: карта · Работа идёт под картой",
    ]
    hits.append((action_row, "action", left + 3))
    return "Изготовление", rect, rows, [], hits


def craft_click(controller, x, y, width, height):
    _, rect, _, _, hits = craft_layout(controller, width, height)
    row, local = y - rect.y - 1, x - rect.x - 2
    b = controller.craft
    for hit_row, kind, value in hits:
        if hit_row != row:
            continue
        if kind == "category":
            column = min(34, max(22, (rect.width - 4) // 3))
            if 0 <= local < column:
                b.handle(controller, "left" if local < column // 2 else "right")
        elif kind == "select" and 0 <= local < min(34, max(22, (rect.width - 4) // 3)):
            b.selected, b.recipe_ref, b.work_id, b.variant, controller.page = (
                value,
                None,
                None,
                None,
                0,
            )
        elif kind == "action" and local >= value:
            b.handle(controller, "2" if b.work_id and local >= value + 15 else "1")
    return True
