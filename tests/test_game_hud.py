"""HUD placement, coin weight and inspection pointer behavior."""

import unittest

import tcod.console
import tcod.event as events

from scripts.testing import fixture_store
from tuidungeon.presentation.tui import Controller, Layout, View, render, popup_layout
from tuidungeon.presentation.window import (
    draw,
    handle_mouse,
    handle_event,
    render_map,
    PALETTE,
)
from tuidungeon.world.maps import Position


class GameHudTests(unittest.TestCase):
    def setUp(self):
        store = fixture_store()
        self.c = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            map_ref="base:crypt",
            test_map=True,
        )

    def test_clock_gold_experience_and_load_at_all_window_sizes(self):
        c = self.c
        hero = c.engine.state.hero
        equipment_weight = hero.carried_weight
        hero.gold, hero.experience = 50, 123
        self.assertEqual(hero.gold_weight, 0.5)
        self.assertEqual(hero.carried_weight, equipment_weight + 0.5)
        hero.gold = int(hero.max_carry_weight * 100) + 50
        self.assertTrue(hero.overloaded)
        hero.gold = 50
        for width, height in ((80, 24), (100, 28), (140, 40)):
            layout = Layout.for_size(width, height)
            self.assertLess(layout.actions.width, layout.main.width)
            self.assertEqual(layout.status.x, layout.actions.width)
            self.assertEqual(layout.status.x + layout.status.width, width)
            rows = render(c, width, height)
            self.assertIn("День: 1 | 08:00", rows[0][: layout.main.width])
            self.assertIn(
                "Золото: 50 (0.5 кг)",
                "\n".join(
                    row[layout.sidebar.x :] for row in rows[: layout.sidebar.height]
                ),
            )
            self.assertIn("Журнал событий", rows[layout.status.y])
            self.assertNotIn("Опыт:", "\n".join(rows))
            console = tcod.console.Console(width, height)
            draw(console, c)
            for y, row in enumerate(rows):
                if "Золото:" in row:
                    self.assertEqual(
                        tuple(console.fg[y, row.index("Золото:")]), PALETTE[11]
                    )
        c.handle("2")
        self.assertIn("Опыт: 123", "\n".join(render(c, 80, 24)))

    def test_journal_keeps_results_and_engine_events_without_changing_engine_history(
        self,
    ):
        c = self.c
        c.handle("3")
        c.handle("3")
        c.handle("escape")
        wait = c.message
        c.engine.events.append({"kind": "fire", "message": "Факел погас."})
        events_before = tuple(c.engine.events)
        c.handle("z")
        self.assertEqual(tuple(c.engine.events), events_before)
        messages = [entry["message"] for entry in c.logs]
        self.assertIn(wait, messages)
        self.assertEqual(messages[-2], "Факел погас.")
        self.assertEqual(messages[-1], c.message)
        count, turns, minutes = (
            len(c.logs),
            c.engine.state.turns,
            c.engine.state.clock.elapsed_minutes,
        )
        c.handle("e")
        c.look_position = Position(4, 9)
        rows = render(c, 100, 28)
        rect = Layout.for_size(100, 28).status
        preview = "\n".join(row[rect.x :] for row in rows[rect.y :])
        self.assertIn("Осмотр (4, 9)", preview)
        self.assertIn("не видна", preview)
        self.assertNotIn(c.engine.state.items[0][1].name, preview)
        c.look_position = Position(5, 3)
        preview = "\n".join(render(c, 100, 28)[rect.y :])
        self.assertNotIn(c.engine.state.level.traps[0].definition.name, preview)
        c.handle("escape")
        self.assertIn(wait, "\n".join(render(c, 100, 28)[rect.y :]))
        self.assertEqual(
            (len(c.logs), c.engine.state.turns, c.engine.state.clock.elapsed_minutes),
            (count, turns, minutes),
        )
        for i in range(210):
            c.message = f"Событие {i}"
        self.assertEqual(len(c.logs), 200)
        self.assertEqual(c.logs[-1]["message"], "Событие 209")

    def test_consecutive_steps_stack_but_other_events_break_the_stack(self):
        c = self.c
        for key in "dad":
            c.handle(key)
        self.assertEqual(c.logs[-1], {"message": "Вы сделали шаг (3).", "steps": 3})
        self.assertEqual(c.engine.state.turns, 3)
        c.handle("z")
        c.handle("a")
        self.assertEqual(c.logs[-1], {"message": "Вы сделали шаг.", "steps": 1})
        c.engine.events.append({"kind": "fire", "message": "Факел погас."})
        c.message = "Вы делаете шаг. Факел погас."
        self.assertIn("Факел погас.", c.logs[-1]["message"])
        c.handle("d")
        self.assertEqual(c.logs[-1]["steps"], 1)
        self.assertIn("Вы сделали шаг (3).", "\n".join(e["message"] for e in c.logs))

    def test_journal_pages_latest_first_and_restores_view_without_spending_time(self):
        c = self.c
        c.logs.clear()
        for i in range(45):
            c.message = f"Событие {i}: " + "длинное описание " * 4
        c.handle("e")
        before = (
            c.engine.state.turns,
            c.engine.state.clock.elapsed_minutes,
            list(c.logs),
        )
        for width, height in ((80, 24), (100, 28), (140, 40)):
            handle_event(
                c,
                events.KeyDown(
                    sym=ord("д"), scancode=events.Scancode.L, mod=events.Modifier.NONE
                ),
            )
            self.assertEqual(c.view, View.JOURNAL)
            rows = render(c, width, height)
            self.assertTrue(all(len(row) == width for row in rows))
            self.assertIn("Событие 44:", "\n".join(popup_layout(c, width, height)[2]))
            self.assertGreater(c.log_pages, 2)
            draw(tcod.console.Console(width, height), c)
            c.handle("up")
            self.assertEqual(c.log_page, 1)
            self.assertNotIn(
                "Событие 44:", "\n".join(popup_layout(c, width, height)[2])
            )
            c.handle("pageup")
            self.assertEqual(c.log_page, 2)
            c.handle("home")
            oldest = "\n".join(popup_layout(c, width, height)[2])
            self.assertIn("Событие 0:", oldest)
            c.handle("up")
            self.assertEqual(c.log_page, c.log_pages - 1)
            c.handle("down")
            self.assertEqual(c.log_page, c.log_pages - 2)
            c.handle("end")
            c.handle("pagedown")
            self.assertEqual(c.log_page, 0)
            c.handle("escape")
            self.assertEqual(c.view, View.LOOK)
        self.assertEqual(
            (c.engine.state.turns, c.engine.state.clock.elapsed_minutes, list(c.logs)),
            before,
        )
        c.handle("l")
        c.handle("l")
        self.assertEqual(c.view, View.LOOK)
        c.handle("escape")
        c.handle("f")
        c.handle("l")
        self.assertTrue(c.inventory.editing)
        self.assertEqual(c.inventory.query, "l")
        self.assertEqual(c.view, View.EXPLORE)

    def test_keyboard_and_mouse_obey_look_range_and_only_known_walls(self):
        import random
        from tuidungeon.application.engine import Engine
        from tuidungeon.domain.stats import Stats
        from tuidungeon.world.maps import DungeonMap
        from tuidungeon.world.state import GameState

        c = self.c
        hero = c.engine.state.hero
        torch = next(i for i in hero.inventory if i.id == "torch")
        hero.inventory[:] = [torch]
        hero.stats = Stats((10, 10, 10, 10, 3, 10))
        torch.equipped = torch.lit = True
        c.engine = Engine(
            GameState(
                hero,
                DungeonMap((".......", ".......", "...#...", ".......", ".......")),
                Position(1, 2),
            ),
            random.Random(42),
        )
        c.view, c.look_position = View.LOOK, c.engine.state.position
        for _ in range(4):
            c.handle("right")
        self.assertEqual(c.look_position, Position(3, 2))
        console = tcod.console.Console(100, 28)
        frame = render_map(c, 100, 28, 36)
        rect, origin = frame[1], frame[2]

        def hover(position, click=False):
            point = events.Point(
                rect.x + (position.x - origin.x + 0.5) * 36,
                rect.y + (position.y - origin.y + 0.5) * 36,
            )
            event = (
                events.MouseButtonDown(position=point, button=events.MouseButton.LEFT)
                if click
                else events.MouseMotion(position=point)
            )
            return handle_mouse(c, event, frame, 36, console, (1200, 672), (1200, 672))

        self.assertFalse(hover(Position(4, 2), click=True))
        self.assertEqual((c.look_position, c.view), (Position(3, 2), View.LOOK))
        self.assertFalse(hover(Position(5, 0)))
        # Even a forced target must not disclose physical light in the HUD.
        c.look_position = Position(4, 2)
        status = Layout.for_size(100, 28).status
        preview = "\n".join(row[status.x :] for row in render(c, 100, 28)[status.y :])
        self.assertIn("не видна", preview)
        self.assertNotIn("Освещение:", preview)
        torch.lit = False
        c.look_position = Position(2, 2)
        c.handle("right")
        c.handle("right")
        self.assertEqual(c.look_position, Position(4, 2))
        c.handle("right")
        self.assertEqual(c.look_position, Position(4, 2))  # MДР 3, not hidden geometry.
        self.assertTrue(hover(Position(3, 2)))
        self.assertEqual(c.look_position, Position(3, 2))
        self.assertEqual(
            (c.engine.state.turns, c.engine.state.clock.elapsed_minutes), (0, 480)
        )

    def test_hover_and_click_use_scaled_map_coordinates_and_keep_camera_still(self):
        c = self.c
        state = c.engine.state
        before = state.position, state.turns, state.clock.elapsed_minutes, len(c.logs)
        c.handle("e")
        console = tcod.console.Console(100, 28)
        for size in (24, 36, 72):
            c.look_camera = None
            c.look_position = state.position
            frame = render_map(c, 100, 28, size)
            origin, rect = frame[2], frame[1]

            def pointer(position):
                # A 2x HiDPI framebuffer and logical mouse coordinates.
                return events.Point(
                    (rect.x + (position.x - origin.x + 0.5) * size) / 2,
                    (rect.y + (position.y - origin.y + 0.5) * size) / 2,
                )

            for dx in (1, 2):
                position = Position(state.position.x + dx, state.position.y)
                event = events.MouseMotion(position=pointer(position))
                self.assertTrue(
                    handle_mouse(
                        c, event, frame, size, console, (600, 336), (1200, 672)
                    )
                )
                self.assertEqual(c.look_position, position)
                self.assertEqual(render_map(c, 100, 28, size)[2], origin)
            event = events.MouseButtonDown(
                position=pointer(position), button=events.MouseButton.LEFT
            )
            self.assertTrue(
                handle_mouse(c, event, frame, size, console, (600, 336), (1200, 672))
            )
            self.assertEqual(c.view, View.INSPECT)
            self.assertEqual(c.inspection[0], f"Клетка ({position.x}, {position.y})")
            c.handle("escape")
            c.handle("a")
            self.assertIsNone(c.look_camera)
        self.assertEqual(
            (state.position, state.turns, state.clock.elapsed_minutes, len(c.logs)),
            before,
        )


if __name__ == "__main__":
    unittest.main()
