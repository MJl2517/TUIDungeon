"""Regression scenarios for immutable content, cached frames and world indexes."""

from copy import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.benchmark_engine import synthetic_map
from scripts.probe_engine_contracts import probe
from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import MapDocument, EquipmentDocument
from tuidungeon.domain.mechanics import mechanics, Parameters
from tuidungeon.domain.effects import EffectOutcome
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.tui import Controller, View, render, draw_colors
from tuidungeon.tooling.server import template
from tuidungeon.world.lighting import LightField, line_of_sight
from tuidungeon.world.maps import Position
from tuidungeon.world.state import ItemPlacement


class RuntimeOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.store.documents["maps", "base:benchmark"] = synthetic_map(12)
        self.factory = SessionFactory(self.store)
        self.engine = self.factory.session("base:benchmark", seed=42)

    def test_audit_contracts_are_fixed(self):
        checks = probe()
        self.assertTrue(all(c["ok"] for c in checks), checks)

    def test_new_map_template_does_not_inherit_out_of_bounds_lights(self):
        raw = synthetic_map(32).model_dump()
        raw["lights"] = [{"id": "old_light", "x": 30, "y": 30}]
        self.store.documents["maps", "base:crypt"] = MapDocument.model_validate(raw)
        new = MapDocument.model_validate(template(self.store, "maps"))
        self.assertEqual(new.roof, [[False] * new.width for _ in range(new.height)])
        self.assertEqual((new.width, new.height), (20, 12))
        self.assertEqual(new.lights, [])
        self.assertEqual(new.ambient_light, "bright")

    def test_content_snapshot_is_pinned_and_nested_containers_are_read_only(self):
        old = self.store.snapshot()
        doc = old.get("maps", "base:benchmark")
        with self.assertRaises(TypeError):
            doc.walkability[0][0] = False
        with self.assertRaises(TypeError):
            doc.lights.append(None)
        with self.assertRaises(TypeError):
            old.documents["maps", "base:benchmark"] = doc
        self.store.documents["maps", "base:benchmark"] = doc.model_copy(
            update={"name": "New revision"}
        )
        new = self.store.snapshot()
        self.assertIsNot(new, old)
        self.assertEqual(old.get("maps", "base:benchmark").name, "Synthetic benchmark")
        self.assertEqual(new.get("maps", "base:benchmark").name, "New revision")
        self.assertIs(old.runtime_catalog(), old.runtime_catalog())
        with self.assertRaises(TypeError):
            old.runtime_catalog().equipment.clear()
        with self.assertRaises(TypeError):
            old.runtime_catalog().equipment = {}

    def test_plugin_parameters_preserve_text_and_execute_through_same_registry(self):
        class Marker(Parameters):
            target: str

        def handler(params, target, dice):
            self.assertEqual(params.target, "base:secret")
            target.gold += 1
            return EffectOutcome("marker_text", amount=1)

        mechanics.register("marker_text", Marker, handler)
        self.addCleanup(mechanics.entries.pop, "marker_text")
        raw = self.store.get("equipment", "base:healing_potion").model_dump()
        raw.update(
            id="marker_item",
            name="Marker",
            properties=[{"kind": "marker_text", "params": {"target": "base:secret"}}],
        )
        self.store.documents["equipment", "base:marker_item"] = (
            EquipmentDocument.model_validate(raw)
        )
        self.store.validate_references(self.store.documents, self.store.manifests)
        factory = SessionFactory(self.store)
        definition = factory.catalog.equipment["marker_item"]
        with self.assertRaises(TypeError):
            definition.properties[0].params["target"] = "changed"
        engine = factory.session("base:benchmark")
        item = Equipment.create(definition)
        engine.state.hero.inventory.append(item)
        self.assertTrue(engine.use_item(item).performed)
        self.assertEqual((engine.state.hero.gold, item.charges), (1, 0))

    def test_compiled_terrain_and_static_illumination_are_reused_without_shared_state(
        self,
    ):
        other = self.factory.session("base:benchmark")
        self.assertIs(self.engine.state.level.terrain, other.state.level.terrain)
        original = self.engine.lighting
        self.engine.apply(Action.EAST)
        moved = self.engine.lighting
        self.assertIs(moved.illumination, original.illumination)
        self.assertIsNot(moved.cells, original.cells)
        self.assertEqual(other.state.position, Position(6, 6))
        self.assertEqual(self.engine.state.position, Position(7, 6))

    def test_terminal_reuses_light_calculation_across_render_passes_and_wait(self):
        engine = self.factory.session("base:benchmark")
        controller = Controller(catalog=engine.catalog)
        controller.engine, controller.view = engine, View.EXPLORE
        colors = SimpleNamespace(
            curses=SimpleNamespace(A_DIM=0, error=RuntimeError),
            attribute=lambda *args: 0,
        )
        with patch.object(LightField, "calculate", wraps=LightField.calculate) as calls:
            engine.render_cells()
            engine.render_cells()
            render(controller, 80, 24)
            draw_colors(Mock(), controller, 80, 24, colors)
            self.assertEqual(calls.call_count, 1)
            engine.apply(Action.WAIT)
            engine.render_cells()
            self.assertEqual(calls.call_count, 1)
            engine.apply(Action.EAST)
            engine.render_cells()
            self.assertEqual(calls.call_count, 2)

    def test_expiring_light_updates_cached_visibility_and_removes_torch(self):
        doc = self.engine.state.level.definition
        self.engine.state.level.definition = doc.model_copy(
            update={"ambient_light": "dark"}
        )
        hero = self.engine.state.hero
        hero.unequip(next(i for i in hero.inventory if i.id == "shield"))
        torch = next(i for i in hero.inventory if i.id == "torch")
        torch.fuel_minutes = 2
        self.engine.manage_equipment(torch, True)
        position = Position(9, 6)
        self.assertEqual(self.engine.lighting.at(position), 2)
        self.engine.apply(Action.WAIT)
        self.assertEqual(self.engine.lighting.at(position), 0)
        self.assertNotIn(torch, hero.inventory)
        self.assertEqual(self.engine.render_cells()[6][9].char, " ")

    def test_new_geometry_invalidates_light_and_viewport_matches_full_frame(self):
        self.assertEqual(self.engine.lighting.at(Position(10, 6)), 2)
        raw = self.engine.state.level.definition.model_dump()
        for row in raw["blocks_sight"]:
            row[8] = True
        self.engine.state.level.definition = MapDocument.model_validate(raw)
        self.assertEqual(self.engine.lighting.at(Position(10, 6)), 0)
        full = self.engine.render_cells()
        region = self.engine.render_cells((4, 3, 7, 6))
        self.assertEqual(region, tuple(row[4:11] for row in full[3:9]))
        self.assertIs(region, self.engine.render_cells((4, 3, 7, 6)))
        self.assertTrue(self.engine.state.dungeon.walkable(Position(8, 6)))

    def test_open_map_fast_path_matches_rays_without_limiting_view(self):
        state = self.engine.state
        field = self.engine.lighting
        blocks = state.level.terrain.blocks_sight
        for y in range(12):
            for x in range(12):
                self.assertTrue(line_of_sight(state.position, Position(x, y), blocks))
                self.assertEqual(field.at(Position(x, y)), 2)

    def test_item_index_handles_stacks_drop_pickup_and_collection_replacement(self):
        state = self.engine.state
        definition = self.factory.catalog.equipment["healing_potion"]
        items = [Equipment.create(definition) for _ in range(2)]
        p = state.position
        state.items.extend(
            (ItemPlacement(f"potion_{n}", "base:healing_potion", p.x, p.y), item)
            for n, item in enumerate(items)
        )
        self.assertEqual(len(state.item_index.at(p.x, p.y)), 2)
        self.engine.pickup_item()
        self.assertIs(state.hero.inventory[-1], items[0])
        self.assertEqual(len(state.item_index.at(p.x, p.y)), 1)
        state.level.items = []  # Loading replaces collections too.
        self.assertEqual(state.item_index.at(p.x, p.y), ())
        self.engine.place_item(items[0], p)
        self.assertIs(state.item_index.at(p.x, p.y)[0][1], items[0])

    def test_actor_movement_updates_occupancy_and_frame(self):
        state = self.engine.state
        placement = self.engine.add_monster("base:goblin", Position(7, 6))
        self.assertEqual(
            self.engine.render_cells()[6][7].char,
            self.store.get("monsters", "base:goblin").glyph,
        )
        self.assertFalse(self.engine.apply(Action.EAST).performed)
        updated = state.move_monster(placement, Position(8, 6))
        self.assertEqual(state.actor_index.at(7, 6), ())
        self.assertIs(state.actor_index.at(8, 6)[0], updated)
        self.assertTrue(self.engine.apply(Action.EAST).performed)
        with self.assertRaises(ValueError):
            state.move_monster(updated, state.position)

    def test_nonlight_items_are_not_processed_by_fuel_updates(self):
        state = self.engine.state
        definition = self.factory.catalog.equipment["healing_potion"]
        state.items.extend(
            (
                ItemPlacement(f"potion_{n}", "base:healing_potion", 0, 0),
                Equipment.create(definition),
            )
            for n in range(1000)
        )
        with patch.object(Equipment, "burn", autospec=True) as burn:
            self.engine.apply(Action.WAIT)
            burn.assert_not_called()
        self.assertEqual(len(state.items), 1000)


class IncrementalContentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "base/tiles").mkdir(parents=True)
        (self.root / "base/manifest.json").write_text(
            json.dumps({"id": "base", "name": "Base"})
        )
        self.path = self.root / "base/tiles/floor.json"
        self.write("Floor")
        self.store = PackStore(self.root)

    def write(self, name):
        self.path.write_text(json.dumps({"id": "floor", "name": name, "glyph": "."}))

    def test_unchanged_reload_does_not_read_json_and_external_edits_are_detected(self):
        original = self.store.get("tiles", "base:floor")
        snapshot = self.store.snapshot()
        with patch.object(
            Path, "read_bytes", side_effect=AssertionError("Unexpected read")
        ):
            self.store.reload()
        self.assertIs(self.store.get("tiles", "base:floor"), original)
        self.assertIs(self.store.snapshot(), snapshot)
        self.write("Changed")
        self.store.reload()
        self.assertEqual(self.store.get("tiles", "base:floor").name, "Changed")
        self.assertEqual(snapshot.get("tiles", "base:floor").name, "Floor")
        self.path.write_text("{invalid")
        with self.assertRaises(ContentError):
            self.store.reload()
        self.assertEqual(self.store.get("tiles", "base:floor").name, "Changed")

    def test_reference_index_tracks_added_and_deleted_documents(self):
        path = self.path.with_name("loot.json")
        path.write_text(
            json.dumps(
                {"id": "loot", "name": "Loot", "brush": {"underlay": "base:floor"}}
            )
        )
        self.store.reload()
        usages = self.store.usages("tiles", "base:floor")
        self.assertEqual(len(usages), 1)
        self.assertEqual(usages[0]["field"], "brush.underlay")
        usages[0]["ref"] = "wrong"  # Caller cannot modify the cached index.
        self.assertEqual(
            self.store.usages("tiles", "base:floor")[0]["ref"], "base:loot"
        )
        path.unlink()
        self.store.reload()
        self.assertEqual(self.store.usages("tiles", "base:floor"), [])


if __name__ == "__main__":
    unittest.main()
