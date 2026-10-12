"""Map skins preserve visibility, UI text and the original text renderer."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, call, patch

import numpy as np
import tcod.console
import tcod.event as events

from scripts.testing import fixture_store
from tuidungeon.presentation.tilesets import (
    SPRITE_START,
    load_symbol_tileset,
    load_map_style,
    save_map_style,
)
from tuidungeon.presentation.tui import (
    Controller,
    View,
    handle_click,
    popup_layout,
    render,
)
from tuidungeon.presentation.window import draw, load_tileset, render_map, run
from tuidungeon.world.graphics import glyph_cell
from tuidungeon.world.lighting import shaded_cell


class MapTilesetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = fixture_store()
        cls.font = load_tileset()
        cls.tileset, cls.mapping = load_symbol_tileset(cls.font, cls.store.documents)

    def controller(self):
        c = Controller(
            42,
            symbols="unicode",
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:crypt",
            test_map=True,
        )
        c.windowed = True
        return c

    def test_atlas_manifest_and_persistent_selection(self):
        self.assertEqual(self.tileset.tile_shape, (16, 16))
        self.assertGreater(self.tileset[ord("Я")][:, :, 3].sum(), 0)
        for (category, ref), symbol in self.store.documents.items():
            if category != "symbols":
                continue
            self.assertIn(ref, self.mapping)
            sprite = self.mapping[ref]
            self.assertGreaterEqual(ord(sprite), SPRITE_START)
            expected = sum(row.count("1") for row in symbol.pixels) * 255
            self.assertEqual(int(self.tileset[ord(sprite)][:, :, 3].sum()), expected)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saves" / "appearance.json"
            self.assertEqual(load_map_style(path), "text")
            for style in ("symbols", "text"):
                save_map_style(style, path)
                self.assertEqual(load_map_style(path), style)
                self.assertEqual(list(path.parent.iterdir()), [path])
            for invalid in ("{", "[]", '{"map_style": []}', '{"map_style": "unknown"}'):
                path.write_text(invalid, encoding="utf-8")
                self.assertEqual(load_map_style(path), "text")
            with self.assertRaises(ValueError):
                save_map_style("unknown", path)

    def test_keyboard_and_click_settings_keep_text_and_terminal_modes(self):
        c = self.controller()
        c.return_view, c.view = View.EXPLORE, View.SETTINGS
        c.handle("4")
        self.assertEqual(c.map_style, "symbols")
        c.handle("3")
        c.dialog_index = 2
        c.handle("down")
        c.handle("enter")
        self.assertEqual(c.map_style, "symbols")
        for width, height in ((80, 24), (100, 28)):
            text = "\n".join(render(c, width, height))
            self.assertIn("Символы", text)
            _, rect, _, hits = popup_layout(c, width, height)
            row = next(row for index, row in hits if index == 2)
            self.assertTrue(
                handle_click(c, rect.x + 3, rect.y + 1 + row, width, height)
            )
            self.assertEqual(c.map_style, "text")
            c.handle("4")
        c.windowed = False
        c.handle("3")
        c.handle("4")
        self.assertEqual(c.map_style, "text")
        self.assertEqual(c.engine.state.turns, 0)

    def test_skin_preserves_darkness_light_colors_cursor_and_ui(self):
        c = self.controller()
        state = c.engine.state
        initial = state.position, state.turns, c.game_rng.getstate()
        for ambient in ("dark", "dim", "bright"):
            state.level.definition = state.level.definition.model_copy(
                update={"ambient_light": ambient, "lights": []}
            )
            plain = render_map(c, 100, 28, 36)[0]
            c.map_style = "symbols"
            graphical = render_map(c, 100, 28, 36, sprites=self.mapping)[0]
            np.testing.assert_array_equal(
                plain.ch == ord(" "), graphical.ch == ord(" ")
            )
            np.testing.assert_array_equal(plain.fg, graphical.fg)
            np.testing.assert_array_equal(plain.bg, graphical.bg)
            self.assertEqual(
                graphical.ch[graphical.height // 2, graphical.width // 2],
                ord(self.mapping["hero"]),
            )
        before, after = tcod.console.Console(100, 28), tcod.console.Console(100, 28)
        c.map_style = "text"
        draw(before, c)
        c.map_style = "symbols"
        draw(after, c)
        np.testing.assert_array_equal(before.rgb, after.rgb)
        c.view, c.look_position = View.LOOK, state.position
        cursor = render_map(c, 100, 28, 36, sprites=self.mapping)[0]
        self.assertEqual(cursor.ch[cursor.height // 2, cursor.width // 2], ord("X"))
        c.view = View.EXPLORE
        cells = [
            [
                shaded_cell(glyph_cell("#", 7, visual_ref="tiles/base:wall"), 1),
                shaded_cell(glyph_cell("#", 6, visual_ref="objects/base:barricade"), 1),
                glyph_cell("Ж", 13),
                glyph_cell("#", 7, visual_ref="objects/custom:unknown"),
            ]
        ]
        with patch.object(c.engine, "render_cells", return_value=cells):
            fallback = render_map(c, 100, 28, 36, sprites=self.mapping)[0]
        self.assertIn(ord(self.mapping["tiles/base:wall"]), fallback.ch)
        self.assertIn(ord(self.mapping["objects/base:barricade"]), fallback.ch)
        self.assertIn(ord(self.mapping.get(("glyph", "Ж"), "Ж")), fallback.ch)
        self.assertIn(ord("#"), fallback.ch)
        self.assertEqual((state.position, state.turns, c.game_rng.getstate()), initial)

    def test_window_loads_graphics_once_and_switches_back_without_restart(self):
        c = self.controller()
        c.view, c.return_view = View.SETTINGS, View.EXPLORE
        context = SimpleNamespace(
            sdl_window=MagicMock(),
            sdl_renderer=MagicMock(),
            new_console=lambda **_: tcod.console.Console(100, 28),
        )

        def key(number):
            return events.KeyDown(
                sym=ord(str(number)),
                scancode=events.Scancode.N4,
                mod=events.Modifier.NONE,
            )

        ui, text_map, graphics_map = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("tuidungeon.presentation.window.Controller", return_value=c),
            patch("tuidungeon.presentation.window.load_map_style", return_value="text"),
            patch("tuidungeon.presentation.window.save_map_style") as save,
            patch(
                "tuidungeon.presentation.window.load_tileset", return_value=self.font
            ),
            patch(
                "tuidungeon.presentation.window.load_symbol_tileset",
                return_value=(self.tileset, self.mapping),
            ) as load,
            patch("tcod.context.new") as create,
            patch("tcod.render.SDLTilesetAtlas"),
            patch(
                "tcod.render.SDLConsoleRender", side_effect=[ui, text_map, graphics_map]
            ),
            patch(
                "tuidungeon.presentation.window.present", return_value=None
            ) as present,
            patch(
                "tcod.event.wait",
                side_effect=[[key(4)], [key(3)], [key(4)], [events.Quit()]],
            ),
        ):
            create.return_value.__enter__.return_value = context
            run()
        load.assert_called_once()
        self.assertEqual(
            save.call_args_list,
            [call("symbols"), call("text"), call("symbols")],
        )
        self.assertEqual(
            [entry.args[2] for entry in present.call_args_list],
            [text_map, graphics_map, text_map, graphics_map],
        )
        self.assertIs(present.call_args_list[-1].kwargs["sprites"], self.mapping)
        self.assertEqual(c.engine.state.turns, 0)

    def test_missing_asset_falls_back_to_text_without_aborting_window(self):
        c = self.controller()
        context = SimpleNamespace(
            sdl_window=MagicMock(),
            sdl_renderer=MagicMock(),
            new_console=lambda **_: tcod.console.Console(100, 28),
        )
        with (
            patch("tuidungeon.presentation.window.Controller", return_value=c),
            patch(
                "tuidungeon.presentation.window.load_map_style",
                return_value="symbols",
            ),
            patch("tuidungeon.presentation.window.save_map_style") as save,
            patch(
                "tuidungeon.presentation.window.load_tileset", return_value=self.font
            ),
            patch(
                "tuidungeon.presentation.window.load_symbol_tileset",
                side_effect=FileNotFoundError("missing sheet"),
            ),
            patch("tcod.context.new") as create,
            patch("tcod.render.SDLTilesetAtlas"),
            patch("tcod.render.SDLConsoleRender"),
            patch("tuidungeon.presentation.window.present", return_value=None),
            patch("tcod.event.wait", return_value=[events.Quit()]),
        ):
            create.return_value.__enter__.return_value = context
            run()
        self.assertEqual(c.map_style, "text")
        self.assertIn("Не удалось загрузить символы", c.message)
        save.assert_called_once_with("text")


if __name__ == "__main__":
    unittest.main()
