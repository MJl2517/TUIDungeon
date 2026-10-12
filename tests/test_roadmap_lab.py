"""The unified roadmap fixture must be reachable and run real game commands."""

from collections import Counter, deque
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from scripts.build_roadmap_lab import UNKNOWN, build_documents
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import ContentError, PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position


class RoadmapLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def setUp(self):
        self.e = SessionFactory(self.store).session(
            "dev:roadmap_lab", character_class="dev:roadmap_tester", seed=42
        )

    def at(self, x, y):
        self.e.state.position = Position(x, y)

    def finish(self):
        for _ in range(50):
            if not self.e.active_craft:
                return
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        self.fail("Work did not finish")

    def take(self, bag, ref, quantity=1):
        container = next(
            c for c in self.e.state.level.containers if c.placement.id == bag
        )
        item = next(i for i in container.items if i.id == ref)
        result = self.e.transfer_storage(bag, item.instance_id, quantity, deposit=False)
        self.assertTrue(result.performed, result.message)
        return next(
            i for i in self.e.state.hero.inventory if i.instance_id == item.instance_id
        )

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_generator_reachable_samples_and_complete_recipe_supplies(self):
        level, art, tester, entries = build_documents(self.store)
        for category, document in (("maps", level), ("art", art), ("classes", tester)):
            self.assertEqual(document, self.store.get(category, "dev:" + document.id))
        seen = {(level.spawn.x, level.spawn.y)}
        pending = deque(seen)
        while pending:
            x, y = pending.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (
                    0 <= nx < level.width
                    and 0 <= ny < level.height
                    and (nx, ny) not in seen
                    and self.e.state.walkable(Position(nx, ny))
                ):
                    seen.add((nx, ny))
                    pending.append((nx, ny))
        for identifier, _, x, y in entries:
            self.assertTrue(
                any(
                    p in seen for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                ),
                identifier,
            )
        self.assertEqual(len(entries), len({(x, y) for _, _, x, y in entries}))
        self.assertLess(
            self.e.state.hero.carried_weight, self.e.state.hero.max_carry_weight
        )
        self.assertEqual(
            set(self.e.catalog.recipes) - self.e.state.hero.known_recipes, UNKNOWN
        )
        inputs = Counter(
            i.id
            for c in self.e.state.level.containers
            if c.placement.id == "basics"
            for i in c.items
        )
        for recipe in self.e.catalog.recipes.values():
            for variant in recipe.variants:
                for ingredient in variant.ingredients:
                    for ref in ingredient.items:
                        self.assertGreaterEqual(
                            inputs[ref.removeprefix("base:")], ingredient.quantity
                        )
        for p in level.objects + level.doors:
            self.assertEqual(level.tiles[p.y][p.x], "base:floor")

    def test_light_gate_and_all_station_combinations(self):
        self.at(33, 9)
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 1)
        self.assertFalse(self.e.assess_craft("base:craft_torch").reasons)
        self.assertTrue(self.e.assess_craft("base:craft_workshop_torch").reasons)
        self.at(44, 9)
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        turns = self.e.state.turns
        self.assertFalse(self.e.start_craft("base:craft_torch").performed)
        self.assertEqual(turns, self.e.state.turns)
        for x, y, recipe in (
            (61, 26, "craft_iron_blade"),
            (67, 25, "craft_ram"),
            (72, 25, "fire_clay_pot"),
            (67, 31, "craft_healing_potion"),
        ):
            self.at(x, y)
            self.assertFalse(self.e.assess_craft("base:" + recipe).reasons, recipe)
            self.assertTrue(self.e.start_craft("base:" + recipe).performed)
            self.finish()

    def test_basic_route_transfer_pause_save_complete_and_cancel(self):
        self.at(10, 7)
        self.assertTrue(self.e.start_dismantle("route_table").performed)
        self.finish()
        self.assertIsNone(self.e.world_object("route_table"))
        self.assertEqual(self.e.state.level.definition.tiles[7][11], "base:floor")
        self.at(5, 6)
        self.assertTrue(self.e.start_craft("base:craft_torch", variant=1).performed)
        work = self.e.active_craft
        turns = self.e.state.turns
        self.assertTrue(self.e.advance_craft().performed)
        self.assertEqual(self.e.state.turns, turns + 1)
        self.e.pause_craft()
        self.at(8, 6)
        self.assertTrue(
            self.e.transfer_storage(
                "workpiece_storage", work, 1, deposit=True
            ).performed
        )
        self.reload()
        self.assertTrue(
            self.e.transfer_storage(
                "workpiece_storage", work, 1, deposit=False
            ).performed
        )
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        self.assertEqual(sum(i.id == "torch" for i in self.e.state.hero.inventory), 2)
        self.at(5, 6)
        self.assertTrue(self.e.start_craft("base:craft_club", variant=0).performed)
        work = self.e.workpiece(self.e.active_craft)
        ingredients = {i.instance_id for i in work.work.ingredients}
        self.e.pause_craft()
        self.assertTrue(self.e.cancel_craft(work.instance_id).performed)
        self.assertTrue(
            ingredients <= {i.instance_id for i in self.e.state.hero.inventory}
        )
        self.reload()
        self.assertIsNone(self.e.world_object("route_table"))

    def test_water_fire_cleaning_and_authored_damage_survive_save(self):
        self.at(30, 33)
        self.assertTrue(self.e.pickup_item().performed)
        dirty = next(i for i in self.e.state.hero.inventory if i.contaminated)
        pot = next(i for i in self.e.state.hero.inventory if i.id == "cooking_pot")
        self.at(39, 25)
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "fill", target="water_clean_water"
            ).performed
        )
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "wash", target=dirty.instance_id
            ).performed
        )
        self.assertFalse(dirty.contaminated)
        self.assertEqual(pot.liquid_portions, 2)
        self.e.water_action(pot.instance_id, "empty")
        self.at(43, 25)
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "fill", target="water_dirty_water"
            ).performed
        )
        self.at(34, 25)
        self.take("camp_supplies", "wood", 2)
        self.assertTrue(self.e.campfire_action("campfire", "refuel").performed)
        self.assertTrue(self.e.campfire_action("campfire", "ignite").performed)
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        self.finish()
        pot = next(
            i for i in self.e.state.hero.inventory if i.instance_id == pot.instance_id
        )
        self.assertEqual(pot.liquid_kind, "clean_water")
        self.assertTrue(
            self.e.start_craft("base:make_poultice", target=pot.instance_id).performed
        )
        self.finish()
        self.at(56, 34)
        self.assertTrue(self.e.pickup_item().performed)
        damaged = next(
            i
            for i in self.e.state.hero.inventory
            if i.id == "dagger" and i.durability < i.definition.durability
        )
        self.at(61, 26)
        self.assertTrue(
            self.e.start_craft(
                "base:repair_metal", target=damaged.instance_id
            ).performed
        )
        self.finish()
        restored_hp = next(
            i
            for i in self.e.state.hero.inventory
            if i.instance_id == damaged.instance_id
        ).durability
        self.reload()
        self.assertFalse(
            next(
                i
                for i in self.e.state.hero.inventory
                if i.instance_id == dirty.instance_id
            ).contaminated
        )
        self.assertEqual(
            next(
                i
                for i in self.e.state.hero.inventory
                if i.instance_id == damaged.instance_id
            ).durability,
            restored_hp,
        )
        self.assertFalse(
            any(
                p.id in ("dirty_dagger", "damaged_dagger")
                for p, _ in self.e.state.items
            )
        )

    def test_knowledge_experiment_and_native_recipe_journal(self):
        self.at(58, 7)
        self.assertTrue(self.e.interact("recipe_book", "read_note").performed)
        self.at(64, 7)
        self.assertTrue(self.e.interact("recipe_workshop", "study").performed)
        self.assertTrue(UNKNOWN <= self.e.state.hero.known_recipes)
        self.reload()
        self.assertTrue(UNKNOWN <= self.e.state.hero.known_recipes)
        engine = SessionFactory(self.store).session(
            "dev:roadmap_lab", character_class="dev:roadmap_tester", seed=42
        )
        engine.state.position = Position(59, 48)
        self.assertTrue(engine.start_craft("base:experiment_binding").performed)
        for _ in range(3):
            self.assertTrue(engine.advance_craft().performed)
        self.assertTrue(UNKNOWN <= engine.state.hero.known_recipes)
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:roadmap_lab",
            test_map=True,
            test_class="dev:roadmap_tester",
        )
        c.handle("j")
        c.handle("3")
        self.assertEqual(c.view, View.CRAFT)
        for width, height in ((80, 24), (100, 28), (140, 40)):
            render(c, width, height)

    def test_initial_item_state_validation(self):
        original = self.store.get("maps", "dev:roadmap_lab")
        raw = original.model_dump(mode="json")
        raw["objects"][0]["item_state"] = {"contaminated": True}
        with self.assertRaises(ValidationError):
            MapDocument.model_validate(raw)
        for ref, durability in (
            ("base:dagger", -1),
            ("base:dagger", 1000),
            ("base:cloth", 1),
        ):
            raw = original.model_dump(mode="json")
            raw["equipment"][0].update(ref=ref, item_state=dict(durability=durability))
            with self.assertRaises((ValidationError, ContentError)):
                level = MapDocument.model_validate(raw)
                candidate = dict(self.store.documents)
                candidate["maps", "dev:roadmap_lab"] = level
                self.store.validate_references(candidate, self.store.manifests)

    def test_lazy_recipe_catalog_categories_and_availability(self):
        e = self.e
        with patch.object(e, "assess_craft", wraps=e.assess_craft) as assess:
            catalog = e.craft_list()
            assess.assert_not_called()
        self.assertEqual(len(catalog), len(e.state.hero.known_recipes))
        from tuidungeon.presentation.crafting import CraftBrowser

        browser = CraftBrowser()
        browser.open()
        self.assertTrue(all(r["category"] == "basic" for r in browser.entries(e)))
        browser.filter = "available"
        with patch.object(e, "assess_craft", wraps=e.assess_craft) as assess:
            browser.entries(e)
            calls = assess.call_count
            self.assertGreater(calls, 0)
            self.assertTrue(
                all(
                    e.catalog.recipes[c.args[0]].category == "basic"
                    for c in assess.call_args_list
                )
            )
            browser.entries(e)
            self.assertEqual(assess.call_count, calls)
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:roadmap_lab",
            test_map=True,
            test_class="dev:roadmap_tester",
        )
        c.handle("c")
        render(c, 140, 40)
        categories = c.craft.categories(c.engine)
        c.handle("left")
        self.assertEqual(c.craft.category, categories[-1])
        c.handle("right")
        self.assertEqual(c.craft.category, "basic")
        self.assertTrue(
            all(r["category"] == "basic" for r in c.craft.entries(c.engine))
        )
        c.craft.recipe_ref = "base:craft_torch"
        before = c.craft.assessment(c.engine).variant
        c.handle("b")
        self.assertNotEqual(before, c.craft.assessment(c.engine).variant)
        self.assertEqual(c.craft.category, "basic")
        c.craft.query = "base:craft_iron_blade"
        self.assertEqual(
            [r["ref"] for r in c.craft.entries(c.engine)], ["base:craft_iron_blade"]
        )
        self.assertEqual(c.craft.category, "smith")

    def test_recipe_journal_reuses_definitions_but_keeps_world_state_live(self):
        from tuidungeon.content.placements import override_document

        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:roadmap_lab",
            test_map=True,
            test_class="dev:roadmap_tester",
        )
        c.handle("j")
        c.handle("3")
        render(c, 140, 40)
        with (
            patch(
                "tuidungeon.content.placements.override_document",
                wraps=override_document,
            ) as resolve,
            patch.object(
                c.engine, "assess_craft", wraps=c.engine.assess_craft
            ) as assess,
        ):
            render(c, 140, 40)
            selected = c.craft.recipe_ref
            self.assertTrue(assess.call_args_list)
            self.assertTrue(
                all(call.args[0] == selected for call in assess.call_args_list)
            )
            self.assertFalse(any(call.args[2] for call in resolve.call_args_list))
        e = c.engine
        self.assertIsNone(e.world_object("hidden_trap"))
        hidden = next(t for t in e.state.level.traps if t.placement.id == "hidden_trap")
        hidden.discovered = True
        self.assertIsNotNone(e.world_object("hidden_trap"))
        obj = e.world_object("burnable")
        obj.state.burning = True
        self.assertTrue(e.campfire_lights())
        obj.state.burning = False
        self.assertFalse(e.campfire_lights())
        level = e.state.level
        moved = obj.placement.model_copy(
            update={"x": 18, "overrides": {"name": "Перенесённая баррикада"}}
        )
        level.definition = level.definition.model_copy(
            update={
                "objects": [
                    moved if p.id == moved.id else p for p in level.definition.objects
                ]
            }
        )
        changed = e.world_object("burnable")
        self.assertEqual(changed.placement.x, 18)
        self.assertEqual(changed.definition.name, "Перенесённая баррикада")


if __name__ == "__main__":
    unittest.main()
