"""Physical dimensions and load are independent storage constraints."""

from copy import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.catalog import ContentError
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import EquipmentDocument, MapDocument, StorageSpec
from tuidungeon.domain.crafting import CraftWork
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.item_sizes import ITEM_SIZES, SIZE_RANK
from tuidungeon.presentation.inventory import item_details
from tuidungeon.presentation.storage import storage_layout
from tuidungeon.presentation.tui import Controller
from scripts.prepare_item_sizes import updates


class ItemSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="size_test",
            name="Размеры вещей",
            width=8,
            height=6,
            tiles=[["base:floor"] * 8 for _ in range(6)],
            walkability=[[True] * 8 for _ in range(6)],
            blocks_sight=[[False] * 8 for _ in range(6)],
            ambient_light="bright",
            spawn={"x": 2, "y": 2},
            objects=[
                dict(
                    id="shelf",
                    ref="base:bookcase",
                    x=3,
                    y=2,
                    overrides={"storage": {"personal": True}},
                ),
                dict(
                    id="large_box",
                    ref="base:cabinet",
                    x=2,
                    y=3,
                    overrides={"storage": {"personal": True}},
                ),
            ],
            points_of_interest=[
                dict(
                    id="chest",
                    ref="base:terrain_chest",
                    x=1,
                    y=2,
                    overrides={"storage": {"personal": True}},
                )
            ],
        )
        self.make_engine()
        self.e.state.hero.inventory.clear()

    def make_engine(self):
        self.store.documents["maps", "base:size_test"] = MapDocument.model_validate(
            self.raw
        )
        self.e = SessionFactory(self.store).session("base:size_test", seed=42)
        return self.e

    def give(self, ref, quantity=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref]) for _ in range(quantity)
        ]
        self.e.state.hero.inventory.extend(items)
        return items

    def deposit(self, ref, item, quantity=1):
        return self.e.transfer_storage(ref, item.instance_id, quantity, deposit=True)

    def test_defaults_strict_schemas_and_runtime_definitions(self):
        self.assertEqual(
            EquipmentDocument(id="legacy", name="Старый предмет").size, "medium"
        )
        self.assertEqual(StorageSpec().max_item_size, "large")
        for size in ("huge", 3, None):
            with self.assertRaises(ValidationError):
                EquipmentDocument(id="invalid", name="Ошибка", size=size)
            with self.assertRaises(ValidationError):
                StorageSpec(max_item_size=size)
        with self.assertRaises(ValueError):
            replace(self.e.catalog.equipment["staff"], size="huge")
        self.assertEqual(list(updates()), [])
        for (category, ref), doc in self.source.documents.items():
            if category == "equipment":
                self.assertIn(doc.size, ITEM_SIZES)
                raw = json.loads(self.source.paths[category, ref].read_text())
                self.assertIn("size", raw, ref)

    def test_all_nine_size_combinations_allow_equal_and_smaller(self):
        container = self.e.storage_at("large_box")
        for maximum in ITEM_SIZES:
            container.spec = container.spec.model_copy(
                update={"max_item_size": maximum}
            )
            for ref in ("spellbook", "torch", "staff"):
                with self.subTest(maximum=maximum, item=ref):
                    container.items.clear()
                    self.e.state.hero.inventory.clear()
                    item = self.give(ref)[0]
                    result = self.deposit("large_box", item)
                    expected = SIZE_RANK[item.size] <= SIZE_RANK[maximum]
                    self.assertEqual(result.performed, expected, result.message)
                    self.assertEqual(item in container.items, expected)
                    self.assertEqual(item in self.e.state.hero.inventory, not expected)
        self.assertEqual(self.e.state.turns, 0)

    def test_shelf_30kg_small_chest_300kg_medium_and_sizes_ignore_weight(self):
        for ref in ("base:bookcase", "base:shelf"):
            spec = self.store.get("objects", ref).storage
            self.assertEqual((spec.capacity, spec.max_item_size), (30, "small"))
        for ref in (
            "base:chest",
            "base:terrain_chest",
            "base:terrain_chest_open",
            "base:terrain_chest_treasure",
        ):
            spec = self.store.get("points_of_interest", ref).storage
            self.assertEqual((spec.capacity, spec.max_item_size), (300, "medium"))
        book, torch, staff = (
            self.give(ref)[0] for ref in ("spellbook", "torch", "staff")
        )
        self.assertGreater(book.weight, staff.weight)
        self.assertTrue(self.deposit("shelf", book).performed)
        self.assertFalse(self.deposit("shelf", torch).performed)
        self.assertTrue(self.deposit("chest", torch).performed)
        self.assertFalse(self.deposit("chest", staff).performed)
        self.assertTrue(self.deposit("large_box", staff).performed)

    def test_weight_boundary_still_applies_to_many_small_items(self):
        books = self.give("spellbook", 11)
        self.assertTrue(self.deposit("shelf", books[0], 10).performed)
        self.assertEqual(self.e.storage_at("shelf").weight, 30)
        self.assertFalse(self.deposit("shelf", books[-1]).performed)
        self.assertEqual(len(self.e.storage_at("shelf").items), 10)
        self.assertIn(books[-1], self.e.state.hero.inventory)

    def test_rejected_transfer_is_atomic_preserving_equipment_light_rng_and_time(self):
        torch = self.give("torch")[0]
        torch.equipped = torch.lit = True
        torch.fuel_minutes = 17
        before = (
            list(self.e.state.hero.inventory),
            list(self.e.events),
            self.e.dice.rng.getstate(),
            self.e.state.turns,
        )
        result = self.deposit("shelf", torch)
        self.assertFalse(result.performed)
        self.assertIn("слишком большой", result.message)
        self.assertEqual(
            (torch.equipped, torch.lit, torch.fuel_minutes), (True, True, 17)
        )
        self.assertEqual(
            (
                self.e.state.hero.inventory,
                self.e.events,
                self.e.dice.rng.getstate(),
                self.e.state.turns,
            ),
            before,
        )
        self.assertEqual(self.e.storage_at("shelf").items, [])

    def test_initial_contents_and_placement_overrides_reject_large_items(self):
        self.raw["objects"][0]["overrides"]["storage"]["contents"] = [
            {"item": "base:staff", "quantity": 1}
        ]
        self.store.documents["maps", "base:size_test"] = MapDocument.model_validate(
            self.raw
        )
        with self.assertRaisesRegex(ContentError, "Размер"):
            self.store.validate_references(self.store.documents, self.store.manifests)
        with self.assertRaisesRegex(ValueError, "Размер"):
            SessionFactory(self.store).session("base:size_test", seed=42)

    def test_restock_checks_size_before_replacing_existing_loot(self):
        container = self.e.storage_at("shelf")
        container.spec = container.spec.model_copy(update={"personal": False})
        book = self.give("spellbook")[0]
        staff = self.give("staff")[0]
        container.replace_loot([book])
        with self.assertRaisesRegex(ValueError, "Размер"):
            container.replace_loot([staff])
        self.assertEqual(container.items, [book])

    def test_limits_and_contents_roundtrip_legacy_default_and_invalid_save(self):
        book = self.give("spellbook")[0]
        self.assertTrue(self.deposit("shelf", book).performed)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            loaded = repo.load(store=self.store)
            self.assertEqual(loaded.storage_at("shelf").spec.max_item_size, "small")
            self.assertEqual(
                loaded.storage_at("shelf").items[0].instance_id, book.instance_id
            )
            raw = json.loads(repo.path.read_text())
            for c in raw["levels"][0]["containers"].values():
                c.pop("max_item_size")
            repo.path.write_text(json.dumps(raw))
            self.assertEqual(
                repo.load(store=self.store).storage_at("shelf").spec.max_item_size,
                "small",
            )
            self.e.storage_at("shelf").items.append(self.give("staff")[0])
            repo.save(self.e)
            with self.assertRaisesRegex(ValueError, "содержимое контейнера"):
                repo.load(store=self.store)

    def test_lifted_furniture_cannot_bypass_size_limit_and_keeps_nested_contents(self):
        book = self.give("spellbook")[0]
        self.assertTrue(self.deposit("shelf", book).performed)
        self.assertTrue(self.e.lift_furniture("shelf").performed)
        cargo = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertEqual(cargo.size, "large")
        self.assertFalse(self.deposit("chest", cargo).performed)
        self.assertTrue(self.deposit("large_box", cargo).performed)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            loaded = repo.load(store=self.store)
            restored = loaded.storage_at("large_box").items[0]
            self.assertEqual(restored.size, "large")
            self.assertEqual(restored.furniture.items[0].instance_id, book.instance_id)
            self.assertEqual(restored.furniture.container_spec.max_item_size, "small")

    def test_workpiece_does_not_hide_large_repair_target(self):
        staff = self.give("staff")[0]
        work = Equipment.create(self.e.catalog.equipment["craft_workpiece"])
        work.work = CraftWork(
            "base:repair_wood",
            self.e.catalog.recipes["base:repair_wood"],
            0,
            [],
            target=staff,
        )
        self.e.state.hero.inventory.append(work)
        self.assertEqual(work.size, "large")
        self.assertFalse(self.deposit("chest", work).performed)

    def test_storage_greys_size_and_personal_restrictions_and_keeps_cursor_grey(self):
        import tcod.console
        from tuidungeon.presentation.window import draw, PALETTE

        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:size_test",
            test_map=True,
        )
        c.engine.state.hero.inventory.clear()
        c.engine.state.hero.inventory.extend(
            Equipment.create(c.engine.catalog.equipment[ref])
            for ref in ("spellbook", "staff")
        )
        c.open_storage("shelf")
        _, rect, _, _ = storage_layout(c, 100, 28)
        colors = c.storage.colors
        self.assertFalse(
            next(row for row in colors if "Книга заклинаний" in row[2])[-1]
        )
        staff = next(row for row in colors if "Посох" in row[2])
        self.assertTrue(staff[-1])
        self.assertEqual(staff[3], 8)
        c.storage.side = 0
        c.storage.selected[0] = 1
        console = tcod.console.Console(100, 28)
        draw(console, c)
        self.assertEqual(
            tuple(console.rgb[rect.y + 1 + staff[0], rect.x + 2 + staff[1]]["fg"]),
            PALETTE[8],
        )
        self.assertEqual(
            tuple(console.rgb[rect.y + 1 + staff[0], rect.x + 2 + staff[1]]["bg"]),
            PALETTE[11],
        )
        container = c.engine.storage_at("shelf")
        container.spec = container.spec.model_copy(update={"personal": False})
        storage_layout(c, 100, 28)
        self.assertTrue(all(row[-1] for row in c.storage.colors if row[1] == 0))
        self.assertEqual(c.engine.state.turns, 0)

    def test_partial_stacks_stay_available_and_colors_refresh_after_transfer(self):
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:size_test",
            test_map=True,
        )
        c.engine.state.hero.inventory.clear()
        books = [
            Equipment.create(c.engine.catalog.equipment["spellbook"]) for _ in range(2)
        ]
        c.engine.state.hero.inventory.extend(books)
        c.open_storage("shelf")
        c.storage.side = 0
        container = c.engine.storage_at("shelf")
        container.spec = container.spec.model_copy(update={"capacity": 3})
        storage_layout(c, 100, 28)
        self.assertFalse(next(row for row in c.storage.colors if row[1] == 0)[-1])
        c.storage.handle(c, "enter")
        self.assertIsNotNone(c.storage.pending)
        c.storage.handle(c, "enter")
        self.assertIsNone(c.storage.pending)
        storage_layout(c, 100, 28)
        self.assertTrue(next(row for row in c.storage.colors if row[1] == 0)[-1])
        c.storage.handle(c, "enter")
        self.assertIsNone(c.storage.pending)
        self.assertIn("нагрузки", c.message)
        # A loaded hero cannot withdraw even one unit; freeing load refreshes eligibility.
        hero = c.engine.state.hero
        while hero.carried_weight + 3 <= hero.max_carry_weight:
            hero.inventory.append(
                Equipment.create(c.engine.catalog.equipment["spellbook"])
            )
        storage_layout(c, 100, 28)
        self.assertTrue(next(row for row in c.storage.colors if row[1] > 0)[-1])
        hero.inventory.clear()
        storage_layout(c, 100, 28)
        self.assertFalse(next(row for row in c.storage.colors if row[1] > 0)[-1])
        self.assertEqual(c.engine.state.turns, 0)

    def test_details_and_storage_window_show_dimensions(self):
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:size_test",
            test_map=True,
        )
        c.open_storage("shelf")
        for width, height in ((80, 24), (100, 28), (140, 40)):
            _, rect, rows, _ = storage_layout(c, width, height)
            self.assertIn("Макс. размер: Маленький", "\n".join(rows))
            self.assertLessEqual(len(rows), rect.height - 2)
        self.assertIn("Размер: Маленький", item_details(self.give("spellbook")[0]))


if __name__ == "__main__":
    unittest.main()
