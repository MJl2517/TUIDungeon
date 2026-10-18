"""Town atlas acceptance: geometry, storage, reading and a saved crop lifecycle."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import ContentError, PackStore, validate_regrowth
from tuidungeon.domain.equipment import Equipment
from tuidungeon.world.maps import Position


class TownTilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session(
            "tiles:town_lab", character_class="dev:empty_tester", seed=42
        )

    def near(self, identifier):
        p = next(
            p
            for cat in ("objects", "points_of_interest")
            for p in getattr(self.e.state.level.definition, cat)
            if p.id == identifier
        )
        self.e.state.position = Position(p.x - 1, p.y)
        return Position(p.x, p.y)

    def give(self, ref, quantity=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
            for _ in range(quantity)
        ]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "town.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_requested_symbols_colors_and_600_replacement(self):
        expected = {
            844,
            893,
            894,
            845,
            846,
            847,
            848,
            798,
            701,
            702,
            750,
            751,
            597,
            598,
            599,
            600,
            651,
            349,
            351,
            356,
            357,
            344,
            345,
            346,
            308,
            309,
            310,
            311,
            312,
        }
        refs = set()
        for (cat, ref), d in self.store.documents.items():
            if not ref.startswith("tiles:") or cat not in (
                "objects",
                "tiles",
                "equipment",
                "points_of_interest",
            ):
                continue
            refs.update([d.symbol, *d.state_symbols.values()])
        self.assertTrue({f"tiles:cell_{n:04}" for n in expected}.issubset(refs))
        atlas = Image.open(
            "assets/1 bit/Tilesheet/monochrome-transparent_packed.png"
        ).convert("RGBA")
        for n in expected:
            d = self.store.get("symbols", f"tiles:cell_{n:04}")
            c, r = (n - 1) % 49, (n - 1) // 49
            self.assertEqual(d.source.coordinates, [c, r])
            self.assertEqual(
                list(d.pixels),
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
        for n in (844, 893, 894):
            colors = {
                self.store.get("tiles", f"tiles:brick_wall_{n}" + suffix).foreground
                for suffix in ("", "_sand", "_gray", "_dark")
            }
            self.assertEqual(len(colors), 4)
        self.assertNotIn(("objects", "tiles:door_hatch"), self.store.documents)
        d = self.factory.session(
            "tiles:doors_lab", character_class="dev:empty_tester", seed=42
        )
        self.assertIsNone(d._door("door_hatch"))
        self.assertEqual(
            d.world_object("door_hatch"), None
        )  # Fixed pipes expose no work actions.
        self.assertTrue(
            any(p.ref == "tiles:pipe_600" for p in d.state.level.definition.objects)
        )

    def test_walls_lever_hole_and_immutable_pipes(self):
        e = self.e
        self.assertFalse(e.state.walkable(Position(5, 3)))
        self.assertTrue(e.state.level.terrain.blocks_sight[3][5])
        for i in range(4):
            p = Position(5 + i * 6, 9)
            self.assertFalse(e.state.walkable(p))
            self.assertEqual(
                e.state.level.render_cells(e.state)[p.y][p.x].foreground,
                [131, 180, 245, 240][i],
            )
        self.near("lever_0")
        self.assertTrue(e.interact("lever_0", "activate_mechanism").performed)
        self.assertTrue(e._door("gate").door.opened)
        self.reload()
        self.assertTrue(self.e._door("gate").door.opened)
        for n in (597, 598, 599, 600, 651):
            p = self.near("pipe_" + str(n))
            before = self.e.state.turns
            self.assertFalse(self.e.state.walkable(p))
            self.assertFalse(self.e.interact("pipe_" + str(n), "dismantle").performed)
            self.assertEqual(self.e.damage_cell(p, 999, "fire"), 0)
            self.assertEqual(self.e.state.turns, before)
        e = self.e
        p = self.near("wood_wall_798")
        self.assertFalse(e.interact("wood_wall_798", "dismantle").performed)
        torch = self.give("base:torch")
        self.assertTrue(e.manage_equipment(torch, True).performed)
        self.assertTrue(e.ignite_cell(torch, p).performed)
        for _ in range(5):
            e.apply(Action.WAIT)
        self.assertTrue(e.state.walkable(p))
        self.assertEqual(e.state.level.terrain.tiles[p.y][p.x], "base:floor")

    def test_grille_removal_leaves_lit_passable_hole_and_saved_single_loot(self):
        e = self.e
        p = self.near("wall_grate")
        self.assertFalse(e.state.walkable(p))
        self.assertFalse(e.state.level.terrain.blocks_sight[p.y][p.x])
        self.assertFalse(e.interact("wall_grate", "dismantle").performed)
        self.give("base:tinker_tools")
        self.assertTrue(e.interact("wall_grate", "dismantle").performed)
        for _ in range(3):
            self.assertTrue(e.advance_craft().performed)
        self.assertTrue(e.state.walkable(p))
        self.assertFalse(e.state.level.terrain.blocks_sight[p.y][p.x])
        self.assertEqual(
            e.state.level.terrain.cells[p.y][p.x].symbol, "tiles:cell_0847"
        )
        self.reload()
        self.assertTrue(self.e.state.walkable(p))
        self.assertEqual(
            Counter(i.id for pp, i in self.e.state.items if (pp.x, pp.y) == (p.x, p.y)),
            Counter({"metal": 2}),
        )
        self.assertFalse(self.e.interact("wall_grate", "dismantle").performed)

    def test_crates_states_capacity_cabinets_and_safe(self):
        e = self.e
        self.near("crate_small")
        self.assertFalse(e.open_container("crate_small").performed)
        self.give("base:crowbar")
        medium = self.give("tiles:cooking_pot")
        small = self.give("base:gold")
        self.assertTrue(e.open_container("crate_small").performed)
        self.assertFalse(
            e.transfer_storage(
                "crate_small", medium.instance_id, deposit=True
            ).performed
        )
        self.assertTrue(
            e.transfer_storage("crate_small", small.instance_id, deposit=True).performed
        )
        c = e.storage_at("crate_small")
        p = c.placement
        self.assertEqual(
            e.state.level.render_cells(e.state)[p.y][p.x].symbol, "tiles:cell_0751"
        )
        self.assertTrue(e.close_container("crate_small").performed)
        self.assertEqual(
            e.state.level.render_cells(e.state)[p.y][p.x].symbol, "tiles:cell_0702"
        )
        self.near("cabinet_349")
        self.assertTrue(e.open_container("cabinet_349").performed)
        self.assertTrue(
            e.transfer_storage(
                "cabinet_349", medium.instance_id, deposit=True
            ).performed
        )
        large = self.give("base:terrain_decor_greataxe")
        self.assertFalse(
            e.transfer_storage("cabinet_349", large.instance_id, deposit=True).performed
        )
        self.near("cabinet_357")
        self.assertFalse(e.open_container("cabinet_357").performed)
        self.give("tiles:key_container").bind_key(
            e.state.level.ref, e.state.level.definition.name
        )
        self.assertTrue(e.interact("cabinet_357", "unlock_container_key").performed)
        self.assertTrue(e.open_container("cabinet_357").performed)
        self.reload()
        self.assertFalse(
            next(
                c
                for c in self.e.state.level.containers
                if c.placement.id == "cabinet_357"
            ).locked
        )
        self.near("wall_stash")
        self.assertTrue(self.e.open_container("wall_stash").performed)
        self.assertEqual(self.e.storage_at("wall_stash").spec.max_item_size, "small")

    def test_reading_signs_and_board_persist_in_journal(self):
        for n in (344, 345, 346):
            self.near("sign_" + str(n))
            self.assertTrue(self.e.interact("sign_" + str(n), "read_note").performed)
        self.assertEqual(len(self.e.read_notes), 3)
        self.reload()
        self.assertEqual(len(self.e.read_notes), 3)
        self.assertIn(
            "Доска объявлений", [note.text.title for note in self.e.read_notes.values()]
        )

    def test_seed_placement_initial_growth_save_harvest_and_regrowth(self):
        e = self.e
        self.give("tiles:seedlings_berry")
        before = len(e.state.level.regrowing_objects)
        self.assertFalse(
            e.start_craft("tiles:plant_berry", destination=(5, 3)).performed
        )
        self.assertTrue(
            e.start_craft("tiles:plant_berry", destination=(2, 3)).performed
        )
        self.assertTrue(e.advance_craft().performed)
        placed = next(
            p for p in e.state.level.definition.objects if (p.x, p.y) == (2, 3)
        )
        pending = next(
            p for p in e.state.level.regrowing_objects if p.sprout_id == placed.id
        )
        mature_id = pending.placement.id
        self.assertEqual(len(e.state.level.regrowing_objects), before + 1)
        self.assertEqual(pending.ready_at - e.state.clock.elapsed_minutes, 1440)
        self.reload()
        e = self.e
        e._advance(1439)
        self.assertIsNone(e.world_object(mature_id))
        self.reload()
        e = self.e
        e._advance(1)
        self.assertIsNotNone(e.world_object(mature_id))
        self.near(mature_id)
        self.assertTrue(e.interact(mature_id, "dismantle").performed)
        self.assertTrue(e.advance_craft().performed)
        crops = [
            r for r in e.state.level.regrowing_objects if r.placement.id == mature_id
        ]
        self.assertEqual(len(crops), 1)
        self.assertIsNotNone(e.world_object(crops[0].sprout_id))
        drops = Counter(i.id for p, i in e.state.items if (p.x, p.y) == (2, 3))
        self.assertEqual(
            drops, Counter({"tiles:berries": 2, "tiles:seedlings_berry": 1})
        )
        self.reload()
        e = self.e
        e._advance(1440)
        self.assertIsNotNone(e.world_object(mature_id))
        self.assertEqual(
            Counter(i.id for p, i in e.state.items if (p.x, p.y) == (2, 3)), drops
        )

    def test_destroyed_seedling_cancels_growth_and_invalid_growth_rejected(self):
        e = self.e
        p = self.near("sprout_root")
        self.assertTrue(
            any(r.sprout_id == "sprout_root" for r in e.state.level.regrowing_objects)
        )
        e.damage_cell(p, 999, "fire")
        self.assertFalse(
            any(r.sprout_id == "sprout_root" for r in e.state.level.regrowing_objects)
        )
        self.reload()
        self.e._advance(1440)
        self.assertFalse(
            any(
                o.placement.x == p.x and o.placement.y == p.y
                for o in self.e.world_objects()
            )
        )
        young = self.store.get("objects", "tiles:crop_sprout_berry")
        with self.assertRaises(ContentError):
            validate_regrowth(young, self.store.documents, "tiles:crop_sprout_root")


if __name__ == "__main__":
    unittest.main()
