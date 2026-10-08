"""Brush contracts and the actual mechanics used by browser-authored maps."""

from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from pydantic import ValidationError
from tuidungeon.content.packs import DEFAULT_PACKS, ContentError, PackStore
from tuidungeon.content.schemas import TileDocument
from tuidungeon.tooling.sessions import TestSession
from tuidungeon.tooling.server import template


class BrushContractTests(unittest.TestCase):
    def test_new_tile_template_does_not_inherit_the_first_catalog_hazard(self):
        raw = template(PackStore(), "tiles")
        tile = TileDocument.model_validate(raw)
        self.assertTrue(tile.walkable)
        self.assertFalse(tile.blocks_sight)
        self.assertFalse(any(tile.brush.model_dump().values()))

    def test_old_tiles_work_and_brush_parameters_are_strict(self):
        self.assertFalse(
            any(TileDocument(id="old", name="Старый").brush.model_dump().values())
        )
        for brush in (
            {"unknown": 1},
            {"light": {"radius": 2, "bright_radius": 3}},
            {"trap": "spikes"},
        ):
            with self.subTest(brush=brush), self.assertRaises(ValidationError):
                TileDocument(id="bad", name="Неверный", brush=brush)
        with self.assertRaises(ValidationError):
            TileDocument(
                id="bad",
                name="Неверный",
                walkable=False,
                brush={"interaction": "base:chest"},
            )

    def test_brush_references_are_checked_and_count_as_usages(self):
        store = PackStore()
        self.assertTrue(
            any(
                u["category"] == "tiles"
                for u in store.usages("traps", "base:terrain_pressure_plate")
            )
        )
        candidate = dict(store.documents)
        candidate[("tiles", "base:missing_brush")] = TileDocument(
            id="missing_brush", name="Нет объекта", brush={"item": "base:missing"}
        )
        with self.assertRaisesRegex(ContentError, "неизвестная ссылка"):
            store.validate_references(candidate, store.manifests)


class FunctionalBrushTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "packs"
        shutil.copytree(DEFAULT_PACKS, self.root)
        self.store = PackStore(self.root)
        raw = deepcopy(self.store.get("maps", "base:dungeon").model_dump(mode="json"))
        raw.update(
            id="brush_test",
            name="Кисти",
            width=10,
            height=5,
            ambient_light="bright",
            tiles=[["base:floor"] * 10 for _ in range(5)],
            walkability=[[True] * 10 for _ in range(5)],
            blocks_sight=[[False] * 10 for _ in range(5)],
            spawn={"x": 1, "y": 1},
            decorations=[],
            traps=[],
            points_of_interest=[],
            monsters=[],
            equipment=[],
            transitions=[],
            lights=[],
        )
        for x, ref in [
            (2, "pressure_plate"),
            (3, "decor_dagger"),
            (4, "chest"),
            (5, "portal"),
            (7, "torch_wall"),
        ]:
            tile = self.store.get("tiles", "base:" + ref)
            raw["tiles"][1][x] = "base:" + ref
            raw["walkability"][1][x] = tile.walkable
            raw["blocks_sight"][1][x] = tile.blocks_sight
            for key, field in [
                ("traps", "trap"),
                ("equipment", "item"),
                ("points_of_interest", "interaction"),
            ]:
                reference = getattr(tile.brush, field)
                if reference:
                    raw[key].append(
                        {"id": f"tile_{key}_{x}_1", "ref": reference, "x": x, "y": 1}
                    )
            if tile.brush.light:
                raw["lights"].append(
                    {
                        "id": f"tile_lights_{x}_1",
                        "x": x,
                        "y": 1,
                        "enabled": True,
                        **tile.brush.light.model_dump(),
                    }
                )
            if tile.brush.transition:
                raw["transitions"].append(
                    {
                        "id": f"tile_transitions_{x}_1",
                        "x": x,
                        "y": 1,
                        "target": "base:dungeon",
                    }
                )
        self.store.save("maps", "base:brush_test", raw, None)
        self.options = {"map_ref": "base:brush_test", "seed": 99}

    def test_drawn_recipe_objects_trigger_interact_pickup_and_transition(self):
        session = TestSession(self.store, self.options)
        snapshot = session.command("d")
        self.assertTrue(snapshot["traps"][0]["triggered"])
        self.assertEqual(snapshot["events"][0]["kind"], "trap")
        session.command("d")
        before = len(session.snapshot()["hero"]["inventory"])
        snapshot = session.command("pickup")
        self.assertEqual(len(snapshot["hero"]["inventory"]), before + 1)
        self.assertEqual(snapshot["ground"], [])
        point = snapshot["nearby"][0]
        snapshot = session.command("interact", point["id"], point["choices"][0]["id"])
        self.assertGreater(snapshot["hero"]["gold"], 0)
        self.assertTrue(snapshot["points"][0]["completed"])
        session.command("d")
        self.assertEqual(session.command("d")["map"], "base:dungeon")

    def test_reset_and_second_session_restore_resources_and_placement_state(self):
        session = TestSession(self.store, self.options)
        original = session.snapshot()
        session.command("d")
        session.command("d")
        session.command("pickup")
        session.reset()
        reset = session.snapshot()
        self.assertEqual(reset["traps"], original["traps"])
        self.assertEqual(len(reset["ground"]), 1)
        second = TestSession(self.store, self.options)
        self.assertNotEqual(
            session.engine.state.level.traps[0].instance_id,
            second.engine.state.level.traps[0].instance_id,
        )
        self.assertEqual(session.engine.state.level.definition.lights[0].radius, 6)
        self.assertEqual(
            PackStore(self.root).get("maps", "base:brush_test").equipment[0].ref,
            "base:terrain_decor_dagger",
        )

    def test_hidden_brush_trap_is_not_disclosed_by_the_underlying_tile_name(self):
        from tuidungeon.world.maps import Position

        raw = self.store.get("maps", "base:brush_test").model_dump(mode="json")
        raw["tiles"][1][2] = "base:spikes_hidden"
        raw["traps"][0]["ref"] = "base:terrain_spikes_hidden"
        self.store.save(
            "maps",
            "base:brush_test",
            raw,
            self.store.versions[("maps", "base:brush_test")],
        )
        session = TestSession(self.store, self.options)
        name = self.store.get("tiles", "base:spikes_hidden").name
        self.assertNotIn(name, " ".join(session.engine.inspect_cell(Position(2, 1))))
        session.command("d")
        self.assertIn(name, " ".join(session.engine.inspect_cell(Position(2, 1))))


if __name__ == "__main__":
    unittest.main()
