"""Craft groups and furniture salvage use real commands and seeded dice."""

from collections import Counter
from copy import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.crafting import craft_layout, craft_click
from tuidungeon.presentation.tui import Controller, View
from tuidungeon.world.maps import Position


class CraftFurnitureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.store.documents["maps", "dev:crafting_lab"] = self.store.get(
            "maps", "dev:crafting_lab"
        ).model_copy(update={"ambient_light": "bright", "lights": []})
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        self.e.state.hero.tool_proficiencies.clear()
        self.target = self.e.world_object("lab_table")
        self.position = Position(self.target.placement.x, self.target.placement.y)
        self.e.state.position = Position(self.position.x - 1, self.position.y)

    def give(self, ref):
        item = Equipment.create(self.e.catalog.equipment[ref])
        self.e.state.hero.inventory.append(item)
        return item

    def drops(self, engine=None):
        engine = engine or self.e
        return Counter(
            i.id
            for p, i in engine.state.items
            if (p.x, p.y) == (self.position.x, self.position.y)
        )

    def test_wood_requires_physical_carpenter_tools_without_proficiency(self):
        self.assertFalse(self.e.start_dismantle("lab_table").performed)
        self.give("crowbar")
        self.assertFalse(self.e.start_dismantle("lab_table").performed)
        self.e.state.hero.tool_proficiencies.add("carpenter_tools")
        self.assertFalse(self.e.start_dismantle("lab_table").performed)
        self.e.state.hero.tool_proficiencies.clear()
        self.give("carpenter_tools")
        self.assertTrue(self.e.start_dismantle("lab_table").performed)
        self.assertEqual(self.e.state.turns, 0)
        self.assertFalse(self.e.state.hero.tool_proficiencies)

    def test_missing_tool_pauses_and_save_restores_guaranteed_hardware(self):
        tools = self.give("carpenter_tools")
        self.assertTrue(self.e.start_dismantle("lab_table").performed)
        self.e.advance_craft()
        progress = self.e.world_object("lab_table").state.progress
        self.e.state.hero.inventory.remove(tools)
        self.assertFalse(self.e.advance_craft().performed)
        self.assertEqual(self.e.world_object("lab_table").state.progress, progress)
        self.e.state.hero.inventory.append(tools)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        self.assertTrue(self.e.start_dismantle("lab_table").performed)
        with patch.object(
            self.e.dice,
            "roll",
            side_effect=AssertionError(
                "Careful dismantling must not roll for hardware"
            ),
        ):
            while self.e.active_craft:
                self.assertTrue(self.e.advance_craft().performed)
        self.assertEqual(self.drops()["furniture_hardware"], 1)
        before = self.drops()
        self.assertFalse(self.e.start_dismantle("lab_table").performed)
        self.assertEqual(self.drops(), before)

    def test_metal_requires_tinker_tools_even_for_custom_legacy_definition(self):
        level = self.e.state.level
        objects = [
            p.model_copy(
                update={
                    "overrides": {
                        "tags": ["furniture", "metal"],
                        "destruction": {
                            "dismantle": {
                                "tools": [],
                                "loot": [{"item": "base:metal", "quantity": 2}],
                            }
                        },
                    }
                }
            )
            if p.id == "lab_table"
            else p
            for p in level.definition.objects
        ]
        level.definition = level.definition.model_copy(update={"objects": objects})
        self.give("carpenter_tools")
        self.assertFalse(self.e.start_dismantle("lab_table").performed)
        self.give("tinker_tools")
        self.assertTrue(self.e.start_dismantle("lab_table").performed)
        while self.e.active_craft:
            self.e.advance_craft()
        self.assertEqual(self.drops()["furniture_hardware"], 0)
        self.assertEqual(self.drops()["metal"], 2)

    def test_destruction_rolls_once_at_the_fifty_percent_boundary(self):
        for roll, quantity in ((50, 1), (51, 0)):
            engine = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
            with patch.object(engine.dice, "roll", return_value=(roll,)) as dice:
                engine.damage_world_objects(self.position, 999, "bludgeoning")
                self.assertEqual(self.drops(engine)["furniture_hardware"], quantity)
                dice.assert_called_once_with(1, 100)
                before = self.drops(engine)
                engine.damage_world_objects(self.position, 999, "bludgeoning")
                self.assertEqual(self.drops(engine), before)
                dice.assert_called_once()
            self.assertLessEqual(self.drops(engine)["wood"], 1)

    def test_save_preserves_destruction_drop_and_following_rng(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e.damage_world_objects(self.position, 999, "bludgeoning")
            expected = self.drops()
            following = self.e.dice.roll(1, 20)
            restored = repo.load(store=self.store)
            restored.damage_world_objects(self.position, 999, "bludgeoning")
            self.assertEqual(self.drops(restored), expected)
            self.assertEqual(restored.dice.roll(1, 20), following)

    def test_all_shipped_wooden_furniture_has_tools_and_fittings(self):
        for (category, ref), doc in self.source.documents.items():
            if (
                category not in ("objects", "points_of_interest")
                or not ("furniture" in doc.tags or doc.movable)
                or "wooden" not in doc.tags
                or not doc.destruction
                or not doc.destruction.dismantle
            ):
                continue
            spec = doc.destruction.dismantle
            self.assertIn("carpenter_tools", spec.tools, ref)
            self.assertEqual(
                sum(
                    x.quantity for x in spec.loot if x.item == "base:furniture_hardware"
                ),
                1,
                ref,
            )

    def test_groups_fold_by_keyboard_and_mouse_without_spending_time(self):
        c = Controller(42, store=self.store, map_ref="dev:crafting_lab", test_map=True)
        c.engine, c.view = self.e, View.CRAFT
        self.e.state.hero.known_recipes = {"base:repair_wood", "base:craft_pole"}
        c.craft.open()
        rows = c.craft.rows(self.e)
        self.assertEqual(
            [requires for _, recipe, requires in rows if recipe is None], [False, True]
        )
        c.craft.selected = 0
        c.handle("enter")
        self.assertNotIn(
            "base:repair_wood", [r["ref"] for _, r, _ in c.craft.rows(self.e) if r]
        )
        self.assertIn(
            "base:craft_pole", [r["ref"] for _, r, _ in c.craft.rows(self.e) if r]
        )
        self.assertIn("Требует умения в инструменте: нет", c.craft.details(self.e)[0])
        c.handle(" ")
        self.assertIn(
            "base:repair_wood", [r["ref"] for _, r, _ in c.craft.rows(self.e) if r]
        )
        _, rect, _, _, hits = craft_layout(c, 100, 28)
        row, _, index = next(
            h for h in hits if h[1] == "group" and c.craft.rows(self.e)[h[2]][2]
        )
        craft_click(c, rect.x + 3, rect.y + row + 1, 100, 28)
        self.assertNotIn(
            "base:craft_pole", [r["ref"] for _, r, _ in c.craft.rows(self.e) if r]
        )
        c.handle("f")
        for key in "base:craft_pole":
            c.handle(key)
        c.handle("enter")
        self.assertEqual(c.craft.assessment(self.e).ref, "base:craft_pole")
        self.assertEqual(self.e.state.turns, 0)
