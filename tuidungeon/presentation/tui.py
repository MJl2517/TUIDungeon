"""Input controller and pure text renderer; only run() touches curses."""

from dataclasses import dataclass
from enum import Enum, auto
import random
import textwrap
import time

from ..application.creation import CharacterCreation, CreationStep
from ..application.engine import Action, Engine
from ..domain.actors import Hero
from ..domain.rules import Ability, Dice
from ..content.catalog import ContentCatalog
from .symbols import GlyphTheme
from .menus import ActionMenu, SidebarTab, SHEET_SECTIONS, PAGE_SIZE, action_lines
from .inventory import InventoryBrowser, render_inventory, item_details
from .conditions import condition_lines
from .creation import render_creation, creation_button_entries
from ..domain.actions import SpellSource
from ..world.maps import Position
from ..application.saves import SaveRepository


MIN_WIDTH = 80
MIN_HEIGHT = 24
MAIN_MENU = ("Новая игра", "Загрузить", "Настройки", "Справка", "Выйти")


class View(Enum):
    MAIN_MENU = auto()
    CREATION = auto()
    LOAD = auto()
    SETTINGS = auto()
    HELP = auto()
    EXPLORE = auto()
    CHARACTER = auto()
    INTERACTION = auto()
    LOOK = auto()
    INSPECT = auto()
    ITEM = auto()
    ITEM_INSPECT = auto()
    THROW = auto()


class Controller:
    def __init__(
        self,
        seed: int | None = None,
        *,
        symbols: str = "ascii",
        catalog: ContentCatalog | None = None,
        map_ref=None,
        store=None,
        test_map: bool = False,
        save_path=None,
    ):
        self.map_ref, self.store = map_ref, store
        self.catalog = catalog
        self.action_menu = ActionMenu.ROOT
        self.alt_held = False
        self.return_view = View.MAIN_MENU
        self.sheet_section = 0
        self.page = 0
        self.look_position = None
        self.inspection = []
        self.detail_page = 0
        self.selected_item = None
        self.inventory = InventoryBrowser()
        self.inventory_focus = False
        self.item_return_view = View.EXPLORE
        self.spell_index = 0
        self.selected_spell = None
        self.saves = (
            SaveRepository(save_path) if save_path is not None else SaveRepository()
        )
        self.point_id = None
        self.rng = random.Random(seed)
        self.game_rng = random.Random(seed)
        self.theme = GlyphTheme.named(symbols)
        self.symbols = symbols
        self.creation = CharacterCreation(Dice(self.rng), catalog)
        self.creation_help_page = 0
        self.creation_help_pages = 1
        self.engine: Engine | None = None
        self.view = View.MAIN_MENU
        self.menu_index = 0
        self.sidebar_tab = SidebarTab.INVENTORY
        self.running = True
        self.message = "Добро пожаловать в TUI Dungeon!"
        if test_map:
            from ..application.factories import create_test_hero

            hero = create_test_hero(self.creation.catalog)
            self.engine = Engine.new_game(hero, self.game_rng, self.map_ref, self.store)
            self.view = View.EXPLORE
            self.message = "Тест карты. ↑↓/Enter: вещи | F: поиск."

    def open_interaction(self):
        points = self.engine.nearby_points()
        if points:
            self.point_id = points[0].placement.id if len(points) == 1 else None
            self.view = View.INTERACTION
            self.action_menu = ActionMenu.ROOT

    @property
    def spells_tab(self):
        """Compatibility with callers of the original two-tab controller."""
        return self.sidebar_tab is SidebarTab.SPELLS

    @spells_tab.setter
    def spells_tab(self, value):
        self.sidebar_tab = SidebarTab.SPELLS if value else SidebarTab.INVENTORY

    @property
    def spell_options(self):
        hero = self.engine.state.hero
        return [(s, SpellSource.CLASS) for s in hero.class_spells] + (
            [(hero.racial_spell, SpellSource.RACIAL)] if hero.racial_spell else []
        )

    @property
    def targets(self):
        light = self.engine.lighting
        return [
            p.monster
            for p in self.engine.state.monsters
            if p.monster.hp > 0 and light.at(p.position)
        ]

    def open_magic(self):
        self.view = View.EXPLORE
        self.action_menu = ActionMenu.MAGIC
        self.page = 0

    def choose_spell(self, index):
        options = self.spell_options
        if not 0 <= index < len(options):
            return
        self.selected_spell = options[index]
        if self.selected_spell[0].target == "other":
            self.action_menu = ActionMenu.TARGET
            self.view = View.EXPLORE
            self.page = 0
        else:
            self.cast_selected()

    def cast_selected(self, target=None):
        spell, source = self.selected_spell
        result = self.engine.cast_spell(spell.id, source, target)
        self.message = result.message
        if result.performed:
            self.view = View.EXPLORE
            self.action_menu = ActionMenu.ROOT

    def load_game(self):
        try:
            engine = self.saves.load(self.creation.catalog, self.store)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            self.message = f"Не удалось загрузить: {error}"
            return False
        self.engine = engine
        self.game_rng = engine.dice.rng
        self.view = View.EXPLORE
        self.action_menu = ActionMenu.ROOT
        self.point_id = None
        self.page = 0
        self.inventory = InventoryBrowser()
        self.inventory_focus = False
        self.selected_item = None
        self.message = "Сохранение загружено."
        return True

    def meta_action(self, key):
        if key == "1":
            try:
                self.saves.save(self.engine)
                self.message = "Игра сохранена."
            except (OSError, ValueError) as error:
                self.message = f"Не удалось сохранить: {error}"
        elif key == "2":
            self.load_game()
        elif key in ("3", "5"):
            self.return_view = self.view
            self.view = View.HELP if key == "3" else View.SETTINGS
        elif key == "4":
            self.action_menu = ActionMenu.EXIT
        elif key in ("m", "backspace", "escape"):
            self.action_menu = ActionMenu.ROOT

    def handle(self, key: str) -> None:
        key = key.lower()
        if key == "ctrl_c":
            self.running = False
            return
        if self.inventory.editing:
            self.inventory.search_key(key)
            return
        if key in ("alt_press", "alt_release"):
            self.alt_held = key == "alt_press"
            return
        if (
            key.startswith("alt+")
            and self.engine
            and self.view not in (View.MAIN_MENU, View.CREATION)
        ):
            self.meta_action(key[4:])
            return
        if key == "q":
            if self.engine and self.view not in (View.MAIN_MENU, View.CREATION):
                self.view = View.EXPLORE
                self.action_menu = ActionMenu.EXIT
            else:
                self.running = False
            return
        if self.view is View.MAIN_MENU:
            if key in ("up", "w"):
                self.menu_index = (self.menu_index - 1) % len(MAIN_MENU)
            elif key in ("down", "s"):
                self.menu_index = (self.menu_index + 1) % len(MAIN_MENU)
            elif key == "enter" or key in ("1", "2", "3", "4", "5"):
                if key != "enter":
                    self.menu_index = int(key) - 1
                if self.menu_index == 0:
                    self.engine = None
                    self.creation = CharacterCreation(Dice(self.rng), self.catalog)
                    self.creation_help_page = 0
                    self.action_menu = ActionMenu.ROOT
                    self.view = View.CREATION
                elif self.menu_index == 4:
                    self.running = False
                elif self.menu_index == 1:
                    self.return_view = View.MAIN_MENU
                    self.view = View.LOAD
                    self.load_game()
                else:
                    self.return_view = View.MAIN_MENU
                    self.view = (View.SETTINGS, View.HELP)[self.menu_index - 2]
            return
        if self.view in (View.LOAD, View.SETTINGS, View.HELP):
            if key in ("backspace", "escape"):
                self.view = self.return_view
            elif self.view is View.LOAD and key == "enter":
                self.load_game()
            elif self.view is View.SETTINGS:
                if key in ("left", "right", "up", "down", "w", "s", "tab"):
                    self.symbols = "unicode" if self.symbols == "ascii" else "ascii"
                elif key in ("1", "2"):
                    self.symbols = "ascii" if key == "1" else "unicode"
                self.theme = GlyphTheme.named(self.symbols)
            return
        if self.view is View.CREATION:
            if key in ("backspace", "escape"):
                if self.creation.step is CreationStep.RACE:
                    self.view = View.MAIN_MENU
                else:
                    self.creation.back()
                self.creation_help_page = 0
            elif key in ("w", "a", "up", "left", "s", "d", "down", "right", "tab"):
                self.creation.move(-1 if key in ("w", "a", "up", "left") else 1)
                self.creation_help_page = 0
            elif key in ("pageup", "pagedown"):
                self.creation.change_page(-1 if key == "pageup" else 1)
                self.creation_help_page = 0
            elif key == "h":
                self.creation_help_page = (
                    self.creation_help_page + 1
                ) % self.creation_help_pages
            elif key == "enter" or key in "0123456789" and len(key) == 1:
                number = (
                    self.creation.focused_button.number if key == "enter" else int(key)
                )
                if number == 0:
                    if self.creation.step is CreationStep.RACE:
                        self.view = View.MAIN_MENU
                    else:
                        self.creation.back()
                    self.creation_help_page = 0
                    return
                hero = self.creation.select(number)
                self.creation_help_page = 0
                if hero is not None:
                    self.engine = Engine.new_game(
                        hero, self.game_rng, self.map_ref, self.store
                    )
                    self.view = View.EXPLORE
                    self.message = "WASD: шаг. Alt+цифра / M: мета-действия."
            return
        if self.alt_held or self.action_menu is ActionMenu.META:
            self.meta_action(key)
            return
        if key == "m":
            self.action_menu = ActionMenu.META
            return
        if self.action_menu is ActionMenu.EXIT:
            if key == "1":
                self.view = View.MAIN_MENU
                self.action_menu = ActionMenu.ROOT
                self.menu_index = 0
            elif key == "2":
                self.running = False
            elif key in ("backspace", "escape"):
                self.action_menu = ActionMenu.ROOT
            return
        if self.view in (View.LOOK, View.THROW):
            if key in ("backspace", "escape"):
                self.view = View.ITEM if self.view is View.THROW else View.EXPLORE
            elif key == "enter":
                if self.view is View.THROW:
                    result = self.engine.place_item(
                        self.selected_item, self.look_position, throwing=True
                    )
                    self.message = result.message
                    if result.performed:
                        self.view = self.item_return_view
                        self.selected_item = None
                else:
                    self.inspection = self.engine.inspect_cell(self.look_position)
                    self.page = 0
                    self.view = View.INSPECT
            else:
                directions = {
                    "w": (0, -1),
                    "up": (0, -1),
                    "s": (0, 1),
                    "down": (0, 1),
                    "a": (-1, 0),
                    "left": (-1, 0),
                    "d": (1, 0),
                    "right": (1, 0),
                }
                if key in directions:
                    dx, dy = directions[key]
                    p = Position(self.look_position.x + dx, self.look_position.y + dy)
                    dungeon = self.engine.state.dungeon
                    in_range = (
                        abs(p.x - self.engine.state.position.x)
                        + abs(p.y - self.engine.state.position.y)
                        <= self.engine.throw_range
                    )
                    if (
                        0 <= p.x < dungeon.width
                        and 0 <= p.y < dungeon.height
                        and (self.view is View.LOOK or in_range)
                    ):
                        self.look_position = p
            return
        if self.view is View.INSPECT:
            if key in ("backspace", "escape"):
                self.view = View.LOOK
            elif key in ("pageup", "pagedown"):
                self.page = max(0, self.page + (1 if key == "pagedown" else -1))
            return
        if self.view is View.INTERACTION:
            points = self.engine.nearby_points()
            if key in ("backspace", "escape"):
                self.view, self.point_id = View.EXPLORE, None
            elif key in "123456789" and len(key) == 1:
                index = int(key) - 1
                if self.point_id is None:
                    if index < len(points):
                        self.point_id = points[index].placement.id
                else:
                    point = next(
                        (p for p in points if p.placement.id == self.point_id), None
                    )
                    choices = (
                        point.challenge.available_choices(self.engine.state.hero)
                        if point
                        else ()
                    )
                    if index < len(choices):
                        self.message = self.engine.interact(
                            self.point_id, choices[index].id
                        ).message
                        self.view, self.point_id = View.EXPLORE, None
            return
        if self.view is View.ITEM:
            if key in ("backspace", "escape"):
                self.view = self.item_return_view
            elif key == "1":
                item = self.selected_item
                result = (
                    self.engine.manage_equipment(item, not item.equipped)
                    if item.definition.slot
                    else self.engine.use_item(item)
                )
                self.message = result.message
                if result.performed and not any(
                    owned is item for owned in self.engine.state.hero.inventory
                ):
                    self.selected_item = None
                    self.view = self.item_return_view
            elif key == "2":
                self.detail_page = 0
                self.view = View.ITEM_INSPECT
            elif key == "3":
                self.look_position = self.engine.state.position
                self.view = View.THROW
            elif key == "4":
                result = self.engine.place_item(
                    self.selected_item, self.engine.state.position
                )
                self.message = result.message
                if result.performed:
                    self.view = self.item_return_view
                    self.selected_item = None
            return
        if self.view is View.ITEM_INSPECT:
            if key in ("backspace", "escape", "enter"):
                self.view = View.ITEM
            elif key in ("pageup", "pagedown", "up", "down"):
                self.detail_page = max(
                    0, self.detail_page + (1 if key in ("pagedown", "down") else -1)
                )
            return
        if self.view is View.CHARACTER:
            if key in ("backspace", "escape"):
                self.view = View.EXPLORE
                self.inventory_focus = False
            elif key in ("[", "]", "left", "right", "tab"):
                self.sheet_section = (
                    self.sheet_section + (-1 if key in ("[", "left") else 1)
                ) % len(SHEET_SECTIONS)
                self.page = 0
                self.spell_index = 0
            elif self.sheet_section == 1 and self.inventory_key(key):
                pass
            elif self.sheet_section == 2 and key in ("up", "down", "enter"):
                if key == "enter":
                    self.choose_spell(self.spell_index)
                else:
                    self.spell_index = max(
                        0,
                        min(
                            len(self.spell_options) - 1,
                            self.spell_index + (1 if key == "down" else -1),
                        ),
                    )
                    self.page = self.spell_index // PAGE_SIZE
            elif key in ("pageup", "pagedown"):
                if self.sheet_section == 0:
                    self.page = max(
                        0, min(1, self.page + (1 if key == "pagedown" else -1))
                    )
                else:
                    self.change_page(
                        key,
                        len(self.engine.state.hero.inventory)
                        if self.sheet_section == 1
                        else len(self.spell_options),
                    )
                    if self.sheet_section == 2:
                        self.spell_index = self.page * PAGE_SIZE
            elif key in "123456" and len(key) == 1:
                index = self.page * PAGE_SIZE + int(key) - 1
                if self.sheet_section == 2:
                    self.choose_spell(index)
            return
        if self.view is View.EXPLORE and self.action_menu is ActionMenu.ROOT:
            if key in ("left", "right", "tab"):
                self.sidebar_tab = self.sidebar_tab.next(-1 if key == "left" else 1)
                self.inventory_focus = False
                return
            if self.sidebar_tab is SidebarTab.INVENTORY and self.inventory_key(key):
                return
            if key == "i":
                self.sidebar_tab = SidebarTab.INVENTORY
                self.inventory_focus = not self.inventory_focus
                return
            if key == "g":
                self.message = self.engine.pickup_item().message
                return
        if self.action_menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
            options = (
                self.spell_options
                if self.action_menu is ActionMenu.MAGIC
                else self.targets
            )
            if key in ("backspace", "escape"):
                self.action_menu = (
                    ActionMenu.ACTIONS
                    if self.action_menu is ActionMenu.MAGIC
                    else ActionMenu.MAGIC
                )
                self.page = 0
            elif key in ("pageup", "pagedown"):
                self.change_page(key, len(options))
            elif key in "123456" and len(key) == 1:
                index = self.page * PAGE_SIZE + int(key) - 1
                if self.action_menu is ActionMenu.MAGIC:
                    self.choose_spell(index)
                elif index < len(options):
                    self.cast_selected(options[index])
            return
        if key in ("backspace", "escape"):
            self.action_menu = ActionMenu.ROOT
            return
        if self.action_menu is ActionMenu.ACTIONS:
            if key == "1":
                self.message = self.engine.toggle_sneaking().message
            elif key == "2":
                self.open_magic()
            elif key == "3":
                self.message = self.engine.apply(Action.WAIT).message
            return
        if self.action_menu is ActionMenu.REST:
            if key in ("1", "2"):
                self.message = self.engine.apply(
                    Action.SHORT_REST if key == "1" else Action.REST
                ).message
                self.action_menu = ActionMenu.ROOT
            return
        if key == "enter":
            self.open_interaction()
        elif key == "1":
            self.look_position = self.engine.state.position
            self.view = View.LOOK
        elif key == "2":
            self.sheet_section, self.page = 0, 0
            self.view = View.CHARACTER
            self.inventory_focus = False
        elif key == "3":
            self.action_menu = ActionMenu.ACTIONS
        elif key == "4":
            self.action_menu = ActionMenu.REST
        else:
            action = {
                "w": Action.NORTH,
                "s": Action.SOUTH,
                "a": Action.WEST,
                "d": Action.EAST,
            }.get(key)
            if action:
                self.inventory_focus = False
                self.message = self.engine.apply(action).message

    def open_item(self, item):
        self.selected_item = item
        self.item_return_view = self.view
        self.detail_page = 0
        self.view = View.ITEM

    def inventory_key(self, key):
        hero = self.engine.state.hero
        if key == "f":
            self.inventory_focus = True
            self.inventory.begin_search()
        elif key in ("up", "down", "pageup", "pagedown"):
            self.inventory_focus = True
            amount = 6 if key in ("pageup", "pagedown") else 1
            self.inventory.move(
                hero, amount if key in ("down", "pagedown") else -amount
            )
        elif key == "enter" and (
            self.view is View.CHARACTER
            or self.inventory_focus
            or not self.engine.nearby_points()
        ):
            self.inventory_focus = True
            item = self.inventory.activate(hero)
            if item is not None:
                self.open_item(item)
        elif (
            key in ("backspace", "escape")
            and self.inventory_focus
            and self.view is View.EXPLORE
        ):
            self.inventory_focus = False
        else:
            return False
        return True

    def change_page(self, key, count):
        last = max(0, (count - 1) // PAGE_SIZE)
        self.page = max(0, min(last, self.page + (1 if key == "pagedown" else -1)))


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Layout:
    main: Rect
    actions: Rect
    sidebar: Rect
    status: Rect

    @classmethod
    def for_size(cls, width: int, height: int) -> "Layout":
        right_width = 28
        bottom_height = 7
        left_width = width - right_width
        top_height = height - bottom_height
        return cls(
            Rect(0, 0, left_width, top_height),
            Rect(0, top_height, left_width, bottom_height),
            Rect(left_width, 0, right_width, top_height),
            Rect(left_width, top_height, right_width, bottom_height),
        )


class Canvas:
    def __init__(self, width: int, height: int, theme: GlyphTheme | None = None):
        self.width, self.height = width, height
        self.theme = theme or GlyphTheme.named("ascii")
        self.cells = [[" "] * width for _ in range(height)]

    def text(self, x: int, y: int, text: str, limit: int | None = None) -> None:
        if not 0 <= y < self.height:
            return
        if limit is not None:
            text = text[: max(0, limit)]
        for offset, character in enumerate(text):
            if 0 <= x + offset < self.width:
                self.cells[y][x + offset] = character

    def box(self, rect: Rect, title: str) -> None:
        theme = self.theme
        middle = theme.horizontal * (rect.width - 2)
        self.text(rect.x, rect.y, theme.top_left + middle + theme.top_right)
        self.text(
            rect.x,
            rect.y + rect.height - 1,
            theme.bottom_left + middle + theme.bottom_right,
        )
        for y in range(rect.y + 1, rect.y + rect.height - 1):
            self.text(rect.x, y, theme.vertical)
            self.text(rect.x + rect.width - 1, y, theme.vertical)
        self.text(rect.x + 2, rect.y, f" {title} ", rect.width - 4)

    def line(self, rect: Rect, row: int, text: str) -> None:
        if 0 <= row < rect.height - 2:
            self.text(rect.x + 1, rect.y + 1 + row, text, rect.width - 2)

    def lines(self, rect: Rect, lines: list[str]) -> None:
        for row, text in enumerate(lines):
            self.line(rect, row, text)

    def finish(self) -> list[str]:
        return ["".join(row) for row in self.cells]


def hero_lines(hero: Hero) -> list[str]:
    lines = [
        f"Раса: {hero.race.value}",
        f"Класс: {hero.character_class.value} | Уровень: {hero.level}",
        f"Здоровье: {hero.hp}/{hero.max_hp}",
        "",
    ]
    for ability in Ability:
        lines.append(
            f"{ability.value:12} {hero.stats.score(ability):2} ({hero.stats.modifier(ability):+d})"
        )
    lines.extend(
        [
            f"КД: {hero.armor_class} | Скорость: {hero.speed / (2 if hero.sneaking else 1):g} кл./ход",
            f"Руки: {hero.hands_used}/2 | Вес: {hero.carried_weight:g}/{hero.max_carry_weight:g} кг"
            + (" (перегрузка)" if hero.overloaded else ""),
        ]
    )
    if hero.background:
        lines.append(f"Предыстория: {hero.background.name}")
        lines.append("Навыки (план): " + (", ".join(hero.background.skills) or "нет"))
        lines.append(
            "Теги предыстории: " + (", ".join(sorted(hero.background.tags)) or "нет")
        )
    return lines


def render_sidebar(
    canvas: Canvas, rect: Rect, hero: Hero, sidebar_tab: SidebarTab, controller=None
) -> None:
    if controller and (
        controller.view is View.CHARACTER
        or controller.view in (View.ITEM, View.ITEM_INSPECT)
        and controller.item_return_view is View.CHARACTER
    ):
        canvas.box(rect, "Квесты")
        return
    if sidebar_tab is SidebarTab.CONDITIONS:
        canvas.box(rect, "Состояния [<- ->] 3/3")
        canvas.lines(rect, ["Пока не отслеживаются.", ""] + condition_lines())
        canvas.line(rect, rect.height - 3, "←/→ / Tab: вкладки")
        return
    if sidebar_tab is SidebarTab.INVENTORY:
        render_inventory(
            canvas,
            rect,
            hero,
            controller.inventory if controller else InventoryBrowser(),
            focused=bool(controller and controller.inventory_focus),
        )
        return
    canvas.box(rect, "Заклинания [<- ->]")
    lines = ["Классовые заклинания:"]
    if hero.class_spells:
        lines.extend(f"- {spell.name} ({spell.level})" for spell in hero.class_spells)
        for level, capacity in hero.max_spell_slots.items():
            lines.append(f"Ячейки ур. {level}: {hero.spell_slots[level]}/{capacity}")
    else:
        lines.extend(["Нет.", "Классовых ячеек нет."])
    lines.extend(["", "Расовое заклинание:"])
    if hero.racial_spell:
        lines.extend(
            [
                f"{hero.racial_spell.name} ({hero.racial_spell.level})",
                f"Применения: {hero.racial_uses}/{hero.max_racial_uses}",
            ]
        )
    else:
        lines.append("Нет.")
    canvas.lines(rect, lines)
    canvas.line(rect, rect.height - 3, "2: персонаж → заклинания")


def menu_entries(controller: Controller, width: int, height: int):
    """Share menu placement between plain text rendering and terminal styling."""
    first_y = height // 2 - len(MAIN_MENU) + 1
    for index, label in enumerate(MAIN_MENU):
        selected = index == controller.menu_index
        text = f"[ {label} ]" if selected else label
        yield (width - len(text)) // 2, first_y + index * 2, text, selected


def render_start_screen(canvas: Canvas, controller: Controller) -> None:
    def centered(y, text):
        canvas.text((canvas.width - len(text)) // 2, y, text)

    if controller.view is View.MAIN_MENU:
        centered(canvas.height // 2 - 7, "TUI DUNGEON")
        for x, y, text, _ in menu_entries(controller, canvas.width, canvas.height):
            canvas.text(x, y, text)
        centered(
            canvas.height - 3,
            "Стрелки / W/S: выбор | Enter: открыть | 1-5: быстрый выбор",
        )
        return
    if controller.view is View.LOAD:
        title = "Загрузить"
        lines = [
            "Нет доступного сохранения или файл повреждён.",
            "Enter: повторить загрузку",
        ]
        lines += textwrap.wrap(controller.message, canvas.width - 8)[:8]
    elif controller.view is View.SETTINGS:
        title = "Настройки"
        lines = [
            "Набор символов игры:",
            "",
            "[ 1) ASCII ]" if controller.symbols == "ascii" else "1) ASCII",
            "[ 2) Unicode ]" if controller.symbols == "unicode" else "2) Unicode",
            "",
            "1/2 или стрелки: изменить",
            "Выбор действует до выхода из приложения.",
        ]
    else:
        title = "Справка"
        lines = [
            "Создание: WASD / стрелки и Enter; H: подсказки",
            "Свет: факел/лампа через инвентарь → Enter → 1",
            "WASD: перемещение персонажа",
            "←/→ / Tab: вкладки | ↑↓/Enter: выбор вещей",
            "1: осмотр | 2: персонаж | 3: действия | 4: отдых",
            "Enter рядом с точкой интереса: взаимодействовать",
            "Alt+цифра / M: сохранение, загрузка, справка и выход",
            "←/→: страницы персонажа | F: поиск | G: подобрать",
            "Backspace: назад | Q: меню выхода",
            "",
            "Успешный шаг и ожидание: один ход и одна минута.",
            "Отдых: восемь часов, восстановление HP и заклинаний.",
            "Просмотр меню и вкладок не расходует игровое время.",
        ]
    centered(3, title)
    for row, text in enumerate(lines, 6):
        centered(row, text)
    centered(canvas.height - 3, "Backspace / Esc: назад")


def camera(controller, rect):
    state = controller.engine.state
    focus = (
        controller.look_position
        if controller.view in (View.LOOK, View.THROW)
        else state.position
    )
    vw, vh = rect.width - 2, rect.height - 3
    return (
        max(0, min(focus.x - vw // 2, state.dungeon.width - vw)),
        max(0, min(focus.y - vh // 2, state.dungeon.height - vh)),
    )


def spell_lines(controller):
    hero = controller.engine.state.hero
    lines = []
    for index, (spell, source) in enumerate(controller.spell_options):
        uses = (
            hero.racial_uses
            if source is SpellSource.RACIAL
            else hero.spell_slots.get(spell.level, 0)
        )
        label = "раса" if source is SpellSource.RACIAL else "класс"
        resource = "без ячейки" if spell.level == 0 else f"{uses} прим."
        lines.append(f"{index % PAGE_SIZE + 1}) {spell.name} ({label}, {resource})")
    return lines


def paginated(canvas, rect, lines, page, per_page=None):
    size = per_page or max(1, rect.height - 5)
    last = max(0, (len(lines) - 1) // size)
    page = min(page, last)
    canvas.lines(rect, lines[page * size : (page + 1) * size])
    if last:
        canvas.line(
            rect, rect.height - 5, f"Страница {page + 1}/{last + 1} | PgUp/PgDn"
        )


def render_sheet(canvas, rect, controller):
    hero = controller.engine.state.hero
    section = controller.sheet_section
    canvas.box(rect, f"Персонаж | {section + 1}/3 " + SHEET_SECTIONS[section])
    if section == 0:
        lines = hero_lines(hero)
        lines[3] = "Крадётся: да" if hero.sneaking else "Крадётся: нет"
        lines[10] = (
            f"КД: {hero.armor_class} | Скорость: {hero.speed / (2 if hero.sneaking else 1):g}"
        )
        left_width = (rect.width - 2) // 2
        size = max(1, rect.height - 5)
        last = max(0, (len(lines) - 1) // size)
        page = min(controller.page, last)
        for row, line in enumerate(lines[page * size : (page + 1) * size]):
            # Identity rows span the sheet; abilities and conditions sit side by side.
            canvas.text(
                rect.x + 1,
                rect.y + row + 1,
                line,
                rect.width - 2 if row < 4 else left_width,
            )
        x = rect.x + left_width + 2
        canvas.text(x, rect.y + 5, "Состояния (план):", left_width - 1)
        for row, line in enumerate(condition_lines(), rect.y + 6):
            canvas.text(x, row, line, left_width - 1)
        hint = f"PgUp/PgDn: текст {page + 1}/{last + 1} | --: не отслеживается"
    elif section == 1:
        render_inventory(canvas, rect, hero, controller.inventory, character=True)
        return
    else:
        lines = spell_lines(controller)
        lines = [
            ("> " if index == controller.spell_index else "  ") + line
            for index, line in enumerate(lines)
        ]
        paginated(
            canvas, rect, lines or ["Нет заклинаний."], controller.page, PAGE_SIZE
        )
        hint = "↑↓: выбор | Enter: применить | PgUp/PgDn"
    canvas.line(rect, rect.height - 4, hint)
    canvas.line(rect, rect.height - 3, "←/→: страницы | Backspace: карта")


def item_overlay_rect(width, height):
    return Rect(4, 2, width - 8, height - 4)


def render_item_overlay(canvas, controller):
    rect = item_overlay_rect(canvas.width, canvas.height)
    # An opaque window covers every underlying panel it intersects.
    for row in range(rect.y, rect.y + rect.height):
        canvas.text(rect.x, row, " " * rect.width)
    canvas.box(rect, "Осмотр предмета")
    lines = [
        part
        for line in item_details(controller.selected_item)
        for part in (textwrap.wrap(line, rect.width - 4) or [""])
    ]
    paginated(canvas, rect, lines, controller.detail_page)
    canvas.line(rect, rect.height - 4, "↑↓ / PgUp/PgDn: страницы")
    canvas.line(rect, rect.height - 3, "Enter / Backspace / Esc: закрыть")


def render(controller: Controller, width: int, height: int) -> list[str]:
    canvas = Canvas(width, height, controller.theme)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        canvas.text(0, 0, "Увеличьте окно до 80x24.")
        canvas.text(0, 1, f"Сейчас: {width}x{height}. Q: выход.")
        return canvas.finish()
    if controller.view in (View.MAIN_MENU, View.LOAD, View.SETTINGS, View.HELP):
        render_start_screen(canvas, controller)
        return canvas.finish()
    layout = Layout.for_size(width, height)
    if controller.view is View.CREATION:
        render_creation(canvas, layout, controller, hero_lines)
        return canvas.finish()
    state = controller.engine.state
    view = (
        controller.item_return_view
        if controller.view in (View.ITEM, View.ITEM_INSPECT)
        else controller.view
    )
    if view is View.INTERACTION:
        canvas.box(layout.main, "Взаимодействие | Backspace: назад")
        points = controller.engine.nearby_points()
        point = next((p for p in points if p.placement.id == controller.point_id), None)
        if point:
            lines = (
                [point.definition.name]
                + textwrap.wrap(point.challenge.text, layout.main.width - 4)
                + [""]
            )
            lines += [
                f"{i + 1}) {choice.text}"
                for i, choice in enumerate(
                    point.challenge.available_choices(state.hero)[:9]
                )
            ]
        else:
            lines = [f"{i + 1}) {p.definition.name}" for i, p in enumerate(points[:9])]
        canvas.lines(layout.main, lines)
    elif view is View.CHARACTER:
        render_sheet(canvas, layout.main, controller)
    elif view is View.INSPECT:
        canvas.box(layout.main, "Осмотр")
        wrapped = [
            part
            for line in controller.inspection
            for part in textwrap.wrap(line, layout.main.width - 4)
        ]
        paginated(canvas, layout.main, wrapped, controller.page)
        canvas.line(layout.main, layout.main.height - 4, "PgUp/PgDn: страницы")
        canvas.line(layout.main, layout.main.height - 3, "Backspace: назад")
    elif controller.action_menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
        canvas.box(
            layout.main,
            "Магия" if controller.action_menu is ActionMenu.MAGIC else "Выбор цели",
        )
        lines = (
            spell_lines(controller)
            if controller.action_menu is ActionMenu.MAGIC
            else [
                f"{i % PAGE_SIZE + 1}) {target.name} | HP {target.hp}/{target.max_hp}"
                for i, target in enumerate(controller.targets)
            ]
        )
        paginated(
            canvas,
            layout.main,
            lines or ["Нет доступных заклинаний или целей."],
            controller.page,
            PAGE_SIZE,
        )
    else:
        canvas.box(
            layout.main,
            f"Подземелье | HP {state.hero.hp}/{state.hero.max_hp} | Ход {state.turns} | "
            + (
                "Свет: "
                + ", ".join(
                    f"{i.fuel_minutes}м"
                    for i in state.hero.inventory
                    if i.equipped and i.shining
                )
                if any(i.equipped and i.shining for i in state.hero.inventory)
                else "Свет: нет"
            ),
        )
        viewport_width = layout.main.width - 2
        viewport_height = layout.main.height - 3  # Leave a line for movement help.
        camera_x, camera_y = camera(controller, layout.main)
        level = getattr(state, "level", None)
        cells = controller.engine.render_cells(
            (camera_x, camera_y, viewport_width, viewport_height)
        )
        for row in range(viewport_height):
            map_y = camera_y + row
            if map_y >= state.dungeon.height:
                break
            text = "".join(c.char if c else " " for c in cells[row])
            if not level or (
                level.ref == "base:dungeon" and not level.definition.decorations
            ):
                text = text.translate(
                    str.maketrans(
                        {
                            "#": controller.theme.wall,
                            ".": controller.theme.floor,
                            "g": controller.theme.monster,
                            "@": controller.theme.hero,
                        }
                    )
                )
            if map_y == state.position.y:
                hero_x = state.position.x - camera_x
                if 0 <= hero_x < len(text):
                    text = text[:hero_x] + controller.theme.hero + text[hero_x + 1 :]
            if view in (View.LOOK, View.THROW) and map_y == controller.look_position.y:
                cursor_x = controller.look_position.x - camera_x
                if 0 <= cursor_x < len(text):
                    text = text[:cursor_x] + "X" + text[cursor_x + 1 :]
            canvas.line(layout.main, row, text)
        canvas.line(
            layout.main,
            viewport_height,
            "WASD/стрелки: цель | Enter: бросить"
            if view is View.THROW
            else "WASD: курсор | Enter: осмотреть"
            if view in (View.LOOK, View.THROW)
            else "WASD: шаг | ↑↓/Enter: вещи | G: подобрать",
        )
    effective_meta = controller.alt_held or controller.action_menu is ActionMenu.META
    canvas.box(
        layout.actions,
        "Мета-действия | Alt / M" if effective_meta else "Действия | Backspace: назад",
    )
    if effective_meta or controller.action_menu is ActionMenu.EXIT:
        actions = action_lines(
            controller, ActionMenu.META if effective_meta else controller.action_menu
        )
    elif controller.view is View.ITEM:
        actions = [
            "1) Надеть/зажечь или снять/погасить"
            if controller.selected_item.definition.light
            else "1) Использовать (надеть/снять)",
            "2) Осмотреть | 3) Бросить",
            "4) Положить на землю",
            "Backspace: список предметов",
            controller.message,
        ]
    elif controller.view is View.THROW:
        actions = [
            f"Дальность: {controller.engine.throw_range} кл. (СИЛ мод. + 1)",
            "WASD / стрелки: клетка | Enter: бросить",
            "Backspace: отменить",
            "Бросок перемещает вещь; урона нет.",
            controller.message,
        ]
    elif controller.inventory.editing:
        actions = [
            "Введите название, тип или тег предмета.",
            "Enter: принять фильтр | Esc: отменить",
            "Backspace: удалить символ",
            "Поиск не расходует время.",
            controller.message,
        ]
    elif controller.view is View.INTERACTION:
        actions = ["Цифра: выбрать вариант", "Backspace: карта", "", controller.message]
    elif controller.view is View.LOOK:
        actions = [
            "WASD / стрелки: курсор",
            "Enter: осмотреть клетку",
            "Backspace: карта",
            "Осмотр не расходует время.",
            controller.message,
        ]
    elif controller.view in (View.CHARACTER, View.ITEM, View.INSPECT):
        actions = [
            "Команды внизу листа.",
            "Backspace: назад | Alt/M: мета",
            "",
            controller.message,
        ]
    else:
        actions = action_lines(controller)
    canvas.lines(layout.actions, actions)
    render_sidebar(
        canvas, layout.sidebar, state.hero, controller.sidebar_tab, controller
    )
    canvas.box(layout.status, "Время и средства")
    canvas.lines(
        layout.status,
        [
            f"День: {state.clock.day}",
            f"{state.clock.hour:02}:{state.clock.minute:02} | {state.clock.time_of_day}",
            f"Деньги: {state.hero.gold}",
            f"Опыт: {state.hero.experience}",
        ],
    )
    if controller.view is View.ITEM_INSPECT:
        render_item_overlay(canvas, controller)
    return canvas.finish()


def run(
    screen,
    seed: int | None = None,
    symbols: str = "ascii",
    catalog: ContentCatalog | None = None,
    map_ref=None,
    store=None,
    test_map: bool = False,
    save_path=None,
) -> None:
    import curses

    screen.keypad(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass  # Some terminals cannot hide their cursor.
    controller = Controller(
        seed,
        symbols=symbols,
        catalog=catalog,
        map_ref=map_ref,
        store=store,
        test_map=test_map,
        save_path=save_path,
    )
    colors = TerminalColors(curses)
    from .keyboard import TerminalKeyboard

    with TerminalKeyboard(screen, curses) as keyboard:
        dirty, last_size, last_blink = True, None, None
        while controller.running:
            height, width = screen.getmaxyx()
            blink = int(time.monotonic() * 2) % 2
            if dirty or last_size != (width, height):
                screen.erase()
                rows = render(controller, width, height)
                for y, line in enumerate(rows):
                    try:
                        screen.addnstr(y, 0, line, width)
                    except curses.error:
                        pass
                draw_colors(screen, controller, width, height, colors)
                draw_emphasis(screen, controller, width, height, rows, curses)
                screen.refresh()
                dirty, last_size = False, (width, height)
            elif controller.view in (View.LOOK, View.THROW) and blink != last_blink:
                # Cursor animation updates terminal attributes, not the game frame.
                draw_emphasis(screen, controller, width, height, rows, curses)
                screen.refresh()
            last_blink = blink
            event = keyboard.read()
            if event.alt is not None:
                controller.handle("alt_press" if event.alt else "alt_release")
                dirty = True
            if event.key == "resize":
                dirty = True
                continue
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                if event.key in ("q", "ctrl_c"):
                    controller.running = False
                continue
            if event.key:
                controller.handle(event.key)
                dirty = True


def draw_emphasis(screen, controller, width, height, rows, curses):
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return
    if controller.view is View.CREATION:
        for x, y, text, selected, limit in creation_button_entries(
            Layout.for_size(width, height), controller.creation
        ):
            if selected:
                try:
                    screen.addnstr(y, x, text, limit, curses.A_BOLD)
                except curses.error:
                    pass
    if controller.view is View.MAIN_MENU:
        for x, y, text, selected in menu_entries(controller, width, height):
            if selected:
                try:
                    screen.addnstr(y, x, text, len(text), curses.A_BOLD)
                except curses.error:
                    pass
    if controller.view in (View.CHARACTER, View.ITEM, View.ITEM_INSPECT):
        labels = [ability.value for ability in Ability] + [
            "Раса:",
            "Класс:",
            "Здоровье:",
            "КД:",
            "Вес:",
            "Предыстория:",
            "Надето:",
            "Стойкость:",
            "Заряды:",
            "Руки:",
            "Свет:",
            "Топливо:",
            "Крадётся:",
            "Состояния (план):",
            "Тип снаряжения:",
            "Урон:",
            "Слот:",
            "Теги:",
            "Особые свойства и эффекты:",
        ]
        rect = (
            item_overlay_rect(width, height)
            if controller.view is View.ITEM_INSPECT
            else Layout.for_size(width, height).main
        )
        for y in range(rect.y + 1, rect.y + rect.height - 1):
            for label in labels:
                x = rows[y].find(label, rect.x + 1, rect.x + rect.width - 1)
                if x >= 0:
                    try:
                        screen.addnstr(y, x, label, len(label), curses.A_BOLD)
                    except curses.error:
                        pass
    if controller.view is not View.ITEM_INSPECT:
        layout = Layout.for_size(width, height)
        for rect in (layout.main, layout.sidebar):
            for y in range(rect.y + 1, rect.y + rect.height - 1):
                text = rows[y][rect.x + 1 : rect.x + rect.width - 1]
                if text.startswith(">"):
                    try:
                        screen.addnstr(y, rect.x + 1, text, len(text), curses.A_BOLD)
                    except curses.error:
                        pass
    if controller.view in (View.LOOK, View.THROW):
        rect = Layout.for_size(width, height).main
        cx, cy = camera(controller, rect)
        x, y = (
            controller.look_position.x - cx + rect.x + 1,
            controller.look_position.y - cy + rect.y + 1,
        )
        try:
            attribute = curses.A_BOLD | (
                curses.A_REVERSE if int(time.monotonic() * 2) % 2 else 0
            )
            screen.addstr(y, x, "X", attribute)
        except curses.error:
            pass


class TerminalColors:
    """Allocate only used fg/bg combinations, with monochrome fallback."""

    def __init__(self, curses):
        self.curses = curses
        self.pairs = {}
        self.enabled = False
        self.default = -1
        if curses.has_colors():
            try:
                curses.start_color()
                try:
                    curses.use_default_colors()
                except curses.error:
                    self.default = 0
                self.enabled = True
            except curses.error:
                pass

    def attribute(self, foreground, background):
        if not self.enabled:
            return 0
        foreground = (
            foreground
            if foreground < self.curses.COLORS
            else foreground % min(16, self.curses.COLORS)
        )
        background = (
            self.default if background is None else background % self.curses.COLORS
        )
        key = (foreground, background)
        if key not in self.pairs:
            pair = len(self.pairs) + 1
            if pair >= self.curses.COLOR_PAIRS:
                return 0
            try:
                self.curses.init_pair(pair, *key)
            except self.curses.error:
                return 0
            self.pairs[key] = pair
        return self.curses.color_pair(self.pairs[key])


def draw_colors(screen, controller, width, height, colors):
    if (
        not controller.engine
        or controller.view not in (View.EXPLORE, View.LOOK, View.THROW)
        or controller.action_menu in (ActionMenu.MAGIC, ActionMenu.TARGET)
        or width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):
        return
    state = controller.engine.state
    level = getattr(state, "level", None)
    rect = Layout.for_size(width, height).main
    vw, vh = rect.width - 2, rect.height - 3
    cx, cy = camera(controller, rect)
    cells = controller.engine.render_cells((cx, cy, vw, vh))
    lighting = controller.engine.lighting
    for y in range(min(vh, state.dungeon.height - cy)):
        for x in range(min(vw, state.dungeon.width - cx)):
            cell = cells[y][x]
            if cell:
                char = (
                    "X"
                    if controller.view in (View.LOOK, View.THROW)
                    and (cx + x, cy + y)
                    == (controller.look_position.x, controller.look_position.y)
                    else cell.char
                )
                if not level or (
                    level.ref == "base:dungeon" and not level.definition.decorations
                ):
                    char = char.translate(
                        str.maketrans(
                            {
                                "#": controller.theme.wall,
                                ".": controller.theme.floor,
                                "@": controller.theme.hero,
                                "g": controller.theme.monster,
                            }
                        )
                    )
                try:
                    screen.addstr(
                        rect.y + 1 + y,
                        rect.x + 1 + x,
                        char,
                        colors.attribute(cell.foreground, cell.background)
                        | (
                            colors.curses.A_DIM
                            if lighting.cells[cy + y][cx + x] == 1
                            else 0
                        ),
                    )
                except colors.curses.error:
                    pass
