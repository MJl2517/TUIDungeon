"""Reflection is per visual/placement, never a new symbol or new geometry."""

from copy import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np
import tcod.tileset

from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument, Cell, TileDocument
from tuidungeon.presentation.tilesets import load_symbol_tileset
from tuidungeon.presentation.window import render_map
from tuidungeon.presentation.tui import Controller
from tuidungeon.world.maps import Position


class MirroringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="mirrors",
            name="Отражение",
            width=8,
            height=5,
            tiles=[["base:floor"] * 8 for _ in range(5)],
            walkability=[[True] * 8 for _ in range(5)],
            blocks_sight=[[False] * 8 for _ in range(5)],
            spawn=dict(x=1, y=2),
            ambient_light="dim",
            objects=[
                dict(
                    id="rails",
                    ref="tiles:rails_247",
                    x=4,
                    y=2,
                    overrides={"mirror_x": True},
                )
            ],
            doors=[
                dict(
                    id="door",
                    ref="base:door_wood",
                    x=6,
                    y=2,
                    overrides={"mirror_x": True},
                )
            ],
        )
        self.raw["tiles"][3][3] = "tiles:wood_bridge_suspended_252"
        self.raw["tile_mirrors"] = [[False] * 8 for _ in range(5)]
        self.raw["tile_mirrors"][3][3] = True
        self.store.documents["maps", "tiles:mirrors"] = MapDocument.model_validate(
            self.raw
        )
        self.e = SessionFactory(self.store).session("tiles:mirrors", seed=42)

    def cell(self, x, y):
        return self.e.render_cells((x, y, 1, 1))[0][0]

    def test_defaults_strict_flags_and_mask_dimensions(self):
        old = {k: v for k, v in self.raw.items() if k != "tile_mirrors"}
        doc = MapDocument.model_validate(old)
        self.assertFalse(any(any(row) for row in doc.tile_mirrors))
        self.assertFalse(Cell().mirror_x)
        self.assertFalse(TileDocument(id="plain", name="Тайл").mirror_x)
        self.assertEqual(Cell().rotation, 0)
        self.assertFalse(any(any(row) for row in doc.tile_rotations))
        for angle in (45, -90, 360, True, "90"):
            with self.subTest(angle=angle), self.assertRaises(ValueError):
                Cell(rotation=angle)
        with self.assertRaises(ValueError):
            Cell(mirror_x="yes")
        with self.assertRaisesRegex(ValueError, "tile_mirrors"):
            MapDocument.model_validate({**old, "tile_mirrors": [[True]]})

    def test_studio_new_map_template_resets_the_visual_mask_size(self):
        from tuidungeon.tooling.server import template

        raw = template(self.store, "maps")
        self.assertEqual(
            (len(raw["tile_mirrors"]), len(raw["tile_mirrors"][0])), (12, 20)
        )
        MapDocument.model_validate(raw)
        self.assertEqual(
            (len(raw["tile_rotations"]), len(raw["tile_rotations"][0])), (12, 20)
        )

    def test_surfaces_objects_doors_and_oil_keep_visual_flag_without_geometry_change(
        self,
    ):
        for x, y in [(3, 3), (4, 2), (6, 2)]:
            self.assertTrue(self.cell(x, y).mirror_x)
        self.assertTrue(self.e.state.walkable(Position(3, 3)))
        self.assertTrue(self.e.state.walkable(Position(4, 2)))
        self.assertFalse(self.e.state.walkable(Position(6, 2)))
        self.e.state.oil[Position(3, 3)] = 5
        self.assertTrue(self.cell(3, 3).mirror_x)
        self.assertEqual(self.cell(3, 3).background, 58)  # Oil remains dimly shaded.
        self.e.state.position = Position(5, 2)
        self.assertTrue(self.e.interact("door", "open").performed)
        self.assertTrue(self.cell(6, 2).mirror_x)
        self.assertEqual(self.cell(6, 2).symbol, "base:door_wood_open")
        self.assertFalse(self.store.get("objects", "base:door_wood").mirror_x)

    def test_relative_surface_reflection_and_save_roundtrip(self):
        template = self.store.get("tiles", "tiles:wood_bridge_suspended_252")
        self.store.documents["tiles", "tiles:wood_bridge_suspended_252"] = (
            template.model_copy(update={"mirror_x": True})
        )
        e = SessionFactory(self.store).session("tiles:mirrors", seed=42)
        self.assertFalse(e.render_cells((3, 3, 1, 1))[0][0].mirror_x)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            loaded = repo.load(store=self.e.state.level.store)
        self.assertTrue(loaded.state.level.definition.tile_mirrors[3][3])
        self.assertTrue(loaded.render_cells((4, 2, 1, 1))[0][0].mirror_x)

    def test_atlas_mirrors_pixels_and_window_uses_mirrored_codepoint(self):
        symbol = self.store.get("symbols", "tiles:cell_0247")
        original = np.array([[c == "1" for c in row] for row in symbol.pixels])
        self.assertFalse(np.array_equal(original, original[:, ::-1]))
        font = tcod.tileset.Tileset(16, 16)
        atlas, mapping = load_symbol_tileset(
            font, {("symbols", "tiles:cell_0247"): symbol}
        )
        normal = atlas[ord(mapping["tiles:cell_0247"])][:, :, 3]
        reflected = atlas[ord(mapping["tiles:cell_0247", "mirror_x"])][:, :, 3]
        np.testing.assert_array_equal(reflected, normal[:, ::-1])
        for rotation in (0, 90, 180, 270):
            rotated = np.rot90(normal, -rotation // 90)
            for mirrored in (False, True):
                actual = atlas[ord(mapping["tiles:cell_0247", rotation, mirrored])][
                    :, :, 3
                ]
                np.testing.assert_array_equal(
                    actual, rotated[:, ::-1] if mirrored else rotated
                )
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="tiles:mirrors",
            test_map=True,
        )
        console, _, origin = render_map(c, 100, 28, 16, sprites=mapping)
        self.assertEqual(
            chr(console.ch[2 - origin.y, 4 - origin.x]),
            mapping["tiles:cell_0247", "mirror_x"],
        )

    def test_rotation_with_mirroring_survives_save_and_matches_window_atlas(self):
        self.raw["tile_rotations"] = [[0] * 8 for _ in range(5)]
        self.raw["tile_rotations"][3][3] = 270
        self.raw["objects"][0]["overrides"]["rotation"] = 90
        self.raw["doors"][0]["overrides"]["rotation"] = 180
        self.store.documents["maps", "tiles:mirrors"] = MapDocument.model_validate(
            self.raw
        )
        self.e = SessionFactory(self.store).session("tiles:mirrors", seed=42)
        self.assertEqual(
            [self.cell(x, y).rotation for x, y in [(3, 3), (4, 2), (6, 2)]],
            [270, 90, 180],
        )
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            loaded = repo.load(store=self.e.state.level.store)
        self.assertEqual(loaded.render_cells((4, 2, 1, 1))[0][0].rotation, 90)
        self.assertTrue(loaded.render_cells((4, 2, 1, 1))[0][0].mirror_x)
        atlas, mapping = load_symbol_tileset(
            tcod.tileset.Tileset(16, 16), self.store.documents
        )
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="tiles:mirrors",
            test_map=True,
        )
        console, _, origin = render_map(c, 100, 28, 16, sprites=mapping)
        self.assertEqual(
            chr(console.ch[2 - origin.y, 4 - origin.x]),
            mapping["tiles:cell_0247", 90, True],
        )


if __name__ == "__main__":
    unittest.main()
