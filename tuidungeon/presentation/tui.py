"""Input controller and pure text renderer; only run() touches curses."""

from dataclasses import dataclass
from enum import Enum, auto
import random
import re
import textwrap
import time

from ..application.creation import CharacterCreation, CreationStep
from ..application.engine import Action, Engine
from ..domain.actors import Hero
from ..domain.collections import EventLog
from ..domain.rules import Ability, Dice
from ..content.catalog import ContentCatalog
from .symbols import GlyphTheme
from .tilesets import MAP_STYLES
from .menus import ActionMenu, SidebarTab, SHEET_SECTIONS, PAGE_SIZE, action_lines
from .crafting import CraftBrowser, craft_layout, craft_click
from .inventory import InventoryBrowser, render_inventory, item_details
from .storage import StorageBrowser, storage_layout, storage_click
from .conditions import condition_lines
from .creation import render_creation, creation_button_entries
from ..domain.actions import SpellSource
from ..world.maps import Position
from ..application.saves import SaveRepository


MIN_WIDTH = 80
MIN_HEIGHT = 24
MAIN_MENU = ("Новая игра", "Загрузить", "Настройки", "Справка", "Выйти")
NOTEBOOK_SECTIONS = ("Квесты", "Записи", "Рецепты", "Бестиарий", "Личный дневник")


def settings_lines(controller):
    lines = [
        "Набор символов:",
        "[1) ASCII]" if controller.symbols == "ascii" else "1) ASCII",
        "[2) Unicode]" if controller.symbols == "unicode" else "2) Unicode",
        "1/2 или ←/→: изменить символы",
        "",
        "Оформление карты:",
    ]
    for number, (style, label) in enumerate(MAP_STYLES.items(), 3):
        text = f"{number}) {label}"
        lines.append(f"[{text}]" if controller.map_style == style else text)
    lines += [
        "3/4: выбрать; оформление запоминается."
        if controller.windowed
        else "Рисунки доступны только в оконном режиме.",
        "Шрифт интерфейса остаётся текстовым.",
    ]
    return lines


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
    JOURNAL = auto()
    NOTEBOOK = auto()
    READING = auto()
    ITEM = auto()
    ITEM_INSPECT = auto()
    LIQUID = auto()
    THROW = auto()
    IGNITE = auto()
    STORAGE = auto()
    CRAFT = auto()
    BUILD = auto()
    SPELL_TARGET = auto()
    HAND_TARGET = auto()


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
        test_profile: str | None = None,
        test_class: str | None = None,
    ):
        self.map_ref, self.store = map_ref, store
        self.catalog = catalog
        self.action_menu = ActionMenu.ROOT
        self.dialog_index = 0
        self.menu_return = ActionMenu.ROOT
        self.magic_return = ActionMenu.ROOT
        self.exit_return = ActionMenu.ROOT
        self.return_view = View.MAIN_MENU
        self.sheet_section = 0
        self.page = 0
        self.look_position = None
        self.look_camera = None
        self.inspection = []
        self.detail_page = 0
        self.selected_item = None
        self.inventory = InventoryBrowser()
        self.inventory_focus = False
        self.item_return_view = View.EXPLORE
        self.spell_index = 0
        self.selected_spell = None
        self.spell_option = None
        self.saves = (
            SaveRepository(save_path) if save_path is not None else SaveRepository()
        )
        self.point_id = None
        self.storage = StorageBrowser()
        self.craft = CraftBrowser()
        self.rng = random.Random(seed)
        self.game_rng = random.Random(seed)
        self.theme = GlyphTheme.named(symbols)
        self.symbols = symbols
        self.map_style = "text"
        self.windowed = False
        self.creation = CharacterCreation(Dice(self.rng), catalog)
        self.creation_help_page = 0
        self.creation_help_pages = 1
        self.engine: Engine | None = None
        self.view = View.MAIN_MENU
        self.menu_index = 0
        self.sidebar_tab = SidebarTab.INVENTORY
        self.running = True
        self.logs = EventLog(limit=200)
        self.log_page = 0
        self.log_pages = 1
        self.log_return_view = View.EXPLORE
        self.notebook_return_view = View.EXPLORE
        self.notebook_section = None
        self.records_page = 0
        self.reading = None
        self.craft_return_view = View.EXPLORE
        self.reading_return_view = View.EXPLORE
        self.reading_page = 0
        self.reading_pages = 1
        self._log_engine = None
        self._last_log_event = None
        self.feedback = None
        self.message = "Добро пожаловать в TUI Dungeon!"
        if test_map or test_profile == "wizard":
            from ..application.factories import create_test_hero, create_test_wizard

            hero = (
                create_test_wizard(self.creation.catalog)
                if test_profile == "wizard"
                else create_test_hero(self.creation.catalog, test_class)
            )
            self.engine = Engine.new_game(hero, self.game_rng, self.map_ref, self.store)
            self.view = View.EXPLORE
            self.message = "Тест карты. ↑↓/Enter: вещи | F: поиск."

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value):
        self._message = value
        if not self.engine:
            return
        if self._log_engine is not self.engine:
            self.logs.clear()
            self._last_log_event = None
            self._log_engine = self.engine
        events = self.engine.events
        start = next(
            (i + 1 for i, event in enumerate(events) if event is self._last_log_event),
            0,
        )
        for event in events[start:]:
            text = event.get("message", "")
            if event.get("kind") == "light_denied":
                self.feedback = text
            if text and text not in value:
                self.logs.append({"message": text})
        self._last_log_event = events[-1] if events else None
        if value == "Вы делаете шаг.":
            if self.logs and self.logs[-1].get("steps"):
                entry = self.logs[-1]
                entry["steps"] += 1
                entry["message"] = f"Вы сделали шаг ({entry['steps']})."
            else:
                self.logs.append({"message": "Вы сделали шаг.", "steps": 1})
        elif value:
            self.logs.append({"message": value})

    @property
    def record_entries(self):
        return sorted(
            self.engine.read_notes.values(),
            key=lambda note: (
                note.text.title.casefold(),
                note.location.casefold(),
                note.map_ref,
                note.placement_id,
            ),
        )

    @property
    def records_pages(self):
        return max(1, (len(self.record_entries) + PAGE_SIZE - 1) // PAGE_SIZE)

    def open_reading(self, note):
        self.reading = note
        self.reading_return_view = self.view
        self.reading_page = 0
        self.view = View.READING

    world_target = None

    def target_furniture(self, kind, identifier):
        self.world_target = (kind, identifier)
        self.look_position = self.engine.state.position
        self.view = View.LOOK
        self.action_menu = ActionMenu.ROOT
        self.message = (
            "Выберите клетку вокруг героя; Enter — вылить, Esc — отмена."
            if kind == "splash"
            else "Выберите свободную клетку вокруг героя; Enter — поставить, Esc — отмена."
        )

    def can_target_cell(self, position):
        if self.world_target:
            hero = self.engine.state.position
            return (
                max(abs(position.x - hero.x), abs(position.y - hero.y)) <= 1
                and self.engine._inside(position)
                and self.engine.lighting.at(position)
                and self.engine._clear_throw_path(position, allow_target_door=True)
            )
        return self.engine.can_look_at(position)

    def open_storage(self, identifier):
        result = self.engine.open_container(identifier)
        self.message = result.message
        if result.performed:
            self.storage.open(identifier)
            self.view = View.STORAGE

    def open_interaction(self):
        points = self.engine.nearby_points()
        if points:
            self.point_id = points[0].placement.id if len(points) == 1 else None
            self.view = View.INTERACTION
            self.page = 0
            self.action_menu = ActionMenu.ROOT
            if (
                self.point_id
                and self.engine.storage_at(self.point_id)
                and not any(
                    o.placement.id == self.point_id
                    for o in self.engine.nearby_world_objects()
                )
            ):
                self.open_storage(self.point_id)

    @property
    def spells_tab(self):
        """Compatibility with callers of the original two-tab controller."""
        return self.sidebar_tab is SidebarTab.SPELLS

    @spells_tab.setter
    def spells_tab(self, value):
        self.sidebar_tab = SidebarTab.SPELLS if value else SidebarTab.INVENTORY

    @property
    def spell_options(self):
        return self.engine.spell_options()

    @property
    def targets(self):
        light = self.engine.lighting
        return [
            p.monster
            for p in self.engine.state.monsters
            if p.monster.hp > 0 and light.at(p.position)
        ]

    def open_magic(self):
        self.magic_return = (
            self.action_menu
            if self.action_menu is ActionMenu.ACTIONS
            else ActionMenu.ROOT
        )
        self.view = View.EXPLORE
        self.action_menu = ActionMenu.MAGIC
        self.page = 0

    @property
    def spell_items(self):
        if not self.selected_spell:
            return []
        return self.engine.spell_item_targets(self.selected_spell[0])

    def choose_spell(self, index):
        options = self.spell_options
        if not 0 <= index < len(options):
            return
        self.selected_spell = options[index]
        spell = self.selected_spell[0]
        self.spell_option = None
        self.view = View.EXPLORE
        if "exploration" not in spell.modes:
            self.message = "Этот заговор доступен в песочнице будущего боя."
        elif spell.target == "item":
            self.action_menu = ActionMenu.SPELL_ITEM
            self.page = 0
        elif spell.world_effect in ("tricks", "elementalism", "illusion"):
            self.action_menu = ActionMenu.SPELL_OPTION
        elif spell.target == "cell":
            self.open_spell_target()
        elif spell.target == "other":
            self.action_menu = ActionMenu.TARGET
            self.page = 0
        else:
            self.cast_selected()

    @property
    def spell_variants(self):
        if self.selected_spell and self.selected_spell[0].world_effect == "illusion":
            return (("mark", "Неподвижная иллюзия"), ("noise", "Звук"))
        return (
            ("ignite", "Поджечь"),
            ("extinguish", "Погасить"),
            ("mark", "Метка"),
            ("noise", "Звук"),
        )

    def open_spell_target(self):
        self.look_position = self.engine.state.position
        self.action_menu = ActionMenu.ROOT
        self.view = View.SPELL_TARGET

    def cast_selected(self, target=None):
        spell, source = self.selected_spell
        result = self.engine.cast_spell(
            spell.id, source, target, option=self.spell_option
        )
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
        self.craft = CraftBrowser()
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
            self.exit_return = ActionMenu.META
            self.action_menu = ActionMenu.EXIT
        elif key in ("backspace", "escape"):
            self.action_menu = self.menu_return

    def handle(self, key: str) -> None:
        key = key.lower()
        if self.feedback:
            if key in ("escape", "backspace", "enter", "space", " ", "1"):
                self.feedback = None
            return
        if key.startswith("alt"):
            return
        before = (
            self.view,
            self.action_menu,
            self.point_id,
            self.page,
            self.notebook_section,
            self.records_page,
        )
        if not self.inventory.editing:
            options = popup_content(self)[2]
            if options and key in ("up", "down", "enter"):
                if key != "enter":
                    self.dialog_index = (
                        self.dialog_index + (1 if key == "down" else -1)
                    ) % len(options)
                    return
                key = str(self.dialog_index + 1)
        self._handle(key)
        if before != (
            self.view,
            self.action_menu,
            self.point_id,
            self.page,
            self.notebook_section,
            self.records_page,
        ):
            self.dialog_index = 0

    def _handle(self, key: str) -> None:
        if key == "ctrl_c":
            self.running = False
            return
        if self.view is View.CRAFT:
            self.craft.handle(self, key)
            return
        if self.view is View.BUILD:
            if key in ("escape", "backspace", "b"):
                self.view = View.EXPLORE
            return
        if self.engine and self.engine.active_craft:
            if key in ("right", "space", " "):
                self.message = self.engine.advance_craft().message
            elif key in ("escape", "backspace"):
                self.message = self.engine.pause_craft().message
            elif key in ("c", "m", "i", "b", "q", "j", "l"):
                self.message = self.engine.pause_craft().message
                self._handle(key)
            return
        if self.view is View.READING:
            if key in ("backspace", "escape"):
                self.view = self.reading_return_view
            elif key in ("left", "right"):
                self.reading_page = max(
                    0,
                    min(
                        self.reading_pages - 1,
                        self.reading_page + (1 if key == "right" else -1),
                    ),
                )
            return
        if self.view is View.NOTEBOOK and key != "l":
            if key == "j":
                self.view = self.notebook_return_view
            elif key in ("backspace", "escape"):
                if self.notebook_section is None:
                    self.view = self.notebook_return_view
                else:
                    self.notebook_section = None
            elif self.notebook_section is None:
                if key in "12345" and len(key) == 1:
                    self.notebook_section = int(key) - 1
                    self.records_page = 0
                    if self.notebook_section == 2:
                        self.notebook_section = None
                        self.craft.open()
                        self.craft_return_view = View.NOTEBOOK
                        self.view = View.CRAFT
                        self.page = 0
            elif self.notebook_section == 1:
                if key in ("pageup", "pagedown"):
                    self.records_page = max(
                        0,
                        min(
                            self.records_pages - 1,
                            self.records_page + (1 if key == "pagedown" else -1),
                        ),
                    )
                elif key in "123456" and len(key) == 1:
                    index = self.records_page * PAGE_SIZE + int(key) - 1
                    if index < len(self.record_entries):
                        self.open_reading(self.record_entries[index])
            return
        if self.view is View.JOURNAL:
            if key in ("l", "backspace", "escape"):
                self.view = self.log_return_view
            elif key in ("up", "pageup"):
                self.log_page = min(self.log_pages - 1, self.log_page + 1)
            elif key in ("down", "pagedown"):
                self.log_page = max(0, self.log_page - 1)
            elif key in ("home", "end"):
                self.log_page = self.log_pages - 1 if key == "home" else 0
            return
        if (
            key == "j"
            and self.engine
            and self.view not in (View.MAIN_MENU, View.CREATION)
            and not self.inventory.editing
            and not self.engine.lockpick_attempt
        ):
            self.notebook_return_view = self.view
            self.notebook_section = None
            self.records_page = 0
            self.view = View.NOTEBOOK
            return
        if (
            key == "l"
            and self.engine
            and self.view not in (View.MAIN_MENU, View.CREATION)
            and not self.inventory.editing
            and not self.engine.lockpick_attempt
        ):
            self.log_return_view = self.view
            self.log_page = 0
            self.view = View.JOURNAL
            return
        if self.view is View.STORAGE:
            self.storage.handle(self, key)
            return
        if self.engine and self.engine.lockpick_attempt:
            if key in (" ", "space"):
                self.message = self.engine.advance_lockpick().message
            elif key in ("backspace", "escape"):
                self.message = self.engine.cancel_lockpick().message
            self.view = View.EXPLORE
            self.action_menu = ActionMenu.ROOT
            self.point_id = None
            return
        if self.inventory.editing:
            self.inventory.search_key(key)
            return
        if key == "q":
            if self.engine and self.view not in (View.MAIN_MENU, View.CREATION):
                if self.view in (View.HELP, View.SETTINGS):
                    self.view = self.return_view
                self.exit_return = self.action_menu
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
                if key in ("up", "down", "w", "s", "tab"):
                    self.dialog_index = (
                        self.dialog_index + (-1 if key in ("up", "w") else 1)
                    ) % 4
                elif key in ("left", "right"):
                    self.symbols = "unicode" if self.symbols == "ascii" else "ascii"
                if key == "enter":
                    key = str(self.dialog_index + 1)
                if key in ("1", "2"):
                    self.symbols = "ascii" if key == "1" else "unicode"
                elif key == "3":
                    self.map_style = "text"
                elif key == "4" and self.windowed:
                    self.map_style = "kenney_1bit"
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
                    self.message = "WASD: шаг. Esc: меню | I: инвентарь | M: магия | B: строительство."
            return
        if self.action_menu is ActionMenu.META:
            self.meta_action(key)
            return
        if self.action_menu is ActionMenu.EXIT:
            if key == "1":
                self.view = View.MAIN_MENU
                self.action_menu = ActionMenu.ROOT
                self.menu_index = 0
            elif key == "2":
                self.running = False
            elif key in ("backspace", "escape"):
                self.action_menu = self.exit_return
            return
        if self.view in (
            View.LOOK,
            View.THROW,
            View.IGNITE,
            View.SPELL_TARGET,
            View.HAND_TARGET,
        ):
            if key in ("backspace", "escape"):
                self.world_target = None
                if self.view in (View.SPELL_TARGET, View.HAND_TARGET):
                    self.action_menu = (
                        ActionMenu.MAGIC
                        if self.view is View.SPELL_TARGET
                        else ActionMenu.ROOT
                    )
                    self.view = View.EXPLORE
                else:
                    self.view = View.EXPLORE if self.view is View.LOOK else View.ITEM
            elif key == "enter":
                if self.world_target and self.view is View.LOOK:
                    kind, identifier = self.world_target
                    result = (
                        self.engine.water_action(
                            identifier, "splash", position=self.look_position
                        )
                        if kind == "splash"
                        else self.engine.move_furniture(identifier, self.look_position)
                        if kind == "move"
                        else self.engine.place_furniture(
                            self.selected_item, self.look_position
                        )
                    )
                    self.message = result.message
                    if result.performed:
                        self.world_target = None
                        self.view = View.EXPLORE
                    return
                if self.view is View.SPELL_TARGET:
                    self.cast_selected(self.look_position)
                elif self.view is View.HAND_TARGET:
                    result = self.engine.use_magic_hand(self.look_position)
                    self.message = result.message
                    if result.performed:
                        self.view = View.EXPLORE
                elif self.view in (View.THROW, View.IGNITE):
                    result = (
                        self.engine.ignite_cell(self.selected_item, self.look_position)
                        if self.view is View.IGNITE
                        else self.engine.place_item(
                            self.selected_item, self.look_position, throwing=True
                        )
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
                    self.look_camera = None
                    dx, dy = directions[key]
                    p = Position(self.look_position.x + dx, self.look_position.y + dy)
                    dungeon = self.engine.state.dungeon
                    in_range = (
                        abs(p.x - self.engine.state.position.x)
                        + abs(p.y - self.engine.state.position.y)
                        <= self.engine.throw_range
                    )
                    if self.view in (View.SPELL_TARGET, View.HAND_TARGET):
                        reach = (
                            self.selected_spell[0].range
                            if self.view is View.SPELL_TARGET
                            else self.engine.magic_hand_range
                        )
                        in_range = (
                            max(
                                abs(p.x - self.engine.state.position.x),
                                abs(p.y - self.engine.state.position.y),
                            )
                            <= reach
                        )
                    if self.view is View.IGNITE:
                        in_range = (
                            max(
                                abs(p.x - self.engine.state.position.x),
                                abs(p.y - self.engine.state.position.y),
                            )
                            <= 1
                        )
                    if (
                        0 <= p.x < dungeon.width
                        and 0 <= p.y < dungeon.height
                        and (
                            self.can_target_cell(p)
                            if self.view is View.LOOK
                            else in_range
                        )
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
            elif key in ("pageup", "pagedown"):
                self.page = max(0, self.page + (1 if key == "pagedown" else -1))
            elif key in "123456789" and len(key) == 1:
                index = int(key) - 1
                if self.point_id is None:
                    if index < len(points):
                        self.point_id = points[index].placement.id
                        if self.engine.storage_at(self.point_id) and not any(
                            o.placement.id == self.point_id
                            for o in self.engine.nearby_world_objects()
                        ):
                            self.open_storage(self.point_id)
                    self.page = 0
                else:
                    point = next(
                        (p for p in points if p.placement.id == self.point_id), None
                    )
                    choices = (
                        point.available_choices(self.engine.state.hero) if point else ()
                    )
                    if index < len(choices):
                        choice_id = choices[index].id
                        if choice_id == "move":
                            self.target_furniture("move", self.point_id)
                            return
                        if choice_id == "open_storage":
                            self.open_storage(self.point_id)
                            return
                        result = self.engine.interact(self.point_id, choice_id)
                        self.message = result.message
                        if (
                            choice_id == "read_note"
                            and result.performed
                            and point.definition.reading
                        ):
                            note = self.engine.read_notes[
                                self.engine.state.level.ref, self.point_id
                            ]
                            self.open_reading(note)
                        else:
                            self.view, self.point_id = View.EXPLORE, None
            return
        if self.view is View.LIQUID:
            choices = self.engine.vessel_choices(self.selected_item)
            if key in ("escape", "backspace"):
                self.view = View.ITEM
            elif key in ("pageup", "pagedown"):
                self.page = max(
                    0,
                    min(
                        (len(choices) - 1) // 9,
                        self.page + (1 if key == "pagedown" else -1),
                    ),
                )
            elif key in "123456789" and len(key) == 1:
                index = self.page * 9 + int(key) - 1
                if index < len(choices):
                    choice = choices[index]
                    if choice["action"] == "splash":
                        self.target_furniture("splash", self.selected_item.instance_id)
                        return
                    result = self.engine.water_action(
                        self.selected_item.instance_id,
                        choice["action"],
                        target=choice.get("target"),
                        position=Position(choice["x"], choice["y"])
                        if "x" in choice
                        else None,
                    )
                    self.message = result.message
                    if result.performed:
                        self.view = View.ITEM
            return
        if self.view is View.ITEM:
            if key in ("backspace", "escape"):
                self.view = self.item_return_view
            elif key == "1":
                item = self.selected_item
                if item.furniture:
                    self.target_furniture("place", item.instance_id)
                    return
                if item.work:
                    self.craft.open(item)
                    self.craft_return_view = View.EXPLORE
                    self.view = View.CRAFT
                    self.page = 0
                    return
                if item.definition.cast_spell:
                    index = next(
                        (
                            n
                            for n, (_, source) in enumerate(self.spell_options)
                            if source == "scroll:" + item.instance_id
                        ),
                        None,
                    )
                    if index is not None:
                        self.choose_spell(index)
                    return
                result = (
                    self.engine.manage_equipment(
                        item,
                        not item.equipped
                        or bool(item.definition.light and not item.shining),
                    )
                    if item.definition.slot
                    else self.engine.use_item(item)
                )
                self.message = result.message
                if result.performed and item.definition.reading:
                    note = self.engine.read_notes.get(
                        (
                            self.engine.state.level.ref,
                            "item_" + item.instance_id.replace("-", "_"),
                        )
                    )
                    if note:
                        self.open_reading(note)
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
            elif (
                key == ("6" if self.selected_item.ignition_source else "5")
                and self.selected_item.definition.light
                and self.selected_item.equipped
                and not self.selected_item.shining
            ):
                self.message = self.engine.manage_equipment(
                    self.selected_item, False
                ).message
            elif key == "5" and self.selected_item.definition.vessel:
                self.view, self.page = View.LIQUID, 0
            elif key == "5" and self.selected_item.ignition_source:
                self.look_position = self.engine.state.position
                self.view = View.IGNITE
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
            if key == "escape":
                self.menu_return = ActionMenu.ROOT
                self.action_menu = ActionMenu.META
                return
            if key == "i":
                self.sheet_section, self.page = 1, 0
                self.sidebar_tab = SidebarTab.INVENTORY
                self.inventory_focus = True
                self.view = View.CHARACTER
                return
            if key == "m":
                self.open_magic()
                return
            if key == "b":
                self.view = View.BUILD
                self.page = 0
                return
            if key == "c":
                self.craft.open()
                self.craft_return_view = View.EXPLORE
                self.craft_return_view = View.EXPLORE
                self.view = View.CRAFT
                self.page = 0
                return
            if key == "z":
                self.message = self.engine.toggle_sneaking().message
                return
            if key in ("left", "right", "tab"):
                self.sidebar_tab = self.sidebar_tab.next(-1 if key == "left" else 1)
                self.inventory_focus = False
                return
            if self.sidebar_tab is SidebarTab.INVENTORY and self.inventory_key(key):
                return
            if key == "g":
                self.message = self.engine.pickup_item().message
                return
        if self.action_menu in (ActionMenu.SPELL_ITEM, ActionMenu.SPELL_OPTION):
            if key in ("backspace", "escape"):
                self.action_menu = ActionMenu.MAGIC
                self.page = 0
            elif (
                key in ("pageup", "pagedown")
                and self.action_menu is ActionMenu.SPELL_ITEM
            ):
                self.change_page(key, len(self.spell_items))
            elif key in "123456" and len(key) == 1:
                index = int(key) - 1
                if self.action_menu is ActionMenu.SPELL_OPTION and index < len(
                    self.spell_variants
                ):
                    self.spell_option = self.spell_variants[index][0]
                    self.open_spell_target()
                elif self.action_menu is ActionMenu.SPELL_ITEM:
                    items = self.spell_items
                    index += self.page * PAGE_SIZE
                    if index < len(items):
                        self.cast_selected(items[index])
            return
        if self.action_menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
            options = (
                self.spell_options
                if self.action_menu is ActionMenu.MAGIC
                else self.targets
            )
            if key in ("backspace", "escape"):
                self.action_menu = (
                    self.magic_return
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
            if key in ("1", "z"):
                self.message = self.engine.toggle_sneaking().message
            elif key == "2":
                self.open_magic()
            elif key == "3":
                self.message = self.engine.apply(Action.WAIT).message
            elif key == "4" and self.engine.active_hand:
                self.look_position = self.engine.state.position
                self.view = View.HAND_TARGET
                self.action_menu = ActionMenu.ROOT
            elif key == "6" or key == "5" and not self.engine.active_hand:
                self.message = self.engine.discover_traps().message
            elif key == "5" or key == "4" and not self.engine.active_hand:
                self.craft.open()
                self.craft_return_view = View.EXPLORE
                self.action_menu = ActionMenu.ROOT
                self.view = View.CRAFT
                self.page = 0
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
        elif key in ("1", "e"):
            self.look_camera = None
            self.look_position = self.engine.state.position
            self.view = View.LOOK
            self.inventory_focus = False
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
        self.dialog_index = 0
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
    def for_size(cls, width: int, height: int, *, creation=False) -> "Layout":
        right_width = 28
        bottom_height = 7
        left_width = width - right_width
        top_height = height - bottom_height
        actions_width = left_width if creation else max(38, left_width // 2)
        return cls(
            Rect(0, 0, left_width, top_height),
            Rect(0, top_height, actions_width, bottom_height),
            Rect(left_width, 0, right_width, top_height),
            Rect(actions_width, top_height, width - actions_width, bottom_height),
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
        f"Здоровье: {hero.hp}/{hero.max_hp} | Опыт: {hero.experience}",
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
    lines.extend(
        [
            f"Заговоры: {hero.cantrip_uses}/{hero.max_cantrip_uses}",
            "Концентрация: " + ("да" if hero.concentration_id else "нет"),
            "",
            "Расовое заклинание:",
        ]
    )
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
        lines = settings_lines(controller)
    else:
        title = "Справка"
        lines = [
            "Создание: WASD / стрелки и Enter; H: подсказки",
            "Свет: факел/лампа через инвентарь → Enter → 1",
            "WASD: перемещение персонажа",
            "←/→ / Tab: вкладки | ↑↓/Enter: выбор вещей",
            "1/E: осмотр | 2: персонаж | 3: действия | 4: отдых",
            "Z: скрытность | J: журнал | L: логи",
            "Enter рядом с точкой интереса: взаимодействовать",
            "Esc: сохранение, загрузка, справка и выход",
            "I: инвентарь | M: заклинания | B: строительство",
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
        if background_view(controller)
        in (View.LOOK, View.THROW, View.IGNITE, View.SPELL_TARGET, View.HAND_TARGET)
        else state.position
    )
    vw, vh = rect.width - 2, rect.height - 3
    return (
        max(0, min(focus.x - vw // 2, state.dungeon.width - vw)),
        max(0, min(focus.y - vh // 2, state.dungeon.height - vh)),
    )


def map_symbols(controller, text):
    level = getattr(controller.engine.state, "level", None)
    if not level or (level.ref == "base:dungeon" and not level.definition.decorations):
        return text.translate(
            str.maketrans(
                {
                    "#": controller.theme.wall,
                    ".": controller.theme.floor,
                    "@": controller.theme.hero,
                    "g": controller.theme.monster,
                }
            )
        )
    return text


def spell_lines(controller):
    hero = controller.engine.state.hero
    lines = []
    for index, (spell, source) in enumerate(controller.spell_options):
        uses = (
            hero.racial_uses
            if source is SpellSource.RACIAL
            else hero.spell_slots.get(spell.level, 0)
        )
        scroll = controller.engine.scroll_item(source)
        label = (
            "свиток" if scroll else "раса" if source is SpellSource.RACIAL else "класс"
        )
        resource = (
            f"{scroll.charges} прим."
            if scroll
            else (
                f"{hero.cantrip_uses}/{hero.max_cantrip_uses} заряд."
                if spell.level == 0
                else f"{uses} прим."
            )
        )
        lines.append(
            f"{index % PAGE_SIZE + 1}) {spell.name} ({label}, {resource})"
            + (" [бой]" if "exploration" not in spell.modes else "")
        )
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


def background_view(controller):
    view = (
        controller.log_return_view
        if controller.view is View.JOURNAL
        else controller.view
    )
    if view is View.READING:
        view = controller.reading_return_view
    if view is View.NOTEBOOK:
        view = controller.notebook_return_view
    if (
        view in (View.HELP, View.SETTINGS)
        and controller.return_view is not View.MAIN_MENU
    ):
        view = controller.return_view
    if view in (View.ITEM, View.ITEM_INSPECT, View.LIQUID, View.THROW, View.IGNITE):
        return (
            view if view in (View.THROW, View.IGNITE) else controller.item_return_view
        )
    if view is View.INSPECT:
        return View.LOOK
    return (
        View.EXPLORE
        if view in (View.INTERACTION, View.STORAGE, View.CRAFT, View.BUILD)
        else view
    )


def popup_content(controller):
    if controller.feedback:
        return "Недостаточно света", [controller.feedback], ["Понятно"]
    if controller.engine and controller.engine.lockpick_attempt:
        return "", [], []
    """The same choices drive keyboard navigation, mouse clicks and both renderers."""
    if not controller.engine or controller.view in (View.MAIN_MENU, View.CREATION):
        return "", [], []
    if controller.view is View.STORAGE:
        return "Контейнер", [], []
    view, menu = controller.view, controller.action_menu
    if view is View.CRAFT:
        return controller.craft.content(controller)
    if view is View.BUILD:
        return (
            "Строительство",
            [
                "Здесь появятся доступные постройки.",
                "Механика строительства будет добавлена позже.",
            ],
            [],
        )
    if view is View.READING:
        return controller.reading.text.title, controller.reading.text.pages, []
    if view is View.NOTEBOOK:
        section = controller.notebook_section
        if section is None:
            return "Журнал", [], list(NOTEBOOK_SECTIONS)
        title = NOTEBOOK_SECTIONS[section]
        if section == 1:
            entries = controller.record_entries
            start = controller.records_page * PAGE_SIZE
            return (
                title,
                [f"Прочитано записей: {len(entries)}"]
                if entries
                else ["Вы ещё не читали записок."],
                [
                    f"{note.text.title} — {note.location}"
                    for note in entries[start : start + PAGE_SIZE]
                ],
            )
        return title, ["В этом разделе пока нет записей."], []
    if view is View.JOURNAL:
        return (
            "Журнал событий",
            [entry["message"] for entry in controller.logs] or ["Журнал пуст."],
            [],
        )
    if view in (View.HELP, View.SETTINGS) and controller.return_view is View.MAIN_MENU:
        return "", [], []
    if view is View.HELP:
        return (
            "Справка",
            [
                "WASD: шаг | 1/E: осмотр | 2: персонаж",
                "Z: скрытность | J: журнал | L: логи",
                "3: действия | 4: отдых | C: крафт | Esc: меню",
                "Enter рядом с объектом: взаимодействовать",
                "I: инвентарь | M: заклинания | B: строительство",
                "↑↓: выбор вещи | Enter / щелчок: предмет",
                "F: поиск | G: подобрать | ←/→: вкладки",
                "В окне: +/- или колесо мыши — масштаб карты",
                "В диалоге: ↑↓ и Enter, либо цифра варианта",
                "Меню и осмотр не расходуют игровое время.",
                "Факел горит час. Успешный шаг занимает минуту.",
            ],
            [],
        )
    if view is View.SETTINGS:
        return (
            "Настройки",
            [
                "1/2: символы | 3/4: оформление карты",
                "Рисунки доступны в оконном режиме.",
                "Оформление карты запоминается между запусками.",
            ],
            [
                "ASCII" + (" ✓" if controller.symbols == "ascii" else ""),
                "Unicode" + (" ✓" if controller.symbols == "unicode" else ""),
                *(
                    label + (" ✓" if controller.map_style == style else "")
                    for style, label in MAP_STYLES.items()
                ),
            ],
        )
    if menu is ActionMenu.META:
        return (
            "Игровое меню",
            [controller.message],
            ["Сохранить", "Загрузить", "Справка", "Выход", "Настройки"],
        )
    if menu is ActionMenu.EXIT:
        return (
            "Выход",
            ["Несохранённые изменения будут потеряны."],
            ["В главное меню", "Выйти из игры"],
        )
    if view is View.ITEM and controller.selected_item:
        item = controller.selected_item
        use = (
            (
                "Снять / погасить"
                if item.equipped and item.shining
                else "Заправить и зажечь"
                if item.definition.light.fuel_tag and item.fuel_minutes <= 0
                else "Зажечь"
                if item.equipped
                else "Надеть / зажечь"
            )
            if item.definition.light
            else ("Снять" if item.equipped else "Надеть")
            if item.definition.slot
            else "Использовать"
        )
        return (
            item.name,
            [
                f"Вес: {item.weight:g} кг" + (" | Надето" if item.equipped else ""),
                controller.message,
            ],
            [
                "Поставить мебель"
                if item.furniture
                else "Работа с заготовкой"
                if item.work
                else use,
                "Осмотреть",
                "Бросить",
                "Положить на землю",
            ]
            + (
                ["Действия с жидкостью"]
                if item.definition.vessel
                else ["Поджечь соседнюю клетку"]
                if item.ignition_source
                else []
            )
            + (
                ["Снять из руки"]
                if item.definition.light and item.equipped and not item.shining
                else []
            ),
        )
    if view is View.LIQUID and controller.selected_item:
        choices = controller.engine.vessel_choices(controller.selected_item)
        return (
            "Действия с жидкостью",
            [
                controller.selected_item.name,
                controller.message,
                f"Страница {controller.page + 1}/{max(1, (len(choices) + 8) // 9)} · PgUp/PgDn",
            ],
            [
                c["label"]
                for c in choices[controller.page * 9 : controller.page * 9 + 9]
            ],
        )
    if view is View.ITEM_INSPECT and controller.selected_item:
        return "Осмотр предмета", item_details(controller.selected_item), []
    if view is View.INSPECT:
        return "Осмотр", controller.inspection, []
    if view is View.INTERACTION:
        points = controller.engine.nearby_points()
        hero = controller.engine.state.position

        def name(point):
            dx = (point.placement.x > hero.x) - (point.placement.x < hero.x)
            dy = (point.placement.y > hero.y) - (point.placement.y < hero.y)
            arrow = (("↖", "↑", "↗"), ("←", "•", "→"), ("↙", "↓", "↘"))[dy + 1][dx + 1]
            return f"[{arrow}] {point.definition.name}"

        point = next((p for p in points if p.placement.id == controller.point_id), None)
        if point:
            return (
                name(point),
                point.text.splitlines(),
                [
                    choice.text
                    for choice in point.available_choices(controller.engine.state.hero)[
                        :9
                    ]
                ],
            )
        return "Взаимодействие", [], [name(p) for p in points[:9]]
    if menu is ActionMenu.SPELL_ITEM:
        spell = controller.selected_spell[0]
        items = controller.spell_items[
            controller.page * PAGE_SIZE : (controller.page + 1) * PAGE_SIZE
        ]
        return (
            spell.name,
            [
                spell.description,
                "Выбор предмета бесплатный. PgUp/PgDn: страницы",
                (
                    "Нет повреждённых предметов с прочностью в инвентаре."
                    if spell.world_effect == "repair"
                    else "Нет подходящих предметов в инвентаре."
                )
                if not items
                else "",
                controller.message,
            ],
            [
                f"{i.name} ({i.durability}/{i.definition.durability})"
                if i.durability is not None
                else i.name
                for i in items
            ],
        )
    if menu is ActionMenu.SPELL_OPTION:
        return (
            controller.selected_spell[0].name,
            ["Выберите эффект, затем клетку. AI на звук пока не реагирует."],
            [label for _, label in controller.spell_variants],
        )
    if menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
        options = (
            spell_lines(controller)
            if menu is ActionMenu.MAGIC
            else [
                f"{i % PAGE_SIZE + 1}) {target.name} | HP {target.hp}/{target.max_hp}"
                for i, target in enumerate(controller.targets)
            ]
        )
        visible = options[
            controller.page * PAGE_SIZE : (controller.page + 1) * PAGE_SIZE
        ]
        body = (
            [controller.message, "PgUp/PgDn: страницы"]
            if visible
            else ["Нет доступных заклинаний или целей."]
        )
        return (
            "Заклинания" if menu is ActionMenu.MAGIC else "Выбор цели",
            body,
            [line.partition(") ")[2] for line in visible],
        )
    if menu in (ActionMenu.ACTIONS, ActionMenu.REST):
        lines = action_lines(controller)
        count = (
            (4 if controller.engine.active_hand else 3)
            if menu is ActionMenu.ACTIONS
            else 2
        )
        return (
            "Действия" if menu is ActionMenu.ACTIONS else "Отдых",
            [controller.message],
            [line.partition(") ")[2] for line in lines[:count]]
            + (
                ["Изготовить [C]", "Искать ловушки"]
                if menu is ActionMenu.ACTIONS
                else []
            ),
        )
    return "", [], []


def item_overlay_rect(width, height):
    w, h = min(72, width - 6), min(24, height - 4)
    return Rect((width - w) // 2, (height - h) // 2, w, h)


def popup_layout(controller, width, height):
    if (
        not controller.feedback
        and controller.view is View.CRAFT
        and width >= MIN_WIDTH
        and height >= MIN_HEIGHT
    ):
        return craft_layout(controller, width, height)[:4]
    if (
        not controller.feedback
        and controller.view is View.STORAGE
        and width >= MIN_WIDTH
        and height >= MIN_HEIGHT
    ):
        title, rect, rows, _ = storage_layout(controller, width, height)
        return title, rect, rows, []
    title, body, options = popup_content(controller)
    if not title or width < MIN_WIDTH or height < MIN_HEIGHT:
        return None
    preferred_width = (
        72
        if controller.view
        in (
            View.INTERACTION,
            View.INSPECT,
            View.ITEM_INSPECT,
            View.LIQUID,
            View.HELP,
            View.JOURNAL,
            View.NOTEBOOK,
            View.READING,
            View.CRAFT,
        )
        else 52
    )
    w, max_height = min(preferred_width, width - 6), min(24, height - 4)
    lines = [part for line in body for part in (textwrap.wrap(line, w - 4) or [""])]
    choice_lines, starts = [], []
    for i, label in enumerate(options):
        starts.append(len(choice_lines))
        marker = ">" if i == controller.dialog_index else " "
        choice_lines.extend(
            textwrap.wrap(
                f"{marker} {i + 1}) {label}", w - 4, subsequent_indent="     "
            )
        )
    capacity = max_height - 4
    option_size = min(len(choice_lines), max(1, capacity - min(3, len(lines))))
    body_size = max(1, capacity - option_size - bool(options))
    page = (
        controller.detail_page
        if controller.view is View.ITEM_INSPECT
        else controller.page
        if controller.view in (View.INSPECT, View.INTERACTION, View.CRAFT)
        else 0
    )
    last = max(0, (len(lines) - 1) // body_size)
    page = min(page, last)
    if controller.view is View.READING:
        pages = []
        for text in body:
            wrapped = [
                part
                for paragraph in text.splitlines()
                for part in (textwrap.wrap(paragraph, w - 4) or [""])
            ]
            pages.extend(
                wrapped[start : start + body_size]
                for start in range(0, len(wrapped), body_size)
            )
        controller.reading_pages = len(pages)
        controller.reading_page = min(controller.reading_page, len(pages) - 1)
        page = controller.reading_page
        rows = pages[page]
    elif controller.view is View.JOURNAL:
        controller.log_pages = last + 1
        controller.log_page = min(controller.log_page, last)
        page = last - controller.log_page
        end = len(lines) - controller.log_page * body_size
        rows = lines[max(0, end - body_size) : end]
    else:
        rows = lines[page * body_size : (page + 1) * body_size]
    hits = []
    if options:
        rows.append("")
        selected = starts[min(controller.dialog_index, len(starts) - 1)]
        scroll = max(0, min(selected, len(choice_lines) - option_size))
        first = len(rows)
        rows.extend(choice_lines[scroll : scroll + option_size])
        hits = [
            (i, first + start - scroll)
            for i, start in enumerate(starts)
            if scroll <= start < scroll + option_size
        ]
    if controller.feedback:
        hint = "Enter / Space / Esc: закрыть"
    elif controller.view is View.READING:
        hint = f"←/→: страница {page + 1}/{controller.reading_pages} | Esc: назад"
    elif controller.view is View.NOTEBOOK and controller.notebook_section == 1:
        hint = f"↑↓ / Enter | PgUp/PgDn: {controller.records_page + 1}/{controller.records_pages} | Esc: назад"
    elif controller.view is View.JOURNAL:
        hint = f"↑↓ / PgUp/PgDn: {page + 1}/{last + 1} | L/Esc: закрыть"
    elif last:
        hint = f"PgUp/PgDn: {page + 1}/{last + 1} | Esc: назад"
    else:
        hint = (
            "↑↓: выбор | Enter: выполнить | Esc: назад"
            if options
            else "Esc / Backspace: назад"
        )
    h = min(max_height, len(rows) + 4)
    rect = Rect((width - w) // 2, (height - h) // 2, w, h)
    rows += [""] * max(0, h - 3 - len(rows))
    rows.append(hint)
    return title, rect, rows, hits


def handle_click(controller, x, y, width, height):
    if (
        not controller.engine
        or controller.inventory.editing
        or width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):
        return False
    if not controller.feedback and controller.view is View.CRAFT:
        return craft_click(controller, x, y, width, height)
    if not controller.feedback and controller.view is View.STORAGE:
        return storage_click(controller, x, y, width, height)
    popup = popup_layout(controller, width, height)
    if popup:
        _, rect, _, hits = popup
        if rect.x < x < rect.x + rect.width - 1:
            row = y - rect.y - 1
            for offset, (i, first) in enumerate(hits):
                stop = (
                    hits[offset + 1][1] if offset + 1 < len(hits) else rect.height - 4
                )
                if first <= row < stop:
                    controller.dialog_index = i
                    controller.handle(str(i + 1))
                    return True
        return False
    if (
        controller.view is not View.EXPLORE
        or controller.action_menu is not ActionMenu.ROOT
    ):
        return False
    rect = Layout.for_size(width, height).sidebar
    if not (
        rect.x < x < rect.x + rect.width - 1 and rect.y <= y < rect.y + rect.height
    ):
        return False
    if y == rect.y:
        controller.handle("right")
        return True
    if controller.sidebar_tab is SidebarTab.SPELLS:
        controller.open_magic()
        controller.dialog_index = 0
        return True
    if controller.sidebar_tab is not SidebarTab.INVENTORY:
        return False
    visible = controller.inventory.window(controller.engine.state.hero, rect.height - 9)
    row = y - rect.y - 2
    if 0 <= row < len(visible):
        controller.inventory.selected = visible[row][0]
        controller.inventory_focus = True
        controller.handle("enter")
        return True
    return False


def render_popup(canvas, controller):
    popup = popup_layout(controller, canvas.width, canvas.height)
    if not popup:
        return
    title, rect, rows, _ = popup
    for y in range(rect.y + 1, rect.y + rect.height + 1):
        canvas.text(rect.x + 1, y, " " * rect.width)
    for y in range(rect.y, rect.y + rect.height):
        canvas.text(rect.x, y, " " * rect.width)
    canvas.box(rect, title)
    for y, line in enumerate(rows[: rect.height - 2]):
        canvas.text(rect.x + 2, rect.y + y + 1, line, rect.width - 4)


def map_status(controller):
    state = controller.engine.state
    lights = ", ".join(
        f"{i.fuel_minutes}м" for i in state.hero.inventory if i.equipped and i.shining
    )
    light = lights or ("магия" if controller.engine.magic_lights() else "нет")
    return f"Ход {state.turns} | Свет: {light}"


def render_info(canvas, controller, rect):
    if (
        background_view(controller) is View.LOOK
        and controller.look_position is not None
    ):
        position = controller.look_position
        details = controller.engine.inspect_cell(position)
        lines = details[1:]
        if lines and lines[0].startswith("Освещение:"):
            # Reorder only information approved by the engine, never query the
            # physical lighting of a hidden cell from the HUD.
            count = 2 if len(lines) > 1 and lines[1].startswith("Тусклый свет") else 1
            lines = lines[count:] + lines[:count]
        canvas.box(rect, f"Осмотр ({position.x}, {position.y})")
        wrapped = [
            part for line in lines for part in textwrap.wrap(line, rect.width - 2)
        ]
        canvas.lines(rect, wrapped[: rect.height - 3])
        canvas.line(rect, rect.height - 3, "Клик / Enter: подробнее")
    else:
        canvas.box(rect, "Журнал событий")
        lines = [
            part
            for event in controller.logs[-20:]
            for part in textwrap.wrap(event["message"], rect.width - 2)
        ]
        canvas.lines(rect, lines[-(rect.height - 2) :])


def render(controller: Controller, width: int, height: int) -> list[str]:
    canvas = Canvas(width, height, controller.theme)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        canvas.text(0, 0, "Увеличьте окно до 80x24.")
        canvas.text(0, 1, f"Сейчас: {width}x{height}. Q: выход.")
        return canvas.finish()
    if (
        controller.view in (View.MAIN_MENU, View.LOAD, View.SETTINGS, View.HELP)
        and not popup_content(controller)[0]
    ):
        render_start_screen(canvas, controller)
        return canvas.finish()
    layout = Layout.for_size(width, height, creation=controller.view is View.CREATION)
    if controller.view is View.CREATION:
        render_creation(canvas, layout, controller, hero_lines)
        return canvas.finish()
    state = controller.engine.state
    view = background_view(controller)
    if view is View.CHARACTER:
        render_sheet(canvas, layout.main, controller)
    else:
        clock = f"День: {state.clock.day} | {state.clock.hour:02}:{state.clock.minute:02} {state.clock.time_of_day}"
        title = f"Подземелье | HP {state.hero.hp}/{state.hero.max_hp}"
        canvas.box(layout.main, title[: max(0, layout.main.width - len(clock) - 7)])
        canvas.text(
            layout.main.x + layout.main.width - len(clock) - 3,
            layout.main.y,
            " " + clock + " ",
        )
        viewport_width = layout.main.width - 2
        viewport_height = layout.main.height - 3  # Leave a line for movement help.
        camera_x, camera_y = camera(controller, layout.main)
        cells = controller.engine.render_cells(
            (camera_x, camera_y, viewport_width, viewport_height)
        )
        for row in range(viewport_height):
            map_y = camera_y + row
            if map_y >= state.dungeon.height:
                break
            text = "".join(c.char if c else " " for c in cells[row])
            text = map_symbols(controller, text)
            if map_y == state.position.y:
                hero_x = state.position.x - camera_x
                if 0 <= hero_x < len(text):
                    text = text[:hero_x] + controller.theme.hero + text[hero_x + 1 :]
            if (
                view
                in (
                    View.LOOK,
                    View.THROW,
                    View.IGNITE,
                    View.SPELL_TARGET,
                    View.HAND_TARGET,
                )
                and map_y == controller.look_position.y
            ):
                cursor_x = controller.look_position.x - camera_x
                if 0 <= cursor_x < len(text):
                    text = text[:cursor_x] + "X" + text[cursor_x + 1 :]
            canvas.line(layout.main, row, text)
        canvas.line(layout.main, viewport_height, map_status(controller))
    canvas.box(
        layout.actions,
        "Изготовление"
        if controller.engine.active_craft
        else "Взлом замка"
        if controller.engine.lockpick_attempt
        else "Действия | Esc: меню",
    )
    if controller.view in (View.CRAFT, View.STORAGE) or popup_content(controller)[0]:
        actions = action_lines(controller, ActionMenu.ROOT)
    elif controller.view in (View.SPELL_TARGET, View.HAND_TARGET):
        actions = [
            "Выберите видимую клетку в пределах дальности.",
            "WASD / стрелки: цель | Enter: применить",
            "Backspace: отменить; выбор бесплатный.",
            "Действие руки: ход, без нового заряда."
            if controller.view is View.HAND_TARGET
            else "Применение: один ход и заряд заговора.",
            controller.message,
        ]
    elif controller.view is View.IGNITE:
        actions = [
            "Поджог: одна из 8 соседних клеток.",
            "WASD / стрелки: цель | Enter: поджечь",
            "Backspace: отменить; выбор цели бесплатный.",
            "Дерево: 5 HP/мин. Масло: +5 урона сразу.",
            controller.message,
        ]
    elif controller.view is View.THROW:
        actions = [
            f"Дальность: {controller.engine.throw_range} кл. (СИЛ мод. + 1)",
            "WASD / стрелки: клетка | Enter: бросить",
            "Backspace: отменить",
            "Масло: покрытие 5 ходов. Кислота: 2d6.",
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
            "Enter: вылить"
            if controller.world_target and controller.world_target[0] == "splash"
            else "Enter: поставить"
            if controller.world_target
            else "Enter: осмотреть клетку",
            "Backspace: карта",
            "Дальность: 1 кл. вокруг героя"
            if controller.world_target
            else f"Дальность: {controller.engine.look_range} кл. (МДР)",
            controller.message,
        ]
    elif controller.view in (View.CHARACTER, View.ITEM, View.INSPECT):
        actions = [
            "Команды внизу листа.",
            "Esc / Backspace: назад",
            "",
            controller.message,
        ]
    else:
        actions = action_lines(controller)
    actions = [
        part
        for line in actions[:-1]
        for part in (textwrap.wrap(line, layout.actions.width - 2) or [""])
    ]
    canvas.lines(layout.actions, actions)
    render_sidebar(
        canvas, layout.sidebar, state.hero, controller.sidebar_tab, controller
    )
    render_info(canvas, controller, layout.status)
    render_popup(canvas, controller)
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
    test_profile: str | None = None,
    test_class: str | None = None,
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
        test_profile=test_profile,
        test_class=test_class,
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
                draw_emphasis(screen, controller, width, height, rows, curses, colors)
                screen.refresh()
                dirty, last_size = False, (width, height)
            elif (
                controller.view
                in (
                    View.LOOK,
                    View.THROW,
                    View.IGNITE,
                    View.SPELL_TARGET,
                    View.HAND_TARGET,
                )
                and blink != last_blink
            ):
                # Cursor animation updates terminal attributes, not the game frame.
                draw_emphasis(screen, controller, width, height, rows, curses, colors)
                screen.refresh()
            last_blink = blink
            event = keyboard.read()
            if event.alt:
                continue
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


def draw_emphasis(screen, controller, width, height, rows, curses, colors=None):
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return
    if controller.view is View.CREATION:
        for x, y, text, selected, limit in creation_button_entries(
            Layout.for_size(width, height, creation=True), controller.creation
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
            popup_layout(controller, width, height)[1]
            if popup_layout(controller, width, height)
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
    if controller.view in (
        View.LOOK,
        View.THROW,
        View.IGNITE,
        View.SPELL_TARGET,
        View.HAND_TARGET,
    ):
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

    if colors:
        for y, row in enumerate(rows):
            x = row.find("Золото:")
            if x >= 0:
                text = row[x:].split(controller.theme.vertical, 1)[0].rstrip()
                try:
                    screen.addnstr(y, x, text, len(text), colors.attribute(11, None))
                except curses.error:
                    pass
    popup = popup_layout(controller, width, height)
    if popup:
        _, rect, _, hits = popup
        normal = colors.attribute(0, 250) if colors else 0
        if not controller.feedback and controller.view in (View.STORAGE, View.CRAFT):
            normal = colors.attribute(15, 4) if colors else 0
        selected = colors.attribute(15, 60) if colors else curses.A_REVERSE
        shadow = colors.attribute(0, 0) if colors else 0
        for y in range(rect.y + 1, rect.y + rect.height + 1):
            try:
                screen.addnstr(y, rect.x + 1, " " * rect.width, rect.width, shadow)
            except curses.error:
                pass

        selected_rows = set()
        for i, start in hits:
            if i == controller.dialog_index:
                stop = next((row for j, row in hits if j == i + 1), rect.height - 4)
                selected_rows.update(range(start + 1, min(stop + 1, rect.height - 2)))
        for y in range(rect.y, rect.y + rect.height):
            try:
                screen.addnstr(
                    y,
                    rect.x,
                    rows[y][rect.x : rect.x + rect.width],
                    rect.width,
                    selected if y - rect.y in selected_rows else normal,
                )
            except curses.error:
                pass

        if colors and controller.view is View.INTERACTION and not controller.feedback:
            green = 22 if getattr(curses, "COLORS", 256) >= 256 else 2
            for y in range(rect.y, rect.y + rect.height):
                for match in re.finditer(
                    r"\[[↖↑↗←•→↙↓↘]\]", rows[y][rect.x : rect.x + rect.width]
                ):
                    try:
                        screen.addnstr(
                            y,
                            rect.x + match.start(),
                            match.group(),
                            3,
                            colors.attribute(
                                10 if y - rect.y in selected_rows else green,
                                60 if y - rect.y in selected_rows else 250,
                            ),
                        )
                    except curses.error:
                        pass

        if not controller.feedback and controller.view is View.CRAFT:
            _, _, body, _, _ = craft_layout(controller, width, height)
            for row, column, text, foreground, background in controller.craft.colors:
                attribute = colors.attribute(foreground, background) if colors else 0
                if not colors and background == 60:
                    attribute |= curses.A_REVERSE
                try:
                    screen.addnstr(
                        rect.y + row + 1,
                        rect.x + 2 + column,
                        text,
                        len(text),
                        attribute,
                    )
                except curses.error:
                    pass

        if not controller.feedback and controller.view is View.STORAGE:
            _, _, body, offsets = storage_layout(controller, width, height)
            column = (rect.width - 5) // 2
            side = controller.storage.side
            row = 2 + controller.storage.selected[side] - offsets[side]
            if 2 <= row < rect.height - 9:
                x = rect.x + 2 + side * (column + 3)
                text = body[row][side * (column + 3) : side * (column + 3) + column]
                attribute = (
                    colors.attribute(0, 11) if colors else curses.A_REVERSE
                ) | curses.A_BOLD
                try:
                    screen.addnstr(rect.y + row + 1, x, text, column, attribute)
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
        or background_view(controller)
        not in (View.EXPLORE, View.LOOK, View.THROW, View.IGNITE)
        or width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):
        return
    state = controller.engine.state
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
                    if background_view(controller)
                    in (
                        View.LOOK,
                        View.THROW,
                        View.IGNITE,
                        View.SPELL_TARGET,
                        View.HAND_TARGET,
                    )
                    and (cx + x, cy + y)
                    == (controller.look_position.x, controller.look_position.y)
                    else cell.char
                )
                char = map_symbols(controller, char)
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
