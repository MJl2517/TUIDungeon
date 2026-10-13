"""Acceptance scenarios for recipe knowledge and mutable surroundings."""

from copy import copy
from pathlib import Path
from collections import Counter
import tempfile
import unittest
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.world.maps import Position
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.tui import Controller, View, render


class EnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw.update(ambient_light="bright", lights=[])
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.append(
            Equipment.create(self.e.catalog.equipment["carpenter_tools"])
        )

    def near(self, identifier):
        o = self.e.world_object(identifier)
        self.e.state.position = Position(o.placement.x - 1, o.placement.y)
        return o

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            saves = SaveRepository(Path(folder) / "save.json")
            saves.save(self.e)
            self.e = saves.load(store=self.store)
        return self.e

    def test_read_workshop_proficiency_and_journal(self):
        e = self.e
        self.assertNotIn("base:craft_workshop_torch", e.state.hero.known_recipes)
        self.assertEqual(len(e.craft_list()), len(e.state.hero.known_recipes))
        self.assertFalse(e.start_craft("base:craft_workshop_torch").performed)
        e.state.position = Position(3, 3)
        self.assertTrue(e.interact("manual", "read_note").performed)
        self.assertIn("base:craft_workshop_torch", e.state.hero.known_recipes)
        self.assertEqual(len(e.read_notes), 1)
        e.interact("manual", "read_note")
        self.assertEqual(e.state.turns, 0)
        self.reload()
        self.assertIn("base:craft_workshop_torch", self.e.state.hero.known_recipes)
        self.e.state.position = Position(5, 3)
        self.assertTrue(self.e.interact("workshop", "study").performed)
        expected = sorted(
            ref
            for ref, r in self.e.catalog.recipes.items()
            if "carpenter_tools" in r.learn_on_proficiency
            and ref not in self.e.state.hero.known_recipes
        )
        self.assertEqual(
            self.e.state.hero.learn_tool_proficiency("carpenter_tools"), expected
        )
        self.assertEqual(
            self.e.state.hero.learn_tool_proficiency("carpenter_tools"), []
        )
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.handle("j")
        c.handle("3")
        self.assertEqual(c.view, View.CRAFT)
        render(c, 80, 24)
        c.handle("escape")
        self.assertEqual(c.view, View.NOTEBOOK)

    def test_dismantle_pause_load_floor_and_single_loot(self):
        e = self.e
        target = self.near("lab_table")
        p = Position(target.placement.x, target.placement.y)
        floor = e.state.level.definition.tiles[p.y][p.x]
        self.assertFalse(e.state.walkable(p))
        self.assertTrue(e.start_dismantle("lab_table").performed)
        self.assertEqual(e.state.turns, 0)
        self.assertTrue(e.advance_craft().performed)
        self.assertEqual(e.state.turns, 1)
        self.assertTrue(e.pause_craft().performed)
        e = self.reload()
        self.assertEqual(e.world_object("lab_table").state.progress, 1)
        self.assertTrue(e.start_dismantle("lab_table").performed)
        e.advance_craft()
        e.advance_craft()
        self.assertIsNone(e.world_object("lab_table"))
        self.assertTrue(e.state.walkable(p))
        self.assertEqual(e.state.level.definition.tiles[p.y][p.x], floor)
        self.assertEqual(
            Counter(i.id for q, i in e.state.items if (q.x, q.y) == (p.x, p.y)),
            {"wood": 3, "furniture_hardware": 1},
        )
        self.assertFalse(e.start_dismantle("lab_table").performed)
        self.reload()
        self.assertIsNone(self.e.world_object("lab_table"))
        self.assertTrue(
            any(
                p.id == "lab_table"
                for p in self.store.get("maps", "dev:crafting_lab").objects
            )
        )

    def test_container_lift_move_place_save_and_dismantle(self):
        e = self.e
        target = self.near("lab_crate")
        container = next(
            c for c in e.state.level.containers if c.placement.id == "lab_crate"
        )
        item = Equipment.create(e.catalog.equipment["wood"])
        container.items.append(item)
        self.assertTrue(e.lift_furniture("lab_crate").performed)
        cargo = e.state.hero.inventory[-1]
        self.assertEqual(cargo.weight, target.definition.weight + item.weight)
        self.assertIs(cargo.furniture.items[0], item)
        e = self.reload()
        cargo = e.state.hero.inventory[-1]
        p = Position(e.state.position.x, e.state.position.y + 1)
        self.assertTrue(e.place_furniture(cargo, p).performed)
        c = next(c for c in e.state.level.containers if c.placement.id == "lab_crate")
        self.assertEqual(c.items[0].instance_id, item.instance_id)
        self.assertTrue(e.move_furniture("lab_crate", Position(p.x - 1, p.y)).performed)
        self.assertEqual(c.placement.x, p.x - 1)
        e.state.position = Position(c.placement.x, c.placement.y - 1)
        self.assertTrue(e.start_dismantle("lab_crate").performed)
        for _ in range(3):
            e.advance_craft()
        self.assertTrue(
            any(i.instance_id == item.instance_id for _, i in e.state.items)
        )
        self.reload()

    def test_damage_protection_weight_and_fast_tool(self):
        e = self.e
        target = self.near("lab_table")
        p = Position(target.placement.x, target.placement.y)
        self.assertEqual(e.damage_world_objects(p, 4, "bludgeoning"), 4)
        self.assertEqual(target.state.hp, 16)
        self.assertEqual(e.repair_world_object("lab_table", 2), 2)
        self.assertEqual(e.damage_world_objects(Position(0, 0), 100, "bludgeoning"), 0)
        heavy = Equipment.create(e.catalog.equipment["wood"])
        e.state.hero.inventory.extend(
            Equipment.create(heavy.definition) for _ in range(1000)
        )
        self.assertFalse(e.lift_furniture("lab_table").performed)
        self.assertIsNotNone(e.world_object("lab_table"))
        e.state.hero.inventory.clear()
        crowbar = next(d for d in e.catalog.equipment.values() if "lever" in d.tags)
        e.state.hero.inventory.extend(
            [
                Equipment.create(crowbar),
                Equipment.create(e.catalog.equipment["carpenter_tools"]),
            ]
        )
        self.assertTrue(e.start_dismantle("lab_table").performed)
        self.assertEqual(target.state.total, 1)
        self.assertTrue(e.advance_craft().performed)
        self.assertIsNone(e.world_object("lab_table"))

    def test_native_work_controls_and_darkness(self):
        e = self.e
        self.near("lab_table")
        self.assertTrue(e.interact("lab_table", "dismantle").performed)
        self.assertIsNotNone(e.active_craft)
        c = Controller(
            42,
            store=self.store,
            catalog=e.catalog,
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.engine, c.view = e, View.EXPLORE
        render(c, 80, 24)
        render(c, 160, 50)
        c.handle(" ")
        self.assertEqual(e.world_object("lab_table").state.progress, 1)
        c.handle("escape")
        e.state.level.definition = e.state.level.definition.model_copy(
            update={"ambient_light": "dark"}
        )
        self.assertFalse(e.start_dismantle("lab_table").performed)
        self.assertEqual(e.state.turns, 1)

    def test_old_save_defaults_and_session_isolation(self):
        import json
        from tuidungeon.world.terrain import Terrain

        other = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.near("lab_table")
        self.e.damage_cell(Position(4, 6), 999, "bludgeoning")
        self.assertIsNotNone(other.world_object("lab_table"))
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "old.json")
            repo.save(other)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            saved = raw["levels"][0]
            for key in ("world", "object_states", "discovered_traps", "door_loot"):
                saved.pop(key, None)
            legacy = Terrain.compile(
                other.state.level.store, other.state.level.definition
            )
            saved["rows"] = [
                "".join("." if c else "#" for c in row) for row in legacy.walkability
            ]
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            loaded = repo.load(store=self.store)
            self.assertIsNotNone(loaded.world_object("lab_table"))
            self.assertEqual(loaded.world_object("lab_table").state.hp, 20)

    def test_invalid_destination_and_missing_floor_spend_nothing(self):
        e = self.e
        target = self.near("lab_crate")
        before = e.state.turns
        self.assertFalse(
            e.move_furniture(
                "lab_crate", Position(target.placement.x, target.placement.y)
            ).performed
        )
        self.assertFalse(e.move_furniture("lab_crate", e.state.position).performed)
        self.assertFalse(e.move_furniture("lab_crate", Position(100, 100)).performed)
        raw = e.state.level.definition.model_dump(mode="json")
        raw["tiles"][target.placement.y][target.placement.x] = None
        e.state.level.definition = MapDocument.model_validate(raw)
        self.assertFalse(e.start_dismantle("lab_crate").performed)
        self.assertFalse(e.lift_furniture("lab_crate").performed)
        self.assertEqual(e.state.turns, before)
        self.assertFalse(e.interact("lab_crate", "missing_choice").performed)

    def test_light_geometry_and_surface_follow_runtime_changes(self):
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw["ambient_light"] = "dark"
        raw["objects"][0]["overrides"] = {
            "brush": {"light": {"radius": 4, "bright_radius": 2}}
        }
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.e = e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        target = self.near("lab_table")
        p = Position(target.placement.x, target.placement.y)
        self.assertGreater(e.lighting.level_at(e.state.position), 0)
        e.damage_cell(p, 999, "bludgeoning")
        self.assertEqual(e.lighting.level_at(e.state.position), 0)
        self.assertTrue(e.state.walkable(p))
        wall = Position(7, 6)
        self.assertTrue(e.state.level.terrain.blocks_sight[wall.y][wall.x])
        e.damage_cell(wall, 999, "bludgeoning")
        self.assertFalse(e.state.level.terrain.blocks_sight[wall.y][wall.x])
        e.replace_surface(p, "base:floor")
        self.reload()
        self.assertEqual(self.e.state.level.definition.tiles[p.y][p.x], "base:floor")

    def test_professional_recipe_grants_are_atomic_and_effect_compatible(self):
        from tuidungeon.domain.mechanics import mechanics

        hero = self.e.state.hero
        with self.assertRaises(ValueError):
            hero.learn_recipes(["base:craft_workshop_torch", "base:missing_recipe"])
        self.assertNotIn("base:craft_workshop_torch", hero.known_recipes)
        self.assertEqual(
            hero.learn_tool_proficiency("carpenter_tools"),
            sorted(
                ref
                for ref, r in self.e.catalog.recipes.items()
                if "carpenter_tools" in r.learn_on_proficiency
            ),
        )
        params = mechanics.entries["learn_recipe"].parameters.model_validate(
            {"learn_recipes": ["base:craft_workshop_torch"]}
        )
        outcome = mechanics.entries["learn_recipe"].handler(params, hero, self.e.dice)
        self.assertEqual(outcome.amount, 0)
        self.reload()
        self.assertIn("carpenter_tools", self.e.state.hero.tool_proficiencies)

    def test_discovery_dismantles_hidden_traps_without_triggering(self):
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw["traps"][0]["overrides"] = {"hidden": True, "difficulty": 1}
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.e = e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        e.state.position = Position(6, 5)
        self.assertIsNone(e.world_object("lab_trap"))
        self.assertFalse(e.start_dismantle("lab_trap").performed)
        self.assertTrue(e.discover_traps().performed)
        self.assertTrue(e.state.level.traps[0].discovered)
        self.assertFalse(e.state.level.traps[0].triggered)
        e = self.reload()
        self.assertTrue(e.state.level.traps[0].discovered)
        self.assertTrue(e.start_dismantle("lab_trap").performed)
        hp = e.state.hero.hp
        for _ in range(3):
            e.advance_craft()
        self.assertEqual(e.state.hero.hp, hp)
        self.assertNotIn("lab_trap", [t.placement.id for t in e.state.level.traps])
        self.reload()
        self.assertNotIn("lab_trap", [t.placement.id for t in self.e.state.level.traps])

    def test_door_remains_once_and_current_geometry_light(self):
        self.e = e = SessionFactory(self.store).session("base:crypt", seed=42)
        door = e.state.level.doors[0]
        p = Position(door.placement.x, door.placement.y)
        self.assertFalse(e.start_dismantle(door.placement.id).performed)
        floor = e.state.level.terrain.tiles[p.y][p.x]
        e.damage_cell(p, 999, "bludgeoning")
        self.assertTrue(door.door.destroyed)
        ids = {i.instance_id for q, i in e.state.items if (q.x, q.y) == (p.x, p.y)}
        self.assertTrue(ids)
        e.damage_cell(p, 999, "bludgeoning")
        e.collect_door_remains()
        self.assertEqual(
            ids, {i.instance_id for q, i in e.state.items if (q.x, q.y) == (p.x, p.y)}
        )
        self.assertEqual(e.state.level.terrain.tiles[p.y][p.x], floor)
        e = self.reload()
        e.collect_door_remains()
        self.assertEqual(
            ids, {i.instance_id for q, i in e.state.items if (q.x, q.y) == (p.x, p.y)}
        )

    def test_cargo_moves_between_maps_without_regenerating_source(self):
        e = self.e
        self.near("lab_table")
        self.assertTrue(e.start_dismantle("lab_table").performed)
        e.advance_craft()
        e.pause_craft()
        self.assertTrue(e.lift_furniture("lab_table").performed)
        cargo = e.state.hero.inventory[-1]
        identity = cargo.furniture.state.instance_id
        source = e.state
        destination = SessionFactory(self.store).state("dev:reading_room", source.hero)
        destination.level.definition = destination.level.definition.model_copy(
            update={"ambient_light": "bright"}
        )
        # Authored ambient light must remain stable across a saved level.
        destination.level.authored_definition = self.store.get(
            "maps", "dev:reading_room"
        )
        destination.level.definition = destination.level.authored_definition
        e.levels[destination.level.ref] = destination
        e.state = destination
        destination.position = Position(3, 3)
        self.assertTrue(e.place_furniture(cargo, Position(3, 4)).performed)
        placed = e.world_object("lab_table")
        self.assertEqual(placed.state.instance_id, identity)
        self.assertEqual(placed.state.progress, 1)
        self.assertFalse(
            any(p.id == "lab_table" for p in source.level.definition.objects)
        )
        self.reload()
        self.assertEqual(self.e.world_object("lab_table").state.instance_id, identity)
        self.assertFalse(
            any(
                p.id == "lab_table"
                for p in self.e.levels["dev:crafting_lab"].level.definition.objects
            )
        )


if __name__ == "__main__":
    unittest.main()
