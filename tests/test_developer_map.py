"""The developer showcase must remain complete, spaced and playable."""

from collections import deque
from copy import copy
from itertools import combinations
import unittest

from scripts.build_developer_map import build_documents
from tuidungeon.application.engine import Action
from tuidungeon.content.packs import PackStore
from tuidungeon.tooling.sessions import TestSession
from tuidungeon.world.maps import Position


class DeveloperMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = copy(PackStore())
        cls.store.documents = dict(cls.store.documents)
        _, generated, art, _ = build_documents(cls.store)
        cls.store.documents["maps", "dev:all_items"] = generated
        cls.store.documents["art", "dev:" + art.id] = art
        cls.level = cls.store.get("maps", "dev:all_items")

    def test_all_interactive_definitions_are_spaced_and_reachable(self):
        level = self.level
        objects = []
        for category in ("equipment", "points_of_interest", "traps"):
            placements = getattr(level, category)
            expected = {
                ref
                for cat, ref in self.store.documents
                if cat == category and not ref.startswith("dev:")
            }
            self.assertEqual({p.ref for p in placements}, expected)
            self.assertEqual(len(placements), len(expected))
            objects.extend(placements)
        for a, b in combinations(objects, 2):
            self.assertGreaterEqual(max(abs(a.x - b.x), abs(a.y - b.y)), 4)
        seen = {(level.spawn.x, level.spawn.y)}
        pending = deque(seen)
        while pending:
            x, y = pending.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (
                    0 <= nx < level.width
                    and 0 <= ny < level.height
                    and level.walkability[ny][nx]
                    and (nx, ny) not in seen
                ):
                    seen.add((nx, ny))
                    pending.append((nx, ny))
        self.assertTrue(all((p.x, p.y) in seen for p in objects))
        _, generated, art, _ = build_documents(self.store)
        self.assertEqual(generated, level)
        self.assertEqual(art, self.store.get("art", "dev:all_items_labels"))

    def test_pickup_interaction_trap_and_reset_use_real_instances(self):
        session = TestSession(self.store, {"map_ref": "dev:all_items", "seed": 42})
        engine = session.engine
        level = self.level
        for placement in level.equipment:
            engine.state.position = Position(placement.x, placement.y)
            self.assertTrue(engine.pickup_item().performed)
            self.assertEqual(engine.render_cells()[placement.y][placement.x].char, "@")
            engine.state.position = Position(placement.x + 1, placement.y)
            self.assertEqual(engine.render_cells()[placement.y][placement.x].char, ".")
        self.assertFalse(engine.state.level.items)
        point = engine.state.level.points[0]
        engine.state.position = Position(point.placement.x - 1, point.placement.y)
        self.assertIn(point, engine.nearby_points())
        choice = point.challenge.definition.choices[0]
        self.assertTrue(engine.interact(point.placement.id, choice.id).performed)
        trap = engine.state.level.traps[0]
        engine.state.position = Position(trap.placement.x - 1, trap.placement.y)
        self.assertTrue(engine.apply(Action.EAST).performed)
        self.assertTrue(trap.triggered)
        session.reset()
        self.assertEqual(len(session.engine.state.level.items), len(level.equipment))
        self.assertFalse(session.engine.state.level.points[0].challenge.completed)
        self.assertFalse(session.engine.state.level.traps[0].triggered)
        self.assertIs(self.store.get("maps", "dev:all_items"), level)


if __name__ == "__main__":
    unittest.main()
