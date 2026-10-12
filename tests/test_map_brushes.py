"""Brush contracts and the actual mechanics used by browser-authored maps."""

from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from pydantic import ValidationError
from tuidungeon.content.packs import DEFAULT_PACKS, ContentError, PackStore
from tuidungeon.content.schemas import TileDocument
from tuidungeon.content.migrations import compatibility
from tuidungeon.tooling.server import template
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.engine import Action


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
                u["category"] == "maps"
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
            roof=[[False] * 10 for _ in range(5)],
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
            tile = TileDocument.model_validate(
                compatibility()["tiles"]["base:" + ref]["legacy"]
            )
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
        for p in raw["points_of_interest"]:
            p["overrides"] = {"storage": {"search_contents": True}}
        self.store.save("maps", "base:brush_test", raw, None)
        self.options = {"map_ref": "base:brush_test", "seed": 99}

    def test_drawn_recipe_objects_trigger_interact_pickup_and_transition(self):
        engine = SessionFactory(self.store).session(**self.options)
        engine.apply(Action.EAST)
        self.assertTrue(engine.state.level.traps[0].triggered)
        self.assertEqual(engine.events[0]["kind"], "trap")
        engine.apply(Action.EAST)
        before = len(engine.state.hero.inventory)
        self.assertTrue(engine.pickup_item().performed)
        self.assertEqual(len(engine.state.hero.inventory), before + 1)
        self.assertFalse(engine.state.items)
        point = engine.nearby_points()[0]
        choice = point.available_choices(engine.state.hero)[0]
        self.assertTrue(engine.interact(point.placement.id, choice.id).performed)
        self.assertGreater(engine.state.hero.gold, 0)
        self.assertTrue(engine.state.level.points[0].completed)
        engine.apply(Action.EAST)
        engine.apply(Action.EAST)
        self.assertEqual(engine.state.level.ref, "base:dungeon")

    def test_fresh_games_restore_resources_and_placement_state(self):
        factory = SessionFactory(self.store)
        engine = factory.session(**self.options)
        engine.apply(Action.EAST)
        engine.apply(Action.EAST)
        engine.pickup_item()
        fresh = factory.session(**self.options)
        self.assertFalse(fresh.state.level.traps[0].triggered)
        self.assertEqual(len(fresh.state.items), 1)
        self.assertNotEqual(
            engine.state.level.traps[0].instance_id,
            fresh.state.level.traps[0].instance_id,
        )
        self.assertEqual(fresh.state.light_sources()[0][1].definition.light.radius, 6)
        self.assertEqual(
            PackStore(self.root).get("maps", "base:brush_test").equipment[0].ref,
            "base:dagger",
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
        engine = SessionFactory(self.store).session(**self.options)
        name = self.store.get("traps", "base:terrain_spikes_hidden").name
        self.assertNotIn(name, " ".join(engine.inspect_cell(Position(2, 1))))
        engine.apply(Action.EAST)
        self.assertIn(name, " ".join(engine.inspect_cell(Position(2, 1))))


if __name__ == "__main__":
    unittest.main()
