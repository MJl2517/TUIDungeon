"""Exploration commands, navigation, keyboard protocols and save round trips."""

from scripts.testing import fixture_store, lay_bedroll

import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from tuidungeon.application.engine import Action, Engine
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.domain.actions import SpellSource
from tuidungeon.domain.rules import Ability, Dice
from tuidungeon.presentation.keyboard import decode_sequence
from tuidungeon.presentation.menus import ActionMenu
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position


class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.store = fixture_store()
        self.factory = SessionFactory(self.store)
        self.engine = self.factory.session(
            "base:crypt", race="base:elf", character_class="base:wizard", seed=42
        )

    def test_sneaking_slows_only_successful_movement_and_advantages_trap(self):
        engine = self.engine
        self.assertTrue(engine.toggle_sneaking().performed)
        self.assertEqual(engine.state.turns, 0)
        start = engine.state.position
        engine.state.position = Position(1, 1)
        self.assertEqual(engine.apply(Action.NORTH).minutes, 0)
        engine.state.position = start
        self.assertEqual(engine.apply(Action.WAIT).minutes, 1)
        for _ in range(3):
            self.assertEqual(engine.apply(Action.EAST).minutes, 2)
        self.assertEqual(engine.state.turns, 4)
        event = engine.events[-1]
        self.assertTrue(event["advantage"])
        self.assertEqual(len(event["rolls"]), 2)
        self.assertEqual(event["roll"], max(event["rolls"]))
        engine.toggle_sneaking()
        self.assertEqual(engine.apply(Action.WEST).minutes, 1)

    def test_sneaking_initiative_uses_better_of_two_dice(self):
        hero = self.engine.state.hero
        hero.sneaking = True
        expected = Dice(random.Random(19)).check(
            hero.stats.score(Ability.DEXTERITY),
            0,
            bonus=hero.initiative_bonus,
            advantage=True,
        )
        self.assertEqual(hero.roll_initiative(Dice(random.Random(19))), expected.total)
        hero.sneaking = False
        expected = Dice(random.Random(19)).check(
            hero.stats.score(Ability.DEXTERITY), 0, bonus=hero.initiative_bonus
        )
        self.assertEqual(hero.roll_initiative(Dice(random.Random(19))), expected.total)

    def test_short_rest_heals_without_refilling_magic_then_long_rest_restores_all(self):
        hero = self.engine.state.hero
        hero.hp = 1
        hero.spell_slots[1] = 0
        hero.racial_uses = 0
        hero.sneaking = True
        result = self.engine.apply(Action.SHORT_REST)
        self.assertEqual(result.minutes, 60)
        self.assertEqual(hero.hp, 1 + hero.max_hp // 2)
        self.assertEqual((hero.spell_slots[1], hero.racial_uses), (0, 0))
        self.assertFalse(hero.sneaking)
        lay_bedroll(self.engine)
        self.assertEqual(self.engine.apply(Action.REST).minutes, 480)
        self.assertEqual(
            (hero.hp, hero.spell_slots[1], hero.racial_uses), (hero.max_hp, 2, 1)
        )

    def test_magic_uses_correct_source_and_preserves_time_on_failure(self):
        hero = self.engine.state.hero
        for source in (SpellSource.CLASS, SpellSource.RACIAL):
            self.assertTrue(self.engine.cast_spell("detect_magic", source).performed)
        self.assertEqual((hero.spell_slots[1], hero.racial_uses), (1, 0))
        self.assertEqual(hero.conditions["detect_magic"], 10)
        before = self.engine.state.turns
        self.assertFalse(
            self.engine.cast_spell("detect_magic", SpellSource.RACIAL).performed
        )
        self.assertFalse(
            self.engine.cast_spell("magic_missile", SpellSource.CLASS).performed
        )
        self.assertEqual(self.engine.state.turns, before)
        self.engine.state.position = self.engine.state.monsters[0].position
        monster = self.engine.state.monsters[0].monster
        previous = monster.hp
        self.assertTrue(
            self.engine.cast_spell(
                "magic_missile", SpellSource.CLASS, monster
            ).performed
        )
        self.assertLess(monster.hp, previous)
        self.assertEqual(hero.spell_slots[1], 0)

    def test_inspection_does_not_reveal_hidden_traps_or_change_time(self):
        trap = self.engine.state.level.traps[0]
        position = Position(trap.placement.x, trap.placement.y)
        self.engine.state.position = position
        text = "\n".join(self.engine.inspect_cell(position))
        if trap.definition.hidden:
            self.assertNotIn(trap.definition.name, text)
        trap.triggered = True
        self.assertIn(
            trap.definition.name, "\n".join(self.engine.inspect_cell(position))
        )
        monster = self.engine.state.monsters[0]
        self.engine.state.position = monster.position
        self.assertIn(
            monster.monster.name, "\n".join(self.engine.inspect_cell(monster.position))
        )
        point = self.engine.state.level.points[0]
        self.engine.state.position = Position(point.placement.x, point.placement.y)
        self.assertIn(
            point.definition.description,
            "\n".join(
                self.engine.inspect_cell(Position(point.placement.x, point.placement.y))
            ),
        )
        self.assertEqual(self.engine.state.turns, 0)
        self.assertEqual(self.engine.state.clock.elapsed_minutes, 480)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "slot.json"
        self.repository = SaveRepository(self.path)
        self.store = fixture_store()
        self.factory = SessionFactory(self.store)
        self.engine = self.factory.session(
            "base:crypt", race="base:elf", character_class="base:wizard", seed=17
        )

    def test_roundtrip_world_resources_instances_and_random_sequence(self):
        engine = self.engine
        engine.toggle_sneaking()
        engine.cast_spell("detect_magic", SpellSource.RACIAL)
        for _ in range(3):
            engine.apply(Action.EAST)
        engine.state.level.points[0].challenge.completed = True
        engine.state.monsters[0].monster.hp = 1
        engine.state.hero.inventory[0].equipped = False
        engine.state.hero.gold = 91
        second = self.factory.state("base:dungeon", engine.state.hero)
        engine.levels["base:dungeon"] = second
        self.repository.save(engine)
        saved = json.loads(self.path.read_text())
        loaded = self.repository.load(self.factory.catalog, self.store)
        self.assertEqual(loaded.state.hero.stats, engine.state.hero.stats)
        self.assertEqual(loaded.state.hero.inventory, engine.state.hero.inventory)
        self.assertEqual(loaded.state.hero.conditions, engine.state.hero.conditions)
        self.assertTrue(loaded.state.hero.sneaking)
        self.assertEqual(loaded.state.hero.racial_uses, 0)
        self.assertEqual(loaded.state.hero.gold, 91)
        self.assertTrue(loaded.state.level.traps[0].triggered)
        self.assertTrue(loaded.state.level.points[0].challenge.completed)
        self.assertEqual(loaded.state.monsters[0].monster.hp, 1)
        self.assertEqual(len(loaded.levels), 2)
        self.repository.save(loaded)
        self.assertEqual(json.loads(self.path.read_text()), saved)
        self.assertEqual(loaded.dice.roll(8, 20), engine.dice.roll(8, 20))

    def test_legacy_map_and_dead_monster_under_hero_load_correctly(self):
        engine = Engine.new_game(self.engine.state.hero, random.Random(1))
        self.repository.save(engine)
        loaded = self.repository.load(self.factory.catalog)
        self.assertEqual(loaded.state.dungeon, engine.state.dungeon)
        placement = self.engine.state.monsters[0]
        placement.monster.hp = 0
        self.engine.state.position = placement.position
        self.repository.save(self.engine)
        loaded = self.repository.load(self.factory.catalog, self.store)
        self.assertEqual(loaded.state.position, placement.position)
        self.assertEqual(loaded.state.monsters[0].monster.hp, 0)

    def test_atomic_write_failure_keeps_previous_save(self):
        self.repository.save(self.engine)
        original = self.path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.repository.save(self.engine)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob(".save-*")), [])

    def test_invalid_version_resources_rng_and_changed_map_are_rejected(self):
        self.repository.save(self.engine)
        original = json.loads(self.path.read_text())
        cases = [
            lambda s: s.update(version=2),
            lambda s: s["hero"].update(hp=-1),
            lambda s: s.update(rng=[0]),
            lambda s: s["levels"][0]["definition"].update(name="changed"),
        ]
        for change in cases:
            data = json.loads(json.dumps(original))
            change(data)
            self.path.write_text(json.dumps(data))
            with self.assertRaises((ValueError, IndexError)):
                self.repository.load(self.factory.catalog, self.store)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = fixture_store()
        self.controller = Controller(
            42,
            catalog=self.store.runtime_catalog(),
            store=self.store,
            map_ref="base:crypt",
            test_map=True,
            save_path=Path(self.directory.name) / "save.json",
        )

    def test_look_cursor_boundaries_inspection_and_back_do_not_move_hero(self):
        controller = self.controller
        start = controller.engine.state.position
        controller.handle("1")
        for _ in range(50):
            controller.handle("left")
        self.assertEqual(controller.look_position.x, 0)
        controller.handle("enter")
        self.assertEqual(controller.view, View.INSPECT)
        controller.handle("backspace")
        self.assertEqual(controller.view, View.LOOK)
        controller.handle("backspace")
        self.assertEqual(controller.view, View.EXPLORE)
        self.assertEqual(controller.engine.state.position, start)
        self.assertEqual(controller.engine.state.turns, 0)

    def test_nested_actions_back_rest_and_meta_do_not_trigger_root_commands(self):
        c = self.controller
        c.handle("3")
        c.handle("1")
        self.assertTrue(c.engine.state.hero.sneaking)
        self.assertEqual(c.action_menu, ActionMenu.ACTIONS)
        c.handle("backspace")
        c.handle("4")
        before = c.engine.state.clock.elapsed_minutes
        c.handle("1")
        self.assertEqual(c.engine.state.clock.elapsed_minutes, before + 60)
        c.handle("escape")
        self.assertIn("Игровое меню", "\n".join(render(c, 80, 24)))
        c.handle("1")
        self.assertTrue(c.saves.path.exists())
        c.handle("escape")
        c.handle("d")
        c.handle("escape")
        c.handle("2")
        self.assertEqual(c.engine.state.turns, 1)
        c.handle("escape")
        c.handle("5")
        c.handle("2")
        c.handle("backspace")
        self.assertEqual(c.view, View.EXPLORE)
        c.handle("backspace")
        c.handle("escape")
        c.handle("4")
        c.handle("1")
        self.assertEqual(c.view, View.MAIN_MENU)
        c.handle("2")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.engine.state.turns, 1)

    def test_equipment_sheet_commands_at_bottom_and_slot_management_costs_turn(self):
        c = self.controller
        c.handle("2")
        c.handle("]")
        self.assertIn("Снаряжение", "\n".join(render(c, 80, 24)))
        c.handle("enter")
        self.assertEqual(c.view, View.ITEM)
        before = c.selected_item.equipped
        c.handle("1")
        self.assertNotEqual(c.selected_item.equipped, before)
        self.assertEqual(c.engine.state.turns, 1)
        c.handle("backspace")
        c.handle("backspace")
        self.assertEqual(c.view, View.EXPLORE)

    def test_magic_menu_and_sheet_paginate_and_cast_both_spell_sources(self):
        from dataclasses import replace

        c = self.controller
        hero = SessionFactory(self.store).hero("base:elf", "base:wizard")
        c.engine.state.hero = hero
        # More than a page, including distinct new definitions supplied at runtime.
        original = hero.class_spells[1]
        hero.class_spells = hero.class_spells + tuple(
            replace(original, id=f"test_spell_{i}", name=f"Тест {i}") for i in range(7)
        )
        c.handle("3")
        c.handle("2")
        c.handle("pagedown")
        self.assertEqual(c.page, 1)
        self.assertIn("Тест 4", "\n".join(render(c, 80, 24)))
        c.handle("1")
        self.assertEqual(hero.spell_slots[1], 1)
        self.assertEqual(c.engine.state.turns, 1)
        c.handle("2")
        c.handle("]")
        c.handle("]")
        c.handle("pagedown")
        c.handle("pagedown")
        c.handle("1")  # Racial spell follows 5 class spells and 7 test spells.
        self.assertEqual(hero.racial_uses, 0)
        self.assertEqual(hero.spell_slots[1], 1)
        c.handle("3")
        c.handle("2")
        c.handle("1")
        self.assertEqual(c.action_menu, ActionMenu.TARGET)
        c.engine.state.position = c.engine.state.monsters[0].position
        hp = c.targets[0].hp
        c.handle("1")
        self.assertLess(c.engine.state.monsters[0].monster.hp, hp)
        self.assertEqual(hero.spell_slots[1], 0)
        self.assertEqual(c.engine.state.turns, 3)

    def test_missing_or_corrupt_save_keeps_current_session(self):
        c = self.controller
        original = c.engine
        c.handle("escape")
        c.handle("2")
        self.assertIs(c.engine, original)
        c.saves.path.write_text("{broken")
        c.handle("escape")
        c.handle("escape")
        c.handle("2")
        self.assertIs(c.engine, original)
        self.assertIn("Не удалось загрузить", c.message)


class KeyboardTests(unittest.TestCase):
    def test_windows_console_alt_digits_and_normal_keys(self):
        from tuidungeon.presentation.keyboard import TerminalKeyboard

        curses = SimpleNamespace(
            KEY_UP=259,
            KEY_DOWN=258,
            KEY_LEFT=260,
            KEY_RIGHT=261,
            KEY_BACKSPACE=263,
            KEY_ENTER=343,
            KEY_PPAGE=339,
            KEY_NPAGE=338,
            KEY_RESIZE=546,
            error=RuntimeError,
        )
        keys = [0x197 + digit for digit in range(10)] + [
            "W",
            curses.KEY_LEFT,
            "\r",
            "\x08",
            "\t",
            "\x03",
            curses.KEY_RESIZE,
        ]
        screen = MagicMock()
        screen.get_wch.side_effect = keys
        with patch("sys.platform", "win32"):
            keyboard = TerminalKeyboard(screen, curses)
            self.assertEqual(
                [keyboard.read().key for _ in keys],
                [f"alt+{digit}" for digit in range(10)]
                + ["w", "left", "enter", "backspace", "tab", "ctrl_c", "resize"],
            )

    def test_windows_console_does_not_write_kitty_sequences(self):
        from tuidungeon.presentation.keyboard import TerminalKeyboard

        curses = MagicMock()
        screen = MagicMock()
        with (
            patch("sys.platform", "win32"),
            patch.dict("os.environ", {"WEZTERM_PANE": "test"}, clear=True),
            patch("sys.stdout") as output,
        ):
            with TerminalKeyboard(screen, curses) as keyboard:
                self.assertFalse(keyboard.enhanced)
            output.write.assert_not_called()
        screen.timeout.assert_called_with(-1)

    def test_pdcurses_codes_are_not_reinterpreted_on_posix(self):
        from tuidungeon.presentation.keyboard import TerminalKeyboard

        with patch("sys.platform", "linux"):
            keyboard = TerminalKeyboard(MagicMock(), MagicMock())
            self.assertEqual(keyboard.normalize(0x198), "")

    def test_kitty_modifier_press_release_alt_digits_arrows_and_control_c(self):
        self.assertTrue(decode_sequence("\x1b[57443;3u").alt)
        self.assertFalse(decode_sequence("\x1b[57443;1:3u").alt)
        event = decode_sequence("\x1b[49;3u")
        self.assertEqual((event.key, event.alt), ("1", True))
        self.assertEqual(decode_sequence("\x1b[49;1:3u").key, "")
        self.assertEqual(decode_sequence("\x1b[1;3D").key, "left")
        self.assertEqual(decode_sequence("\x1b[99;5u").key, "ctrl_c")
        self.assertEqual(decode_sequence("\x1b[13u").key, "enter")
        self.assertEqual(decode_sequence("\x1b[bad").key, "")
        self.assertEqual(decode_sequence("\x1b[6;1~").key, "pagedown")
        self.assertEqual(decode_sequence("\x1b[5;1:3~").key, "")

    def test_enhanced_keyboard_is_restored_even_if_game_loop_raises(self):
        from tuidungeon.presentation.keyboard import TerminalKeyboard

        screen = MagicMock()
        curses = SimpleNamespace(
            **{
                name: index
                for index, name in enumerate(
                    (
                        "KEY_UP",
                        "KEY_DOWN",
                        "KEY_LEFT",
                        "KEY_RIGHT",
                        "KEY_BACKSPACE",
                        "KEY_ENTER",
                        "KEY_PPAGE",
                        "KEY_NPAGE",
                    )
                )
            }
        )
        with (
            patch("sys.platform", "linux"),
            patch.dict("os.environ", {"KITTY_WINDOW_ID": "test"}),
            patch("sys.stdout") as output,
        ):
            with self.assertRaises(RuntimeError):
                with TerminalKeyboard(screen, curses):
                    raise RuntimeError("game failure")
            self.assertEqual(
                [call.args[0] for call in output.write.call_args_list],
                ["\x1b[>11u", "\x1b[<u"],
            )
        screen.timeout.assert_called_with(-1)
