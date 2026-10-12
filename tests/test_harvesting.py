"""Renewable resources keep their floor, work, loot and saved game-time deadlines."""

from copy import copy
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import DestructionSpec, MapDocument, Placement
from tuidungeon.world.maps import Position


class HarvestingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.map = MapDocument(
            id="gather_test",
            name="Сбор ресурсов",
            width=8,
            height=8,
            tiles=[["base:floor"] * 8 for _ in range(8)],
            walkability=[[True] * 8 for _ in range(8)],
            blocks_sight=[[False] * 8 for _ in range(8)],
            spawn={"x": 2, "y": 2},
            ambient_light="bright",
            objects=[
                Placement(
                    id="flower",
                    ref="base:medicinal_flower",
                    x=3,
                    y=2,
                    overrides={"destruction": {"regrow_minutes": 3}},
                ),
                Placement(
                    id="tree",
                    ref="base:tree",
                    x=4,
                    y=5,
                    overrides={"destruction": {"regrow_minutes": 5}},
                ),
                Placement(
                    id="mine",
                    ref="base:cracked_barrier",
                    x=5,
                    y=2,
                    overrides={"destruction": {"regrow_minutes": 4}},
                ),
            ],
        )
        self.store.documents["maps", "dev:gather_test"] = self.map
        self.e = SessionFactory(self.store).session("dev:gather_test", seed=42)

    def finish(self, identifier):
        target = self.e.world_object(identifier)
        self.e.state.position = Position(target.placement.x - 1, target.placement.y)
        self.assertTrue(self.e.interact(identifier, "dismantle").performed)
        for _ in range(10):
            if not self.e.active_craft:
                break
            self.assertTrue(self.e.advance_craft().performed)
        self.assertIsNone(self.e.active_craft)
        self.assertIsNone(self.e.world_object(identifier))

    def loot(self):
        return Counter(item.id for _, item in self.e.state.items)

    def test_colored_flowers_supply_existing_recipe_ingredients(self):
        refs = (
            "medicinal_flower",
            "poison_flower",
            "bitter_flower",
            "alchemy_flower",
            "fiber_flower",
        )
        colors = set()
        used = {
            item
            for (category, _), recipe in self.store.documents.items()
            if category == "recipes"
            for variant in recipe.variants
            for ingredient in variant.ingredients
            for item in ingredient.items
        }
        for ref in refs:
            flower = self.store.get("objects", "base:" + ref)
            colors.add(flower.foreground)
            self.assertEqual(flower.glyph, "✿")
            self.assertEqual(flower.destruction.dismantle.verb, "harvest")
            self.assertIn(flower.destruction.dismantle.loot[0].item, used)
        self.assertEqual(len(colors), len(refs))
        self.assertIn(
            "Собрать",
            next(
                c.text
                for c in self.e.world_object("flower").available_choices(
                    self.e.state.hero
                )
                if c.id == "dismantle"
            ),
        )

    def test_harvest_save_wait_and_repeat_has_single_yield_per_cycle(self):
        self.finish("flower")
        self.assertEqual(self.e.state.turns, 1)
        self.assertEqual(self.loot(), {"medicinal_herb": 1})
        self.assertEqual(self.e.state.level.definition.tiles[2][3], "base:floor")
        self.assertFalse(self.e.start_dismantle("flower").performed)
        self.e.apply(Action.WAIT)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        self.e.apply(Action.WAIT)
        self.assertIsNone(self.e.world_object("flower"))
        self.e.apply(Action.WAIT)
        restored = self.e.world_object("flower")
        self.assertEqual(
            (restored.state.progress, restored.state.total, restored.state.hp),
            (0, 0, 3),
        )
        self.assertEqual(self.loot(), {"medicinal_herb": 1})
        self.finish("flower")
        self.assertEqual(self.loot(), {"medicinal_herb": 2})
        self.assertEqual(len(self.e.state.level.regrowing_objects), 1)
        self.assertEqual(self.map, self.store.get("maps", "dev:gather_test"))

    def test_tree_requires_blade_and_regrowth_waits_for_hero_to_leave(self):
        target = self.e.world_object("tree")
        self.e.state.position = Position(3, 5)
        inventory = list(self.e.state.hero.inventory)
        self.e.state.hero.inventory[:] = [i for i in inventory if "blade" not in i.tags]
        self.assertFalse(self.e.start_dismantle("tree").performed)
        self.assertEqual(self.e.state.turns, 0)
        self.e.state.hero.inventory[:] = inventory
        self.assertFalse(self.e.state.walkable(Position(4, 5)))
        identity = target.state.instance_id
        self.finish("tree")
        self.assertTrue(self.e.state.walkable(Position(4, 5)))
        self.e.state.position = Position(4, 5)
        self.e._advance(5)
        self.assertIsNone(self.e.world_object("tree"))
        self.e.state.position = Position(3, 5)
        self.e.apply(Action.WAIT)
        restored = self.e.world_object("tree")
        self.assertNotEqual(restored.state.instance_id, identity)
        self.assertFalse(self.e.state.walkable(Position(4, 5)))
        self.assertTrue(self.e.state.level.terrain.blocks_sight[5][4])
        self.assertEqual(self.loot(), {"wood": 3})

    def test_damage_and_offscreen_time_restore_mine_without_extra_loot(self):
        source = self.e.state
        self.e.damage_world_objects(Position(5, 2), 100, "bludgeoning")
        self.assertIsNone(self.e.world_object("mine"))
        self.assertEqual(self.loot(), {"stone": 3})
        other = self.map.model_copy(update={"id": "other_gather", "objects": []})
        self.store.documents["maps", "dev:other_gather"] = other
        destination = SessionFactory(self.store).state("dev:other_gather", source.hero)
        destination.clock = source.clock
        self.e.levels[destination.level.ref] = destination
        self.e.state = destination
        self.e._advance(4)
        self.assertIn("mine", {p.id for p in source.level.definition.objects})
        self.e.state = source
        self.assertEqual(self.loot(), {"stone": 3})
        self.assertEqual(self.e.world_object("mine").state.hp, 12)

    def test_new_object_on_cell_defers_recovery(self):
        self.finish("flower")
        level = self.e.state.level
        blocker = Placement(id="new_building", ref="base:cracked_barrier", x=3, y=2)
        level.definition = level.definition.model_copy(
            update={"objects": [*level.definition.objects, blocker]}
        )
        self.e._advance(3)
        self.assertIsNone(self.e.world_object("flower"))
        self.e.damage_world_objects(Position(3, 2), 100, "bludgeoning")
        self.e.apply(Action.WAIT)
        self.assertIsNotNone(self.e.world_object("flower"))

    def test_invalid_recovery_settings_and_saved_placements_are_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DestructionSpec(regrow_minutes=value)
        self.finish("flower")
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            raw["levels"][0]["regrowing_objects"][0]["placement"]["x"] = 99
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "восстанавливаемого объекта"):
                repo.load(store=self.store)

    def test_old_save_without_recovery_records_loads(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            for level in raw["levels"]:
                level.pop("regrowing_objects")
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            restored = repo.load(store=self.store)
        self.assertEqual(restored.state.level.regrowing_objects, [])
        self.assertIsNotNone(restored.world_object("flower"))

    def test_recovering_container_preserves_completed_event_without_duplicating_contents(
        self,
    ):
        from tuidungeon.domain.equipment import Equipment

        level = self.e.state.level
        crate = Placement(
            id="crate",
            ref="base:terrain_crate",
            x=6,
            y=5,
            overrides={"destruction": {"regrow_minutes": 2}},
        )
        definition = level.store.resolve("points_of_interest", crate)
        item = Equipment.create(self.e.catalog.equipment["wood"])
        from tuidungeon.world.objects import ObjectState

        self.e._attach_world_object(
            level,
            "points_of_interest",
            crate,
            definition,
            ObjectState(hp=15),
            items=[item],
            completed=True,
        )
        self.e.state.position = Position(5, 5)
        self.assertTrue(self.e.lift_furniture("crate").performed)
        self.assertEqual(level.regrowing_objects, [])
        cargo = self.e.state.hero.inventory[-1]
        self.assertTrue(self.e.place_furniture(cargo, Position(6, 5)).performed)
        self.e.damage_world_objects(Position(6, 5), 100, "bludgeoning")
        self.e._advance(2)
        restored = self.e.world_object("crate")
        self.assertTrue(restored.completed)
        container = next(c for c in level.containers if c.placement.id == "crate")
        self.assertEqual(container.items, [])
        self.assertEqual(
            sum(i.instance_id == item.instance_id for _, i in self.e.state.items), 1
        )


if __name__ == "__main__":
    unittest.main()
