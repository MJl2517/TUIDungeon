"""The developer showcase must remain complete, spaced and playable."""

from collections import deque
from copy import copy
from itertools import combinations
import unittest
from tuidungeon.application.factories import SessionFactory

from scripts.build_developer_map import build_documents
from tuidungeon.application.engine import Action
from tuidungeon.content.packs import PackStore
from tuidungeon.world.maps import Position


class DeveloperMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = copy(PackStore())
        cls.store.documents = dict(cls.store.documents)
        _, generated, art, cls.entries = build_documents(cls.store)
        cls.store.documents["maps", "dev:all_items"] = generated
        cls.store.documents["art", "dev:" + art.id] = art
        cls.level = cls.store.get("maps", "dev:all_items")

    def test_all_interactive_definitions_are_spaced_and_reachable(self):
        level = self.level
        objects = []
        for category in (
            "equipment",
            "points_of_interest",
            "traps",
            "objects",
            "monsters",
        ):
            placements = list(getattr(level, category))
            if category == "objects":
                placements += level.doors
            expected = {
                ref
                for cat, ref in self.store.documents
                if cat == category and not ref.startswith("dev:")
            }
            self.assertEqual({p.ref for p in placements}, expected)
            self.assertEqual(len(placements), len(expected))
            objects.extend(placements)
        state = SessionFactory(self.store).session("dev:all_items", seed=42).state
        seen = {(level.spawn.x, level.spawn.y)}
        pending = deque(seen)
        while pending:
            x, y = pending.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (
                    0 <= nx < level.width
                    and 0 <= ny < level.height
                    and state.walkable(Position(nx, ny))
                    and (nx, ny) not in seen
                ):
                    seen.add((nx, ny))
                    pending.append((nx, ny))
        self.assertTrue(all((p.x - 1, p.y) in seen for p in objects))
        surfaces = [
            (ref, x, y)
            for _, category, _, ref, x, y in self.entries
            if category == "Поверхности и стены"
        ]
        self.assertEqual(
            {ref for ref, _, _ in surfaces},
            {
                ref
                for cat, ref in self.store.documents
                if cat == "tiles" and not ref.startswith("dev:")
            },
        )
        positions = [(entry[-2], entry[-1]) for entry in self.entries]
        self.assertEqual(len(positions), len(set(positions)))
        for a, b in combinations(positions, 2):
            self.assertGreaterEqual(max(abs(a[0] - b[0]), abs(a[1] - b[1])), 4)
        for ref, x, y in surfaces:
            definition = self.store.get("tiles", ref)
            self.assertEqual(level.tiles[y][x], ref)
            self.assertEqual(level.walkability[y][x], definition.walkable)
            self.assertEqual(level.blocks_sight[y][x], definition.blocks_sight)
            self.assertTrue(
                all(
                    (nx, ny) in seen
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                )
            )
        for placement in level.objects + level.doors:
            self.assertEqual(level.tiles[placement.y][placement.x], "base:floor")
            self.assertTrue(level.walkability[placement.y][placement.x])
            self.assertFalse(level.blocks_sight[placement.y][placement.x])
        expected_lights = {
            (p.x, p.y)
            for p in level.objects
            if self.store.get("objects", p.ref).brush.light
            and not self.store.get("objects", p.ref).light_fixture
        }
        self.assertEqual({(p.x, p.y) for p in level.lights}, expected_lights)
        expected_transitions = {
            (p.x, p.y)
            for p in level.objects
            if self.store.get("objects", p.ref).brush.transition
        }
        self.assertEqual({(p.x, p.y) for p in level.transitions}, expected_transitions)
        self.assertTrue(all(p.target == "dev:all_items" for p in level.transitions))
        _, generated, art, _ = build_documents(self.store)
        self.assertEqual(generated, level)
        self.assertEqual(art, self.store.get("art", "dev:all_items_labels"))

    def test_pickup_interaction_trap_and_reset_use_real_instances(self):
        engine = SessionFactory(self.store).session("dev:all_items", seed=42)
        level = self.level
        for placement in level.equipment:
            engine.state.position = Position(placement.x, placement.y)
            self.assertTrue(engine.pickup_item().performed)
            self.assertEqual(
                engine.render_cells((placement.x, placement.y, 1, 1))[0][0].char, "@"
            )
            engine.state.position = Position(placement.x + 1, placement.y)
            self.assertEqual(
                engine.render_cells((placement.x, placement.y, 1, 1))[0][0].char, "."
            )
        self.assertFalse(engine.state.level.items)
        point = next(
            p
            for p in engine.state.level.points
            if p.challenge and not p.definition.storage
        )
        engine.state.position = Position(point.placement.x - 1, point.placement.y)
        self.assertTrue(
            any(getattr(p, "original", p) is point for p in engine.nearby_points())
        )
        choice = point.challenge.definition.choices[0]
        self.assertTrue(engine.interact(point.placement.id, choice.id).performed)
        trap = engine.state.level.traps[0]
        engine.state.position = Position(trap.placement.x - 1, trap.placement.y)
        self.assertTrue(engine.apply(Action.EAST).performed)
        self.assertTrue(trap.triggered)
        engine = SessionFactory(self.store).session("dev:all_items", seed=42)
        self.assertEqual(len(engine.state.level.items), len(level.equipment))
        self.assertFalse(engine.state.level.points[0].challenge.completed)
        self.assertFalse(engine.state.level.traps[0].triggered)
        self.assertIs(self.store.get("maps", "dev:all_items"), level)


if __name__ == "__main__":
    unittest.main()
