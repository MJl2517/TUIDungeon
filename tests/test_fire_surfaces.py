"""Oil, ignition, door damage and identical client commands."""

from scripts.testing import lay_bedroll

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_doors as door_fixtures
from tuidungeon.application.engine import Action
from tuidungeon.application.saves import SaveRepository, ItemRecord, restore_item
from tuidungeon.content.packs import PackStore
from tuidungeon.content.migrations import compatibility
from tuidungeon.content.schemas import DoorSpec, EquipmentDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.tui import Controller, View, popup_content, render
from tuidungeon.world.maps import Position


class FireSurfaceTests(unittest.TestCase):
    setup_map = door_fixtures.DoorTests.setup_map

    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def item(self, name):
        item = Equipment.create(self.engine.catalog.equipment[name])
        self.engine.state.hero.inventory.append(item)
        return item

    def test_fire_is_red_first_then_brown_and_burns_in_three_turns(self):
        engine = self.setup_map()
        flint = self.item("flint_and_steel")
        target = Position(4, 2)
        self.assertTrue(engine.ignite_cell(flint, target).performed)
        frame = engine.render_cells()
        self.assertEqual((self.instance.door.hp, frame[2][4].foreground), (10, 9))
        self.assertIs(engine.render_cells(), frame)
        engine.inspect_cell(target)
        self.assertIs(engine.render_cells(), frame)
        self.assertIn("5 урона", " ".join(engine.inspect_cell(target)))
        engine.apply(Action.WAIT)
        self.assertEqual(
            (self.instance.door.hp, engine.render_cells()[2][4].foreground), (5, 130)
        )
        engine.apply(Action.WAIT)
        self.assertTrue(self.instance.door.destroyed)
        self.assertTrue(engine.state.walkable(target))
        self.assertEqual(engine.state.turns, 3)

    def test_stone_slab_has_only_attack_and_cannot_be_opened_or_forced(self):
        engine = self.setup_map("stone", locked=True)
        self.assertEqual(
            DoorSpec(material="stone", state="open", locked=True).state, "closed"
        )
        self.assertEqual(
            [c.id for c in self.instance.available_choices(engine.state.hero)],
            ["attack"],
        )
        with patch.object(engine.dice, "roll") as rng:
            for action in ("open", "close", "force", "pick", "bend", "ignite", "acid"):
                self.assertFalse(engine.interact("door", action).performed)
            rng.assert_not_called()
        self.assertFalse(self.instance.door.force_open())
        self.assertFalse(engine.state.walkable(Position(4, 2)))
        self.assertEqual(engine.state.turns, 0)
        engine.state.hero.inventory.clear()
        pickaxe = self.item("pickaxe")
        engine.manage_equipment(pickaxe, True)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (4,) * n):
            self.assertTrue(engine.interact("door", "attack").performed)
        self.assertLess(self.instance.door.hp, 30)
        self.assertIsNone(pickaxe.durability)

    def test_each_hit_wears_weapon_even_when_door_is_immune_and_breaks_it(self):
        engine = self.setup_map("steel")
        engine.state.hero.inventory.clear()
        weapon = self.item("sword")
        engine.manage_equipment(weapon, True)
        weapon.durability = 3
        with patch.object(
            engine.dice, "roll", side_effect=lambda n, sides: (sides,) * n
        ) as rng:
            result = engine.interact("door", "attack")
            self.assertTrue(result.performed)
            self.assertIn("сломано", result.message)
            self.assertEqual(rng.call_args_list[-1].args, (1, 4))
        self.assertEqual(weapon.durability, 0)
        self.assertEqual(self.instance.door.hp, 40)

    def test_acid_uses_two_d6_and_double_damage_on_both_metals(self):
        for material, maximum in (("steel", 40), ("bars", 20)):
            engine = self.setup_map(material)
            acid = self.item("acid_flask")
            with patch.object(engine.dice, "roll", return_value=(2, 3)) as rng:
                self.assertTrue(
                    engine.place_item(acid, Position(4, 2), throwing=True).performed
                )
                rng.assert_called_once_with(2, 6)
            self.assertEqual(self.instance.door.hp, maximum - 10 - 2)
            self.assertTrue(self.instance.door.corroding)
            self.assertNotIn(acid, engine.state.hero.inventory)
            lay_bedroll(engine)
            engine.apply(Action.REST)
            self.assertTrue(self.instance.door.destroyed)

    def test_oil_works_on_blocked_tiles_expires_after_five_subsequent_turns(self):
        engine = self.setup_map()
        oil = self.item("oil")
        target = Position(4, 2)
        self.assertTrue(engine.place_item(oil, target, throwing=True).performed)
        self.assertEqual(engine.state.oil[target], 5)
        self.assertNotIn(oil, engine.state.hero.inventory)
        self.assertEqual(engine.render_cells()[2][4].background, 94)
        self.assertIn("5 ход", " ".join(engine.inspect_cell(target)))
        before = engine.state.turns
        engine.inspect_cell(target)
        self.assertEqual(engine.state.turns, before)
        for remaining in (4, 3, 2, 1):
            engine.apply(Action.WAIT)
            self.assertEqual(engine.state.oil[target], remaining)
        engine.apply(Action.WAIT)
        self.assertNotIn(target, engine.state.oil)
        self.assertNotEqual(engine.render_cells()[2][4].background, 94)

    def test_oil_time_counts_turns_not_minutes_and_covers_any_map_cell(self):
        engine = self.setup_map()
        oil = self.item("oil")
        target = Position(3, 0)  # A visible outer wall, not a door.
        self.assertTrue(engine.place_item(oil, target, throwing=True).performed)
        engine.apply(Action.SHORT_REST)
        self.assertEqual(engine.state.oil[target], 4)
        lay_bedroll(engine)
        engine.apply(Action.REST)
        self.assertEqual(engine.state.oil[target], 3)

    def test_oil_is_consumed_by_first_fire_once_and_non_fire_leaves_it(self):
        engine = self.setup_map()
        target = Position(4, 2)
        oil = self.item("oil")
        flint = self.item("flint_and_steel")
        engine.place_item(oil, target, throwing=True)
        self.assertTrue(engine.ignite_cell(flint, target).performed)
        self.assertEqual(self.instance.door.hp, 5)  # +5 oil, +5 first minute.
        self.assertNotIn(target, engine.state.oil)
        self.assertEqual(sum(e.get("kind") == "oil" for e in engine.events), 1)
        engine.apply(Action.WAIT)
        self.assertTrue(self.instance.door.destroyed)
        engine = self.setup_map()
        engine.state.oil[target] = 5
        self.assertEqual(engine.damage_cell(target, 1), 1)
        self.assertEqual(engine.state.oil[target], 5)
        self.assertEqual(engine.damage_cell(target, 1, "fire"), 6)
        self.assertNotIn(target, engine.state.oil)
        self.assertEqual(engine.damage_cell(target, 1, "fire"), 1)

    def test_oil_on_burning_door_bursts_immediately(self):
        engine = self.setup_map()
        engine.ignite_cell(self.item("flint_and_steel"), Position(4, 2))
        result = engine.place_item(self.item("oil"), Position(4, 2), throwing=True)
        self.assertTrue(result.performed)
        self.assertTrue(self.instance.door.destroyed)
        self.assertFalse(engine.state.oil)

    def test_ignite_neighbors_respects_corners_requires_source_and_never_own_tile(self):
        for dx, dy in ((x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if x or y):
            engine = self.setup_map()
            target = Position(3 + dx, 2 + dy)
            engine.state.oil[target] = 5
            result = engine.ignite_cell(self.item("flint_and_steel"), target)
            if dx == 1 and dy != 0:
                # The closed door east of the hero blocks these two corners.
                self.assertFalse(result.performed)
                self.assertIn(target, engine.state.oil)
                self.assertEqual(engine.state.turns, 0)
            else:
                self.assertTrue(result.performed)
                self.assertNotIn(target, engine.state.oil)
        engine = self.setup_map()
        flint = self.item("flint_and_steel")
        for p in (Position(3, 2), Position(5, 2), Position(-1, 2)):
            self.assertFalse(engine.ignite_cell(flint, p).performed)
        self.assertEqual(engine.state.turns, 0)
        torch = self.item("torch")
        self.assertTrue(torch.ignition_source)
        self.assertFalse(engine.ignite_cell(torch, Position(4, 2)).performed)
        engine.state.hero.inventory[:] = [torch, flint]
        self.assertTrue(engine.manage_equipment(torch, True).performed)
        self.assertTrue(engine.ignite_cell(torch, Position(4, 2)).performed)
        engine = self.setup_map()
        engine.state.hero.inventory.clear()
        lamp = self.item("lamp")
        self.item("oil")
        engine.manage_equipment(lamp, True)
        self.assertFalse(lamp.ignition_source)
        self.assertFalse(engine.ignite_cell(lamp, Position(4, 2)).performed)

    def test_future_fire_weapon_can_ignite_and_uses_oil_damage(self):
        engine = self.setup_map()
        engine.state.hero.inventory.clear()
        sword = self.item("sword")
        sword.definition = replace(
            sword.definition, tags=sword.definition.tags | {"fire_damage"}
        )
        self.assertFalse(sword.can_ignite)
        engine.manage_equipment(sword, True)
        self.assertTrue(sword.can_ignite)
        engine.state.oil[Position(4, 2)] = 5
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (1,) * n):
            engine.interact("door", "attack")
        self.assertFalse(engine.state.oil)
        self.assertTrue(self.instance.door.burning or self.instance.door.destroyed)

    def test_universal_oil_refs_and_old_saves_resolve_to_one_definition(self):
        engine = self.setup_map()
        self.assertNotIn(("equipment", "base:terrain_decor_oil"), self.store.documents)
        self.assertEqual(
            compatibility()["tiles"]["base:decor_oil"]["ref"],
            "base:oil",
        )
        record = ItemRecord(
            definition="terrain_decor_oil",
            instance_id="old-oil",
            charges=1,
            equipped=False,
        )
        item = restore_item(record, engine.catalog)
        self.assertEqual(item.id, "oil")
        self.assertIn("lamp_oil", item.tags)
        EquipmentDocument(id="fire_tool", name="Поджигатель", tags=["поджог"])

    def test_save_restores_oil_burn_phase_and_rng_without_changing_template(self):
        engine = self.setup_map()
        engine.ignite_cell(self.item("flint_and_steel"), Position(4, 2))
        engine.state.oil[Position(4, 1)] = 3
        before = self.store.get("maps", "base:door_test").model_dump()
        with tempfile.TemporaryDirectory() as directory:
            repository = SaveRepository(Path(directory) / "save.json")
            repository.save(engine)
            restored = repository.load(store=self.store)
        self.assertEqual(engine.state.oil, restored.state.oil)
        self.assertEqual(engine.render_cells(), restored.render_cells())
        for _ in range(3):
            engine.apply(Action.WAIT)
            restored.apply(Action.WAIT)
        self.assertEqual(engine.render_cells(), restored.render_cells())
        self.assertEqual(self.store.get("maps", "base:door_test").model_dump(), before)

    def test_tui_item_ignite_target_and_cancel(self):
        self.setup_map()
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:door_test",
            test_map=True,
        )
        c.engine.state.hero.inventory.clear()
        flint = Equipment.create(c.engine.catalog.equipment["flint_and_steel"])
        c.engine.state.hero.inventory.append(flint)
        c.selected_item, c.item_return_view, c.view = flint, View.EXPLORE, View.ITEM
        self.assertIn("Поджечь", popup_content(c)[2][4])
        c.handle("5")
        self.assertEqual(c.view, View.IGNITE)
        self.assertIn("8 соседних", " ".join(render(c, 100, 30)))
        c.handle("d")
        c.handle("backspace")
        self.assertEqual(c.view, View.ITEM)
        self.assertEqual(c.engine.state.turns, 0)
        c.handle("5")
        c.handle("d")
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.engine.state.level.doors[0].door.hp, 10)


if __name__ == "__main__":
    unittest.main()
