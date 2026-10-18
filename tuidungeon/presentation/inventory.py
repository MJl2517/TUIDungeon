"""Shared inventory navigation and rendering for the sheet and adventure sidebar."""

from dataclasses import dataclass, field

from ..domain.equipment import Equipment
from ..domain.liquids import portion_text
from ..domain.storage import item_stacks
from ..domain.materials import MATERIAL_TAGS, material_details, material_search_terms
from ..domain.damage import DAMAGE_LABELS, profile_details


CATEGORIES = {
    "weapons": "Вооружение",
    "armor": "Доспехи",
    "consumables": "Расходники",
    "tools": "Инструменты",
    "gear": "Снаряжение",
    "materials": "Материалы",
}


def inventory_category(item):
    if "tool" in item.definition.tags:
        return "tools"
    return "gear" if item.category == "tools" else item.category


@dataclass(frozen=True)
class InventoryRow:
    category: str
    item: Equipment | None = None
    count: int = 0
    quantity: int = 1


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
                if inventory_category(item) == category
                and (
                    not query
                    or query
                    in " ".join(
                        (
                            item.name,
                            item.id,
                            item.definition.description,
                            label,
                            *sorted(item.definition.tags & MATERIAL_TAGS),
                            "свечение свет glowing" if item.glow else "",
                            *material_search_terms(item.definition.tags),
                        )
                    ).casefold()
                )
            ]
            if (query or category in ("gear", "materials")) and not items:
                continue
            rows.append(InventoryRow(category, count=len(items)))
            if category not in self.collapsed or query:
                rows.extend(
                    InventoryRow(category, stack.first, quantity=stack.quantity)
                    for stack in item_stacks(items)
                )
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
    window = browser.window(hero, load_row - 3)
    for row, (index, entry) in enumerate(window, 1):
        marker = ">" if focused and index == browser.selected else " "
        if entry.item:
            item = entry.item
            checkbox = (
                ("[*] " if item.equipped else "[ ] ") if item.definition.slot else ""
            )
            durability = (
                f" ({item.durability}/{item.definition.durability})"
                if item.durability is not None
                else ""
            )
            charges = (
                f" [{item.charges}/{item.definition.charges}]"
                if item.charges is not None
                else ""
            )
            glow = f" [свет:{item.glow.remaining_turns}]" if item.glow else ""
            quantity = f" x{entry.quantity}" if entry.quantity > 1 else ""
            available = max(
                1,
                rect.width
                - 4
                - len(checkbox)
                - len(durability)
                - len(charges)
                - len(glow)
                - len(quantity),
            )
            name = (
                item.name
                if len(item.name) <= available
                else item.name[: available - 1] + "~"
            )
            text = f"{marker} {checkbox}{name}{durability}{charges}{glow}{quantity}"
        else:
            expanded = entry.category not in browser.collapsed or bool(browser.query)
            text = f"{marker} {'-' if expanded else '+'} {CATEGORIES[entry.category]} ({entry.count})"
        canvas.line(rect, row, text)
    if not window:
        canvas.line(rect, 1, "Ничего не найдено.")
    canvas.line(rect, load_row - 2, f"Золото: {hero.gold} ({hero.gold_weight:g} кг)")
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
        "Enter: фильтр | Esc: отмена" if browser.editing else "↑↓ Enter | Q: выброс | F"
    )
    canvas.line(rect, load_row + 2, hint)
    if character:
        canvas.line(rect, load_row + 3, "←/→: страницы | Backspace: карта")


def dice_text(expression):
    if expression is None:
        return "—"
    bonus = f"{expression.bonus:+d}" if expression.bonus else ""
    return f"{expression.count}d{expression.sides}{bonus}"


def item_details(item, *, preview=False):
    from ..domain.item_sizes import SIZE_LABELS
    from ..domain.mechanics import mechanics
    from .conditions import CONDITION_LABELS

    if item.furniture:
        cargo = item.furniture
        return [
            item.name,
            cargo.definition.description,
            f"Вес с содержимым: {item.weight:g} кг",
            "Размер: " + SIZE_LABELS[item.size],
            *(
                [
                    "Макс. размер внутри: "
                    + SIZE_LABELS[
                        (cargo.container_spec or cargo.definition.storage).max_item_size
                    ]
                ]
                if (cargo.container_spec or cargo.definition.storage)
                else []
            ),
            *(
                [f"Прочность: {cargo.state.hp}/{cargo.definition.destruction.max_hp}"]
                if cargo.state.hp is not None
                else []
            ),
            *([f"Внутри предметов: {len(cargo.items)}"] if cargo.items else []),
            "Можно поставить на соседнюю свободную клетку.",
        ]
    definition = item.definition
    lines = [item.name]
    if definition.description:
        lines.append(definition.description)
    lines += [
        "Тип снаряжения: " + CATEGORIES[inventory_category(item)],
        f"Вес: {item.weight:g} кг",
        "Размер: " + SIZE_LABELS[item.size],
    ]
    if definition.vessel:
        lines.append(
            f"Вместимость: {portion_text(definition.vessel.capacity_portions)}"
            + (" · можно нагревать" if definition.vessel.heat_safe else "")
        )
        if definition.vessel.fragile:
            lines.append("Разбивается при броске.")
    if definition.key_kind in ("door", "container"):
        lines.append(
            "Уровень находки: "
            + (item.key_level_name or "будет назначен при размещении")
        )
    elif definition.key_kind == "unique":
        lines.append(
            "Подходит только к связанному уникальному замку."
            if definition.key_code
            else "Этот ключ ещё не связан с замком."
        )
    if item.contaminated:
        lines.append("Загрязнён; можно промыть чистой водой.")
    if item.equipped and not preview:
        lines.append("Надето: да")
    if item.durability is not None:
        lines.append(f"Стойкость: {item.durability}/{definition.durability}")
    if item.charges is not None and not definition.vessel:
        lines.append(f"Заряды: {item.charges}/{definition.charges}")
    if item.category == "weapons" and definition.weapon_damage:
        lines.append(
            f"Урон: {dice_text(definition.weapon_damage)} ({DAMAGE_LABELS[item.damage_type]})"
        )
    if definition.cast_spell:
        lines.append(
            "Свиток: одна активация расходует заряд; ячейка заклинания не нужна."
        )
    if definition.reading:
        lines.append("Можно прочитать: " + definition.reading.title)
    if definition.spell_bonus:
        lines.append(
            f"Магический фокус: +{definition.spell_bonus} к атаке заклинанием и СЛ спасброска; действует сильнейший надетый фокус."
        )
    if item.hands:
        lines.append(f"Занимает рук: {item.hands}")
    if definition.light:
        light = definition.light
        if not preview:
            lines.append("Свет: " + ("горит" if item.shining else "погашен"))
        fuel = (
            str(light.burn_minutes)
            if preview
            else f"{item.fuel_minutes}/{light.burn_minutes}"
        )
        lines += [
            f"Топливо: {fuel} мин.",
            f"Радиус света: {light.bright_radius} яркий / {light.radius} общий, кл.",
        ]
    lines.extend(profile_details(definition.damage_profile))
    if item.glow:
        lines.append(item.glow.description)
    for effect in item.liquid_effects if definition.vessel else definition.properties:
        if effect.kind in ("armor_class", "armor_bonus"):
            if item.category == "armor" and (effect.amount or effect.dice):
                lines.append(
                    f"КД: {effect.amount}"
                    if effect.kind == "armor_class"
                    else f"Бонус КД: {effect.amount:+d}"
                )
            continue
        mechanic = mechanics.entries.get(effect.kind)
        name = mechanic.name if mechanic else "Эффект"
        if effect.params:
            lines.append(mechanic.description or name if mechanic else name)
            continue
        if not (effect.dice or effect.amount or effect.condition):
            continue
        value = dice_text(effect.dice) if effect.dice else str(effect.amount)
        if effect.kind == "damage":
            if item.category != "weapons":
                name = "При использовании"
            value += " урона"
            if effect.damage_type:
                value += " (" + DAMAGE_LABELS[effect.damage_type] + ")"
        if effect.condition:
            value = f"{CONDITION_LABELS.get(effect.condition, effect.condition)}, {effect.duration} ход."
        lines.append(f"{name}: {value}")
    if not preview:
        lines.extend(material_details(definition.tags))
    for aid in definition.check_aids:
        mode = "автоматический успех" if aid.mode == "automatic" else "преимущество"
        label = "Взлом замков" if aid.check_tag == "lockpicking" else "Проверки"
        lines.append(f"{label}: {mode}")
    if item.work:
        from collections import Counter

        lines.extend(
            [
                f"Прогресс работы: {item.work.progress}/{item.work.total}",
                "Вложения: "
                + ", ".join(
                    f"{name} ×{count}"
                    for name, count in Counter(
                        i.name for i in item.work.ingredients
                    ).items()
                ),
                "Все материалы возвращаются при разборе заготовки.",
            ]
        )
    return lines
