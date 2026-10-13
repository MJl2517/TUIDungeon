"""First atlas batch exercises real engine commands and portable save state."""

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.content.migrations import equipment_alias, migrate_map
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.tags import interaction_tags, liquid_tags
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
        self.assertEqual(len(flowers), 8)  # Seven adults and the single green sprout.
        self.assertFalse(any(ref.endswith("_decoy") for _, ref in self.store.documents))
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
        self.assertTrue(self.e.state.hero.equip(self.give("base:terrain_decor_axe")))
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

    def test_juice_harvest_and_poisonous_flower_property_are_usable(self):
        self.finish("cactus_57")
        item = next(
            i for _, i in self.e.state.items if i.id == "tiles:cactus_juice_flask"
        )
        self.e.state.hero.inventory.append(item)
        self.e.state.items[:] = [(p, i) for p, i in self.e.state.items if i is not item]
        hp = self.e.state.hero.hp
        self.assertTrue(self.e.use_item(item).performed)
        self.assertEqual(self.e.state.hero.hp, hp)
        self.assertEqual(item.liquid_portions, 0)
        self.assertIn(item, self.e.state.hero.inventory)
        target = self.approach("flower_poisonous")
        self.assertTrue(target.definition.poisonous)
        self.assertIn("poison", interaction_tags(target))
        normal = self.store.get("objects", "tiles:flower_5_red")
        self.assertEqual(target.definition.name, normal.name)
        self.assertEqual(target.definition.symbol, normal.symbol)
        self.finish("flower_poisonous")
        poison = next(i for _, i in self.e.state.items if i.id == "poison_herb")
        self.e.state.items[:] = [
            (p, i) for p, i in self.e.state.items if i is not poison
        ]
        self.e.state.hero.inventory.append(poison)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        poison = next(i for i in self.e.state.hero.inventory if i.id == "poison_herb")
        self.assertTrue(self.e.use_item(poison).performed)
        self.assertIn("poisoned", self.e.state.hero.conditions)

    def test_required_harvest_tool_must_stay_in_hands_without_spending_failed_turns(
        self,
    ):
        self.e.state.hero.inventory.clear()
        blade = self.give("base:dagger")
        self.approach("tree_50_v0")
        result = self.e.start_dismantle("tree_50_v0")
        self.assertFalse(result.performed)
        self.assertIn("в руки", result.message)
        self.assertEqual(self.e.state.turns, 0)
        self.assertTrue(self.e.state.hero.equip(blade))
        self.assertTrue(self.e.start_dismantle("tree_50_v0").performed)
        self.assertTrue(self.e.advance_craft().performed)
        self.e.state.hero.unequip(blade)
        before = self.e.state.turns
        self.assertFalse(self.e.advance_craft().performed)
        self.assertEqual(self.e.state.turns, before)
        self.assertIsNone(self.e.active_craft)
        self.assertEqual(self.e.world_object("tree_50_v0").state.progress, 1)
        self.assertTrue(self.e.state.hero.equip(blade))
        wood = self.count("wood")
        self.finish("tree_50_v0")
        self.assertEqual(self.count("wood") - wood, 3)

    def test_flower_leaves_young_green_stage_then_recovers_original_after_save(self):
        for identifier in ("flower_5_blue", "flower_poisonous"):
            self.finish(identifier)
        level = self.e.state.level
        sprouts = [p for p in level.regrowing_objects if p.sprout_id]
        self.assertEqual(len(sprouts), 2)
        for pending in sprouts:
            sprout = self.e.world_object(pending.sprout_id)
            self.assertEqual(sprout.placement.ref, "tiles:flower_4_green")
            self.assertIsNone(sprout.dismantle)
            self.assertFalse(self.e.start_dismantle(sprout.placement.id).performed)
        self.assertEqual(self.count("poison_herb"), 1)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        pending = next(
            p
            for p in self.e.state.level.regrowing_objects
            if p.placement.id == "flower_5_blue"
        )
        self.e.state.position = Position(pending.placement.x, pending.placement.y)
        self.e._advance(3 * 1440)
        self.assertIsNotNone(self.e.world_object(pending.sprout_id))
        self.assertIsNone(self.e.world_object("flower_5_blue"))
        self.e.state.position = Position(2, 2)
        self.e.apply(Action.WAIT)
        self.assertIsNone(self.e.world_object(pending.sprout_id))
        self.assertEqual(
            self.e.world_object("flower_5_blue").definition.foreground,
            self.store.get("objects", "tiles:flower_5_blue").foreground,
        )
        self.assertTrue(self.e.world_object("flower_poisonous").definition.poisonous)
        self.assertEqual(self.count("poison_herb"), 1)
        self.finish("flower_poisonous")
        self.assertEqual(self.count("poison_herb"), 2)

    def test_destroying_young_flower_cancels_growth_and_gives_no_resources(self):
        self.finish("flower_5_red")
        pending = next(
            p
            for p in self.e.state.level.regrowing_objects
            if p.placement.id == "flower_5_red"
        )
        loot = Counter(i.id for _, i in self.e.state.items)
        self.e.damage_world_objects(
            Position(pending.placement.x, pending.placement.y), 10, "fire"
        )
        self.e._advance(3 * 1440)
        self.assertIsNone(self.e.world_object("flower_5_red"))
        self.assertFalse(self.e.state.level.regrowing_objects)
        self.assertEqual(Counter(i.id for _, i in self.e.state.items), loot)

    def test_removed_flowers_migrate_and_invalid_saved_sprout_is_rejected(self):
        raw = self.store.get("maps", "tiles:vegetation_lab").model_dump(mode="json")
        raw["objects"] = [
            {"id": "old_red", "ref": "tiles:flower_4_red", "x": 5, "y": 9},
            {"id": "old_decoy", "ref": "tiles:flower_5_decoy", "x": 8, "y": 9},
        ]
        migrated = migrate_map(raw)
        self.assertEqual(migrate_map(migrated), migrated)
        self.assertEqual(migrated["objects"][0]["ref"], "tiles:flower_5_red")
        self.assertEqual(migrated["objects"][1]["overrides"], {"poisonous": True})
        self.assertEqual(equipment_alias("tiles:false_red_flower"), "base:poison_herb")
        self.finish("flower_5_red")
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            data = json.loads(repo.path.read_text(encoding="utf-8"))
            data["levels"][0]["regrowing_objects"][0]["sprout_id"] = "missing"
            repo.path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "молодое растение"):
                repo.load(store=self.store)


if __name__ == "__main__":
    unittest.main()
