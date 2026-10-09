from scripts.testing import install_test_maps
import shutil

"""End-to-end curses test against a real Unix pseudo-terminal."""

import codecs
import os
from pathlib import Path
import re
import select
import signal
import struct
import subprocess
import time
import tempfile
import unittest

from tuidungeon.ui import Controller, render
from tuidungeon.presentation.tui import menu_entries, View

if os.name == "posix":
    import fcntl
    import pty
    import termios


class TerminalScreen:
    """Small VT screen reader for the cursor/erase commands emitted by curses."""

    csi = re.compile(r"\x1b\[([0-?]*)([ -/]*)([@-~])")

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.cells = [[" "] * width for _ in range(height)]
        self.x = self.y = 0
        self.scroll_top, self.scroll_bottom = 0, height - 1
        self.pending = ""
        self.last_character = " "
        self.bold = False
        self.bold_cells = {}
        self.reverse = False
        self.reverse_cells = {}
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def resize(self, width, height):
        old = self.cells
        self.cells = [[" "] * width for _ in range(height)]
        for y in range(min(height, self.height)):
            self.cells[y][: min(width, self.width)] = old[y][: min(width, self.width)]
        self.width, self.height = width, height
        self.scroll_top, self.scroll_bottom = 0, height - 1
        self.x = min(self.x, width - 1)
        self.y = min(self.y, height - 1)

    def command(self, parameters, command):
        if command == "m":
            for value in [int(value or 0) for value in parameters.split(";")]:
                if value in (0, 22):
                    self.bold = False
                elif value == 1:
                    self.bold = True
                if value in (0, 27):
                    self.reverse = False
                elif value == 7:
                    self.reverse = True
            return
        if parameters.startswith("?") or command in "mhlnt":
            return
        values = [int(value or 0) for value in parameters.split(";")]
        value = values[0]
        count = value or 1
        if command in "Hf":
            self.y = (value or 1) - 1
            self.x = ((values[1] if len(values) > 1 else 1) or 1) - 1
        elif command == "r":
            self.scroll_top = (value or 1) - 1
            self.scroll_bottom = (
                (values[1] if len(values) > 1 else self.height) or self.height
            ) - 1
        elif command == "A":
            self.y -= count
        elif command == "B":
            self.y += count
        elif command == "C":
            self.x += count
        elif command == "D":
            self.x -= count
        elif command == "G":
            self.x = count - 1
        elif command == "d":
            self.y = count - 1
        elif command == "J":
            if value == 2:
                self.cells = [[" "] * self.width for _ in range(self.height)]
            elif value == 0:
                self.cells[self.y][self.x :] = [" "] * (self.width - self.x)
                for row in range(self.y + 1, self.height):
                    self.cells[row] = [" "] * self.width
        elif command == "K":
            if value == 0:
                self.cells[self.y][self.x :] = [" "] * (self.width - self.x)
            elif value == 1:
                self.cells[self.y][: self.x + 1] = [" "] * (self.x + 1)
            elif value == 2:
                self.cells[self.y] = [" "] * self.width
        elif command == "X":
            end = min(self.width, self.x + count)
            self.cells[self.y][self.x : end] = [" "] * (end - self.x)
        elif command == "b":
            for _ in range(count):
                self.put(self.last_character)
        elif command in "STLM":
            if command in "LM" and not self.scroll_top <= self.y <= self.scroll_bottom:
                return
            top = self.y if command in "LM" else self.scroll_top
            count = min(count, self.scroll_bottom - top + 1)
            region = self.cells[top : self.scroll_bottom + 1]
            blanks = [[" "] * self.width for _ in range(count)]
            upwards = command in "SM"
            self.cells[top : self.scroll_bottom + 1] = (
                region[count:] + blanks if upwards else blanks + region[:-count]
            )
            offset = count if upwards else -count
            for attributes in (self.bold_cells, self.reverse_cells):
                previous = attributes.copy()
                for row in range(top, self.scroll_bottom + 1):
                    for column in range(self.width):
                        source = row + offset
                        attributes[row, column] = (
                            previous.get((source, column), False)
                            if top <= source <= self.scroll_bottom
                            else False
                        )
        else:
            raise AssertionError(f"Unhandled terminal command: {parameters}{command}")
        self.x = max(0, min(self.x, self.width - 1))
        self.y = max(0, min(self.y, self.height - 1))

    def put(self, character):
        if self.x == self.width:
            self.x = 0
            self.line_feed()
        self.cells[self.y][self.x] = character
        self.bold_cells[self.y, self.x] = self.bold
        self.reverse_cells[self.y, self.x] = self.reverse
        self.x += 1
        self.last_character = character

    def line_feed(self):
        if self.y == self.scroll_bottom:
            del self.cells[self.scroll_top]
            self.cells.insert(self.scroll_bottom, [" "] * self.width)
        else:
            self.y = min(self.height - 1, self.y + 1)

    def feed(self, data):
        self.pending += self.decoder.decode(data)
        while self.pending:
            character = self.pending[0]
            if character == "\x1b":
                if len(self.pending) < 2:
                    break
                if self.pending[1] == "[":
                    match = self.csi.match(self.pending)
                    if match is None:
                        break
                    self.command(match[1], match[3])
                    self.pending = self.pending[match.end() :]
                    continue
                if self.pending[1] in "()":
                    if len(self.pending) < 3:
                        break
                    self.pending = self.pending[3:]
                    continue
                if self.pending[1] == "M":
                    if self.y == self.scroll_top:
                        self.cells.insert(self.scroll_top, [" "] * self.width)
                        del self.cells[self.scroll_bottom + 1]
                    else:
                        self.y = max(0, self.y - 1)
                elif self.pending[1] == "D":
                    self.line_feed()
                self.pending = self.pending[2:]
                continue
            self.pending = self.pending[1:]
            if character == "\r":
                self.x = 0
            elif character == "\n":
                self.line_feed()
            elif character == "\b":
                self.x = max(0, self.x - 1)
            elif character == "\t":
                self.x = min(self.width - 1, (self.x // 8 + 1) * 8)
            elif ord(character) >= 32:
                self.put(character)

    def lines(self):
        return ["".join(row) for row in self.cells]


@unittest.skipUnless(os.name == "posix", "PTY smoke test requires Unix")
class TerminalSession(unittest.TestCase):
    symbols = "ascii"
    map_ref = None
    test_map = False
    direct_test_map = False
    test_profile = None

    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.original_attributes = termios.tcgetattr(self.slave)
        self.screen = TerminalScreen(80, 24)
        self.resize(80, 24)
        self.save_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.save_directory.cleanup)
        self.save_path = Path(self.save_directory.name) / "quicksave.json"
        from tuidungeon.content.packs import DEFAULT_PACKS, PackStore

        pack_root = Path(self.save_directory.name) / "packs"
        shutil.copytree(DEFAULT_PACKS, pack_root)
        install_test_maps(pack_root)
        store = PackStore(pack_root)
        env = os.environ.copy()
        env.pop("KITTY_WINDOW_ID", None)
        env.pop("WEZTERM_PANE", None)
        env.update(TERM="xterm-256color", LC_ALL="C.UTF-8", PYTHONUTF8="1")
        self.process = subprocess.Popen(
            [
                str(Path(__file__).resolve().parents[1] / "run.sh"),
                "--terminal",
                "--packs-dir",
                str(pack_root),
                "--seed",
                "42",
                "--symbols",
                self.symbols,
                "--save-file",
                str(self.save_path),
            ]
            + (
                ["--test-map" if self.direct_test_map else "--map", self.map_ref]
                if self.map_ref
                else []
            )
            + (["--test-map"] if self.test_map and not self.direct_test_map else [])
            + (["--test-wizard"] if self.test_profile == "wizard" else []),
            cwd="/tmp",
            env=env,
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
        )
        self.addCleanup(self.stop_process)
        if self.map_ref:
            catalog = store.runtime_catalog()
        else:
            catalog = None
        self.controller = Controller(
            42,
            symbols=self.symbols,
            map_ref=self.map_ref,
            catalog=catalog,
            test_map=self.test_map,
            test_profile=self.test_profile,
            save_path=self.save_path,
            store=store,
        )
        self.expect_frame()

    def stop_process(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=3)

    def resize(self, width, height):
        fcntl.ioctl(
            self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0)
        )
        self.screen.resize(width, height)
        if hasattr(self, "process"):
            self.process.send_signal(signal.SIGWINCH)

    def read_output(self, timeout=0.05):
        readable, _, _ = select.select([self.master], [], [], timeout)
        if readable:
            data = os.read(self.master, 65536)
            self.screen.feed(data)

    def expect_frame(self):
        expected = render(self.controller, self.screen.width, self.screen.height)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.read_output()
            if self.screen.lines() == expected:
                return
            if self.process.poll() is not None:
                break
        self.assertEqual(
            self.screen.lines(),
            expected,
            "Actual curses output differs from expected frame",
        )

    def key(self, raw, normalized):
        self.controller.handle(normalized)
        os.write(self.master, raw)
        self.expect_frame()


class WizardTerminalTests(TerminalSession):
    map_ref = "base:crypt"
    test_profile = "wizard"

    def test_wizard_direct_launch_spell_menu_save_and_exit(self):
        import json

        self.assertEqual(self.controller.view, View.EXPLORE)
        hero = self.controller.engine.state.hero
        self.assertEqual(hero.character_class.id, "wizard")
        self.assertEqual({s.id for s in hero.known_spells}, set(hero.catalog.spells))
        self.key(b"3", "3")
        self.key(b"2", "2")
        self.key(b"\x7f", "backspace")
        self.key(b"\x7f", "backspace")
        self.key(b"m", "m")
        self.key(b"1", "1")
        saved = json.loads(self.save_path.read_text())
        self.assertEqual(saved["test_profile"], "wizard")
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class TerminalTests(TerminalSession):
    def test_cantrip_item_cast_cancel_and_save_in_real_terminal(self):
        import json

        self.key(b"\r", "enter")
        for digit in b"121212345612371":
            self.key(bytes([digit]), chr(digit))
        self.assertEqual(self.controller.view, View.EXPLORE)
        hero = self.controller.engine.state.hero
        maximum = hero.max_cantrip_uses
        for digit in b"3231":  # Actions → Magic → Light → staff.
            self.key(bytes([digit]), chr(digit))
        self.assertEqual(
            (hero.cantrip_uses, self.controller.engine.state.turns), (maximum - 1, 1)
        )
        self.assertEqual(self.controller.engine.magic_effects[0].turns, 10)
        for digit in b"324":
            self.key(bytes([digit]), chr(digit))
        self.assertEqual(self.controller.view, View.SPELL_TARGET)
        self.key(b"d", "d")
        self.key(b"\x08", "backspace")
        self.assertEqual(
            (hero.cantrip_uses, self.controller.engine.state.turns), (maximum - 1, 1)
        )
        self.key(b"m", "m")
        self.key(b"1", "1")
        saved = json.loads(self.save_path.read_text())
        self.assertEqual(saved["hero"]["cantrip_uses"], maximum - 1)
        self.assertEqual(saved["magic_effects"][0]["kind"], "light")
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_wasd_creation_buttons_background_confirmation_and_bold_focus(self):
        self.key(b"\r", "enter")
        self.key(b"d", "d")
        self.key(b"a", "a")
        self.key(b"\r", "enter")
        self.key(b"s", "s")
        self.key(b"\r", "enter")
        self.assertIn("Мудрец", "\n".join(self.screen.lines()))
        self.key(b"h", "h")
        self.key(b"\r", "enter")
        self.key(b"\r", "enter")
        for _ in range(6):
            self.key(b"\r", "enter")
        for digit in b"1237":
            self.key(bytes([digit]), chr(digit))
        line = self.screen.lines()[18]
        self.assertIn("[ Начать приключение ]", line)
        self.assertTrue(self.screen.bold_cells.get((18, line.index("["))))
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"\r", "enter")
        self.assertEqual(self.controller.engine.state.hero.background.id, "sage")
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def assert_menu_bold(self):
        for x, y, text, selected in menu_entries(
            self.controller, self.screen.width, self.screen.height
        ):
            for column in range(x, x + len(text)):
                self.assertEqual(
                    self.screen.bold_cells.get((y, column), False), selected
                )

    def test_main_menu_bold_navigation_screens_resize_and_exit(self):
        self.assert_menu_bold()
        self.key(b"\x1bOB", "down")
        self.assert_menu_bold()
        self.key(b"\n", "enter")
        self.key(b"\x7f", "backspace")
        self.key(b"s", "s")
        self.key(b"\r", "enter")
        self.key(b"2", "2")
        self.key(b"\x08", "backspace")
        self.assert_menu_bold()
        self.key(b"4", "4")
        self.key(b"\x1b", "escape")
        self.resize(100, 30)
        self.expect_frame()
        self.assert_menu_bold()
        self.key(b"w", "w")
        self.assert_menu_bold()
        os.write(self.master, b"5")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_creation_gameplay_resize_and_exit_restore_terminal(self):
        self.key(b"\r", "enter")
        # Navigate back using both common byte encodings of Backspace.
        self.key(b"1", "1")
        self.key(b"\x7f", "backspace")
        self.key(b"3", "3")
        self.key(b"2", "2")
        self.key(b"1", "1")
        self.key(b"2", "2")
        self.key(b"1", "1")
        self.key(b"\x08", "backspace")
        for digit in b"12345612371":
            self.key(bytes([digit]), chr(digit))
        self.key(b"\x1bOC", "right")  # Application-mode arrow, enabled by keypad(True).
        self.assertTrue(self.controller.spells_tab)
        self.key(b"\x1bOB", "down")
        self.key(b"\x1bOD", "left")
        self.assertFalse(self.controller.spells_tab)
        self.key(b"\x1bOA", "up")
        self.assertEqual(self.controller.engine.state.turns, 0)
        self.assertEqual(self.controller.engine.state.position.x, 3)
        self.assertEqual(self.controller.engine.state.position.y, 3)
        for key in b"dsaw":
            self.key(bytes([key]), chr(key))
        self.key(b"\t", "tab")
        self.key(b"2", "2")
        self.key(b"w", "w")  # Movement is ignored on the character screen.
        self.key(b"\x7f", "backspace")
        self.key(b"3", "3")
        self.key(b"3", "3")
        self.key(b"\x7f", "backspace")
        self.key(b"4", "4")
        self.key(b"2", "2")
        self.assertEqual(self.controller.engine.state.turns, 6)
        self.resize(40, 10)
        self.expect_frame()
        os.write(self.master, b"3")  # No resting while the terminal is too small.
        for _ in range(3):
            self.read_output()
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"q", "q")
        os.write(self.master, b"2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_q_exits_during_creation_and_restores_terminal(self):
        self.key(b"\r", "enter")
        if self.controller.engine:
            self.key(b"q", "q")
            os.write(self.master, b"2")
        else:
            os.write(self.master, b"q")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_ctrl_c_restores_terminal(self):
        self.process.send_signal(signal.SIGINT)
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class UnicodeTerminalTests(TerminalSession):
    symbols = "unicode"

    def test_unicode_panels_movement_and_arrows(self):
        self.key(b"\r", "enter")
        for key in b"11121234561":
            self.key(bytes([key]), chr(key))
        # Equip a light before checking wall glyphs in the dark dungeon.
        for text in ("shield", "torch"):
            self.key(b"f", "f")
            if text == "torch":
                for _ in "shield":
                    self.key(b"\x7f", "backspace")
            for key in text.encode():
                self.key(bytes([key]), chr(key))
            self.key(b"\r", "enter")
            self.key(b"\r", "enter")
            self.key(b"1", "1")
            self.key(b"\x7f", "backspace")
        self.assertIn("█", "\n".join(self.screen.lines()))
        self.assertIn("┌", "\n".join(self.screen.lines()))
        self.key(b"d", "d")
        self.key(b"\x1bOC", "right")
        self.key(b"\x1bOD", "left")
        self.assertEqual(self.controller.engine.state.turns, 3)
        if self.controller.engine:
            self.key(b"q", "q")
            os.write(self.master, b"2")
        else:
            os.write(self.master, b"q")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class MapTerminalTests(TerminalSession):
    map_ref = "base:crypt"

    def test_authored_map_trap_context_choice_backspace_and_exit(self):
        self.key(b"\r", "enter")
        for digit in b"11121234561":
            self.key(bytes([digit]), chr(digit))
        for _ in range(3):
            self.key(b"d", "d")
        engine = self.controller.engine
        self.assertTrue(engine.state.level.traps[0].triggered)
        self.assertEqual(engine.state.hero.hp, engine.state.hero.max_hp - 2)
        turns = engine.state.turns
        self.key(b"\r", "enter")
        self.key(b"\x7f", "backspace")
        self.assertEqual(engine.state.turns, turns)
        self.key(b"\r", "enter")
        self.assertIs(self.controller.view, View.STORAGE)
        self.key(b"\x1bOS", "f4")
        self.key(b"2", "2")
        self.assertTrue(engine.state.level.points[0].challenge.completed)
        self.key(b"\x1bOC", "right")
        self.key(b"\x1bOD", "left")
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.process.wait(timeout=3)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class StorageTerminalTests(TerminalSession):
    map_ref = "dev:storage_lab"
    test_map = True

    def test_exchange_slider_cancel_resize_and_restore_terminal(self):
        self.key(b"\r", "enter")
        self.key(b"1", "1")  # Several objects nearby: choose the personal chest.
        self.assertIs(self.controller.view, View.STORAGE)
        self.key(b"\r", "enter")
        self.assertIsNotNone(self.controller.storage.pending)
        self.key(b"\x1bOC", "right")
        self.assertEqual(self.controller.storage.quantity, 2)
        self.key(b"\x7f", "backspace")
        self.assertIsNone(self.controller.storage.pending)
        self.key(b"\x1b[15~", "f5")
        self.key(b"\x1bOC", "right")
        self.key(b"\r", "enter")
        container = self.controller.engine.storage_at("personal_chest")
        self.assertEqual(len(container.items), 3)
        self.key(b"\t", "tab")
        self.resize(100, 30)
        self.expect_frame()
        self.assertEqual(self.controller.engine.state.turns, 0)
        self.key(b"\x7f", "backspace")
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class TestMapTerminalTests(TerminalSession):
    map_ref = "base:crypt"
    test_map = True

    def test_lamp_equipping_fuel_save_load_rest_and_resize(self):
        for text in ("shield", "lamp"):
            self.key(b"f", "f")
            if text == "lamp":
                for _ in "shield":
                    self.key(b"\x7f", "backspace")
            for key in text.encode():
                self.key(bytes([key]), chr(key))
            self.key(b"\r", "enter")
            if text == "lamp":
                # "lamp" also matches the oil's lamp_oil tag. Select the lamp row.
                self.key(b"\x1bOB", "down")
                self.key(b"\x1bOB", "down")
            self.key(b"\r", "enter")
            self.key(b"1", "1")
            self.key(b"\x7f", "backspace")
        self.assertIn("Свет: 59м", "\n".join(self.screen.lines()))
        self.assertIn("Руки заняты: 2/2", "\n".join(self.screen.lines()))
        self.key(b"d", "d")
        self.assertIn("Свет: 58м", "\n".join(self.screen.lines()))
        self.key(b"m", "m")
        self.key(b"1", "1")
        self.key(b"\x1b", "escape")
        self.key(b"d", "d")
        self.key(b"m", "m")
        self.key(b"2", "2")
        self.assertIn("Свет: 58м", "\n".join(self.screen.lines()))
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"4", "4")
        self.key(b"1", "1")
        lamp = next(
            i for i in self.controller.engine.state.hero.inventory if i.id == "lamp"
        )
        self.assertEqual((lamp.fuel_minutes, lamp.lit), (0, False))
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_conditions_tab_and_character_summary_survive_resize(self):
        self.key(b"\x1bOC", "right")
        self.key(b"\x1bOC", "right")
        self.assertIn("Состояния", self.screen.lines()[0])
        self.assertIn("Благословление: --", "\n".join(self.screen.lines()))
        self.key(b"2", "2")
        self.assertIn("Квесты", self.screen.lines()[0])
        self.assertIn("Ослепление: --", "\n".join(self.screen.lines()))
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"\x7f", "backspace")
        self.assertIn("Состояния", self.screen.lines()[0])
        self.key(b"\t", "tab")
        self.assertIn("Инвентарь", self.screen.lines()[0])
        self.assertEqual(self.controller.engine.state.turns, 0)
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_inventory_pages_search_overlay_throw_and_ground_pickup(self):
        self.key(b"2", "2")
        self.key(b"\x1bOC", "right")
        self.assertIn("Квесты", self.screen.lines()[0])
        self.key(b"f", "f")
        for character in "меч":
            self.key(character.encode("utf-8"), character)
        self.key(b"\r", "enter")
        self.key(b"\r", "enter")
        self.key(b"2", "2")
        self.assertIn("Осмотр предмета", self.screen.lines()[2])
        self.key(b"\x1bOB", "down")
        self.key(b"\x7f", "backspace")
        self.key(b"3", "3")
        self.key(b"\x1bOC", "right")
        self.key(b"\r", "enter")
        self.assertEqual(self.controller.view, View.CHARACTER)
        self.assertEqual(self.controller.engine.state.turns, 1)
        self.key(b"\x7f", "backspace")
        self.key(b"d", "d")
        self.key(b"g", "g")
        self.assertEqual(self.controller.engine.state.turns, 3)
        self.key(b"f", "f")
        self.key(b"\x1b", "escape")
        self.resize(100, 30)
        self.expect_frame()
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_look_blinks_sheet_is_bold_and_menu_save_load_rest_work(self):
        from tuidungeon.ui import Layout
        from tuidungeon.presentation.tui import camera

        self.key(b"1", "1")
        self.key(b"d", "d")
        rect = Layout.for_size(80, 24).main
        cx, cy = camera(self.controller, rect)
        position = self.controller.look_position
        cell = (position.y - cy + 1, position.x - cx + 1)
        before = self.screen.reverse_cells.get(cell)
        deadline = time.monotonic() + 1.2
        while (
            self.screen.reverse_cells.get(cell) == before
            and time.monotonic() < deadline
        ):
            self.read_output()
        self.assertNotEqual(self.screen.reverse_cells.get(cell), before)
        self.key(b"\r", "enter")
        self.key(b"\x7f", "backspace")
        self.key(b"\x7f", "backspace")
        self.key(b"2", "2")
        line = self.screen.lines()[1]
        self.assertTrue(self.screen.bold_cells.get((1, line.index("Раса:"))))
        self.key(b"]", "]")
        self.key(b"\r", "enter")
        self.key(b"\x7f", "backspace")
        self.key(b"\x7f", "backspace")
        self.key(b"\x1b[57443;3u", "alt_press")
        self.key(b"\x1b[57443;1:3u", "alt_release")
        self.key(b"m", "m")
        self.key(b"1", "1")
        self.key(b"\x1b", "escape")
        self.assertTrue(self.save_path.exists())
        self.key(b"d", "d")
        self.key(b"m", "m")
        self.key(b"2", "2")
        self.assertEqual(self.controller.engine.state.turns, 0)
        self.key(b"4", "4")
        self.key(b"1", "1")
        self.assertEqual(self.controller.engine.state.clock.elapsed_minutes, 540)
        self.key(b"m", "m")
        self.key(b"4", "4")
        self.key(b"1", "1")
        self.key(b"2", "2")
        self.assertEqual(self.controller.engine.state.clock.elapsed_minutes, 480)
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)

    def test_immediate_map_movement_trap_and_exit(self):
        self.assertIn("Подземелье", "\n".join(self.screen.lines()))
        self.assertNotIn("Создание героя", "\n".join(self.screen.lines()))
        for key in b"ddd":
            self.key(bytes([key]), chr(key))
        self.assertTrue(self.controller.engine.state.level.traps[0].triggered)
        self.key(b"q", "q")
        self.key(b"2", "2")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.original_attributes)


class DirectTestMapTerminalTests(TestMapTerminalTests):
    direct_test_map = True


if __name__ == "__main__":
    unittest.main()
