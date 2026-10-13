"""Acceptance checks for the current atlas batch and merged metal components."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_tiles_furnishings import NUMBERS, TABLES
from scripts.unify_metal import rewrite, changes
from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, ItemRecord, restore_item
from tuidungeon.content.migrations import migrate_map, migrate_document, equipment_alias
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import RecipeDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.locks import LOCK_COLORS
from tuidungeon.world.maps import Position


class TilesFurnishingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session("tiles:furnishings_lab", seed=42)

    def near(self, identifier):
        p = next(p for p in self.e.state.level.definition.objects if p.id == identifier)
        self.e.state.position = Position(p.x - 1, p.y)
        return Position(p.x, p.y)

    def give(self, ref):
        item = Equipment.create(self.e.catalog.equipment[ref])
        self.e.state.hero.inventory.append(item)
        return item

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def cell(self, p):
        return self.e.render_cells((p.x, p.y, 1, 1))[0][0]

    def test_atlas_import_and_lab_coverage_without_duplicate_states(self):
        for n in NUMBERS:
            symbol = self.store.get("symbols", f"tiles:cell_{n:04d}")
            original = self.store.get(
                "symbols", f"base:kenney_{(n - 1) % 49}_{(n - 1) // 49}"
            )
            self.assertEqual(symbol.pixels, original.pixels)
            self.assertTrue(symbol.reviewed)
            self.assertEqual(symbol.source.license, "CC0")
        placements = self.e.state.level.definition.objects
        for i, p in enumerate(placements):
            for q in placements[i + 1 :]:
                self.assertGreaterEqual(max(abs(p.x - q.x), abs(p.y - q.y)), 3)
        self.assertNotIn(("objects", "tiles:chest_304"), self.store.documents)
        self.assertNotIn(("objects", "tiles:chest_306"), self.store.documents)

    def test_rails_passable_transparent_and_require_tools_not_proficiency(self):
        for n in range(246, 251):
            p = self.near(f"rails_{n}")
            self.assertTrue(self.e.state.walkable(p))
            self.assertFalse(self.e.state.level.terrain.blocks_sight[p.y][p.x])
        self.e.state.hero.inventory.clear()
        turns = self.e.state.turns
        self.assertFalse(self.e.start_dismantle("rails_250").performed)
        self.assertEqual(self.e.state.turns, turns)
        self.give("tinker_tools")
        self.assertFalse(self.e.state.hero.tool_proficiencies)
        self.assertTrue(self.e.start_dismantle("rails_250").performed)
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)
        drops = Counter(
            i.id for pos, i in self.e.state.items if (pos.x, pos.y) == (p.x, p.y)
        )
        self.assertEqual((drops["metal"], drops["wood"]), (2, 1))
        self.assertIsNone(self.e.world_object("rails_250"))
        self.reload()
        self.assertIsNone(self.e.world_object("rails_250"))

    def test_bookshelves_enforce_size_and_capacity(self):
        for n, capacity in [(300, 30), (347, 30), (348, 15)]:
            self.near(f"bookshelf_{n}")
            box = self.e.storage_at(f"bookshelf_{n}")
            self.assertEqual(
                (box.spec.capacity, box.spec.max_item_size), (capacity, "small")
            )
            box.spec = box.spec.model_copy(update={"personal": True})
            book, staff = self.give("spellbook"), self.give("staff")
            self.assertTrue(
                self.e.transfer_storage(
                    box.placement.id, book.instance_id, deposit=True
                ).performed
            )
            self.assertFalse(
                self.e.transfer_storage(
                    box.placement.id, staff.instance_id, deposit=True
                ).performed
            )
            self.assertIn(book, box.items)
            self.assertNotIn(staff, box.items)

    def test_tables_material_tools_weight_and_stone_destruction(self):
        for n, (_, weight) in TABLES.items():
            for material, factor in [("wooden", 1), ("metal", 2), ("stone", 4)]:
                d = self.store.get("objects", f"tiles:table_{material}_{n}")
                self.assertEqual(d.weight, weight * factor)
                self.assertTrue(d.movable)
                self.assertEqual("flammable" in d.tags, material == "wooden")
                if material == "stone":
                    self.assertIsNone(d.destruction.dismantle)
                else:
                    tool = "carpenter_tools" if material == "wooden" else "tinker_tools"
                    self.assertEqual(list(d.destruction.dismantle.tools), [tool])
        p = self.near("table_stone_350")
        before = self.e.state.turns
        self.assertFalse(self.e.start_dismantle("table_stone_350").performed)
        self.assertEqual(self.e.state.turns, before)
        self.e.damage_world_objects(p, 100, "bludgeoning")
        self.assertIsNone(self.e.world_object("table_stone_350"))
        self.assertTrue(
            any(
                i.id == "stone" and (pos.x, pos.y) == (p.x, p.y)
                for pos, i in self.e.state.items
            )
        )

    def test_chest_state_updates_without_turn_and_survives_save_and_carry(self):
        p = self.near("chest_303")
        box = self.e.storage_at("chest_303")
        self.assertEqual((box.spec.capacity, box.spec.max_item_size), (300, "large"))
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0303")
        turns = self.e.state.turns
        self.assertTrue(self.e.open_container("chest_303").performed)
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0304")
        self.assertEqual(self.e.state.turns, turns)
        self.reload()
        self.assertTrue(self.e.storage_at("chest_303").opened)
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0304")
        self.assertTrue(self.e.lift_furniture("chest_303").performed)
        cargo = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertTrue(self.e.place_furniture(cargo, p).performed)
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0304")
        self.assertTrue(self.e.interact("chest_303", "close_storage").performed)
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0303")
        p = self.near("wall_chest_open")
        self.assertEqual(self.cell(p).symbol, "tiles:cell_0354")
        wall = self.e.storage_at("wall_chest_open")
        self.assertEqual((wall.spec.capacity, wall.spec.max_item_size), (100, "medium"))

    def test_chest_colors_preserve_loot_metadata_and_share_geometry(self):
        for shape in (303, 305):
            definition = self.store.get("objects", f"tiles:chest_{shape}")
            self.assertEqual(
                [v.loot_tier for v in definition.variants],
                ["white", "bronze", "iron", "gold"],
            )
            for tier, color in [
                ("white", 15),
                ("bronze", 130),
                ("iron", 153),
                ("gold", 220),
            ]:
                p = self.near(f"chest_{shape}_{tier}")
                box = self.e.storage_at(f"chest_{shape}_{tier}")
                self.assertEqual(box.definition.loot_tier, tier)
                self.assertEqual(self.cell(p).foreground, color)
                self.e.open_container(box.placement.id)
                self.assertEqual(self.cell(p).symbol, f"tiles:cell_{shape + 1:04d}")

    def test_transitions_use_selected_destination_and_preserve_hero(self):
        self.near("stairs_297")
        hero = self.e.state.hero
        result = self.e.apply(Action.EAST)
        self.assertTrue(result.performed)
        self.assertEqual(self.e.state.level.ref, "tiles:furnishings_annex")
        self.assertIs(self.e.state.hero, hero)
        self.e.apply(Action.EAST)
        self.e.apply(Action.EAST)
        self.assertEqual(self.e.state.level.ref, "tiles:furnishings_lab")
        self.assertIs(self.e.state.hero, hero)

    def test_service_symbols_override_fallback_and_keep_quality_colors(self):
        for quality, color in LOCK_COLORS.items():
            for kind, number in [("simple", 491), ("complex", 540)]:
                p = self.near(f"lock_{quality}_{kind}")
                cell = self.cell(p)
                self.assertEqual(cell.symbol, f"tiles:cell_{number:04d}")
                self.assertEqual(cell.foreground, color)
                self.assertTrue(cell.service_indicator)

    def test_decorations_have_no_invented_traps_and_fence_cannot_be_attacked(self):
        for ref in ("wood_support_301", "pit_302"):
            definition = self.store.get("tiles", "tiles:" + ref)
            self.assertFalse(definition.walkable)
            self.assertFalse(definition.blocks_sight)
            self.assertIsNone(definition.brush.trap)
        self.near("metal_fence_251")
        target = self.e.world_object("metal_fence_251")
        self.assertFalse(target.definition.attackable)
        self.assertNotIn(
            "break_object", {c.id for c in target.available_choices(self.e.state.hero)}
        )


class MetalCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def test_only_one_component_and_old_items_restore_as_metal(self):
        catalog = self.store.runtime_catalog()
        self.assertEqual(catalog.equipment["metal"].weight, 0.3)
        for name in ("iron", "steel", "metal_scrap"):
            self.assertNotIn(name, catalog.equipment)
            self.assertEqual(equipment_alias(name), "metal")
            item = restore_item(
                ItemRecord(definition=name, instance_id="old-" + name, equipped=False),
                catalog,
            )
            self.assertEqual(
                (item.id, item.name, item.weight), ("metal", "Металл", 0.3)
            )

    def test_migration_preserves_repeated_rows_coordinates_and_counts(self):
        raw = dict(
            id="legacy",
            name="Старая карта",
            width=4,
            height=2,
            tiles=[["base:floor"] * 4 for _ in range(2)],
            walkability=[[True] * 4 for _ in range(2)],
            blocks_sight=[[False] * 4 for _ in range(2)],
            spawn=dict(x=0, y=0),
            equipment=[dict(id="metal1", ref="base:iron", x=2, y=1)],
            objects=[
                dict(
                    id="box",
                    ref="base:cabinet",
                    x=3,
                    y=1,
                    overrides={
                        "storage": {
                            "contents": [{"item": "base:metal_scrap", "quantity": 7}]
                        }
                    },
                )
            ],
        )
        new = migrate_map(raw)
        self.assertEqual(new["tiles"], raw["tiles"])
        self.assertEqual(new["walkability"], raw["walkability"])
        self.assertEqual(new["blocks_sight"], raw["blocks_sight"])
        self.assertEqual(
            new["equipment"][0],
            dict(id="metal1", ref="base:metal", x=2, y=1, overrides={}),
        )
        self.assertEqual(
            new["objects"][0]["overrides"]["storage"]["contents"],
            [dict(item="base:metal", quantity=7)],
        )
        self.assertEqual(migrate_map(new), new)
        self.assertEqual(rewrite(raw["tiles"]), raw["tiles"])
        self.assertEqual(changes(), ({}, []))

    def test_legacy_recipe_including_saved_work_uses_canonical_material(self):
        raw = dict(
            id="legacy",
            name="Старый рецепт",
            variants=[
                dict(
                    ingredients=[
                        dict(items=["base:iron", "base:metal_scrap"], quantity=2)
                    ]
                )
            ],
            result=[dict(item="base:steel", quantity=1)],
        )
        recipe = RecipeDocument.model_validate(raw)
        self.assertEqual(set(recipe.variants[0].ingredients[0].items), {"base:metal"})
        self.assertEqual(recipe.result[0].item, "base:metal")
        self.assertEqual(
            migrate_document(raw, "recipes")["variants"][0]["ingredients"][0][
                "quantity"
            ],
            2,
        )


if __name__ == "__main__":
    unittest.main()
