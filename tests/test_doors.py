"""Door rules, geometry, resources, progress and both client contracts."""

from scripts.testing import lay_bedroll

from copy import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, ItemRecord, restore_item
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import DoorSpec, MapDocument, TileDocument
from tuidungeon.domain.doors import Door, MATERIALS, LOCK_DC
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.definitions import CheckAid
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position


class DoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setup_map(
        self,
        material="wood",
        *,
        locked=False,
        complex=False,
        ambient="bright",
        legacy=False,
    ):
        store = copy(self.source)
        store.documents = dict(self.source.documents)
        spec = DoorSpec(
            material=material,
            locked=locked,
            lock_quality="cheap",
            lock_complexity="complex" if complex else "simple",
        )
        tile = TileDocument(id="test_door", name="Дверь", brush={"door": spec})
        store.documents["tiles", "base:test_door"] = tile
        tiles = [["base:floor"] * 9 for _ in range(5)]
        masks = [
            [x == 4 or x in (0, 8) or y in (0, 4) for x in range(9)] for y in range(5)
        ]
        walk = [[not value for value in row] for row in masks]
        for y in range(5):
            for x in range(9):
                if masks[y][x]:
                    tiles[y][x] = "base:wall"
        tiles[2][4] = "base:test_door" if legacy else "base:floor"
        walk[2][4] = not legacy
        masks[2][4] = legacy
        raw = dict(
            id="door_test",
            name="Двери",
            width=9,
            height=5,
            tiles=tiles,
            walkability=walk,
            blocks_sight=masks,
            spawn={"x": 3, "y": 2},
            ambient_light=ambient,
            lights=[dict(id="lamp", x=2, y=2, radius=8, bright_radius=8)],
        )
        if not legacy:
            raw["doors"] = [dict(id="door", ref="base:test_door", x=4, y=2)]
        store.documents["maps", "base:door_test"] = MapDocument.model_validate(raw)
        self.store = store
        self.engine = SessionFactory(store).session("base:door_test", seed=42)
        self.instance = self.engine.state.level.doors[0]
        return self.engine

    def add_tools(self, engine, *, advantage=True):
        definition = engine.catalog.equipment["thieves_tools"]
        if not advantage:
            definition = replace(definition, check_aids=())
        tools = Equipment.create(definition)
        engine.state.hero.inventory.append(tools)
        return tools

    def test_materials_locks_and_canonical_symbols(self):
        for material, info in MATERIALS.items():
            for quality, dc in LOCK_DC.items():
                for complexity, turns in (("simple", 1), ("complex", 10)):
                    spec = DoorSpec(
                        material=material,
                        locked=True,
                        lock_quality=quality,
                        lock_complexity=complexity,
                    )
                    door = Door.from_spec(spec)
                    tile = TileDocument(
                        id="x",
                        name="Дверь",
                        glyph="?",
                        foreground=0,
                        brush={"door": spec},
                    )
                    self.assertEqual(
                        (door.force_dc, door.lock_dc, door.lock_turns),
                        (info.force_dc, dc, turns),
                    )
                    self.assertEqual(
                        (tile.glyph, tile.foreground),
                        ("#" if material == "stone" else "X", info.color),
                    )
                    door.locked = False
                    self.assertEqual(door.glyph, "#" if material == "stone" else "+")
                    door.opened = True
                    self.assertEqual(door.glyph, "#" if material == "stone" else "/")
        with self.assertRaises(ValidationError):
            DoorSpec(material="plastic")
        with self.assertRaises(ValidationError):
            DoorSpec(lock_quality="easy")

    def test_open_close_updates_movement_light_and_cached_frames(self):
        engine = self.setup_map(ambient="dark")
        original = self.store.get("maps", "base:door_test")
        light = engine.lighting
        self.assertEqual(light.illumination[2][5], 0)
        self.assertFalse(engine.apply(Action.EAST).performed)
        self.assertEqual(engine.state.turns, 0)
        self.assertTrue(engine.interact("door", "open").performed)
        self.assertIsNot(engine.lighting, light)
        self.assertEqual(engine.lighting.illumination[2][5], 2)
        self.assertEqual(engine.render_cells((4, 2, 1, 1))[0][0].char, "/")
        self.assertTrue(engine.apply(Action.EAST).performed)
        self.assertFalse(engine.interact("door", "close").performed)
        self.assertTrue(engine.apply(Action.WEST).performed)
        self.assertTrue(engine.interact("door", "close").performed)
        self.assertEqual(engine.lighting.illumination[2][5], 0)
        self.assertEqual(engine.render_cells((4, 2, 1, 1))[0][0].char, "+")
        self.assertIs(original, self.store.get("maps", "base:door_test"))

    def test_bars_transmit_light_and_can_be_forced_but_not_bent(self):
        engine = self.setup_map("bars", locked=True, ambient="dark")
        self.assertEqual(engine.lighting.illumination[2][5], 2)
        self.assertFalse(engine.apply(Action.EAST).performed)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (20,) * n):
            self.assertFalse(engine.interact("door", "bend").performed)
            self.assertTrue(engine.interact("door", "force").performed)
        self.assertFalse(self.instance.door.bent)
        self.assertTrue(self.instance.door.opened)
        self.assertEqual(engine.events[-1]["difficulty"], 15)
        self.assertTrue(engine.apply(Action.EAST).performed)

    def test_simple_and_complex_lockpick_turns_and_cancellation(self):
        engine = self.setup_map(locked=True, complex=True)
        tools = self.add_tools(engine)
        with patch.object(
            engine.dice, "roll", side_effect=lambda n, sides: (20,) * n
        ) as rolls:
            self.assertTrue(engine.interact("door", "pick").performed)
            self.assertEqual(engine.state.turns, 0)
            for _ in range(3):
                engine.advance_lockpick()
            self.assertEqual(engine.lockpick_attempt.progress, 3)
            self.assertEqual(engine.state.turns, 3)
            self.assertEqual(engine.state.clock.elapsed_minutes, 483)
            rolls.assert_not_called()
            self.assertFalse(engine.apply(Action.WEST).performed)
            engine.cancel_lockpick()
            self.assertEqual(tools.durability, 10)
            self.assertTrue(self.instance.door.locked)
            engine.interact("door", "pick")
            for _ in range(10):
                engine.advance_lockpick()
            self.assertIsNone(engine.lockpick_attempt)
            self.assertFalse(self.instance.door.locked)
            self.assertEqual(engine.state.turns, 13)
            self.assertEqual(rolls.call_count, 1)
            self.assertEqual(tools.durability, 10)
        engine = self.setup_map(locked=True)
        self.add_tools(engine)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (20,) * n):
            engine.interact("door", "pick")
        self.assertEqual(engine.state.turns, 1)
        self.assertFalse(self.instance.door.locked)
        self.assertEqual(engine.render_cells((4, 2, 1, 1))[0][0].char, "+")

    def test_crowbar_requires_a_hand_and_does_not_wear_or_aid_locks(self):
        engine = self.setup_map("adamantine", locked=True)
        hero = engine.state.hero
        hero.inventory.clear()
        crowbar = Equipment.create(engine.catalog.equipment["crowbar"])
        hero.inventory.append(crowbar)
        tools = self.add_tools(engine, advantage=False)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (1,) * n):
            engine.interact("door", "force")
            self.assertFalse(engine.events[-1]["advantage"])
            self.assertIsNone(crowbar.durability)
            engine.manage_equipment(crowbar, True)
            engine.interact("door", "pick")
            self.assertFalse(engine.events[-1]["advantage"])
            self.assertIsNone(crowbar.durability)
            self.assertEqual(tools.durability, 9)
            for _ in range(5):
                engine.interact("door", "force")
                self.assertTrue(engine.events[-1]["advantage"])
                self.assertIsNone(crowbar.durability)
            engine.interact("door", "force")
            self.assertTrue(engine.events[-1]["advantage"])

    def test_damage_material_rules(self):
        for material in MATERIALS:
            door = Door.from_spec(DoorSpec(material=material))
            amount = door.take_damage(3, "physical")
            self.assertEqual(
                amount, 0 if material in ("steel", "stone", "adamantine") else 3
            )
        stone = Door.from_spec(DoorSpec(material="stone"))
        self.assertEqual(stone.take_damage(4, "bludgeoning"), 4)
        self.assertEqual(stone.take_damage(4, "pickaxe"), 4)
        self.assertFalse(stone.ignite())
        steel = Door.from_spec(DoorSpec(material="steel"))
        self.assertEqual(steel.apply_acid(4), 8)
        self.assertEqual(steel.tick(2), 4)
        adamantine = Door.from_spec(DoorSpec(material="adamantine", locked=True))
        for kind in ("physical", "fire", "acid", "pickaxe", "bludgeoning"):
            self.assertEqual(adamantine.take_damage(999, kind), 0)
        self.assertTrue(adamantine.daylight())
        self.assertEqual(adamantine.material, "stone")
        self.assertFalse(adamantine.locked)
        self.assertIsNone(adamantine.force_dc)

    def test_ignition_acid_throw_and_daylight_resources(self):
        engine = self.setup_map()
        hero = engine.state.hero
        hero.inventory.clear()
        torch = Equipment.create(engine.catalog.equipment["torch"])
        hero.inventory.append(torch)
        engine.manage_equipment(torch, True)
        self.assertTrue(engine.interact("door", "ignite").performed)
        self.assertEqual(self.instance.door.hp, 10)
        lay_bedroll(engine)
        engine.apply(Action.REST)
        self.assertTrue(self.instance.door.destroyed)
        self.assertTrue(engine.state.walkable(Position(4, 2)))
        engine = self.setup_map("steel", locked=True)
        acid = Equipment.create(engine.catalog.equipment["acid_flask"])
        engine.state.hero.inventory.append(acid)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (6,) * n):
            self.assertTrue(
                engine.place_item(acid, Position(4, 2), throwing=True).performed
            )
        self.assertNotIn(acid, engine.state.hero.inventory)
        self.assertEqual(self.instance.door.hp, 14)
        lay_bedroll(engine)
        engine.apply(Action.REST)
        self.assertTrue(self.instance.door.destroyed)
        self.setup_map("adamantine", locked=True)
        engine = SessionFactory(self.store).session(
            "base:door_test", character_class="base:wizard"
        )
        self.assertFalse(engine.interact("door", "daylight").performed)
        hero = engine.state.hero
        hero.class_spells += (engine.catalog.spells["daylight"],)
        hero.spell_slots[3] = hero.max_spell_slots[3] = 1
        self.assertTrue(engine.interact("door", "daylight").performed)
        self.assertEqual(hero.spell_slots[3], 0)
        self.assertEqual(engine.state.level.doors[0].door.material, "stone")

    def test_save_load_progress_state_and_session_independence(self):
        engine = self.setup_map(locked=True, complex=True)
        self.add_tools(engine)
        engine.interact("door", "pick")
        for _ in range(3):
            engine.advance_lockpick()
        with tempfile.TemporaryDirectory() as directory:
            saves = SaveRepository(Path(directory) / "save.json")
            saves.save(engine)
            restored = saves.load(store=self.store)
        self.assertEqual(restored.lockpick_attempt.progress, 3)
        for _ in range(7):
            engine.advance_lockpick()
            restored.advance_lockpick()
        self.assertEqual(
            engine.state.level.doors[0].door, restored.state.level.doors[0].door
        )
        fresh = SessionFactory(self.store).session("base:door_test")
        self.assertTrue(fresh.state.level.doors[0].door.locked)
        self.assertFalse(fresh.state.level.doors[0].door.opened)

    def test_legacy_tiles_gain_independent_doors_and_bad_references_fail(self):
        engine = self.setup_map(legacy=True)
        self.assertFalse(engine.apply(Action.EAST).performed)
        self.assertTrue(engine.interact("tile_doors_4_2", "open").performed)
        self.assertTrue(engine.apply(Action.EAST).performed)
        raw = self.store.get("maps", "base:door_test").model_dump(mode="json")
        raw["doors"] = [dict(id="wrong", ref="base:floor", x=4, y=2)]
        candidate = dict(self.store.documents)
        candidate["maps", "base:door_test"] = MapDocument.model_validate(raw)
        with self.assertRaises(ContentError):
            self.store.validate_references(candidate, self.store.manifests)

    def test_saves_restore_burning_corrosion_and_transformed_material(self):
        for material in ("wood", "steel", "adamantine"):
            with self.subTest(material=material):
                engine = self.setup_map(material, locked=True)
                door = self.instance.door
                if material == "wood":
                    door.ignite()
                    door.take_damage(4, "fire")
                elif material == "steel":
                    door.apply_acid(4)
                else:
                    door.daylight()
                    door.force_open()
                with tempfile.TemporaryDirectory() as directory:
                    saves = SaveRepository(Path(directory) / "save.json")
                    saves.save(engine)
                    restored = saves.load(store=self.store)
                self.assertEqual(door, restored.state.level.doors[0].door)

    def test_legacy_saves_with_static_door_wall_are_migrated_in_memory(self):
        import json

        engine = self.setup_map(legacy=True)
        with tempfile.TemporaryDirectory() as directory:
            saves = SaveRepository(Path(directory) / "save.json")
            saves.save(engine)
            raw = json.loads(saves.path.read_text(encoding="utf-8"))
            del raw["levels"][0]["doors"]
            row = list(raw["levels"][0]["rows"][2])
            row[4] = "#"
            raw["levels"][0]["rows"][2] = "".join(row)
            saves.path.write_text(json.dumps(raw), encoding="utf-8")
            restored = saves.load(store=self.store)
        self.assertFalse(restored.state.walkable(Position(4, 2)))
        self.assertTrue(restored.interact("tile_doors_4_2", "open").performed)
        self.assertTrue(restored.state.walkable(Position(4, 2)))

    def test_tui_progress_panel_and_cancel(self):
        self.setup_map(locked=True, complex=True)
        controller = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:door_test",
            test_map=True,
        )
        self.add_tools(controller.engine)
        controller.handle("enter")
        self.assertEqual(controller.view, View.INTERACTION)
        controller.handle("1")
        self.assertIsNotNone(controller.engine.lockpick_attempt)
        text = "\n".join(render(controller, 100, 30))
        self.assertIn("[ ]" * 10, text)
        for _ in range(3):
            controller.handle(" ")
        self.assertIn("[#]" * 3, "\n".join(render(controller, 100, 30)))
        controller.handle("backspace")
        self.assertIsNone(controller.engine.lockpick_attempt)
        self.assertEqual(controller.engine.state.turns, 3)

    def test_lockpicking_requires_working_tools_without_spending_time_or_rng(self):
        for complex in (False, True):
            with self.subTest(complex=complex):
                engine = self.setup_map(locked=True, complex=complex)
                with patch.object(engine.dice, "roll") as rolls:
                    result = engine.interact("door", "pick")
                    self.assertFalse(result.performed)
                    self.assertIn("инструменты", result.message)
                    self.assertEqual(result.minutes, 0)
                    tools = self.add_tools(engine)
                    engine.state.hero.inventory.remove(tools)
                    self.assertFalse(engine.interact("door", "pick").performed)
                    self.assertIsNone(engine.lockpick_attempt)
                    self.assertEqual(engine.state.turns, 0)
                    rolls.assert_not_called()

    def test_failed_lockpicking_wears_and_breaks_tools(self):
        engine = self.setup_map(locked=True)
        tools = self.add_tools(engine)
        with patch.object(
            engine.dice, "roll", side_effect=lambda n, sides: (1,) * n
        ) as rolls:
            for attempt in range(10):
                result = engine.interact("door", "pick")
                self.assertTrue(result.performed)
                self.assertTrue(self.instance.door.locked)
                self.assertEqual(tools.durability, 9 - attempt)
            self.assertIn("сломаны", result.message)
            self.assertFalse(engine.interact("door", "pick").performed)
            self.assertEqual(rolls.call_count, 10)
            self.assertEqual(engine.state.turns, 10)

    def test_lockpicking_is_one_d20_even_with_an_advantage_tool(self):
        for complex in (False, True):
            with self.subTest(complex=complex):
                engine = self.setup_map(locked=True, complex=complex)
                tools = self.add_tools(engine)
                self.assertIsNone(tools.check_support("lockpicking"))
                # Old saves and custom templates must not reintroduce advantage.
                tools.definition = replace(
                    tools.definition, check_aids=(CheckAid("lockpicking", "advantage"),)
                )
                with patch.object(engine.dice, "roll", return_value=(1,)) as rolls:
                    engine.interact("door", "pick")
                    if complex:
                        for _ in range(10):
                            engine.advance_lockpick()
                    rolls.assert_called_once_with(1, 20)
                self.assertFalse(engine.events[-1]["advantage"])
                self.assertEqual(tools.durability, 9)

    def test_complex_lock_wears_once_at_final_failure_and_rechecks_presence(self):
        engine = self.setup_map(locked=True, complex=True)
        tools = self.add_tools(engine)
        with patch.object(
            engine.dice, "roll", side_effect=lambda n, sides: (1,) * n
        ) as rolls:
            engine.interact("door", "pick")
            for _ in range(9):
                engine.advance_lockpick()
                self.assertEqual(tools.durability, 10)
            rolls.assert_not_called()
            engine.advance_lockpick()
            self.assertEqual(tools.durability, 9)
            self.assertEqual(rolls.call_count, 1)
            engine.interact("door", "pick")
            engine.state.hero.inventory.remove(tools)
            self.assertFalse(engine.advance_lockpick().performed)
            self.assertEqual(engine.state.turns, 10)
            self.assertIsNone(engine.lockpick_attempt)
            self.assertEqual(tools.durability, 9)

    def test_tools_save_preserves_wear_and_legacy_unbreakable_tools_get_durability(
        self,
    ):
        engine = self.setup_map(locked=True)
        tools = self.add_tools(engine)
        with patch.object(engine.dice, "roll", side_effect=lambda n, sides: (1,) * n):
            engine.interact("door", "pick")
        with tempfile.TemporaryDirectory() as directory:
            saves = SaveRepository(Path(directory) / "save.json")
            saves.save(engine)
            restored = saves.load(store=self.store)
        restored_tools = next(
            i for i in restored.state.hero.inventory if i.id == tools.id
        )
        self.assertEqual(restored_tools.durability, 9)
        self.assertEqual(restored_tools.instance_id, tools.instance_id)
        for value in (None, 10, 7, 0):
            record = ItemRecord(
                definition="thieves_tools",
                instance_id=tools.instance_id,
                durability=value,
                equipped=False,
            )
            restored = restore_item(record, engine.catalog)
            self.assertEqual(restored.durability, 10 if value is None else value)
            self.assertEqual(restored.usable, value != 0)
        record.durability = 11
        with self.assertRaises(ValueError):
            restore_item(record, engine.catalog)


if __name__ == "__main__":
    unittest.main()
