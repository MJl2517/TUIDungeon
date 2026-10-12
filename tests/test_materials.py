"""Curated materials, consistent brushes, schema forms and runtime visibility."""

import unittest

from scripts.tag_materials import collect_updates
from tuidungeon.content.catalog import ContentCatalog, DEFAULT_ROOT
from tuidungeon.content.migrations import compatibility
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import EquipmentDocument, PointDocument, TileDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.materials import FLAMMABLE, WOODEN, MATERIAL_TAGS
from tuidungeon.presentation.inventory import InventoryBrowser, item_details
from tuidungeon.application.factories import SessionFactory


class MaterialTests(unittest.TestCase):
    def visual(self, ref):
        key = "base:" + ref
        alias = compatibility()["tiles"].get(key)
        return (
            self.store.get(alias["category"], alias["ref"])
            if alias
            else self.store.get("tiles", key)
        )

    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def test_all_furniture_and_wood_in_bundled_catalog_are_flammable(self):
        furniture = []
        for (category, ref), doc in self.store.documents.items():
            if not ref.startswith("base:"):
                continue
            tags = set(getattr(doc, "tags", ()))
            if category == "objects" and "furniture" in tags:
                furniture.append(doc)
                self.assertIn(FLAMMABLE, tags, ref)
            if WOODEN in tags:
                self.assertIn(FLAMMABLE, tags, ref)
        self.assertGreater(len(furniture), 10)

    def test_positive_and_negative_material_assignments(self):
        for ref in (
            "table",
            "chair",
            "bookcase",
            "barrel",
            "chest",
            "crate",
            "door_wood",
            "wooden_support",
            "floor_planks",
            "tree_dead",
        ):
            self.assertTrue(MATERIAL_TAGS <= set(self.visual(ref).tags), ref)
        for ref in ("book", "scroll", "sack", "web", "grass_dry", "bedroll"):
            tags = self.visual(ref).tags
            self.assertIn(FLAMMABLE, tags, ref)
            self.assertNotIn(WOODEN, tags, ref)
        for ref in (
            "door_stone",
            "door_steel",
            "door_bars",
            "door_adamantine",
            "wall",
            "jug",
            "pot",
            "urn",
            "water_calm",
            "bones",
        ):
            self.assertFalse(MATERIAL_TAGS & set(self.visual(ref).tags), ref)
        for ref in (
            "oil",
            "robe",
            "rope",
            "parchment",
            "spellbook",
            "leather",
            "bedroll",
        ):
            tags = self.store.get("equipment", "base:" + ref).tags
            self.assertIn(FLAMMABLE, tags, ref)
            self.assertNotIn(WOODEN, tags, ref)
        for ref in (
            "sword",
            "mail",
            "crowbar",
            "acid_flask",
            "healing_potion",
            "flint_and_steel",
        ):
            self.assertFalse(
                MATERIAL_TAGS & set(self.store.get("equipment", "base:" + ref).tags),
                ref,
            )

    def test_brush_and_linked_object_materials_agree(self):
        for (category, ref), tile in self.store.documents.items():
            if category != "tiles" or not ref.startswith("base:"):
                continue
            for category, target in (
                ("equipment", tile.brush.item),
                ("points_of_interest", tile.brush.interaction),
            ):
                if target:
                    obj = self.store.get(category, target)
                    self.assertEqual(
                        MATERIAL_TAGS & set(tile.tags),
                        MATERIAL_TAGS & set(obj.tags),
                        ref,
                    )

    def test_legacy_runtime_and_pack_items_agree(self):
        old, current = ContentCatalog.load(DEFAULT_ROOT), self.store.runtime_catalog()
        for ref, old_item in old.equipment.items():
            self.assertEqual(
                MATERIAL_TAGS & old_item.tags,
                MATERIAL_TAGS & current.equipment[ref].tags,
                ref,
            )
        self.assertEqual(collect_updates(), [])

    def test_schema_forms_expose_independent_material_traits(self):
        for cls in (EquipmentDocument, PointDocument, TileDocument):
            fields = cls.model_json_schema()["properties"]["tags"]
            self.assertTrue(MATERIAL_TAGS <= set(fields["tag_labels"]))
        wooden = EquipmentDocument(
            id="fireproof_wood", name="Защищённое дерево", tags=[WOODEN]
        )
        self.assertNotIn(FLAMMABLE, wooden.tags)
        source = self.store.get("equipment", "base:staff")
        variant = EquipmentDocument.model_validate({**source.model_dump(), "tags": []})
        self.assertFalse(variant.tags)
        self.assertIn(WOODEN, source.tags)

    def test_materials_survive_breakage_and_do_not_grant_ignition_action(self):
        staff = Equipment.create(self.store.runtime_catalog().equipment["staff"])
        self.assertTrue(staff.flammable)
        self.assertTrue(staff.wooden)
        self.assertFalse(staff.ignition_source)
        staff.wear(staff.durability)
        self.assertFalse(staff.usable)
        self.assertTrue(staff.flammable)
        self.assertTrue(staff.wooden)
        self.assertIn("Горючесть: горючий.", item_details(staff))

    def test_inventory_search_in_russian_and_identifiers(self):
        hero = SessionFactory(self.store).session("base:dungeon").state.hero
        catalog = self.store.runtime_catalog()
        staff = Equipment.create(catalog.equipment["staff"])
        oil = Equipment.create(catalog.equipment["oil"])
        sword = Equipment.create(catalog.equipment["sword"])
        hero.inventory[:] = [staff, oil, sword]
        browser = InventoryBrowser()
        for query, expected in (
            ("горюч", [staff, oil]),
            ("flammable", [staff, oil]),
            ("деревян", [staff]),
            ("wooden", [staff]),
        ):
            browser.query = query
            self.assertEqual([r.item for r in browser.rows(hero) if r.item], expected)


if __name__ == "__main__":
    unittest.main()
