"""Construction selects a real adjacent map cell before spending materials."""

from pathlib import Path
import tempfile
import unittest

from scripts.testing import fixture_store
from tuidungeon.application.saves import SaveRepository
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.tui import Controller, View
from tuidungeon.world.maps import Position


class BuildCursorTests(unittest.TestCase):
    def test_cursor_cancel_bounds_invalid_cell_and_saved_build_destination(self):
        store = fixture_store()
        c = Controller(
            42,
            store=store,
            catalog=store.runtime_catalog(),
            test_map=True,
            map_ref="dev:crafting_lab",
        )
        e = c.engine
        e.state.position = Position(3, 3)
        e.state.hero.inventory.clear()
        for ref in ("wood", "wood", "tinder", "flint_and_steel"):
            e.state.hero.inventory.append(Equipment.create(e.catalog.equipment[ref]))
        e.state.hero.known_recipes.add("base:build_campfire")
        c.craft.open()
        c.craft.recipe_ref = "base:build_campfire"
        c.craft.query = "Костёр"
        c.view = View.CRAFT
        before = (e.state.turns, len(e.state.hero.inventory))
        self.assertFalse(e.start_craft("base:build_campfire").performed)
        self.assertEqual(before, (e.state.turns, len(e.state.hero.inventory)))
        c.craft.handle(c, "enter")
        self.assertEqual(c.view, View.LOOK)
        self.assertEqual(c.world_target[0], "build")
        c.handle("escape")
        self.assertEqual(c.view, View.CRAFT)
        self.assertEqual(before, (e.state.turns, len(e.state.hero.inventory)))
        c.craft.handle(c, "enter")
        c.handle("enter")  # Hero's own cell cannot be built on.
        self.assertIsNone(e.active_craft)
        for _ in range(8):
            c.handle("right")
        self.assertEqual(c.look_position, Position(4, 3))
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIsNotNone(e.active_craft)
        self.assertEqual(e.workpiece(e.active_craft).work.destination, (4, 3))
        e.advance_craft()
        e.pause_craft()
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "work.json")
            repo.save(e)
            e = repo.load(store=store)
        item = next(i for i in e.state.hero.inventory if i.work)
        self.assertTrue(e.resume_craft(item.instance_id).performed)
        while e.active_craft:
            self.assertTrue(e.advance_craft().performed)
        fire = next(
            o for o in e.world_objects() if getattr(o.definition, "campfire", None)
        )
        self.assertEqual((fire.placement.x, fire.placement.y), (4, 3))


if __name__ == "__main__":
    unittest.main()
