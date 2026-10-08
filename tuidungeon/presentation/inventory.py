"""Shared inventory navigation and rendering for the sheet and adventure sidebar."""

from dataclasses import dataclass, field
import json

from ..domain.equipment import Equipment


CATEGORIES = {
    "weapons": "Вооружение",
    "armor": "Доспехи",
    "consumables": "Расходники",
    "tools": "Инструменты",
}


@dataclass(frozen=True)
class InventoryRow:
    category: str
    item: Equipment | None = None
    count: int = 0


@dataclass
class InventoryBrowser:
    query: str = ""
    editing: bool = False
    previous_query: str = ""
    selected: int = 1
    scroll: int = 0
    collapsed: set[str] = field(default_factory=set)

    def rows(self, hero):
        rows = []
        query = self.query.casefold().strip()
        for category, label in CATEGORIES.items():
            items = [
                item
                for item in hero.inventory
                if item.category == category
                and (
                    not query
                    or query
                    in " ".join(
                        (
                            item.name,
                            item.id,
                            item.definition.description,
                            label,
                            *sorted(item.definition.tags),
                        )
                    ).casefold()
                )
            ]
            if query and not items:
                continue
            rows.append(InventoryRow(category, count=len(items)))
            if category not in self.collapsed or query:
                rows.extend(InventoryRow(category, item) for item in items)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        return rows

    def move(self, hero, amount):
        rows = self.rows(hero)
        self.selected = max(0, min(self.selected + amount, len(rows) - 1))

    def activate(self, hero):
        rows = self.rows(hero)
        if not rows:
            return None
        row = rows[self.selected]
        if row.item is not None:
            return row.item
        if row.category in self.collapsed:
            self.collapsed.remove(row.category)
        else:
            self.collapsed.add(row.category)
        return None

    def begin_search(self):
        self.previous_query = self.query
        self.editing = True

    def search_key(self, key):
        if key == "enter":
            self.editing = False
        elif key == "escape":
            self.query, self.editing = self.previous_query, False
        elif key == "backspace":
            self.query = self.query[:-1]
        elif len(key) == 1 and key.isprintable() and len(self.query) < 100:
            self.query += key
        self.selected, self.scroll = 1, 0
        return True

    def window(self, hero, size):
        rows = self.rows(hero)
        size = max(1, size)
        self.scroll = min(self.scroll, max(0, len(rows) - size))
        if self.selected < self.scroll:
            self.scroll = self.selected
        elif self.selected >= self.scroll + size:
            self.scroll = self.selected - size + 1
        return list(enumerate(rows[self.scroll : self.scroll + size], self.scroll))


def render_inventory(canvas, rect, hero, browser, *, character=False, focused=True):
    canvas.box(rect, "Персонаж | 2/3 Снаряжение" if character else "Инвентарь [<- ->]")
    prompt = "Поиск: " + browser.query + ("_" if browser.editing else "")
    canvas.line(
        rect,
        0,
        prompt if browser.query or browser.editing else "F: поиск | [*]: надето",
    )
    load_row = rect.height - (7 if character else 6)
    window = browser.window(hero, load_row - 2)
    for row, (index, entry) in enumerate(window, 1):
        marker = ">" if focused and index == browser.selected else " "
        if entry.item:
            item = entry.item
            checkbox = (
                ("[*] " if item.equipped else "[ ] ") if item.definition.slot else ""
            )
            available = max(1, rect.width - 4 - len(checkbox))
            name = (
                item.name
                if len(item.name) <= available
                else item.name[: available - 1] + "~"
            )
            text = f"{marker} {checkbox}{name}"
        else:
            expanded = entry.category not in browser.collapsed or bool(browser.query)
            text = f"{marker} {'-' if expanded else '+'} {CATEGORIES[entry.category]} ({entry.count})"
        canvas.line(rect, row, text)
    if not window:
        canvas.line(rect, 1, "Ничего не найдено.")
    canvas.line(rect, load_row - 1, f"Руки заняты: {hero.hands_used}/2")
    suffix = " ПЕРЕГРУЗ" if hero.overloaded else ""
    canvas.line(
        rect,
        load_row,
        f"Вес: {hero.carried_weight:g}/{hero.max_carry_weight:g} кг{suffix}",
    )
    size = max(1, rect.width - 5)
    fraction = (
        min(1, hero.carried_weight / hero.max_carry_weight)
        if hero.max_carry_weight
        else 1
    )
    used = min(size, int(fraction * size + 0.5))
    canvas.line(
        rect,
        load_row + 1,
        "[" + "#" * used + "-" * (size - used) + "]" + ("!" if hero.overloaded else ""),
    )
    hint = (
        "Enter: фильтр | Esc: отмена"
        if browser.editing
        else "↑↓: выбор | Enter | F: поиск"
    )
    canvas.line(rect, load_row + 2, hint)
    if character:
        canvas.line(rect, load_row + 3, "←/→: страницы | Backspace: карта")


def dice_text(expression):
    if expression is None:
        return "—"
    bonus = f"{expression.bonus:+d}" if expression.bonus else ""
    return f"{expression.count}d{expression.sides}{bonus}"


def item_details(item):
    from ..domain.mechanics import mechanics

    definition = item.definition
    lines = [
        item.name,
        definition.description or "Описание не задано.",
        "",
        "Тип снаряжения: " + CATEGORIES[item.category],
        f"Вес: {item.weight:g} кг",
        "Слот: " + (definition.slot or "нет"),
        "Надето: " + ("да" if item.equipped else "нет"),
        "Стойкость: "
        + (
            f"{item.durability}/{definition.durability}"
            if item.durability is not None
            else "не ломается"
        ),
        "Заряды: "
        + (
            f"{item.charges}/{definition.charges}"
            if item.charges is not None
            else "без ограничения"
        ),
    ]
    lines += ["Урон: " + dice_text(definition.weapon_damage)]
    lines.append(f"Занимает рук: {item.hands}")
    if definition.light:
        light = definition.light
        lines.extend(
            [
                "Свет: " + ("горит" if item.shining else "погашен"),
                f"Топливо: {item.fuel_minutes}/{light.burn_minutes} мин.",
                f"Радиус света: {light.bright_radius} яркий / {light.radius} общий, кл.",
                "Топливо: одна порция масла на час."
                if light.fuel_tag
                else "Одноразовый факел; после выгорания нужен новый.",
                "1: надеть и зажечь / снять и погасить.",
            ]
        )
    if definition.weapon_damage:
        lines.append("Характеристика атаки: " + definition.weapon_ability.value)
    armor = [
        f"{effect.amount}"
        for effect in definition.properties
        if effect.kind == "armor_class"
    ]
    bonus = sum(
        effect.amount
        for effect in definition.properties
        if effect.kind == "armor_bonus"
    )
    lines.append("КД: " + (", ".join(armor) if armor else "не изменяет базовую"))
    if bonus:
        lines.append(f"Бонус КД: {bonus:+d}")
    lines.append("Теги: " + (", ".join(sorted(definition.tags)) or "нет"))
    lines.append("Особые свойства и эффекты:")
    if not definition.properties:
        lines.append("Нет.")
    for effect in definition.properties:
        mechanic = mechanics.entries.get(effect.kind)
        name = mechanic.name if mechanic else effect.kind
        value = dice_text(effect.dice) if effect.dice else str(effect.amount)
        if effect.condition:
            value = f"{effect.condition}, {effect.duration} ход."
        if effect.params:
            value = json.dumps(effect.params, ensure_ascii=False)
        lines.append(f"- {name}: {value}")
    for aid in definition.check_aids:
        mode = "автоматический успех" if aid.mode == "automatic" else "преимущество"
        lines.append(f"Проверка {aid.check_tag}: {mode}")
    return lines
