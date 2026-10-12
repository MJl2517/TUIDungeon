"""First atlas batch exercises real engine commands and portable save state."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.tags import liquid_tags
from tuidungeon.world.maps import Position


class TilesVegetationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session("tiles:vegetation_lab", seed=42)

    def give(self, ref):
        item = Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
        self.e.state.hero.inventory.append(item)
        return item

    def approach(self, identifier):
        obj = self.e.world_object(identifier)
        self.e.state.position = Position(obj.placement.x - 1, obj.placement.y)
        return obj

    def finish(self, identifier):
        self.approach(identifier)
        result = self.e.start_dismantle(identifier)
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        self.assertIsNone(self.e.world_object(identifier))

    def count(self, identifier):
        return Counter(item.id for _, item in self.e.state.items)[identifier]

    def test_masks_colors_rarity_and_lab_cover_every_requested_cell(self):
        expected = {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            50,
            51,
            52,
            53,
            54,
            55,
            56,
            57,
            99,
            100,
            101,
            102,
            103,
            104,
            105,
            106,
        }
        for number in expected:
            symbol = self.store.get("symbols", f"tiles:cell_{number:04}")
            x, y = (number - 1) % 49, (number - 1) // 49
            self.assertEqual(
                symbol.pixels, self.store.get("symbols", f"base:kenney_{x}_{y}").pixels
            )
            self.assertTrue(symbol.reviewed)
        flowers = [
            d
            for (c, ref), d in self.store.documents.items()
            if c == "objects"
            and ref.startswith("tiles:flower_")
            and not ref.endswith("decoy")
        ]
        self.assertEqual(len({d.foreground for d in flowers}), 7)
        self.assertEqual({d.rarity for d in flowers}, {"common", "uncommon", "rare"})
        refs = {p.ref for p in self.e.state.level.definition.objects}
        self.assertTrue(
            all(
                ref in refs
                for c, ref in self.store.documents
                if c == "objects" and ref.startswith("tiles:")
            )
        )
        self.assertEqual(self.store.get("tiles", "tiles:empty").map_category, "service")

    def test_grass_bonus_floor_and_saved_regrowth(self):
        self.e.state.hero.inventory.clear()
        before = self.count("plant_fiber")
        self.finish("grass_6_v0")
        self.assertEqual(self.count("plant_fiber") - before, 1)
        self.give("tiles:sickle")
        self.finish("grass_6_v1")
        self.assertEqual(self.count("plant_fiber") - before, 3)
        self.finish("tall_grass_v0")
        self.assertEqual(self.count("plant_fiber") - before, 6)
        pending = next(
            p
            for p in self.e.state.level.regrowing_objects
            if p.placement.id == "grass_6_v0"
        )
        self.assertEqual(
            self.e.state.level.definition.tiles[pending.placement.y][
                pending.placement.x
            ],
            "base:floor",
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        self.e.state.position = Position(2, 2)
        self.e._advance(3 * 1440)
        self.assertIsNotNone(self.e.world_object("grass_6_v0"))
        self.assertIsNone(self.e.world_object("tall_grass_v0"))
        self.e._advance(1440)
        self.assertIsNotNone(self.e.world_object("tall_grass_v0"))

    def test_vines_require_slashing_and_tree_fire_and_palm_yield(self):
        self.e.state.hero.inventory.clear()
        self.give("base:dagger")
        self.approach("vines")
        self.assertFalse(self.e.start_dismantle("vines").performed)
        self.give("base:terrain_decor_axe")
        self.finish("vines")
        tree = self.approach("tree_50_v0")
        p = Position(tree.placement.x, tree.placement.y)
        self.assertFalse(self.e.state.walkable(p))
        self.assertTrue(self.e.state.level.terrain.blocks_sight[p.y][p.x])
        self.assertTrue(self.e.ignite_world_objects(p))
        self.e._advance(5)
        self.assertIsNone(self.e.world_object("tree_50_v0"))
        self.assertTrue(self.e.state.walkable(p))
        self.finish("palm")
        self.assertEqual(self.count("tiles:coconut"), 1)
        self.e.state.position = Position(2, 2)
        self.e._advance(10 * 1440)
        self.assertIsNotNone(self.e.world_object("tree_50_v0"))
        self.assertIsNotNone(self.e.world_object("palm"))
        self.assertEqual(self.count("tiles:coconut"), 1)

    def test_cactus_damage_juice_save_drink_and_alchemy(self):
        self.e.state.hero.inventory.clear()
        cactus = self.approach("cactus_56")
        hp = self.e.state.hero.hp
        self.assertTrue(self.e.apply(Action.EAST).performed)
        self.assertEqual(self.e.state.hero.hp, hp - 1)
        self.e.apply(Action.WAIT)
        self.assertEqual(self.e.state.hero.hp, hp - 1)
        self.e.apply(Action.WEST)
        pot = self.give("base:cooking_pot")
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "fill", target=cactus.placement.id, portions=1
            ).performed
        )
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("cactus_juice", 1))
        self.assertNotIn("water", liquid_tags("cactus_juice"))
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        pot = next(i for i in self.e.state.hero.inventory if i.id == "cooking_pot")
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("cactus_juice", 1))
        self.give("base:medicinal_herb")
        self.give("base:wood")
        self.give("base:flint_and_steel")
        self.approach("lab_campfire")
        self.assertTrue(self.e.campfire_action("lab_campfire", "refuel").performed)
        self.assertTrue(self.e.campfire_action("lab_campfire", "ignite").performed)
        result = self.e.start_craft("tiles:cactus_broth", target=pot.instance_id)
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("healing_broth", 1))
        self.assertTrue(self.e.use_item(pot).performed)
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), (None, 0))
        self.assertIn(pot, self.e.state.hero.inventory)

    def test_juice_harvest_and_poison_decoy_are_usable(self):
        self.finish("cactus_57")
        item = next(
            i for _, i in self.e.state.items if i.id == "tiles:cactus_juice_flask"
        )
        self.e.state.hero.inventory.append(item)
        hp = self.e.state.hero.hp
        self.assertTrue(self.e.use_item(item).performed)
        self.assertEqual(self.e.state.hero.hp, hp)
        self.assertEqual(item.liquid_portions, 0)
        self.assertIn(item, self.e.state.hero.inventory)
        poison = self.give("tiles:false_red_flower")
        self.assertTrue(self.e.use_item(poison).performed)
        self.assertIn("poisoned", self.e.state.hero.conditions)


if __name__ == "__main__":
    unittest.main()
