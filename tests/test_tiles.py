"""Curated tile content, safe imports and metadata consumed by Studio."""

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from wcwidth import wcwidth

from scripts.import_tileset import PROJECT_ROOT, curated_tiles, install
from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import TileDocument
from tuidungeon.tooling.server import create_app

SOURCE = PROJECT_ROOT / "docs/reference/tui_dungeon_tileset_colored.txt"


class TileLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curated = curated_tiles(SOURCE)
        cls.store = PackStore()

    def test_catalog_is_complete_and_every_symbol_occupies_one_column(self):
        added = [d for _, d in self.curated if d.id not in {"wall", "floor"}]
        self.assertEqual(len(added), 438)
        self.assertEqual(len(Counter(d.group for d in added)), 38)
        for doc in added:
            with self.subTest(tile=doc.id):
                loaded = self.store.get("tiles", f"base:{doc.id}")
                self.assertEqual(loaded.id, doc.id)
                self.assertEqual(loaded.group, doc.group)
                self.assertEqual(wcwidth(loaded.glyph), 1)
                self.assertNotEqual(loaded.glyph, "@")
        self.assertEqual(self.store.get("tiles", "base:water_calm").glyph, "∿")

    def test_movement_and_sight_masks_have_independent_defaults(self):
        examples = {
            "wall_massive": (False, True),
            "door_grate": (False, False),
            "door_open": (True, False),
            "water_deep": (False, False),
            "chasm_deep": (False, False),
            "bookcase": (False, True),
            "table": (False, False),
            "fog_dense": (True, True),
            "floor_tiles": (True, False),
            "chest": (True, False),
            "rune_protection": (True, False),
            "torch_wall": (True, False),
        }
        for identifier, expected in examples.items():
            with self.subTest(tile=identifier):
                doc = self.store.get("tiles", f"base:{identifier}")
                self.assertEqual((doc.walkable, doc.blocks_sight), expected)

    def test_library_exposes_group_and_search_tags_and_old_tiles_still_load(self):
        with TestClient(
            create_app(DEFAULT_PACKS), base_url="http://127.0.0.1"
        ) as client:
            response = client.get("/api/library")
        self.assertEqual(response.status_code, 200)
        entries = {
            e["ref"]: e
            for e in response.json()["documents"]
            if e["category"] == "tiles"
        }
        self.assertEqual(entries["base:door_grate"]["group"], "Двери и проходы")
        self.assertIn("transparent", entries["base:door_grate"]["tags"])
        self.assertEqual(entries["base:wall"]["group"], "Прочее")
        self.assertEqual(self.store.get("tiles", "base:cave_wall").background, 0)


class TileImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pack = Path(self.temp.name) / "sample"
        self.pack.mkdir()
        (self.pack / "manifest.json").write_text(
            '{"id":"sample","name":"Тест","version":"1.0.0","dependencies":[]}',
            encoding="utf-8",
        )
        self.wall = TileDocument(
            id="wall", name="Авторская стена", glyph="%", foreground=123, walkable=False
        )
        self.floor = TileDocument(
            id="floor_tiles", name="Плитка", glyph="·", group="Полы"
        )

    def test_import_preserves_authored_files_and_repeat_is_idempotent(self):
        existing = self.pack / "tiles/wall.json"
        existing.parent.mkdir()
        original = json.dumps(
            self.wall.model_dump(mode="json"), ensure_ascii=False
        ).encode("utf-8")
        existing.write_bytes(original)
        with patch(
            "scripts.import_tileset.curated_tiles",
            return_value=[
                ("walls", self.wall.model_copy(update={"glyph": "#"})),
                ("floors", self.floor),
            ],
        ):
            self.assertEqual(install(SOURCE, self.pack), 1)
            self.assertEqual(install(SOURCE, self.pack), 0)
        self.assertEqual(existing.read_bytes(), original)
        loaded = PackStore(self.pack.parent).get("tiles", "sample:floor_tiles")
        self.assertEqual(loaded, self.floor)

    def test_path_conflicts_are_detected_before_any_file_is_written(self):
        collision = self.pack / "tiles/floors/floor_tiles.json"
        collision.parent.mkdir(parents=True)
        collision.write_text(self.wall.model_dump_json(), encoding="utf-8")
        with patch(
            "scripts.import_tileset.curated_tiles",
            return_value=[
                ("walls", TileDocument(id="other", name="Новый")),
                ("floors", self.floor),
            ],
        ):
            with self.assertRaisesRegex(ValueError, "другим ID"):
                install(SOURCE, self.pack)
        self.assertFalse((self.pack / "tiles/walls/other.json").exists())

    def test_modified_source_order_contract_is_rejected_before_import(self):
        source = Path(self.temp.name) / "invalid.txt"
        source.write_text(
            "[СТЕНЫ И АРХИТЕКТУРА]\n# - Стена - серый\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "список изменён"):
            install(source, self.pack)
        self.assertFalse((self.pack / "tiles").exists())


if __name__ == "__main__":
    unittest.main()
