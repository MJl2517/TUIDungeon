"""Symbols are portable content, not mechanics or renderer-specific indices."""

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from tuidungeon.content.packs import PackStore, ContentError, Referenced, Conflict
from tuidungeon.content.schemas import SymbolDocument
from tuidungeon.content.symbols import appearance, png_bytes, resolve_text
from tuidungeon.tooling.server import create_app
from tuidungeon.world.graphics import visual_cell, overlay


class SymbolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, dependencies in [("base", []), ("extra", ["base"])]:
            path = self.root / name
            path.mkdir()
            (path / "manifest.json").write_text(
                json.dumps(dict(id=name, name=name, dependencies=dependencies))
            )
        self.store = PackStore(self.root)
        self.mask = ["0" * 16 for _ in range(16)]
        self.mask[4] = "0000011100000000"
        self.raw = dict(
            id="star",
            name="Звезда",
            glyph="*",
            pixels=self.mask,
            group="Магия",
            reviewed=True,
        )
        self.store.save("symbols", "base:star", self.raw, None)

    def test_mask_and_terminal_width_are_validated(self):
        for update in (
            {"pixels": ["0" * 16] * 15},
            {"pixels": ["x" * 16] * 16},
            {"glyph": "界"},
            {"glyph": "ab"},
            {"group": "Неразобранное"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                SymbolDocument.model_validate({**self.raw, **update})

    def test_roundtrip_conflicts_and_delete_protection(self):
        self.store.save(
            "tiles",
            "extra:floor",
            dict(id="floor", name="Пол", symbol="base:star"),
            None,
        )
        env = self.store.envelope("symbols", "base:star")
        self.assertEqual(env["document"]["pixels"], self.mask)
        self.assertEqual(env["usages"][0]["ref"], "extra:floor")
        with self.assertRaises(Referenced):
            self.store.delete("symbols", "base:star", env["version"])
        self.store.save(
            "symbols",
            "base:star",
            {**env["document"], "name": "Звезда новая"},
            env["version"],
        )
        with self.assertRaises(Conflict):
            self.store.save("symbols", "base:star", self.raw, env["version"])
        self.assertEqual(
            PackStore(self.root).get("symbols", "base:star").pixels, self.mask
        )

    def test_unreviewed_and_dependency_references_cannot_be_assigned(self):
        self.store.save(
            "symbols",
            "base:unreviewed",
            {**self.raw, "id": "unreviewed", "reviewed": False},
            None,
        )
        with self.assertRaises(ContentError):
            self.store.save(
                "tiles",
                "extra:floor",
                dict(id="floor", name="Пол", symbol="base:unreviewed"),
                None,
            )
        self.store.save("symbols", "extra:other", {**self.raw, "id": "other"}, None)
        with self.assertRaises(ContentError):
            self.store.save(
                "tiles",
                "base:floor",
                dict(id="floor", name="Пол", symbol="extra:other"),
                None,
            )

    def test_state_and_override_references_are_tracked(self):
        self.store.save(
            "tiles",
            "base:floor",
            dict(id="floor", name="Пол", state_symbols={"closed": "base:star"}),
            None,
        )
        self.assertEqual(
            self.store.usages("symbols", "base:star")[0]["field"],
            "state_symbols.closed",
        )
        doc = dict(glyph="#", symbol="base:star", foreground=196, background=None)
        cell = visual_cell(self.store, doc)
        self.assertEqual(
            (cell.char, cell.symbol, cell.foreground), ("*", "base:star", 196)
        )
        self.assertEqual(
            overlay(
                visual_cell(self.store, {"glyph": ".", "background": 4}), cell
            ).background,
            4,
        )
        self.assertEqual(
            appearance(
                self.store.documents,
                {"glyph": "?", "state_symbols": {"open": "base:star"}},
                "open",
            ),
            ("*", "base:star"),
        )

    def test_api_schema_assets_and_text_import_resolve_symbols(self):
        with TestClient(create_app(self.root), base_url="http://127.0.0.1") as client:
            response = client.post(
                "/api/art/import", json={"id": "art", "text": "Жx\n y"}
            )
            self.assertEqual(response.status_code, 200, response.text)
            doc = response.json()
            cells = doc["layers"][0]["cells"]
            self.assertEqual(cells[0][0]["symbol"], "base:glyph_0416")
            response = client.put(
                "/api/documents/art/base:art", json={"document": doc, "version": None}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("symbols", client.get("/api/schemas").json()["schemas"])
            self.assertIn(
                "symbols/base:star", client.get("/api/assets").json()["documents"]
            )
            self.assertEqual(
                client.get("/api/art/base:art/export").json()["text"], "Жx\n y\n"
            )

    def test_text_in_independent_pack_is_portable(self):
        from shutil import copytree

        path = self.root / "independent"
        path.mkdir()
        PackStore.atomic_json(
            path / "manifest.json",
            dict(id="independent", name="Standalone", dependencies=[]),
        )
        self.store.reload()
        refs = resolve_text(self.store, "*Ж", "independent")
        self.assertEqual(refs["*"], "independent:glyph_002a")
        self.store.save(
            "tiles",
            "independent:floor",
            dict(id="floor", name="Пол", symbol=refs["*"]),
            None,
        )
        portable = self.root / "portable"
        copytree(path, portable / "independent")
        loaded = PackStore(portable)
        self.assertEqual(loaded.get("symbols", refs["Ж"]).glyph, "Ж")
        self.assertEqual(loaded.get("tiles", "independent:floor").symbol, refs["*"])

    def test_old_glyph_override_wins_over_new_template_link(self):
        from tuidungeon.content.placements import override_document
        from tuidungeon.content.schemas import TileDocument

        base = TileDocument(id="floor", name="Пол", symbol="base:star")
        instance = override_document("tiles", base, {"glyph": ":"})
        self.assertEqual(appearance(self.store.documents, instance), (":", None))
        self.assertEqual(base.symbol, "base:star")

    def test_png_export_and_atlas_retain_alpha_and_tint(self):
        import tcod.tileset
        import numpy as np
        from tuidungeon.presentation.tilesets import load_symbol_tileset, load_map_style

        font = tcod.tileset.Tileset(12, 24)
        font[ord("?")] = np.full((24, 12), 255, dtype=np.uint8)
        atlas, mapping = load_symbol_tileset(font, self.store.documents)
        tile = atlas[ord(mapping["base:star"])]
        self.assertEqual(tile.shape, (16, 16, 4))
        self.assertEqual(int(tile[:, :, 3].sum()), 3 * 255)
        png = png_bytes([[b"\xff\xff\xff\xff", b"\0\0\0\0"]])
        self.assertTrue(png.startswith(b"\x89PNG"))
        path = self.root / "appearance.json"
        path.write_text('{"map_style":"kenney_1bit"}')
        self.assertEqual(load_map_style(path), "symbols")


class BundledSymbolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def test_all_bundled_visuals_and_references_are_reviewed(self):
        from tuidungeon.content.schemas import Visual
        from tuidungeon.content.packs import references

        atlas = [
            d
            for (cat, ref), d in self.store.documents.items()
            if cat == "symbols" and ref.startswith("base:kenney_")
        ]
        self.assertEqual(len(atlas), 49 * 22)
        self.assertTrue(all(d.source.license == "CC0" for d in atlas))
        for (cat, ref), doc in self.store.documents.items():
            if isinstance(doc, Visual):
                self.assertIsNotNone(doc.symbol, ref)
            for category, target, field in references(doc.model_dump(mode="json"), cat):
                if category == "symbols":
                    self.assertTrue(
                        self.store.get(category, target).reviewed, (ref, field)
                    )

    def test_migration_second_run_is_read_only(self):
        import contextlib
        import io
        from scripts.migrate_symbols import migrate

        versions = dict(self.store.versions)
        with contextlib.redirect_stdout(io.StringIO()):
            result = migrate(self.store.root)
        self.assertEqual(result["changed"], 0)
        self.store.reload()
        self.assertEqual(self.store.versions, versions)

    def test_hardware_is_not_mistaken_for_an_urn(self):
        from scripts.migrate_symbols import family

        self.assertIsNone(family("equipment", {"id": "furniture_hardware"}))
        self.assertEqual(family("objects", {"id": "terrain_urn"}), "pot")


if __name__ == "__main__":
    unittest.main()
