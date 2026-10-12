"""Developer spellbook, CLI routing and persistence without changing normal heroes."""

from dataclasses import replace
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.__main__ import main
from tuidungeon.application.factories import create_test_hero, create_test_wizard
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.catalog import default_catalog
from tuidungeon.domain.actors import Hero
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.tui import Controller, View


class TestWizardTests(unittest.TestCase):
    def test_all_catalog_spells_and_resources_without_affecting_regular_heroes(self):
        catalog = default_catalog()
        extra = replace(catalog.spells["daylight"], id="extra_spell", level=5)
        catalog = replace(catalog, spells={**catalog.spells, extra.id: extra})
        hero = create_test_wizard(catalog)
        self.assertEqual(hero.character_class.id, "wizard")
        self.assertEqual({s.id for s in hero.known_spells}, set(catalog.spells))
        self.assertEqual(hero.spell_slots, {1: 10, 3: 10, 5: 10})
        self.assertEqual(hero.cantrip_uses, hero.max_cantrip_uses)
        self.assertTrue(hero.consume_class_slot("extra_spell"))
        hero.cantrip_uses = 0
        hero.restore_after_rest()
        self.assertEqual(hero.spell_slots[5], 10)
        self.assertEqual(hero.cantrip_uses, hero.max_cantrip_uses)
        regular = Hero.create("human", "wizard", Stats((10,) * 6), catalog=catalog)
        self.assertEqual(regular.spell_slots, {1: 2})
        self.assertEqual(len([s for s in regular.known_spells if s.level == 0]), 3)
        self.assertIsNone(regular.test_profile)
        self.assertEqual(create_test_hero(catalog).character_class.id, "warrior")

    def test_direct_exploration_and_save_load_keep_spells_and_spent_resources(self):
        controller = Controller(42, test_profile="wizard")
        self.assertEqual(controller.view, View.EXPLORE)
        self.assertEqual(controller.creation.rolls, ())
        engine = controller.engine
        hero = engine.state.hero
        self.assertTrue(hero.consume_class_slot("daylight"))
        self.assertTrue(hero.consume_class_slot("light"))
        with tempfile.TemporaryDirectory() as folder:
            repository = SaveRepository(Path(folder) / "wizard.json")
            repository.save(engine)
            restored = repository.load().state.hero
        self.assertEqual(restored.test_profile, "wizard")
        self.assertEqual(
            {s.id for s in restored.known_spells}, set(hero.catalog.spells)
        )
        self.assertEqual(restored.spell_slots, hero.spell_slots)
        self.assertEqual(restored.cantrip_uses, hero.cantrip_uses)

    def test_cli_routes_explicit_map_and_map_fallback_to_window(self):
        for options, expected_map in (
            (["--test-wizard", "base:crypt"], "base:crypt"),
            (["--map", "base:crypt", "--test-wizard"], "base:crypt"),
            (["--test-wizard"], "base:dungeon"),
        ):
            with (
                patch.object(sys, "argv", ["tuidungeon", *options]),
                patch("tuidungeon.presentation.window.run") as launch,
            ):
                self.assertEqual(main(), 0)
                self.assertEqual(launch.call_args.args[3], expected_map)
                self.assertTrue(launch.call_args.args[5])
                self.assertEqual(launch.call_args.kwargs["test_profile"], "wizard")

    def test_cli_routes_profile_to_terminal(self):
        with (
            patch.object(sys, "argv", ["tuidungeon", "--terminal", "--test-wizard"]),
            patch.object(sys.stdin, "isatty", return_value=True),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch("curses.wrapper") as launch,
        ):
            self.assertEqual(main(), 0)
            self.assertEqual(launch.call_args.kwargs["test_profile"], "wizard")
            self.assertTrue(launch.call_args.args[6])

    def test_cli_rejects_conflicting_launch_modes(self):
        for options in (
            ["--test-map", "--test-wizard"],
            ["--studio", "--test-wizard"],
        ):
            with (
                patch.object(sys, "argv", ["tuidungeon", *options]),
                patch.object(sys, "stderr", StringIO()),
                self.assertRaises(SystemExit) as caught,
            ):
                main()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
