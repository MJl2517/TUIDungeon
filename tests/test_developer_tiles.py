"""Interactive tile showcase: complete recipes, spacing and live transitions."""

from itertools import combinations
from copy import copy
import unittest
from tuidungeon.application.factories import SessionFactory

from scripts.build_developer_tiles import build_documents
from tuidungeon.application.engine import Action
from tuidungeon.content.packs import PackStore
from tuidungeon.world.maps import Position


class DeveloperTileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = copy(PackStore())
        cls.store.documents = dict(cls.store.documents)
        _, cls.generated, cls.art, cls.samples = build_documents(cls.store)
        # Authors can edit the real showcase while tests run. Exercise a fresh
        # generated fixture in memory instead of rewriting their map or art.
        cls.store.documents["maps", "dev:all_interactive_tiles"] = cls.generated
        cls.store.documents["art", "dev:" + cls.art.id] = cls.art
        cls.level = cls.store.get("maps", "dev:all_interactive_tiles")

    def test_every_interactive_tile_appears_once_with_space_between_samples(self):
        expected = [
            ref
            for (category, ref), definition in self.store.documents.items()
            if not ref.startswith("dev:")
            and (
                category in ("equipment", "traps", "points_of_interest")
                or category in ("tiles", "objects")
                and any(definition.brush.model_dump().values())
            )
        ]
        self.assertCountEqual([ref for _, ref, _, _, _ in self.samples], expected)
        self.assertEqual(len(self.samples), len(expected))
        for a, b in combinations(self.samples, 2):
            self.assertGreaterEqual(max(abs(a[3] - b[3]), abs(a[4] - b[4])), 4)
        # Every sample has a clear adjacent approach; even transitions and hazards
        # can be bypassed while walking along the empty row above them.
        for _, _, _, x, y in self.samples:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                self.assertTrue(self.level.walkability[ny][nx])
                self.assertEqual(self.level.tiles[ny][nx], "base:floor")

    def test_all_brush_mechanics_and_masks_are_preserved(self):
        level = self.level
        for _, ref, tile, x, y in self.samples:
            self.assertEqual(
                level.walkability[y][x], True if tile.brush.door else tile.walkable
            )
            self.assertEqual(
                level.blocks_sight[y][x],
                False if tile.brush.door else tile.blocks_sight,
            )
            self.assertEqual(
                level.tiles[y][x],
                tile.brush.underlay or "base:floor",
            )
            for category, reference in (
                ("doors", ref if tile.brush.door else None),
                ("equipment", tile.brush.item),
                ("traps", tile.brush.trap),
                ("points_of_interest", tile.brush.interaction),
            ):
                actual = [
                    p.ref for p in getattr(level, category) if (p.x, p.y) == (x, y)
                ]
                self.assertEqual(actual, [reference] if reference else [])
            lights = [p for p in level.lights if (p.x, p.y) == (x, y)]
            obj = self.store.documents.get(("objects", ref))
            fixture = obj and obj.light_fixture and not tile.brush.item
            self.assertEqual(
                len(lights), int(tile.brush.light is not None and not fixture)
            )
            if lights:
                self.assertEqual(lights[0].radius, tile.brush.light.radius)
                self.assertEqual(
                    lights[0].bright_radius, tile.brush.light.bright_radius
                )
                self.assertTrue(lights[0].enabled)
            transitions = [p for p in level.transitions if (p.x, p.y) == (x, y)]
            self.assertEqual(len(transitions), int(tile.brush.transition))
            if transitions:
                self.assertEqual(transitions[0].target, "dev:all_interactive_tiles")

    def test_pickup_light_and_return_transitions_use_the_game_engine(self):
        engine = SessionFactory(self.store).session(
            "dev:all_interactive_tiles", seed=42
        )
        state = engine.state
        item = self.level.equipment[0]
        state.position = Position(item.x, item.y)
        self.assertTrue(engine.pickup_item().performed)
        state.position = Position(item.x - 1, item.y)
        self.assertEqual(engine.render_cells((item.x, item.y, 1, 1))[0][0].char, ".")
        light = self.level.lights[0]
        state.position = Position(light.x, light.y)
        self.assertEqual(engine.lighting.at(state.position), 2)
        for transition in self.level.transitions:
            state.position = Position(transition.x - 1, transition.y)
            self.assertTrue(engine.apply(Action.EAST).performed)
            self.assertIs(engine.state, state)
            self.assertEqual(
                state.position, Position(self.level.spawn.x, self.level.spawn.y)
            )
            self.assertEqual(engine.events[-1]["kind"], "transition")
            self.assertEqual(len(state.level.items), len(self.level.equipment) - 1)
        engine = SessionFactory(self.store).session(
            "dev:all_interactive_tiles", seed=42
        )
        self.assertEqual(len(engine.state.level.items), len(self.level.equipment))


if __name__ == "__main__":
    unittest.main()
