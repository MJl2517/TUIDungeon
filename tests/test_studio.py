"""Authoring contracts, pack transactions and native game launch."""

from scripts.testing import install_test_maps
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError, Field
from fastapi.testclient import TestClient
from tuidungeon.content.packs import (
    PackStore,
    DEFAULT_PACKS,
    Conflict,
    ContentError,
    Referenced,
)
from tuidungeon.content.schemas import ArtDocument, MonsterDocument, MapDocument, MODELS
from tuidungeon.presentation.art import compose, import_txt, export_txt
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.engine import Action
from tuidungeon.presentation.tui import Controller
from tuidungeon.tooling.server import create_app
from tuidungeon.domain.mechanics import mechanics, Parameters
from tuidungeon.domain.effects import EffectOutcome


class PackFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "packs"
        shutil.copytree(DEFAULT_PACKS, self.root)
        install_test_maps(self.root)
        self.store = PackStore(self.root)


class DocumentTests(PackFixture):
    def test_layered_roundtrip_preserves_hidden_locked_and_transparency(self):
        raw = import_txt("ab\ncd", "picture", "Рисунок").model_dump(mode="json")
        raw["layers"].append(
            {
                "id": "overlay",
                "name": "Тень",
                "visible": True,
                "locked": True,
                "cells": [
                    [{"char": "█", "foreground": 196, "background": None}, None],
                    [None, {"char": "░", "foreground": 241, "background": 17}],
                ],
            }
        )
        raw["layers"][0]["cells"][0][0]["background"] = 4
        result = self.store.save("art", "base:picture", raw, None)
        loaded = PackStore(self.root).get("art", "base:picture")
        self.assertEqual(loaded.model_dump(mode="json"), result["document"])
        cells = compose(loaded)
        self.assertEqual(
            (cells[0][0].char, cells[0][0].foreground, cells[0][0].background),
            ("█", 196, 4),
        )
        self.assertEqual(export_txt(loaded), "█b\nc░\n")
        hidden = loaded.model_copy(
            update={
                "layers": [
                    loaded.layers[0],
                    loaded.layers[1].model_copy(update={"visible": False}),
                ]
            }
        )
        self.assertEqual(export_txt(hidden), "ab\ncd\n")

    def test_invalid_glyph_reports_exact_layer_and_coordinates(self):
        raw = import_txt("ab").model_dump(mode="json")
        raw["layers"][0]["cells"][0][1]["char"] = "🙂"
        with self.assertRaises(ValidationError) as caught:
            ArtDocument.model_validate(raw)
        self.assertEqual(
            caught.exception.errors()[0]["loc"], ("layers", 0, "cells", 0, 1, "char")
        )
        from tuidungeon.content.schemas import Cell

        for glyph in ("界", "\t", "e\u0301", "\u0301", "\n"):
            with self.assertRaises(ValueError):
                Cell(char=glyph)

    def test_strict_models_reject_unknown_fields_types_dimensions_and_dice(self):
        raw = self.store.get("monsters", "base:goblin").model_dump(mode="json")
        for key, value in [
            ("speed", "2"),
            ("hit_points", True),
            ("unknown", 1),
            ("glyph", "██"),
        ]:
            changed = deepcopy(raw)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                MonsterDocument.model_validate(changed)
        raw["special_actions"][0]["id"] = "attack"
        with self.assertRaises(ValidationError):
            MonsterDocument.model_validate(raw)
        raw["special_actions"][0]["id"] = "dirty_strike"
        raw["special_actions"][0]["damage"] = "1000d6"
        with self.assertRaises(ValidationError):
            MonsterDocument.model_validate(raw)
        art = import_txt("abc").model_dump(mode="json")
        art["width"] = 2
        with self.assertRaises(ValidationError):
            ArtDocument.model_validate(art)

    def test_narrative_newlines_are_preserved_and_bad_runtime_definitions_rejected(
        self,
    ):
        raw = self.store.get("challenges", "base:locked_chest").model_dump(mode="json")
        raw["text"] = "Первая строка.\nВторая строка."
        self.store.save(
            "challenges",
            "base:locked_chest",
            raw,
            self.store.versions[("challenges", "base:locked_chest")],
        )
        self.assertIn(
            "\n", self.store.runtime_catalog().challenges["locked_chest"].text
        )
        raw["choices"][0]["check_tag"] = "bad tag"
        with self.assertRaises(ValidationError):
            MODELS["challenges"].model_validate(raw)
        class_raw = self.store.get("classes", "base:warrior").model_dump(mode="json")
        class_raw["actions"] = ["base:attack", "base:attack"]
        with self.assertRaises(ValidationError):
            MODELS["classes"].model_validate(class_raw)
        spell = self.store.get("spells", "base:detect_magic").model_dump(mode="json")
        spell["effects"] = [{"kind": "armor_class", "amount": 12}]
        with self.assertRaises(ValidationError):
            MODELS["spells"].model_validate(spell)

    def test_mask_visual_independence_and_map_validation(self):
        raw = self.store.get("maps", "base:crypt").model_dump(mode="json")
        raw["tiles"][3][4] = "base:wall"
        self.store.save(
            "maps", "base:crypt", raw, self.store.versions[("maps", "base:crypt")]
        )
        game = SessionFactory(self.store).session("base:crypt")
        self.assertTrue(game.apply(Action.EAST).performed)
        raw["walkability"][3][3] = False
        with self.assertRaises(ValidationError):
            MapDocument.model_validate(raw)
        raw["walkability"][3][3] = True
        raw["monsters"][0]["x"] = 100
        with self.assertRaises(ValidationError):
            MapDocument.model_validate(raw)

    def test_unreachable_regions_are_warnings_and_placement_refs_errors(self):
        raw = self.store.get("maps", "base:crypt").model_dump(mode="json")
        for y in range(raw["height"]):
            raw["walkability"][y][10] = False
        self.store.save(
            "maps", "base:crypt", raw, self.store.versions[("maps", "base:crypt")]
        )
        self.assertTrue(self.store.warnings("maps", "base:crypt")[0]["cells"])
        raw["traps"][0]["ref"] = "base:missing"
        with self.assertRaises(ContentError):
            self.store.save(
                "maps", "base:crypt", raw, self.store.versions[("maps", "base:crypt")]
            )

    def test_external_conflict_does_not_overwrite_and_identity_is_fixed(self):
        envelope = self.store.envelope("monsters", "base:goblin")
        path = self.store.paths[("monsters", "base:goblin")]
        raw = deepcopy(envelope["document"])
        raw["name"] = "Внешняя правка"
        path.write_text(json.dumps(raw))
        with self.assertRaises(Conflict):
            self.store.save(
                "monsters", "base:goblin", envelope["document"], envelope["version"]
            )
        self.assertEqual(json.loads(path.read_text())["name"], "Внешняя правка")
        self.store.reload()
        raw["id"] = "other"
        with self.assertRaises(ContentError):
            self.store.save(
                "monsters",
                "base:goblin",
                raw,
                self.store.versions[("monsters", "base:goblin")],
            )

    def test_referenced_delete_blocked_and_atomic_failure_keeps_original(self):
        key = ("challenges", "base:locked_chest")
        self.assertTrue(self.store.usages(*key))
        with self.assertRaises(Referenced):
            self.store.delete(*key, self.store.versions[key])
        raw = self.store.get(*key).model_dump(mode="json")
        raw["choices"] = []
        before = self.store.paths[key].read_bytes()
        with self.assertRaises(ValidationError):
            self.store.save(*key, raw, self.store.versions[key])
        self.assertEqual(self.store.paths[key].read_bytes(), before)
        self.assertFalse(list(self.root.rglob(".studio-*.tmp")))

    def test_second_pack_dependencies_missing_cycle_duplicates_and_cross_refs(self):
        self.store.create_pack(
            {"id": "expansion", "name": "Дополнение", "dependencies": ["base"]}
        )
        raw = self.store.get("monsters", "base:goblin").model_dump(mode="json")
        raw["id"] = "scout"
        self.store.save("monsters", "expansion:scout", raw, None)
        self.assertIn("expansion:scout", self.store.runtime_catalog().monsters)
        with self.assertRaises(ContentError):
            self.store.create_pack(
                {"id": "broken", "name": "Broken", "dependencies": ["missing"]}
            )
        manifests = dict(self.store.manifests)
        manifests["base"] = manifests["base"].model_copy(
            update={"dependencies": ["expansion"]}
        )
        with self.assertRaises(ContentError):
            self.store.validate_dependencies(manifests)
        self.store.create_pack({"id": "isolated", "name": "Isolated"})
        with self.assertRaises(ContentError):
            self.store.save("monsters", "isolated:scout", raw, None)
        duplicate = self.root / "base/monsters/duplicate.json"
        shutil.copyfile(self.root / "base/monsters/goblin.json", duplicate)
        with self.assertRaises(ContentError):
            self.store.reload()

    def test_migration_retains_sources_and_matches_original_map(self):
        from tuidungeon.content.migrate import migrate
        from tuidungeon.content.catalog import DEFAULT_ROOT
        from tuidungeon.application.engine import test_dungeon

        before = (DEFAULT_ROOT / "monsters/goblin.json").read_bytes()
        migrated = migrate(Path(self.temp.name) / "migration")
        engine = SessionFactory(migrated).session("base:dungeon")
        self.assertEqual(engine.state.dungeon.rows, test_dungeon().rows)
        self.assertEqual((DEFAULT_ROOT / "monsters/goblin.json").read_bytes(), before)
        with self.assertRaises(ValueError):
            migrate(Path(self.temp.name) / "migration")


class SessionTests(PackFixture):
    def test_trap_one_shot_repeat_and_reset_independence(self):
        factory = SessionFactory(self.store)
        a = factory.session("base:crypt", seed=42)
        b = factory.session("base:crypt", seed=42)
        for _ in range(2):
            a.apply(Action.EAST)
        self.assertEqual(a.state.hero.hp, 10)
        self.assertTrue(a.state.level.traps[0].triggered)
        self.assertFalse(b.state.level.traps[0].triggered)
        self.assertEqual(b.state.hero.hp, 12)
        a.apply(Action.WEST)
        a.apply(Action.EAST)
        self.assertEqual(len(a.events), 1)
        self.assertNotEqual(
            a.state.monsters[0].monster.instance_id,
            b.state.monsters[0].monster.instance_id,
        )
        self.assertNotEqual(
            a.state.level.items[0][1].instance_id, b.state.level.items[0][1].instance_id
        )
        self.assertFalse(self.store.get("traps", "base:spikes").repeatable)
        raw = self.store.get("traps", "base:spikes").model_dump(mode="json")
        raw["repeatable"] = True
        self.store.save(
            "traps", "base:spikes", raw, self.store.versions[("traps", "base:spikes")]
        )
        c = SessionFactory(self.store).session("base:crypt", seed=42)
        for action in [Action.EAST, Action.EAST, Action.WEST, Action.EAST]:
            c.apply(action)
        self.assertEqual(len(c.events), 2)

    def test_point_distance_choices_completion_and_resource_cost(self):
        point = self.store.get("points_of_interest", "base:chest")
        self.store.documents["points_of_interest", "base:chest"] = point.model_copy(
            update={
                "storage": point.storage.model_copy(update={"search_contents": True})
            }
        )
        game = SessionFactory(self.store).session("base:crypt", seed=42)
        self.assertFalse(game.interact("chest_1", "force").performed)
        for _ in range(3):
            game.apply(Action.EAST)
        self.assertEqual(game.nearby_points()[0].placement.id, "chest_1")
        turns = game.state.turns
        clock = game.state.clock.elapsed_minutes
        result = game.interact("chest_1", "force")
        self.assertTrue(result.performed)
        self.assertEqual(game.state.turns, turns + 1)
        self.assertEqual(game.state.clock.elapsed_minutes, clock + 1)
        self.assertFalse(game.interact("chest_1", "force").performed)

    def test_menus_do_not_change_time_and_monsters_block(self):
        factory = SessionFactory(self.store)
        controller = Controller(
            42, catalog=factory.catalog, map_ref="base:crypt", store=self.store
        )
        controller.handle("enter")
        for key in "11112721234561":
            controller.handle(key)
        before = controller.engine.state.clock.elapsed_minutes
        for key in ["2", "d", "backspace", "right", "left", "tab"]:
            controller.handle(key)
        self.assertEqual(controller.engine.state.clock.elapsed_minutes, before)
        game = controller.engine
        game.state.position = __import__(
            "tuidungeon.world.maps", fromlist=["Position"]
        ).Position(15, 7)
        self.assertFalse(game.apply(Action.EAST).performed)

    def test_transitions_preserve_hero_time_and_visited_runtime_state(self):
        raw = self.store.get("maps", "base:crypt").model_dump(mode="json")
        raw["transitions"] = [
            {"id": "stairs", "x": 4, "y": 3, "target": "base:dungeon"}
        ]
        self.store.save(
            "maps", "base:crypt", raw, self.store.versions[("maps", "base:crypt")]
        )
        game = SessionFactory(self.store).session("base:crypt", seed=42)
        hero = game.state.hero
        self.assertTrue(game.apply(Action.EAST).performed)
        self.assertEqual(game.state.level.ref, "base:dungeon")
        self.assertIs(game.state.hero, hero)
        self.assertEqual((game.state.turns, game.state.clock.elapsed_minutes), (1, 481))
        self.assertEqual(game.events[-1]["kind"], "transition")

    def test_registered_mechanic_reaches_schema_forms_and_engine(self):
        class Rally(Parameters):
            points: int = Field(ge=1)

        def handler(params, target, dice):
            target.gold += params.points
            return EffectOutcome("rally", amount=params.points)

        mechanics.register("rally", Rally, handler, name="Ободрение")
        self.addCleanup(mechanics.entries.pop, "rally")
        raw = self.store.get("traps", "base:spikes").model_dump(mode="json")
        raw["difficulty"] = 0
        raw["success"] = [{"kind": "rally", "params": {"points": 7}}]
        self.store.save(
            "traps", "base:spikes", raw, self.store.versions[("traps", "base:spikes")]
        )
        game = SessionFactory(self.store).session("base:crypt")
        game.apply(Action.EAST)
        game.apply(Action.EAST)
        self.assertEqual(game.state.hero.gold, 7)
        schema = next(m for m in mechanics.schemas() if m["id"] == "rally")["schema"]
        self.assertEqual(schema["properties"]["points"]["minimum"], 1)
        raw["success"][0]["params"]["points"] = "7"
        with self.assertRaises(ValidationError):
            MODELS["traps"].model_validate(raw)


class ApiTests(PackFixture):
    def setUp(self):
        super().setUp()
        self.client = TestClient(create_app(self.root), base_url="http://127.0.0.1")

    def test_recipe_authoring_validates_ingredients_and_result_references(self):
        meta = self.client.get("/api/schemas").json()
        raw = meta["templates"]["recipes"]
        raw.update(id="studio_recipe", name="Рецепт из студии")
        response = self.client.put(
            "/api/documents/recipes/base:studio_recipe",
            json={"document": raw, "version": None},
        )
        self.assertEqual(response.status_code, 200, response.text)
        loaded = PackStore(self.root).runtime_catalog()
        self.assertIn("base:studio_recipe", loaded.recipes)
        raw["variants"][0]["ingredients"][0]["items"] = ["base:absent_material"]
        response = self.client.put(
            "/api/documents/recipes/base:studio_recipe",
            json={"document": raw, "version": response.json()["version"]},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertNotEqual(
            PackStore(self.root)
            .get("recipes", "base:studio_recipe")
            .variants[0]
            .ingredients[0]
            .items,
            ["base:absent_material"],
        )

    def test_browser_game_routes_are_removed(self):
        self.assertFalse(hasattr(self.client.app.state, "sessions"))
        for path in (
            "/api/sessions",
            "/api/sessions/old/commands",
            "/api/sessions/old/reset",
        ):
            self.assertEqual(self.client.post(path, json={}).status_code, 404)
        self.assertEqual(self.client.delete("/api/sessions/old").status_code, 404)

    def test_game_map_launch_validation_origin_and_errors(self):
        with patch("tuidungeon.tooling.server.open_test_map") as launch:
            for body in (
                {"map_ref": "base:missing"},
                {"map_ref": "base:crypt & calc"},
                {"map_ref": "base:crypt", "seed": "42"},
                {"map_ref": "base:crypt", "command": "calc"},
                {"map_ref": "base:crypt", "character_class": "base:missing"},
                {"map_ref": "base:crypt", "character_class": "base:rogue & calc"},
                {"map_ref": "base:crypt", "character_class": 1},
            ):
                response = self.client.post("/api/game", json=body)
                self.assertEqual(response.status_code, 422, response.text)
            response = self.client.post(
                "/api/game",
                json={"map_ref": "base:crypt"},
                headers={"origin": "https://example.org"},
            )
            self.assertEqual(response.status_code, 403)
            launch.assert_not_called()
            response = self.client.post(
                "/api/game",
                json={"map_ref": "base:crypt", "seed": 7},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(
                response.json(), {"started": True, "map_ref": "base:crypt"}
            )
            launch.assert_called_once_with(
                self.root.resolve(), "base:crypt", 7, "base:warrior"
            )
            for character_class in ("base:warrior", "base:wizard", "base:rogue"):
                response = self.client.post(
                    "/api/game",
                    json={"map_ref": "base:crypt", "character_class": character_class},
                )
                self.assertEqual(response.status_code, 200, response.text)
                launch.assert_called_with(
                    self.root.resolve(), "base:crypt", 42, character_class
                )
            launch.side_effect = OSError("window unavailable")
            response = self.client.post("/api/game", json={"map_ref": "base:crypt"})
            self.assertEqual(response.status_code, 503)
            self.assertIn("window unavailable", response.json()["detail"])

    def test_full_authoring_api_schemas_save_usages_and_conflicts(self):
        lib = self.client.get("/api/library")
        self.assertEqual(lib.status_code, 200)
        documents = lib.json()["documents"]
        goblin = next(
            d
            for d in documents
            if d["category"] == "monsters" and d["ref"] == "base:goblin"
        )
        self.assertEqual(
            goblin["details"]["hit_points"],
            self.store.get("monsters", "base:goblin").hit_points,
        )
        self.assertIn('"hit_points"', goblin["search_text"])
        wall = next(
            d for d in documents if d["category"] == "tiles" and d["ref"] == "base:wall"
        )
        self.assertTrue(wall["details"]["blocks_sight"])
        self.assertTrue(
            all(
                not d["search_text"]
                for d in documents
                if d["category"] in ("maps", "art")
            )
        )
        assets = self.client.get("/api/assets").json()
        self.assertIn("art/base:goblin", assets["documents"])
        self.assertEqual(
            assets["versions"]["tiles/base:wall"],
            self.store.versions[("tiles", "base:wall")],
        )
        meta = self.client.get("/api/schemas").json()
        self.assertEqual(set(meta["schemas"]), set(MODELS))
        raw = meta["templates"]["monsters"]
        raw.update(id="scout", name="Разведчик")
        response = self.client.put(
            "/api/documents/monsters/base:scout",
            json={"document": raw, "version": None},
        )
        self.assertEqual(response.status_code, 200, response.text)
        version = response.json()["version"]
        self.assertEqual(
            self.client.put(
                "/api/documents/monsters/base:scout",
                json={"document": raw, "version": "stale"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.request(
                "DELETE",
                "/api/documents/monsters/base:scout",
                json={"version": version},
            ).status_code,
            200,
        )

    def test_empty_pack_schemas_and_invalid_hero_refs(self):
        root = Path(self.temp.name) / "empty_packs"
        PackStore.atomic_json(
            root / "starter/manifest.json", {"id": "starter", "name": "Начальный пакет"}
        )
        empty = TestClient(create_app(root), base_url="http://127.0.0.1")
        response = empty.get("/api/schemas")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["templates"]["points_of_interest"]["challenge"],
            "starter:new_challenge",
        )
        self.assertEqual(
            self.client.post(
                "/api/sandbox", json={"monster": "base:missing", "action": "attack"}
            ).status_code,
            422,
        )

    def test_sandbox_local_origin_guard_and_glyph_diagnostics(self):
        self.assertEqual(
            self.client.post(
                "/api/sandbox",
                json={"monster": "base:goblin", "action": "dirty_strike", "seed": 7},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/library", headers={"origin": "https://example.org"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/library", headers={"host": "example.org"}
            ).status_code,
            403,
        )
        raw = import_txt("ab").model_dump()
        raw["layers"][0]["cells"][0][1]["char"] = "界"
        self.assertEqual(
            self.client.post("/api/art/check", json={"document": raw}).json()["issues"][
                0
            ]["x"],
            1,
        )
        self.assertEqual(
            self.client.put(
                "/api/documents/art/base:imported", json={"document": raw}
            ).status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
