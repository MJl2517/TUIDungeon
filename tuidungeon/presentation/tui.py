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
from .menus import ActionMenu, SHEET_SECTIONS, PAGE_SIZE, action_lines
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
        self.engine: Engine | None = None
        self.view = View.MAIN_MENU
        self.menu_index = 0
        self.spells_tab = False
        self.running = True
        self.message = "Добро пожаловать в TUI Dungeon!"
        if test_map:
            from ..application.factories import create_test_hero

            hero = create_test_hero(self.creation.catalog)
            self.engine = Engine.new_game(hero, self.game_rng, self.map_ref, self.store)
            self.view = View.EXPLORE
            self.message = "Тест карты. WASD: шаг. Стрелки: вкладки."

    def open_interaction(self):
        points = self.engine.nearby_points()
        if points:
            self.point_id = points[0].placement.id if len(points) == 1 else None
            self.view = View.INTERACTION
            self.action_menu = ActionMenu.ROOT

    @property
    def spell_options(self):
        hero = self.engine.state.hero
        return [(s, SpellSource.CLASS) for s in hero.class_spells] + (
            [(hero.racial_spell, SpellSource.RACIAL)] if hero.racial_spell else []
        )

    @property
    def targets(self):
        return [p.monster for p in self.engine.state.monsters if p.monster.hp > 0]

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
        if key in ("alt_press", "alt_release"):
            self.alt_held = key == "alt_press"
            return
        if key == "ctrl_c":
            self.running = False
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
            elif key in "123456789" and len(key) == 1:
                hero = self.creation.select(int(key))
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
        if key in ("left", "up", "right", "down", "tab") and self.view is not View.LOOK:
            self.spells_tab = (
                not self.spells_tab if key == "tab" else key in ("right", "down")
            )
            return
        if self.view is View.LOOK:
            if key in ("backspace", "escape"):
                self.view = View.EXPLORE
            elif key == "enter":
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
                    if 0 <= p.x < dungeon.width and 0 <= p.y < dungeon.height:
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
                    if point and index < len(point.challenge.choices):
                        self.message = self.engine.interact(
                            self.point_id, point.challenge.choices[index].id
                        ).message
                        self.view, self.point_id = View.EXPLORE, None
            return
        if self.view is View.ITEM:
            if key in ("backspace", "escape"):
                self.view = View.CHARACTER
            elif key in ("pageup", "pagedown"):
                self.detail_page = max(
                    0, self.detail_page + (1 if key == "pagedown" else -1)
                )
            elif key == "1":
                item = self.selected_item
                self.message = self.engine.manage_equipment(
                    item, not item.equipped
                ).message
            elif key == "2":
                self.message = self.engine.use_item(self.selected_item).message
            return
        if self.view is View.CHARACTER:
            if key in ("backspace", "escape"):
                self.view = View.EXPLORE
            elif key in ("[", "]"):
                self.sheet_section = (
                    self.sheet_section + (1 if key == "]" else -1)
                ) % len(SHEET_SECTIONS)
                self.page = 0
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
            elif key in "123456" and len(key) == 1:
                index = self.page * PAGE_SIZE + int(key) - 1
                if self.sheet_section == 1 and index < len(
                    self.engine.state.hero.inventory
                ):
                    self.selected_item = self.engine.state.hero.inventory[index]
                    self.detail_page = 0
                    self.view = View.ITEM
                elif self.sheet_section == 2:
                    self.choose_spell(index)
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
                self.message = self.engine.apply(action).message

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
            f"Вес: {hero.carried_weight:g}/{hero.max_carry_weight:g} кг"
            + (" (перегрузка)" if hero.overloaded else ""),
        ]
    )
    if hero.background:
        lines.append(f"Предыстория: {hero.background.name}")
    return lines


def render_creation(canvas: Canvas, layout: Layout, controller: Controller) -> None:
    creation = controller.creation
    canvas.box(layout.main, "Создание героя")
    canvas.box(layout.actions, "Выбор цифрами | Backspace: назад | Q: выход")
    canvas.box(layout.sidebar, "Правила")
    canvas.box(layout.status, "Новая игра")
    canvas.lines(layout.status, ["День: 1", "08:00 | Утро", "Деньги: 0", "Опыт: 0"])
    rules = [
        "Шесть характеристик: 4d6,",
        "меньший кубик убирается.",
        "Можно перебросить набор.",
        "",
        "Бонусы учитываются после",
        "распределения значений.",
    ]
    if creation.race:
        rules.extend(["", f"Раса: {creation.race.value}", creation.race.description])
    if creation.character_class:
        rules.extend(
            [
                "",
                f"Класс: {creation.character_class.value}",
                f"Базовое HP: {creation.character_class.hit_points}",
            ]
        )
    canvas.lines(layout.sidebar, rules)
    if creation.step in (CreationStep.RACE, CreationStep.CLASS):
        lines = [
            "Выберите расу:"
            if creation.step is CreationStep.RACE
            else "Выберите класс:",
            "",
        ]
        for number, definition in enumerate(creation.visible_options, 1):
            lines.extend(
                [f"{number}) {definition.name}", f"   {definition.description}"]
            )
        actions = [f"1-{len(creation.visible_options)}) Выбрать", "Backspace) Назад"]
        if creation.page_count > 1:
            actions.extend(
                [
                    "8) Предыдущая страница",
                    "9) Следующая страница",
                    f"Страница {creation.selection_page + 1}/{creation.page_count}",
                ]
            )
    elif creation.step is CreationStep.ROLL:
        lines = ["Результаты 4d6 без меньшего кубика:", ""]
        for number, roll in enumerate(creation.rolls, 1):
            dice_text = " ".join(str(value) for value in roll.dice)
            lines.append(
                f"{number}) [{dice_text}] убран {roll.discarded} => {roll.total}"
            )
        lines.extend(
            ["", "Дальше вы распределите результаты", "по шести характеристикам."]
        )
        actions = ["1) Перебросить весь набор", "2) Распределить результаты"]
    elif creation.step is CreationStep.DISTRIBUTE:
        ability = list(Ability)[len(creation.assignments)]
        lines = [
            f"Назначьте значение: {ability.value}",
            "Выберите номер свободного результата.",
            "",
        ]
        for index, roll in enumerate(creation.rolls):
            assigned = index in creation.assignments
            label = "уже назначен" if assigned else "свободен"
            lines.append(f"{index + 1}) {roll.total:2} - {label}")
        lines.append("")
        for ability, index in zip(Ability, creation.assignments):
            lines.append(f"{ability.value}: {creation.rolls[index].total}")
        actions = [
            "1-6) Назначить свободный результат",
            "Backspace) Отменить последнее назначение",
            "Бонус человека применяется после выбора.",
        ]
    else:
        lines = hero_lines(creation.preview())
        lines.extend(["", "Герой готов. Бонусы расы уже учтены."])
        actions = [
            "1) Начать исследование",
            "2) Перебросить характеристики",
            "Backspace) Исправить распределение",
        ]
    canvas.lines(layout.main, lines)
    canvas.lines(layout.actions, actions)


def render_sidebar(canvas: Canvas, rect: Rect, hero: Hero, spells_tab: bool) -> None:
    canvas.box(rect, "Заклинания [<- ->]" if spells_tab else "Инвентарь [<- ->]")
    if not spells_tab:
        canvas.lines(
            rect,
            ["Стартовое снаряжение:", ""]
            + [f"- {item.name}" for item in hero.inventory]
            + ["", "Управление: 2) Персонаж, затем [/]."],
        )
        return
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
    lines.extend(["", "Управление: 2) Персонаж, затем [/]."])
    canvas.lines(rect, lines)


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
            "Цифры: создание героя и выбор действий",
            "WASD: перемещение персонажа",
            "Стрелки / Tab: инвентарь и заклинания",
            "1: осмотр | 2: персонаж | 3: действия | 4: отдых",
            "Enter рядом с точкой интереса: взаимодействовать",
            "Alt+цифра / M: сохранение, загрузка, справка и выход",
            "[/]: раздел листа | PgUp/PgDn: страница",
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
    focus = controller.look_position if controller.view is View.LOOK else state.position
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
    canvas.box(rect, "Персонаж | " + SHEET_SECTIONS[controller.sheet_section])
    if controller.sheet_section == 0:
        lines = hero_lines(hero)
        lines[3] = "Крадётся: да" if hero.sneaking else "Крадётся: нет"
        # Statistics fit without truncation; extra background goes on the next page.
        paginated(canvas, rect, lines, controller.page)
        hint = "PgUp/PgDn: страницы"
    elif controller.sheet_section == 1:
        lines = [
            f"{i % PAGE_SIZE + 1}) {item.name}" + (" [надето]" if item.equipped else "")
            for i, item in enumerate(hero.inventory)
        ]
        paginated(canvas, rect, lines or ["Нет предметов."], controller.page, PAGE_SIZE)
        hint = "1-6: предмет | PgUp/PgDn: страницы"
    else:
        paginated(
            canvas,
            rect,
            spell_lines(controller) or ["Нет заклинаний."],
            controller.page,
            PAGE_SIZE,
        )
        hint = "1-6: применить | PgUp/PgDn: страницы"
    canvas.line(rect, rect.height - 4, hint)
    canvas.line(rect, rect.height - 3, "[/]: раздел | Backspace: карта")


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
        render_creation(canvas, layout, controller)
        return canvas.finish()
    state = controller.engine.state
    if controller.view is View.INTERACTION:
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
                for i, choice in enumerate(point.challenge.choices[:9])
            ]
        else:
            lines = [f"{i + 1}) {p.definition.name}" for i, p in enumerate(points[:9])]
        canvas.lines(layout.main, lines)
    elif controller.view is View.CHARACTER:
        render_sheet(canvas, layout.main, controller)
    elif controller.view in (View.INSPECT, View.ITEM):
        canvas.box(
            layout.main, "Осмотр" if controller.view is View.INSPECT else "Предмет"
        )
        if controller.view is View.ITEM:
            item = controller.selected_item
            lines = [
                item.name,
                item.definition.description,
                f"Вес: {item.weight:g} кг",
                f"Надето: {'да' if item.equipped else 'нет'}",
                f"Стойкость: {item.durability if item.durability is not None else 'не ломается'}",
                f"Заряды: {item.charges if item.charges is not None else 'без ограничения'}",
            ]
            footer = "1: надеть/снять | 2: применить"
        else:
            lines, footer = controller.inspection, "PgUp/PgDn: страницы"
        wrapped = [
            part
            for line in lines
            for part in textwrap.wrap(line, layout.main.width - 4)
        ]
        paginated(
            canvas,
            layout.main,
            wrapped,
            controller.detail_page if controller.view is View.ITEM else controller.page,
        )
        canvas.line(layout.main, layout.main.height - 4, footer)
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
            f"Подземелье | HP {state.hero.hp}/{state.hero.max_hp} | Ход {state.turns}",
        )
        viewport_width = layout.main.width - 2
        viewport_height = layout.main.height - 3  # Leave a line for movement help.
        camera_x, camera_y = camera(controller, layout.main)
        level = getattr(state, "level", None)
        cells = level.render_cells(state) if level else None
        for row in range(viewport_height):
            map_y = camera_y + row
            if map_y >= state.dungeon.height:
                break
            if level:
                text = "".join(
                    c.char if c else " "
                    for c in cells[map_y][camera_x : camera_x + viewport_width]
                )
            else:
                text = state.dungeon.rows[map_y][camera_x : camera_x + viewport_width]
            if not level or (
                level.ref == "base:dungeon" and not level.definition.decorations
            ):
                text = text.translate(
                    str.maketrans(
                        {"#": controller.theme.wall, ".": controller.theme.floor}
                    )
                )
            for placement in state.monsters:
                monster_x = placement.position.x - camera_x
                if (
                    not level
                    and placement.monster.hp > 0
                    and placement.position.y == map_y
                    and 0 <= monster_x < len(text)
                ):
                    text = (
                        text[:monster_x]
                        + controller.theme.monster
                        + text[monster_x + 1 :]
                    )
            if map_y == state.position.y:
                hero_x = state.position.x - camera_x
                if 0 <= hero_x < len(text):
                    text = text[:hero_x] + controller.theme.hero + text[hero_x + 1 :]
            if controller.view is View.LOOK and map_y == controller.look_position.y:
                cursor_x = controller.look_position.x - camera_x
                if 0 <= cursor_x < len(text):
                    text = text[:cursor_x] + "X" + text[cursor_x + 1 :]
            canvas.line(layout.main, row, text)
        canvas.line(
            layout.main,
            viewport_height,
            "WASD: курсор | Enter: осмотреть"
            if controller.view is View.LOOK
            else "WASD: шаг | Стрелки: вкладки | Alt/M: мета",
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
    render_sidebar(canvas, layout.sidebar, state.hero, controller.spells_tab)
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
        while controller.running:
            height, width = screen.getmaxyx()
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
            event = keyboard.read()
            if event.alt is not None:
                controller.handle("alt_press" if event.alt else "alt_release")
            if event.key == "resize":
                continue
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                if event.key in ("q", "ctrl_c"):
                    controller.running = False
                continue
            if event.key:
                controller.handle(event.key)


def draw_emphasis(screen, controller, width, height, rows, curses):
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return
    if controller.view is View.MAIN_MENU:
        for x, y, text, selected in menu_entries(controller, width, height):
            if selected:
                try:
                    screen.addnstr(y, x, text, len(text), curses.A_BOLD)
                except curses.error:
                    pass
    if controller.view in (View.CHARACTER, View.ITEM):
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
            "Крадётся:",
        ]
        rect = Layout.for_size(width, height).main
        for y in range(rect.y + 1, rect.y + rect.height - 1):
            for label in labels:
                x = rows[y].find(label, rect.x + 1, rect.x + rect.width - 1)
                if x >= 0:
                    try:
                        screen.addnstr(y, x, label, len(label), curses.A_BOLD)
                    except curses.error:
                        pass
    if controller.view is View.LOOK:
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
        or controller.view not in (View.EXPLORE, View.LOOK)
        or controller.action_menu in (ActionMenu.MAGIC, ActionMenu.TARGET)
        or width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):
        return
    state = controller.engine.state
    level = getattr(state, "level", None)
    if not level:
        return
    rect = Layout.for_size(width, height).main
    vw, vh = rect.width - 2, rect.height - 3
    cx, cy = camera(controller, rect)
    cells = level.render_cells(state)
    for y in range(min(vh, state.dungeon.height - cy)):
        for x in range(min(vw, state.dungeon.width - cx)):
            cell = cells[cy + y][cx + x]
            if cell:
                char = (
                    "X"
                    if controller.view is View.LOOK
                    and (cx + x, cy + y)
                    == (controller.look_position.x, controller.look_position.y)
                    else cell.char
                )
                if level.ref == "base:dungeon" and not level.definition.decorations:
                    char = char.translate(
                        str.maketrans(
                            {"#": controller.theme.wall, ".": controller.theme.floor}
                        )
                    )
                try:
                    screen.addstr(
                        rect.y + 1 + y,
                        rect.x + 1 + x,
                        char,
                        colors.attribute(cell.foreground, cell.background),
                    )
                except colors.curses.error:
                    pass
