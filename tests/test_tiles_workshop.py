"""Workshop atlas batch uses the shared world, crafting and save commands."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import CheckResult
from tuidungeon.world.maps import Position


CELLS = {
    453,
    454,
    403,
    398,
    401,
    402,
    361,
    410,
    459,
    261,
    262,
    263,
    168,
    169,
    217,
    218,
    166,
    167,
    215,
    216,
    644,
    743,
    642,
    645,
    638,
    639,
    640,
    541,
    841,
    593,
}


class WorkshopAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session(
            "tiles:workshop_ruins_lab", character_class="dev:empty_tester", seed=42
        )

    def near(self, identifier):
        obj = next(
            p for p in self.e.state.level.definition.objects if p.id == identifier
        )
        self.e.state.position = Position(obj.x - 1, obj.y)
        return Position(obj.x, obj.y)

    def give(self, ref):
        item = Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
        self.e.state.hero.inventory.append(item)
        return item

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "workshop.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def dismantle(self, identifier):
        self.near(identifier)
        result = self.e.start_dismantle(identifier)
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)

    def test_exact_pixels_assignments_and_showcase_coverage(self):
        atlas = Image.open(
            "assets/1 bit/Tilesheet/monochrome-transparent_packed.png"
        ).convert("RGBA")
        assigned = {
            d.symbol
            for (cat, ref), d in self.store.documents.items()
            if ref.startswith("tiles:") and cat in ("objects", "tiles", "traps")
        }
        for n in CELLS:
            symbol = self.store.get("symbols", f"tiles:cell_{n:04}")
            c, r = (n - 1) % 49, (n - 1) // 49
            self.assertEqual(symbol.source.coordinates, [c, r])
            self.assertEqual(symbol.source.license, "CC0")
            self.assertIn(f"tiles:cell_{n:04}", assigned)
            self.assertEqual(
                list(symbol.pixels),
                [
                    "".join(
                        "1"
                        if atlas.getpixel((c * 16 + x, r * 16 + y))[3] > 127
                        else "0"
                        for x in range(16)
                    )
                    for y in range(16)
                ],
            )
        level = self.e.state.level
        rendered = {
            cell.symbol for row in level.render_cells(self.e.state) for cell in row
        }
        self.assertTrue({f"tiles:cell_{n:04}" for n in CELLS} <= rendered)

    def test_walls_floors_bridges_window_and_flags_geometry(self):
        level = self.e.state.level
        for y, row in enumerate(level.definition.tiles):
            for x, ref in enumerate(row):
                if not ref or not ref.startswith("tiles:"):
                    continue
                d = self.store.get("tiles", ref)
                self.assertEqual(self.e.state.walkable(Position(x, y)), d.walkable, ref)
                self.assertEqual(level.terrain.blocks_sight[y][x], d.blocks_sight, ref)
        window = self.near("cobble_window")
        self.assertFalse(self.e.state.walkable(window))
        self.assertFalse(level.terrain.blocks_sight[window.y][window.x])
        for n in (361, 410, 459):
            p = self.near(f"flag_{n}")
            self.assertTrue(self.e.state.walkable(p))
            self.assertFalse(level.terrain.blocks_sight[p.y][p.x])
            self.assertFalse(self.e.start_dismantle(f"flag_{n}").performed)

    def test_chair_move_carry_place_and_floor_after_dismantling(self):
        p = self.near("chair_453")
        destination = Position(p.x - 1, p.y - 1)
        self.assertTrue(self.e.move_furniture("chair_453", destination).performed)
        self.assertTrue(self.e.lift_furniture("chair_453").performed)
        cargo = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertTrue(self.e.place_furniture(cargo, p).performed)
        self.reload()
        self.assertIsNotNone(self.e.world_object("chair_453"))
        other = self.near("chair_454")
        turns = self.e.state.turns
        self.assertFalse(self.e.start_dismantle("chair_454").performed)
        self.assertEqual(self.e.state.turns, turns)
        self.give("base:carpenter_tools")
        self.dismantle("chair_454")
        self.assertTrue(self.e.state.walkable(other))
        self.assertEqual(
            self.e.state.level.terrain.tiles[other.y][other.x], "base:floor"
        )
        self.reload()
        self.assertIsNone(self.e.world_object("chair_454"))

    def test_bed_enables_rest_until_dismantled(self):
        self.assertFalse(self.e.can_long_rest())
        self.near("bed_398")
        self.assertTrue(self.e.apply(Action.REST).performed)
        self.give("base:carpenter_tools")
        self.dismantle("bed_398")
        self.assertFalse(self.e.can_long_rest())
        self.reload()
        self.assertIsNone(self.e.world_object("bed_398"))

    def test_fountain_refills_portions_and_survives_save(self):
        pot = self.give("tiles:cooking_pot")
        self.near("fountain")
        for _ in range(2):
            self.assertTrue(
                self.e.water_action(
                    pot.instance_id, "fill", target="fountain"
                ).performed
            )
            self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("clean_water", 3))
            self.assertTrue(self.e.water_action(pot.instance_id, "empty").performed)
        self.assertTrue(
            self.e.water_action(pot.instance_id, "fill", target="fountain").performed
        )
        self.reload()
        self.assertEqual(self.e.state.hero.inventory[0].liquid_portions, 3)
        self.assertIsNotNone(self.e.world_object("fountain"))

    def test_stations_cook_and_removed_workbench_stops_qualifying(self):
        for name in ("oven", "forge", "workbench"):
            self.near(name)
            self.assertIn(name, self.e.craft_stations())
        self.near("oven")
        self.e.state.hero.learn_tool_proficiency("cook_tools")
        self.give("base:cook_tools")
        self.give("tiles:meat")
        result = self.e.start_craft("tiles:cook_meat")
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)
        self.assertTrue(any(i.id == "cooked_meat" for i in self.e.state.hero.inventory))
        self.give("base:carpenter_tools")
        self.dismantle("workbench")
        self.assertNotIn("workbench", self.e.craft_stations())

    def test_levers_open_only_their_linked_gate_and_save(self):
        for identifier in ("brick_lever_645", "cobble_lever"):
            self.near(identifier)
            self.assertFalse(self.e._door("gate_" + identifier).door.opened)
            self.assertTrue(self.e.interact(identifier, "activate_mechanism").performed)
            self.assertTrue(self.e._door("gate_" + identifier).door.opened)
        self.reload()
        for identifier in ("brick_lever_645", "cobble_lever"):
            self.assertTrue(self.e._door("gate_" + identifier).door.opened)

    def test_pit_trap_failure_success_and_no_second_damage_after_reload(self):
        for roll in (1, 20):
            e = self.factory.session(
                "tiles:workshop_ruins_lab", character_class="dev:empty_tester", seed=42
            )
            trap = next(t for t in e.state.level.traps if t.placement.id == "pit_841")
            e.state.position = Position(trap.placement.x - 1, trap.placement.y)
            hp = e.state.hero.hp
            with patch.object(e.dice, "check", return_value=CheckResult(roll, 0, 12)):
                self.assertTrue(e.apply(Action.EAST).performed)
            damage = hp - e.state.hero.hp
            self.assertTrue(2 <= damage <= 5 if roll == 1 else damage == 0)
            self.e = e
            self.reload()
            e = self.e
            e.state.position = Position(trap.placement.x - 1, trap.placement.y)
            hp = e.state.hero.hp
            self.assertTrue(e.apply(Action.EAST).performed)
            self.assertEqual(e.state.hero.hp, hp)


if __name__ == "__main__":
    unittest.main()
