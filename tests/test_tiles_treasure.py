"""Treasure atlas: all art assigned, real food/light/storage and quantity-based coins."""

from copy import copy
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import ContentError, PackStore
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.storage import item_stacks
from tuidungeon.world.maps import Position


RUINS = [19, 20, 21, 68, 69, 70, 117, 118, 119]
STYLES = [
    [654, 655, 656, 703, 704, 705, 752, 753, 754],
    [801, 802, 803, 850, 851, 852, 899, 900, 901],
    [948, 949, 950, 997, 998, 999, 1046, 1047, 1048],
]
JEWELS = {
    "amulet": [387, 388, 389, 390, 436, 437, 438, 439],
    "ring": [338, 339, 340, 341],
    "crown": [142, 143],
}


class TreasureTilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session(
            "tiles:treasure_lab", character_class="dev:empty_tester", seed=42
        )

    def give(self, ref, quantity=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
            for _ in range(quantity)
        ]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            r = SaveRepository(Path(folder) / "treasure.json")
            r.save(self.e)
            self.e = r.load(store=self.store)

    def test_all_requested_art_assigned_and_pixel_exact(self):
        nums = set(
            RUINS
            + [n for s in STYLES for n in s]
            + [n for s in JEWELS.values() for n in s]
            + [1015, 966, 916, 867, 819, 818, 241, 242, 243, 238, 239]
        )
        self.assertEqual(len(nums), 61)
        refs = set()
        for (cat, ref), d in self.store.documents.items():
            if ref.startswith("tiles:") and cat in ("tiles", "objects", "equipment"):
                refs.update([d.symbol, *d.state_symbols.values()])
        self.assertTrue({f"tiles:cell_{n:04}" for n in nums}.issubset(refs))
        atlas = Image.open(
            "assets/1 bit/Tilesheet/monochrome-transparent_packed.png"
        ).convert("RGBA")
        for n in nums:
            s = self.store.get("symbols", f"tiles:cell_{n:04}")
            x, y = (n - 1) % 49, (n - 1) // 49
            self.assertEqual(s.source.coordinates, [x, y])
            self.assertEqual(
                list(s.pixels),
                [
                    "".join(
                        "1"
                        if atlas.getpixel((x * 16 + c, y * 16 + r))[3] > 127
                        else "0"
                        for c in range(16)
                    )
                    for r in range(16)
                ],
            )

    def test_ruins_center_is_floor_exterior_centers_are_columns_with_real_materials(
        self,
    ):
        floor = self.store.get("tiles", "tiles:ruins_69")
        self.assertTrue(floor.walkable)
        self.assertFalse(floor.blocks_sight)
        for n in RUINS:
            d = self.store.get("tiles", f"tiles:ruins_{n}")
            self.assertEqual(d.walkable, n == 69)
        for style in STYLES:
            for n in style:
                tints = set()
                for mat in ("stone", "brick", "wood", "metal"):
                    cat = "objects" if mat == "wood" else "tiles"
                    d = self.store.get(cat, f"tiles:exterior_{n}_{mat}")
                    self.assertFalse(d.walkable)
                    self.assertTrue(d.blocks_sight)
                    tints.add(d.foreground)
                    self.assertEqual(
                        bool(getattr(d, "destruction", None)), mat == "wood"
                    )
                self.assertEqual(len(tints), 4)
            self.assertIn(
                "колонна",
                self.store.get("tiles", f"tiles:exterior_{style[4]}_stone").name,
            )

    def test_food_stacks_consumes_once_and_raw_meat_cooks(self):
        e = self.e
        for name in ("carrot", "fruit", "cheese_slice", "cheese_wedge"):
            item = self.give("tiles:" + name, 3)
            h = e.state.hero
            h.hp = h.max_hp - 2
            self.assertEqual(
                next(s.quantity for s in item_stacks(h.inventory) if s.first is item), 3
            )
            self.assertTrue(e.use_item(item).performed)
            self.assertEqual(h.hp, h.max_hp)
            self.assertNotIn(item, h.inventory)
            self.assertFalse(e.use_item(item).performed)
        raw = self.give("tiles:monster_meat")
        before = e.state.turns
        self.assertFalse(e.use_item(raw).performed)
        self.assertEqual(e.state.turns, before)
        e.state.position = Position(2, 5)
        torch = self.give("base:torch")
        self.assertTrue(e.manage_equipment(torch, True).performed)
        self.give("base:wood")
        self.give("base:cook_tools")
        e.state.hero.learn_tool_proficiency("cook_tools")
        self.assertTrue(e.interact("campfire", "fire_refuel").performed)
        self.assertTrue(e.interact("campfire", "fire_ignite").performed)
        self.assertTrue(e.start_craft("tiles:cook_monster_meat").performed)
        for _ in range(2):
            self.assertTrue(e.advance_craft().performed)
        self.assertTrue(any(i.id == "cooked_meat" for i in e.state.hero.inventory))

    def test_lantern_oil_pickup_exhaustion_refill_and_save(self):
        e = self.e
        e.state.position = Position(4, 3)
        self.assertTrue(e.interact("lantern", "take_light").performed)
        lamp = next(i for i in e.state.hero.inventory if i.id == "tiles:lantern")
        self.assertEqual(lamp.fuel_minutes, 60)
        self.assertFalse(lamp.lit)
        self.assertTrue(e.manage_equipment(lamp, True).performed)
        e._advance(59)
        self.assertEqual(lamp.fuel_minutes, 0)
        self.assertFalse(lamp.lit)
        self.assertTrue(e.manage_equipment(lamp, False).performed)
        oil = self.give("base:oil")
        self.assertTrue(e.manage_equipment(lamp, True).performed)
        self.assertEqual(lamp.fuel_minutes, 59)
        self.assertNotIn(oil, e.state.hero.inventory)
        self.reload()
        lamp = next(i for i in self.e.state.hero.inventory if i.id == "tiles:lantern")
        self.assertTrue(lamp.lit)
        self.assertEqual(lamp.fuel_minutes, 59)

    def test_sack_open_close_nested_storage_carry_and_save(self):
        e = self.e
        e.state.position = Position(6, 3)
        self.assertTrue(e.open_container("sack").performed)
        self.assertEqual(
            e.state.level.render_cells(e.state)[3][7].symbol, "tiles:cell_0243"
        )
        c = e.storage_at("sack")
        gold = next(i for i in c.items if i.id == "gold")
        self.assertTrue(
            e.transfer_storage("sack", gold.instance_id, quantity=5).performed
        )
        self.assertTrue(e.close_container("sack").performed)
        self.assertEqual(
            e.state.level.render_cells(e.state)[3][7].symbol, "tiles:cell_0242"
        )
        self.assertTrue(e.lift_furniture("sack").performed)
        self.reload()
        e = self.e
        cargo = next(i for i in e.state.hero.inventory if i.furniture)
        self.assertEqual(len(cargo.furniture.items), 2)
        self.assertTrue(e.place_furniture(cargo, Position(6, 4)).performed)
        self.reload()
        self.assertEqual(self.e.state.hero.gold, 5)

    def test_jewelry_metals_slots_magic_and_no_currency_confusion(self):
        e = self.e
        hero = e.state.hero
        for kind, nums in JEWELS.items():
            for n in nums:
                for metal in ("gold", "silver", "copper"):
                    item = self.give(f"tiles:{kind}_{n}_{metal}")
                    self.assertIn(metal, item.tags)
                    self.assertGreater(item.definition.value_gold, 0)
                    self.assertEqual(item.hands, 0)
            item = self.give(f"tiles:{kind}_arcane")
            before = hero.spell_attack_bonus
            self.assertTrue(e.manage_equipment(item, True).performed)
            self.assertEqual(
                hero.spell_attack_bonus,
                max(
                    before,
                    hero.stats.modifier(hero.spellcasting_ability)
                    + hero.proficiency_bonus
                    + 1,
                ),
            )
        self.assertEqual(hero.gold, 0)
        self.assertEqual(hero.hands_used, 0)
        self.reload()
        self.assertEqual(self.e.state.hero.hands_used, 0)
        self.assertTrue(
            all(
                any(
                    i.equipped and i.definition.slot == slot
                    for i in self.e.state.hero.inventory
                )
                for slot in ("ring", "neck", "head")
            )
        )

    def test_coins_quantity_threshold_pickup_drop_storage_save_and_recipe(self):
        e = self.e
        e.state.position = Position(9, 3)

        def symbol(x):
            return self.e.render_cells((x, 3, 1, 1))[0][0].symbol

        self.assertEqual(symbol(10), "tiles:cell_0238")
        self.assertEqual(symbol(12), "tiles:cell_0239")
        e.state.position = Position(12, 3)
        self.assertTrue(e.pickup_item().performed)
        coin = next(i for i in e.state.hero.inventory if i.id == "gold")
        e.state.position = Position(11, 3)
        self.assertEqual(symbol(12), "tiles:cell_0238")
        e.state.position = Position(12, 3)
        self.assertTrue(e.place_item(coin, Position(12, 3)).performed)
        e.state.position = Position(11, 3)
        self.assertEqual(symbol(12), "tiles:cell_0239")
        self.reload()
        e = self.e
        self.assertEqual(symbol(12), "tiles:cell_0239")
        # Canonical coins still satisfy the existing gold crafting ingredient.
        self.give("base:jeweler_tools")
        e.state.hero.learn_tool_proficiency("jeweler_tools")
        self.assertTrue(e.start_craft("tiles:draw_gold_thread").performed)
        for _ in range(2):
            self.assertTrue(e.advance_craft().performed)
        self.assertEqual(sum(i.id == "gold" for _, i in e.state.items), 11)
        self.assertTrue(
            any(i.id == "tiles:gold_thread" for i in e.state.hero.inventory)
        )

    def test_missing_coin_markers_falls_back_and_duplicates_are_invalid(self):
        s = copy(self.store)
        s.documents = {
            k: v
            for k, v in self.store.documents.items()
            if k
            not in [
                ("tiles", "tiles:service_coins_small"),
                ("tiles", "tiles:service_coins_large"),
            ]
        }
        e = SessionFactory(s).session(
            "tiles:treasure_lab", character_class="dev:empty_tester", seed=42
        )
        e.state.position = Position(9, 3)
        self.assertEqual(
            e.render_cells((10, 3, 1, 1))[0][0].symbol,
            self.store.get("equipment", "base:gold").symbol,
        )
        doc = self.store.get("tiles", "tiles:service_coins_small").model_copy(
            update={"id": "duplicate"}
        )
        with self.assertRaises(ContentError):
            self.store.validate_references(
                {**self.store.documents, ("tiles", "tiles:duplicate"): doc},
                self.store.manifests,
            )


if __name__ == "__main__":
    unittest.main()
