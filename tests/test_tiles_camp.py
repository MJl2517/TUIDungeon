"""Atlas camp content reuses light, vessels, loot, work and regrowth commands."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.liquids import PORTION_WEIGHT
from tuidungeon.domain.storage import item_stacks
from tuidungeon.world.maps import Position


class CampTilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session(
            "tiles:camp_lab", character_class="dev:empty_tester", seed=42
        )

    def give(self, ref, quantity=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
            for _ in range(quantity)
        ]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def near(self, identifier):
        p = next(p for p in self.e.state.level.definition.objects if p.id == identifier)
        self.e.state.position = Position(p.x - 1, p.y)
        return Position(p.x, p.y)

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "camp.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def craft(self, ref):
        result = self.e.start_craft(ref)
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)

    def test_all_requested_cells_imported_and_assigned(self):
        expected = {
            692,
            505,
            506,
            646,
            647,
            736,
            737,
            739,
            740,
            741,
            688,
            689,
            698,
            691,
            690,
            603,
            738,
        }
        assigned = set()
        atlas = Image.open(
            "assets/1 bit/Tilesheet/monochrome-transparent_packed.png"
        ).convert("RGBA")
        for (category, ref), doc in self.store.documents.items():
            if (
                category not in ("objects", "equipment")
                or not ref.startswith("tiles:")
                or not doc.symbol
            ):
                continue
            s = self.store.get("symbols", doc.symbol)
            if not s.source or not s.source.coordinates:
                continue
            x, y = s.source.coordinates
            number = y * 49 + x + 1
            if number not in expected:
                continue
            assigned.add(number)
            pixels = [
                "".join(
                    "1" if atlas.getpixel((x * 16 + cx, y * 16 + cy))[3] > 127 else "0"
                    for cx in range(16)
                )
                for cy in range(16)
            ]
            self.assertEqual(list(s.pixels), pixels)
        self.assertEqual(assigned, expected)
        for ref in (
            "tiles:remains_646",
            "tiles:remains_647",
            "tiles:remains_736",
            "tiles:animal_remains_737",
        ):
            self.assertIsNotNone(self.store.get("objects", ref).storage)

    def test_well_pot_capacity_weight_and_save(self):
        e = self.e
        pot = self.give("tiles:cooking_pot")
        self.near("well")
        self.assertTrue(
            e.water_action(pot.instance_id, "fill", target="well").performed
        )
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("clean_water", 3))
        self.assertAlmostEqual(pot.weight, pot.definition.weight + 3 * PORTION_WEIGHT)
        self.assertTrue(pot.definition.vessel.heat_safe)
        before = e.state.turns
        self.assertFalse(
            e.water_action(pot.instance_id, "fill", target="well").performed
        )
        self.assertEqual(e.state.turns, before)
        self.reload()
        pot = next(
            i for i in self.e.state.hero.inventory if i.id == "tiles:cooking_pot"
        )
        self.assertEqual(pot.liquid_portions, 3)
        self.assertTrue(self.e.water_action(pot.instance_id, "empty").performed)
        self.assertEqual(pot.liquid_portions, 0)
        self.assertIsNotNone(self.e.world_object("well"))

    def test_remains_are_loot_containers_not_floor_and_do_not_refill(self):
        e = self.e
        for identifier in (
            "remains_646",
            "remains_647",
            "remains_736",
            "animal_remains_737",
        ):
            p = self.near(identifier)
            self.assertTrue(e.open_container(identifier).performed)
            c = e.storage_at(identifier)
            self.assertEqual(len(c.items), 2)
            self.assertTrue(
                e.transfer_storage(
                    identifier, c.items[0].instance_id, quantity=2
                ).performed
            )
            self.assertFalse(c.items)
            self.assertEqual(e.state.level.definition.tiles[p.y][p.x], "base:floor")
        self.reload()
        for identifier in (
            "remains_646",
            "remains_647",
            "remains_736",
            "animal_remains_737",
        ):
            c = next(
                c for c in self.e.state.level.containers if c.placement.id == identifier
            )
            self.assertFalse(c.items)

    def test_pickup_light_and_mount_back_keep_fuel_and_identity(self):
        e = self.e
        for identifier in ("torch_stand", "candelabra", "candle_fixture"):
            p = self.near(identifier)
            c = next(
                c for c in e.state.level.containers if c.placement.id == identifier
            )
            original = c.items[0]
            fuel = original.fuel_minutes
            self.assertTrue(e.interact(identifier, "take_light").performed)
            self.assertIn(original, e.state.hero.inventory)
            self.assertEqual(original.fuel_minutes, fuel)
            self.assertFalse(original.lit)
            if identifier != "candle_fixture":
                self.assertTrue(e.interact(identifier, "mount_light").performed)
                self.assertIs(c.items[0], original)
                self.assertEqual(original.fuel_minutes, fuel - 1)
                self.assertTrue(original.lit)
                self.assertEqual(
                    e.state.level.render_cells(e.state)[p.y][p.x].symbol,
                    c.definition.symbol,
                )
            else:
                self.assertIsNone(e.world_object(identifier))
                self.assertEqual(e.state.level.terrain.tiles[p.y][p.x], "base:floor")
        self.reload()
        c = next(
            c for c in self.e.state.level.containers if c.placement.id == "candelabra"
        )
        self.assertTrue(c.items[0].lit)
        e = self.e
        self.near("candelabra")
        fuel = c.items[0].fuel_minutes
        self.assertTrue(e.lift_furniture("candelabra").performed)
        cargo = next(i for i in e.state.hero.inventory if i.furniture)
        self.assertFalse(cargo.furniture.items[0].lit)
        self.assertEqual(cargo.furniture.items[0].fuel_minutes, fuel)
        self.reload()
        e = self.e
        cargo = next(i for i in e.state.hero.inventory if i.furniture)
        self.assertTrue(e.place_furniture(cargo, Position(18, 9)).performed)
        self.reload()
        c = next(
            c for c in self.e.state.level.containers if c.placement.id == "candelabra"
        )
        self.assertEqual(c.items[0].fuel_minutes, fuel)
        self.assertFalse(c.items[0].lit)

    def test_campfire_spends_fuel_but_magic_fire_neither_burns_nor_heats(self):
        e = self.e
        self.near("campfire")
        torch = self.give("base:torch")
        self.assertTrue(e.manage_equipment(torch, True).performed)
        self.give("base:wood")
        self.assertTrue(e.interact("campfire", "fire_refuel").performed)
        self.assertTrue(e.interact("campfire", "fire_ignite").performed)
        state = e.world_object("campfire").state
        self.assertEqual(state.fuel_minutes, 59)
        self.assertIn("heat", e.craft_stations())
        self.give("base:smith_tools")
        e.state.hero.learn_tool_proficiency("smith_tools")
        self.give("base:metal", 2)
        self.craft("tiles:forge_cooking_pot")
        self.assertTrue(
            any(i.id == "tiles:cooking_pot" for i in e.state.hero.inventory)
        )
        self.assertTrue(e.interact("campfire", "fire_extinguish").performed)
        self.assertEqual(state.fuel_minutes, 56)
        self.assertNotIn("heat", e.craft_stations())
        self.reload()
        e = self.e
        self.assertEqual(e.world_object("campfire").state.fuel_minutes, 56)
        self.near("magic_fire")
        hp = e.state.hero.hp
        self.assertNotIn("heat", e.craft_stations())
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertEqual(e.state.hero.hp, hp)
        fire = next(i for i in e.state.hero.inventory if i.id == "torch")
        self.near("magic_fire")
        self.assertFalse(e.ignite_cell(fire, Position(9, 4)).performed)
        # Persistent light works independently of any inventory or fuel.
        dark = self.factory.session(
            "tiles:camp_annex", character_class="dev:empty_tester", seed=42
        )
        p = Position(8, 5)
        self.assertEqual(dark.lighting.level_at(p), 2)
        dark._advance(180)
        self.assertEqual(dark.lighting.level_at(p), 2)

    def test_web_harvest_saved_ten_day_regrowth(self):
        e = self.e
        p = self.near("web_hanging")
        self.assertTrue(e.interact("web_hanging", "dismantle").performed)
        self.assertTrue(e.advance_craft().performed)
        self.assertIsNone(e.world_object("web_hanging"))
        ready = next(
            r.ready_at
            for r in e.state.level.regrowing_objects
            if r.placement.id == "web_hanging"
        )
        self.assertEqual(ready - e.state.clock.elapsed_minutes, 14400)
        self.reload()
        e = self.e
        e._advance(14399)
        self.assertIsNone(e.world_object("web_hanging"))
        e._advance(1)
        self.assertIsNotNone(e.world_object("web_hanging"))
        silk = [
            i
            for pp, i in e.state.items
            if (pp.x, pp.y) == (p.x, p.y) and i.id == "spider_silk"
        ]
        self.assertEqual(len(silk), 1)

    def test_dense_web_needs_held_slashing_weapon_and_three_saved_turns_or_fire(self):
        e = self.e
        p = self.near("web_dense")
        self.assertFalse(e.state.walkable(p))
        self.assertTrue(e.state.level.terrain.blocks_sight[p.y][p.x])
        sword = self.give("base:sword")
        self.assertFalse(e.interact("web_dense", "dismantle").performed)
        self.assertEqual(e.state.turns, 0)
        self.assertTrue(e.manage_equipment(sword, True).performed)
        self.assertTrue(e.interact("web_dense", "dismantle").performed)
        self.assertTrue(e.advance_craft().performed)
        self.assertTrue(e.pause_craft().performed)
        self.reload()
        e = self.e
        self.assertEqual(e.world_object("web_dense").state.progress, 1)
        self.assertTrue(e.interact("web_dense", "dismantle").performed)
        for _ in range(2):
            self.assertTrue(e.advance_craft().performed)
        self.assertIsNone(e.world_object("web_dense"))
        self.assertTrue(e.state.walkable(p))
        self.assertFalse(e.state.level.terrain.blocks_sight[p.y][p.x])
        self.assertEqual(e.state.level.terrain.tiles[p.y][p.x], "base:floor")
        e.collect_door_remains()
        self.assertEqual(
            Counter(i.id for pp, i in e.state.items if (pp.x, pp.y) == (p.x, p.y)),
            Counter({"spider_silk": 2}),
        )
        self.setUp()
        e = self.e
        p = self.near("web_dense")
        torch = self.give("base:torch")
        self.assertTrue(e.manage_equipment(torch, True).performed)
        self.assertTrue(e.ignite_cell(torch, p).performed)
        self.assertTrue(e.world_object("web_dense").state.burning)
        e.apply(Action.WAIT)
        self.assertIsNone(e.world_object("web_dense"))
        self.assertTrue(e.state.walkable(p))

    def test_materials_stack_and_make_existing_usable_products(self):
        e = self.e
        for tool in ("weaver_tools", "jeweler_tools", "leatherworker_tools"):
            self.give("base:" + tool)
            e.state.hero.learn_tool_proficiency(tool)
        self.give("base:plant_fiber", 3)
        for _ in range(3):
            self.craft("tiles:spin_thread")
        stacks = [
            s
            for s in item_stacks(e.state.hero.inventory)
            if s.items[0].id == "tiles:thread"
        ]
        self.assertEqual([s.quantity for s in stacks], [3])
        self.craft("tiles:weave_thread_rope")
        self.assertTrue(any(i.id == "rope" for i in e.state.hero.inventory))
        self.give("base:raw_leather", 3)
        self.craft("tiles:cut_leather_strips")
        self.craft("tiles:sew_waterskin")
        self.assertTrue(any(i.id == "waterskin" for i in e.state.hero.inventory))
        self.give("base:gold", 10)
        self.craft("tiles:draw_gold_thread")
        self.give("base:alchemy_reagent")
        e.state.hero.class_spells = (
            *e.state.hero.class_spells,
            e.catalog.spells["light"],
        )
        self.craft("tiles:gold_thread_focus")
        self.assertTrue(any(i.id == "arcane_focus" for i in e.state.hero.inventory))
        self.assertEqual(e.state.hero.gold, 0)

    def test_hatch_transitions_on_entry_and_keeps_floor(self):
        e = self.e
        p = self.near("hatch_transition")
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertEqual(e.state.level.ref, "tiles:camp_annex")
        self.near("return_hatch")
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertEqual(e.state.level.ref, "tiles:camp_lab")
        self.reload()
        self.assertEqual(self.e.state.level.terrain.tiles[p.y][p.x], "base:floor")


if __name__ == "__main__":
    unittest.main()
