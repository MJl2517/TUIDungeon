from scripts.testing import fixture_store
import unittest
from pathlib import Path
import tempfile

from tuidungeon.models import Position
from tuidungeon.ui import Controller, Layout, View, render


def created_controller(seed=42):
    controller = Controller(seed)
    controller.handle("enter")
    # Human warrior; accept rolls, distribute in order, confirm.
    for key in ("1", "1", "1", "2", "1", "2", "3", "4", "5", "6", "1"):
        controller.handle(key)
    return controller


class ControllerTests(unittest.TestCase):
    def test_test_map_starts_exploration_with_fixed_hero_without_creation(self):
        controller = Controller(42, test_map=True)
        self.assertEqual(controller.view, View.EXPLORE)
        self.assertEqual(controller.creation.rolls, ())
        state = controller.engine.state
        self.assertEqual(state.hero.race.id, "human")
        self.assertEqual(state.hero.character_class.id, "warrior")
        self.assertEqual(state.hero.stats.values, (15, 13, 14, 11, 11, 9))
        self.assertEqual(state.hero.hp, state.hero.max_hp)
        self.assertTrue(state.hero.inventory)
        self.assertEqual((state.turns, state.clock.elapsed_minutes), (0, 480))
        self.assertNotIn("Создание героя", "\n".join(render(controller, 80, 24)))
        controller.handle("d")
        self.assertEqual(state.turns, 1)

    def test_test_hero_uses_available_definitions_in_custom_catalog(self):
        from dataclasses import replace
        from tuidungeon.content.catalog import default_catalog

        catalog = default_catalog()
        catalog = replace(
            catalog,
            races={"elf": catalog.races["elf"]},
            classes={"wizard": catalog.classes["wizard"]},
        )
        controller = Controller(42, catalog=catalog, test_map=True)
        hero = controller.engine.state.hero
        self.assertEqual((hero.race.id, hero.character_class.id), ("elf", "wizard"))
        self.assertEqual(hero.spell_slots, {1: 2})
        self.assertEqual(hero.racial_uses, 1)

    def test_test_map_loads_selected_level_and_restarts_its_instances(self):
        store = fixture_store()
        catalog = store.runtime_catalog()

        def start():
            return Controller(
                42, catalog=catalog, map_ref="base:crypt", store=store, test_map=True
            )

        first = start()
        self.assertEqual(first.engine.state.level.ref, "base:crypt")
        initial_hp = first.engine.state.hero.hp
        for key in "ddd":
            first.handle(key)
        self.assertTrue(first.engine.state.level.traps[0].triggered)
        result_hp = first.engine.state.hero.hp
        second = start()
        self.assertFalse(second.engine.state.level.traps[0].triggered)
        self.assertEqual(second.engine.state.hero.hp, initial_hp)
        self.assertEqual(second.engine.state.turns, 0)
        for key in "ddd":
            second.handle(key)
        self.assertEqual(second.engine.state.hero.hp, result_hp)

    def test_main_menu_navigation_wraps_and_opens_selected_screen(self):
        saves = tempfile.TemporaryDirectory()
        self.addCleanup(saves.cleanup)
        controller = Controller(42, save_path=Path(saves.name) / "quicksave.json")
        self.assertEqual(controller.view, View.MAIN_MENU)
        self.assertIsNone(controller.engine)
        controller.handle("up")
        self.assertEqual(controller.menu_index, 4)
        controller.handle("s")
        self.assertEqual(controller.menu_index, 0)
        controller.handle("w")
        controller.handle("down")
        controller.handle("down")
        controller.handle("enter")
        self.assertEqual(controller.view, View.LOAD)
        self.assertIn(
            "Нет доступного сохранения", "\n".join(render(controller, 80, 24))
        )
        controller.handle("backspace")
        self.assertEqual(controller.menu_index, 1)
        controller.handle("4")
        self.assertEqual(controller.view, View.HELP)
        controller.handle("escape")
        controller.handle("5")
        self.assertFalse(controller.running)

    def test_settings_apply_to_new_game_and_cancel_starts_fresh_creation(self):
        controller = Controller(42)
        controller.handle("3")
        self.assertEqual(controller.view, View.SETTINGS)
        controller.handle("right")
        self.assertEqual(controller.symbols, "unicode")
        controller.handle("escape")
        controller.handle("1")
        self.assertEqual(controller.view, View.CREATION)
        self.assertEqual(render(controller, 80, 24)[0][0], "┌")
        controller.handle("3")
        controller.handle("backspace")
        controller.handle("backspace")
        self.assertEqual(controller.view, View.MAIN_MENU)
        controller.handle("enter")
        self.assertIsNone(controller.creation.race)
        self.assertIsNone(controller.engine)
        controller.handle("q")
        if controller.engine:
            controller.handle("2")
        self.assertFalse(controller.running)

    def test_menu_navigation_does_not_consume_random_rolls(self):
        saves = tempfile.TemporaryDirectory()
        self.addCleanup(saves.cleanup)
        controller = Controller(42, save_path=Path(saves.name) / "quicksave.json")
        for key in ("3", "2", "backspace", "4", "escape", "2", "backspace", "1"):
            controller.handle(key)
        for key in "11121234561":
            controller.handle(key)
        self.assertEqual(
            controller.engine.state.hero, created_controller().engine.state.hero
        )

    def test_creation_is_reproducible_with_seed(self):
        first, second = created_controller(), created_controller()
        self.assertEqual(first.engine.state.hero, second.engine.state.hero)

    def test_menus_tab_backspace_and_unknown_keys_do_not_advance_time(self):
        controller = created_controller()
        state = controller.engine.state
        original_position = state.position
        for key in (
            "tab",
            "2",
            "w",
            "1",
            "3",
            "4",
            "tab",
            "backspace",
            "backspace",
            "?",
            "",
            "resize",
        ):
            controller.handle(key)
        self.assertTrue(controller.running)
        self.assertEqual(controller.view, View.EXPLORE)
        self.assertTrue(
            controller.spells_tab
        )  # Character navigation keeps the sidebar tab.
        self.assertEqual(
            (state.clock.elapsed_minutes, state.turns, state.position),
            (480, 0, original_position),
        )

    def test_game_controls_apply_actions_and_exit(self):
        controller = created_controller()
        for key in ("D", "S", "A", "W", "3", "3", "backspace", "4", "2"):
            controller.handle(key)
        self.assertEqual(controller.engine.state.position, Position(3, 3))
        self.assertEqual(controller.engine.state.turns, 6)
        self.assertEqual(controller.engine.state.clock.elapsed_minutes, 965)
        controller.handle("alt+4")
        controller.handle("2")
        self.assertFalse(controller.running)

    def test_arrows_select_tabs_without_moving_or_spending_time(self):
        from tuidungeon.presentation.menus import SidebarTab

        controller = created_controller()
        state = controller.engine.state
        for key, tab in (
            ("right", SidebarTab.SPELLS),
            ("right", SidebarTab.CONDITIONS),
            ("up", SidebarTab.CONDITIONS),
            ("down", SidebarTab.CONDITIONS),
            ("tab", SidebarTab.INVENTORY),
            ("left", SidebarTab.CONDITIONS),
            ("left", SidebarTab.SPELLS),
            ("left", SidebarTab.INVENTORY),
        ):
            controller.handle(key)
            self.assertEqual(controller.sidebar_tab, tab)
            self.assertEqual(
                (state.position, state.turns, state.clock.elapsed_minutes),
                (Position(3, 3), 0, 480),
            )
        controller.handle("2")
        controller.handle("right")
        self.assertEqual(controller.sheet_section, 1)
        self.assertFalse(controller.spells_tab)
        self.assertEqual(controller.view, View.CHARACTER)
        controller.handle("up")
        self.assertFalse(controller.spells_tab)
        self.assertEqual(state.turns, 0)

    def test_conditions_are_visible_in_sheet_and_sidebar_without_changing_actor(self):
        from tuidungeon.presentation.menus import SidebarTab

        controller = created_controller()
        state = controller.engine.state
        state.hero.conditions = {"poisoned": 4}
        rng = controller.engine.dice.rng.getstate()
        for width, height in ((80, 24), (100, 30)):
            controller.sidebar_tab = SidebarTab.CONDITIONS
            sidebar = "\n".join(
                row[width - 27 :] for row in render(controller, width, height)
            )
            controller.handle("2")
            sheet = "\n".join(
                row[: width - 28] for row in render(controller, width, height)
            )
            for label in (
                "Ослепление",
                "Истощение",
                "Жажда",
                "Голод",
                "Отравление",
                "Благословление",
            ):
                self.assertIn(label + ": --", sidebar)
                self.assertIn(label + ": --", sheet)
            self.assertIn("Квесты", render(controller, width, height)[0])
            self.assertIn("Сила", sheet)
            self.assertIn("Телосложение", sheet)
            controller.handle("backspace")
            self.assertEqual(controller.sidebar_tab, SidebarTab.CONDITIONS)
        self.assertEqual(state.hero.conditions, {"poisoned": 4})
        self.assertEqual(controller.engine.dice.rng.getstate(), rng)
        self.assertEqual((state.turns, state.clock.elapsed_minutes), (0, 480))

    def test_backspace_revises_creation_and_q_opens_exit_submenu(self):
        controller = Controller(42)
        controller.handle("enter")
        controller.handle("3")
        controller.handle("backspace")
        controller.handle("2")
        controller.handle("2")
        controller.handle("1")
        controller.handle("2")
        for key in "123456":
            controller.handle(key)
        controller.handle("backspace")
        controller.handle("6")
        controller.handle("1")
        self.assertEqual(controller.engine.state.hero.race.value, "Дварф")
        controller.handle("2")
        controller.handle("q")
        if controller.engine:
            controller.handle("2")
        self.assertFalse(controller.running)


class RenderingTests(unittest.TestCase):
    def test_main_menu_has_no_frames_and_brackets_follow_selection_on_resize(self):
        controller = Controller(42, symbols="unicode")
        for width, height in ((80, 24), (100, 30)):
            for label in ("Новая игра", "Загрузить", "Настройки", "Справка", "Выйти"):
                rows = render(controller, width, height)
                text = "\n".join(rows)
                self.assertIn(f"[ {label} ]", text)
                self.assertEqual(text.count("["), 1)
                self.assertFalse(any(char in text for char in "+┌┐└┘"))
                self.assertTrue(all(row[0] == row[-1] == " " for row in rows))
                self.assertTrue(all(len(row) == width for row in rows))
                controller.handle("down")

    def assert_borders(self, rows):
        layout = Layout.for_size(len(rows[0]), len(rows))
        for rect in (layout.main, layout.actions, layout.sidebar, layout.status):
            self.assertEqual(rows[rect.y][rect.x], "+")
            self.assertEqual(rows[rect.y][rect.x + rect.width - 1], "+")
            for y in range(rect.y + 1, rect.y + rect.height - 1):
                self.assertEqual(rows[y][rect.x], "|")
                self.assertEqual(rows[y][rect.x + rect.width - 1], "|")

    def test_all_creation_screens_fit_at_minimum_size(self):
        controller = Controller(42)
        controller.handle("enter")
        for key in (None, "3", "2", "1", "2", "1", "2", "3", "4", "5", "6"):
            if key:
                controller.handle(key)
            rows = render(controller, 80, 24)
            self.assertEqual(len(rows), 24)
            self.assertTrue(all(len(row) == 80 for row in rows))
            self.assert_borders(rows)
        self.assertIn("Подтверждение", "\n".join(rows))
        self.assertIn("Бонусы уже учтены", "\n".join(rows))

    def test_game_four_panels_and_spells_and_character(self):
        controller = created_controller()
        rows = render(controller, 80, 24)
        self.assert_borders(rows)
        text = "\n".join(rows)
        for label in (
            "Подземелье",
            "Инвентарь",
            "Действия",
            "Время и средства",
            "08:00",
            "Деньги: 0",
            "Опыт: 0",
        ):
            self.assertIn(label, text)
        self.assertEqual(text.count("@"), 1)
        controller.handle("tab")
        self.assertIn("Классовых ячеек нет.", "\n".join(render(controller, 80, 24)))
        controller.handle("2")
        self.assertIn("Телосложение", "\n".join(render(controller, 80, 24)))

    def test_elf_wizard_displays_both_magic_pools_without_truncation(self):
        controller = Controller(42)
        controller.handle("enter")
        for key in ("3", "2", "1", "2", "1", "2", "3", "4", "5", "6", "1", "tab"):
            controller.handle(key)
        text = "\n".join(render(controller, 80, 24))
        for label in (
            "Волшебная стрела (1)",
            "Ячейки ур. 1: 2/2",
            "Расовое заклинание:",
            "Применения: 1/1",
        ):
            self.assertIn(label, text)

    def test_camera_keeps_hero_visible_across_entire_map_and_resize(self):
        controller = created_controller()
        for width, height in ((80, 24), (100, 30), (150, 45)):
            for y, row in enumerate(controller.engine.state.dungeon.rows):
                for x, cell in enumerate(row):
                    if cell == ".":
                        controller.engine.state.position = Position(x, y)
                        rows = render(controller, width, height)
                        self.assertEqual("\n".join(rows).count("@"), 1)
            self.assert_borders(rows)

    def test_small_windows_display_message_without_crashing(self):
        controller = created_controller()
        for width, height in ((79, 24), (80, 23), (40, 10), (1, 1)):
            rows = render(controller, width, height)
            self.assertEqual(len(rows), height)
            self.assertTrue(all(len(row) == width for row in rows))
            if width > 30:
                self.assertIn("Увеличьте окно", "\n".join(rows))


if __name__ == "__main__":
    unittest.main()
