"""Studio-selected test classes reach both renderers and the shared hero factory."""

from dataclasses import replace
from io import StringIO
import sys
import unittest
from unittest.mock import patch

from tuidungeon.__main__ import main
from tuidungeon.application.factories import create_test_hero
from tuidungeon.content.catalog import default_catalog
from tuidungeon.presentation.tui import Controller, View


class TestClassTests(unittest.TestCase):
    def test_selected_classes_skip_creation_and_wizard_has_all_spells(self):
        catalog = default_catalog()
        for character_class in ("warrior", "rogue", "wizard"):
            controller = Controller(
                42, catalog=catalog, test_map=True, test_class=character_class
            )
            self.assertEqual(controller.view, View.EXPLORE)
            self.assertEqual(controller.creation.rolls, ())
            hero = controller.engine.state.hero
            self.assertEqual(hero.character_class.id, character_class)
            self.assertEqual(
                [item.id for item in hero.inventory],
                list(catalog.classes[character_class].starting_items),
            )
            if character_class == "wizard":
                self.assertEqual({s.id for s in hero.known_spells}, set(catalog.spells))
                self.assertEqual(hero.spell_slots, {1: 10, 3: 10})

    def test_custom_class_is_supported_and_unknown_selection_does_not_fall_back(self):
        catalog = default_catalog()
        custom = replace(catalog.classes["rogue"], id="extra:scout", name="Разведчик")
        catalog = replace(catalog, classes={**catalog.classes, custom.id: custom})
        self.assertEqual(create_test_hero(catalog, custom.id).character_class, custom)
        with self.assertRaisesRegex(ValueError, "Неизвестный тестовый класс"):
            create_test_hero(catalog, "missing")

    def test_cli_forwards_runtime_class_to_window_and_terminal(self):
        for terminal in (False, True):
            options = [
                "tuidungeon",
                "--test-map",
                "base:crypt",
                "--test-class",
                "base:rogue",
            ]
            if terminal:
                options.append("--terminal")
            with (
                patch.object(sys, "argv", options),
                patch.object(sys.stdin, "isatty", return_value=True),
                patch.object(sys.stdout, "isatty", return_value=True),
                patch("curses.wrapper") as tui,
                patch("tuidungeon.presentation.window.run") as window,
            ):
                self.assertEqual(main(), 0)
                launch = tui if terminal else window
                self.assertEqual(launch.call_args.kwargs["test_class"], "rogue")
                (window if terminal else tui).assert_not_called()

    def test_cli_rejects_unknown_class_and_non_test_launch(self):
        with (
            patch.object(
                sys,
                "argv",
                ["tuidungeon", "--test-map", "--test-class", "base:missing"],
            ),
            patch.object(sys, "stderr", StringIO()),
            patch("tuidungeon.presentation.window.run") as launch,
        ):
            self.assertEqual(main(), 1)
            launch.assert_not_called()
        with (
            patch.object(sys, "argv", ["tuidungeon", "--test-class", "base:rogue"]),
            patch.object(sys, "stderr", StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            main()
        self.assertEqual(caught.exception.code, 2)
