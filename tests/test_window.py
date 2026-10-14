"""Window input and colors preserve the existing engine and UI behavior."""

import sys
import unittest
from unittest.mock import MagicMock, patch

import tcod.console
import tcod.event as events

from scripts.testing import fixture_store
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.tui import (
    Controller,
    Layout,
    camera,
    View,
    popup_layout,
    handle_click,
)
from tuidungeon.presentation.menus import ActionMenu
from tuidungeon.world.maps import Position
from tuidungeon.presentation.window import (
    draw,
    draw_map_hint,
    render_map,
    map_area,
    map_zoom,
    TILE_SIZE,
    handle_event,
    load_tileset,
    PALETTE,
    BACKGROUND,
)
from tuidungeon.__main__ import main


class WindowTests(unittest.TestCase):
    def test_new_shortcuts_use_physical_sdl_keys(self):
        c = Controller(42, test_map=True)
        for sym, scan, view, menu in (
            (events.KeySym.I, events.Scancode.I, View.CHARACTER, ActionMenu.ROOT),
            (events.KeySym.M, events.Scancode.M, View.EXPLORE, ActionMenu.MAGIC),
            (events.KeySym.B, events.Scancode.B, View.BUILD, ActionMenu.ROOT),
            (
                events.KeySym.ESCAPE,
                events.Scancode.ESCAPE,
                View.EXPLORE,
                ActionMenu.META,
            ),
        ):
            with self.subTest(scan=scan):
                self.assertTrue(
                    handle_event(
                        c,
                        events.KeyDown(
                            sym=sym, scancode=scan, mod=events.Modifier.NONE
                        ),
                    )
                )
                self.assertEqual((c.view, c.action_menu), (view, menu))
                handle_event(
                    c,
                    events.KeyDown(
                        sym=events.KeySym.ESCAPE,
                        scancode=events.Scancode.ESCAPE,
                        mod=events.Modifier.NONE,
                    ),
                )
                self.assertEqual(
                    (c.view, c.action_menu), (View.EXPLORE, ActionMenu.ROOT)
                )
        self.assertEqual(c.engine.state.turns, 0)

        c.engine.state.hero.inventory[:] = [
            Equipment.create(c.engine.catalog.equipment["wood"]) for _ in range(2)
        ]
        c.inventory.query = "wood"
        c.inventory.selected = 1
        handle_event(
            c,
            events.KeyDown(
                sym=ord("й"), scancode=events.Scancode.Q, mod=events.Modifier.NONE
            ),
        )
        self.assertEqual(c.view, View.DROP)
        handle_event(
            c,
            events.KeyDown(
                sym=events.KeySym.N2,
                scancode=events.Scancode.N2,
                mod=events.Modifier.NONE,
            ),
        )
        handle_event(
            c,
            events.KeyDown(
                sym=events.KeySym.RETURN,
                scancode=events.Scancode.RETURN,
                mod=events.Modifier.NONE,
            ),
        )
        self.assertEqual(c.view, View.EXPLORE)
        self.assertFalse(c.engine.state.hero.inventory)
        self.assertEqual(c.engine.state.turns, 1)

    def test_sneaking_shortcut_recolors_cached_hero_without_spending_a_turn(self):
        store = fixture_store()
        c = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            map_ref="base:crypt",
            test_map=True,
        )
        p = c.engine.state.position
        before = c.engine.render_cells((p.x, p.y, 1, 1))
        self.assertEqual(before[0][0].foreground, 15)
        event = events.KeyDown(
            sym=ord("я"), scancode=events.Scancode.Z, mod=events.Modifier.NONE
        )
        handle_event(c, event)
        after = c.engine.render_cells((p.x, p.y, 1, 1))
        self.assertEqual(after[0][0].foreground, 244)
        console, _, _ = render_map(c, 100, 28, 36)
        self.assertEqual(
            tuple(console.fg[console.height // 2, console.width // 2]), PALETTE[244]
        )
        handle_event(c, event)
        self.assertEqual(c.engine.render_cells((p.x, p.y, 1, 1))[0][0].foreground, 15)
        self.assertEqual(c.engine.state.turns, 0)

    def test_zoom_hint_replaces_old_text_and_stays_complete_at_minimum_width(self):
        c = Controller(42, test_map=True)
        for width in (80, 100, 140):
            for view in (View.EXPLORE, View.LOOK, View.THROW):
                c.view = view
                console = tcod.console.Console(width, 28)
                area = map_area(width, 28)
                console.ch[area.y + area.height, area.x : area.x + area.width] = ord(
                    "ь"
                )
                draw_map_hint(console, c)
                text = "".join(
                    map(
                        chr,
                        console.ch[area.y + area.height, area.x : area.x + area.width],
                    )
                ).rstrip()
                self.assertTrue(text.endswith("+/-: масштаб"), text)
                self.assertNotIn("масштабь", text)

    def test_fonts_and_real_map_lighting_reach_rgb_cells(self):
        store = fixture_store()
        font = load_tileset()
        pixels = font.get_tile(ord("Я"))[:, :, 3].nonzero()[0]
        self.assertGreaterEqual(len(set(pixels)), 12)

        glyphs = set("Русский текст Ёё — ┌┐└┘│─")
        for category, ref in store.documents:
            if category == "tiles":
                glyphs.add(store.get(category, ref).glyph)
        self.assertEqual([char for char in sorted(glyphs) if ord(char) not in font], [])
        controller = Controller(
            42,
            symbols="unicode",
            catalog=store.runtime_catalog(),
            store=store,
            map_ref="base:crypt",
            test_map=True,
        )
        console = tcod.console.Console(100, 32)
        rect = Layout.for_size(100, 32).main
        cx, cy = camera(controller, rect)
        width, height = rect.width - 2, rect.height - 3
        for ambient in ("dark", "dim", "bright"):
            controller.engine.state.level.definition = (
                controller.engine.state.level.definition.model_copy(
                    update={"ambient_light": ambient, "lights": []}
                )
            )
            draw(console, controller)
            cells = controller.engine.render_cells((cx, cy, width, height))
            strengths = set()
            for y, row in enumerate(cells):
                for x, cell in enumerate(row):
                    if cell is None:
                        continue
                    strength = controller.engine.lighting.cells[cy + y][cx + x]
                    strengths.add(strength)
                    actual = console.rgb[rect.y + 1 + y, rect.x + 1 + x]
                    foreground = PALETTE[cell.foreground]
                    background = (
                        BACKGROUND
                        if cell.background is None
                        else PALETTE[cell.background]
                    )
                    if strength == 1:
                        foreground = tuple(value // 2 for value in foreground)
                        background = tuple(value // 2 for value in background)
                    self.assertEqual(actual["ch"], ord(cell.char))
                    self.assertEqual(tuple(actual["fg"]), foreground)
                    self.assertEqual(tuple(actual["bg"]), background)
            self.assertIn({"dark": 0, "dim": 1, "bright": 2}[ambient], strengths)

    def test_square_map_centers_at_world_edges_and_tracks_cursor_and_zoom(self):
        store = fixture_store()
        controller = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            map_ref="base:crypt",
            test_map=True,
        )
        state = controller.engine.state
        area = map_area(100, 28)
        for position in (
            state.position,
            Position(0, 0),
            Position(state.dungeon.width - 1, state.dungeon.height - 1),
        ):
            state.position = position
            for size in (24, 36, 48, 72):
                with patch.object(
                    controller.engine,
                    "render_cells",
                    wraps=controller.engine.render_cells,
                ) as render_cells:
                    console, rect, _ = render_map(controller, 100, 28, size)
                self.assertEqual(
                    console.ch[console.height // 2, console.width // 2], ord("@")
                )
                self.assertEqual(
                    (rect.width // console.width, rect.height // console.height),
                    (size, size),
                )
                self.assertGreaterEqual(rect.x, area.x * TILE_SIZE[0])
                self.assertGreaterEqual(rect.y, area.y * TILE_SIZE[1])
                self.assertLessEqual(
                    rect.x + rect.width, (area.x + area.width) * TILE_SIZE[0]
                )
                self.assertLessEqual(
                    rect.y + rect.height, (area.y + area.height) * TILE_SIZE[1]
                )
                x, y, width, height = render_cells.call_args.args[0]
                self.assertGreaterEqual(min(x, y), 0)
                self.assertLessEqual(x + width, state.dungeon.width)
                self.assertLessEqual(y + height, state.dungeon.height)
        controller.view = View.LOOK
        controller.look_position = Position(0, 0)
        console, _, _ = render_map(controller, 100, 28, 36)
        self.assertEqual(console.ch[console.height // 2, console.width // 2], ord("X"))
        self.assertIsNone(render_map(controller, 79, 23, 36))
        plus = events.KeyDown(
            sym=events.KeySym.PLUS,
            scancode=events.Scancode.EQUALS,
            mod=events.Modifier.NONE,
        )
        self.assertEqual(map_zoom(32, plus), 48)
        self.assertEqual(map_zoom(96, plus), 96)
        wheel = events.MouseWheel(x=0, y=-1, flipped=False)
        self.assertEqual(map_zoom(32, wheel), 16)
        self.assertEqual(map_zoom(16, wheel), 16)
        self.assertEqual(state.turns, 0)

    def test_unicode_text_physical_keys_alt_and_window_close(self):
        controller = Controller(42)

        def key(sym, scancode, mod=events.Modifier.NONE):
            return events.KeyDown(sym=sym, scancode=scancode, mod=mod)

        # Russian layout keeps the physical S command for menu navigation.
        handle_event(controller, key(ord("ы"), events.Scancode.S))
        self.assertEqual(controller.menu_index, 1)
        handle_event(controller, events.TextInput(text="ы"))
        self.assertEqual(controller.menu_index, 1)
        controller.inventory.begin_search()
        handle_event(controller, key(events.KeySym.F, events.Scancode.F))
        handle_event(controller, events.TextInput(text="Факел"))
        self.assertEqual(controller.inventory.query, "факел")
        handle_event(
            controller, key(events.KeySym.BACKSPACE, events.Scancode.BACKSPACE)
        )
        self.assertEqual(controller.inventory.query, "факе")
        handle_event(controller, key(events.KeySym.RETURN, events.Scancode.RETURN))
        self.assertFalse(controller.inventory.editing)
        handle_event(controller, key(events.KeySym.LALT, events.Scancode.LALT))
        self.assertEqual(controller.menu_index, 1)
        handle_event(
            controller, key(events.KeySym.N1, events.Scancode.N1, events.Modifier.ALT)
        )
        self.assertEqual(controller.menu_index, 1)
        handle_event(
            controller,
            events.KeyUp(
                sym=events.KeySym.LALT,
                scancode=events.Scancode.LALT,
                mod=events.Modifier.NONE,
            ),
        )
        self.assertEqual(controller.menu_index, 1)
        handle_event(
            controller,
            events.WindowEvent(type="WindowFocusLost", window_id=1, data=(0, 0)),
        )
        self.assertEqual(controller.menu_index, 1)
        handle_event(
            controller, events.WindowEvent(type="WindowClose", window_id=1, data=(0, 0))
        )
        self.assertFalse(controller.running)

    def test_modal_keyboard_mouse_and_menu_resume_preserve_game_state(self):
        store = fixture_store()
        point = store.get("points_of_interest", "base:chest")
        store.documents["points_of_interest", "base:chest"] = point.model_copy(
            update={
                "storage": point.storage.model_copy(update={"search_contents": True})
            }
        )
        c = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            map_ref="base:crypt",
            test_map=True,
        )
        state = c.engine.state
        initial = state.position, state.turns, state.clock.elapsed_minutes
        for key in ("alt_press", "alt+1", "alt+4", "alt_release"):
            c.handle(key)
        self.assertEqual(c.action_menu, ActionMenu.ROOT)
        self.assertIsNone(popup_layout(c, 100, 28))
        sidebar = Layout.for_size(100, 28).sidebar
        self.assertTrue(handle_click(c, sidebar.x + 2, sidebar.y + 3, 100, 28))
        self.assertEqual(c.view, View.ITEM)
        item = c.selected_item
        c.handle("down")
        c.handle("enter")
        self.assertEqual(c.view, View.ITEM_INSPECT)
        self.assertIsNotNone(render_map(c, 100, 28, 36))
        c.handle("escape")
        c.handle("escape")
        c.handle("escape")
        self.assertEqual(popup_layout(c, 100, 28)[0], "Игровое меню")
        c.handle("w")
        c.handle("down")
        self.assertEqual(c.dialog_index, 1)
        c.handle("3")
        self.assertEqual(c.view, View.HELP)
        c.handle("q")
        self.assertEqual(popup_layout(c, 100, 28)[0], "Выход")
        c.handle("escape")
        c.handle("escape")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIs(c.selected_item, item)
        self.assertEqual(c.action_menu, ActionMenu.ROOT)
        c.open_item(item)
        _, rect, _, hits = popup_layout(c, 100, 28)
        inspect_row = next(row for index, row in hits if index == 1)
        self.assertFalse(handle_click(c, 0, 0, 100, 28))
        self.assertTrue(handle_click(c, rect.x + 3, rect.y + 1 + inspect_row, 100, 28))
        self.assertEqual(c.view, View.ITEM_INSPECT)
        self.assertEqual(
            (state.position, state.turns, state.clock.elapsed_minutes), initial
        )
        console = tcod.console.Console(100, 28)
        draw(console, c)
        rect = popup_layout(c, 100, 28)[1]
        self.assertEqual(tuple(console.bg[rect.y, rect.x]), PALETTE[250])
        c.handle("escape")
        c.handle("escape")
        c.handle("3")
        c.handle("escape")
        c.handle("escape")
        c.handle("escape")
        c.handle("3")
        self.assertEqual(c.action_menu, ActionMenu.ACTIONS)
        c.handle("escape")
        state.position = Position(6, 3)
        c.open_interaction()
        if c.view is View.INTERACTION and c.point_id is None:
            c.handle(
                str(
                    next(
                        i + 1
                        for i, p in enumerate(c.engine.nearby_points())
                        if p.placement.id == "chest_1"
                    )
                )
            )
        if c.view is View.INTERACTION:
            point = next(
                p for p in c.engine.nearby_points() if p.placement.id == c.point_id
            )
            c.handle(
                str(
                    next(
                        i + 1
                        for i, choice in enumerate(
                            point.available_choices(c.engine.state.hero)
                        )
                        if choice.id == "open_storage"
                    )
                )
            )
        self.assertEqual(c.view, View.STORAGE)
        c.handle("f4")
        self.assertEqual(c.view, View.INTERACTION)
        from dataclasses import replace

        point = c.engine.nearby_points()[0]
        original = point.challenge.definition
        point.challenge.definition = replace(
            original, text="Длинное описание окружения. " * 100
        )
        first_page = popup_layout(c, 80, 24)[2]
        c.handle("pagedown")
        self.assertNotEqual(popup_layout(c, 80, 24)[2], first_page)
        c.handle("pageup")
        point.challenge.definition = original
        c.handle("w")
        c.handle("down")
        self.assertEqual(c.dialog_index, 1)
        self.assertEqual(state.turns, 0)
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(state.turns, 1)
        for width, height in ((80, 24), (100, 28), (140, 40)):
            c.handle("escape")
            _, rect, rows, _ = popup_layout(c, width, height)
            self.assertGreater(rect.x, 0)
            self.assertGreater(rect.y, 0)
            self.assertLess(rect.x + rect.width, width)
            self.assertLess(rect.y + rect.height, height)
            self.assertLessEqual(len(rows), rect.height - 2)
            c.handle("escape")

    def test_craft_search_enables_sdl_unicode_text_input(self):
        from tuidungeon.presentation.window import run

        store = fixture_store()
        controller = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        context = MagicMock()
        window = context.sdl_window

        def events_with_text():
            for sym, scan in (
                (events.KeySym.C, events.Scancode.C),
                (events.KeySym.F, events.Scancode.F),
            ):
                yield events.KeyDown(sym=sym, scancode=scan, mod=events.Modifier.NONE)
            window.start_text_input.assert_called_once()
            yield events.TextInput(text="факел")
            self.assertEqual(controller.craft.query, "факел")
            yield events.KeyDown(
                sym=events.KeySym.RETURN,
                scancode=events.Scancode.RETURN,
                mod=events.Modifier.NONE,
            )
            self.assertFalse(controller.craft.editing)
            self.assertEqual(window.stop_text_input.call_count, 2)
            yield events.Quit()

        with (
            patch("tuidungeon.presentation.window.Controller", return_value=controller),
            patch("tuidungeon.presentation.window.load_map_style", return_value="text"),
            patch("tuidungeon.presentation.window.load_tileset"),
            patch("tcod.context.new") as create_context,
            patch("tcod.render.SDLTilesetAtlas"),
            patch("tcod.render.SDLConsoleRender"),
            patch("tuidungeon.presentation.window.present", return_value=None),
            patch("tcod.event.wait", side_effect=lambda _: events_with_text()),
        ):
            create_context.return_value.__enter__.return_value = context
            run()
        self.assertEqual(controller.engine.state.turns, 0)

    def test_default_cli_opens_window_without_tty_and_validation_stays_headless(self):
        with (
            patch.object(sys, "argv", ["tuidungeon", "--test-map", "base:crypt"]),
            patch.object(sys.stdin, "isatty", return_value=False),
            patch.object(sys.stdout, "isatty", return_value=False),
            patch("tuidungeon.presentation.window.run") as launch,
        ):
            self.assertEqual(main(), 0)
            args = launch.call_args.args
            self.assertEqual(
                (args[1], args[3], args[5]), ("unicode", "base:crypt", True)
            )
            launch.reset_mock()
            with patch.object(sys, "argv", ["tuidungeon", "--validate-content"]):
                self.assertEqual(main(), 0)
            launch.assert_not_called()
            with patch.object(sys, "argv", ["tuidungeon", "--terminal"]):
                self.assertEqual(main(), 1)
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
