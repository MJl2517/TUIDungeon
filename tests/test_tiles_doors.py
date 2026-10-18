"""The atlas door requests exercise real commands, geometry, loot and saves."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import DoorSpec
from tuidungeon.domain.actions import SpellSource
from tuidungeon.domain.tags import interaction_tags
from tuidungeon.presentation.tui import Controller, View, popup_content, render
from tuidungeon.world.maps import Position


class AtlasDoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def engine(self):
        return SessionFactory(self.store).session(
            "tiles:doors_lab", character_class="dev:empty_tester", seed=42
        )

    def near(self, e, identifier):
        d = e._door(identifier)
        e.state.position = Position(d.placement.x - 1, d.placement.y)
        return d.door

    def supplies(self, e):
        c = next(c for c in e.state.level.containers if c.placement.id == "supplies")
        e.state.hero.inventory.extend(c.items)
        c.items.clear()

    def reload(self, e):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "doors.json")
            repo.save(e)
            return repo.load(store=self.store)

    def test_unique_door_cannot_be_bypassed_and_survives_save(self):
        e = self.engine()
        door = self.near(e, "door_golden")
        for action in (
            "open",
            "force",
            "pick",
            "attack",
            "acid",
            "ignite",
            "daylight",
            "dismantle",
            "use_key",
        ):
            self.assertFalse(e.interact("door_golden", action).performed, action)
        self.assertEqual(e.state.turns, 0)
        self.assertNotIn("destructible", interaction_tags(door))
        for kind in ("physical", "acid", "fire", "bludgeoning", "force"):
            self.assertEqual(e.damage_cell(Position(4, 4), 999, kind), 0)
        self.assertFalse(door.force_open())
        self.assertFalse(door.daylight())
        self.supplies(e)
        self.assertTrue(e.interact("door_golden", "use_key").performed)
        self.assertTrue(e.interact("door_golden", "open").performed)
        e = self.reload(e)
        door = e._door("door_golden").door
        self.assertEqual((door.access, door.key_code), ("unique_key", "GOLD0442"))
        self.assertTrue(door.passable)
        self.assertTrue(e.interact("door_golden", "close").performed)

    def test_magic_spell_scroll_and_mechanism(self):
        e = self.engine()
        self.supplies(e)
        door = self.near(e, "door_magic_field")
        spell = e.catalog.spells["tiles:dispel_magic"]
        scroll = next(i for i in e.state.hero.inventory if i.definition.cast_spell)
        source = "scroll:" + scroll.instance_id
        before = e.state.turns, scroll.charges
        self.assertFalse(e.cast_spell(spell.id, source, Position(4, 4)).performed)
        self.assertEqual((e.state.turns, scroll.charges), before)
        for action in ("open", "use_key", "pick", "force", "attack", "daylight"):
            self.assertFalse(e.interact("door_magic_field", action).performed)
        self.assertEqual(e.damage_cell(Position(8, 4), 999, "acid"), 0)
        self.assertTrue(e.interact("door_magic_field", "dispel").performed)
        self.assertTrue(door.passable)
        self.assertFalse(e.state.level.terrain.blocks_sight[4][8])
        self.assertNotIn(scroll, e.state.hero.inventory)
        before = e.state.turns
        self.assertFalse(e.interact("door_magic_field", "dispel").performed)
        self.assertEqual(e.state.turns, before)
        e.state.position = Position(10, 12)
        self.assertIn("lever", [o.placement.id for o in e.nearby_points()])
        self.assertTrue(e.interact("lever", "activate_mechanism").performed)
        self.assertTrue(e._door("magic_mechanism").door.opened)
        e = self.reload(e)
        self.assertTrue(e._door("magic_mechanism").door.passable)
        self.assertEqual(e._door("magic_mechanism").door.access, "magic")
        self.assertFalse(e.interact("lever", "activate_mechanism").performed)

        # The same handler spends a class slot when no scroll is used.
        e = self.engine()
        self.near(e, "door_magic_field")
        hero = e.state.hero
        hero.class_spells = (*hero.class_spells, spell)
        hero.spell_slots[3] = 1
        self.assertTrue(
            e.cast_spell(spell.id, SpellSource.CLASS, Position(8, 4)).performed
        )
        self.assertEqual(hero.spell_slots[3], 0)
        e._door("door_magic_field").door.opened = False
        self.supplies(e)
        self.assertTrue(e.interact("door_magic_field", "dispel").performed)
        self.assertEqual(hero.spell_slots[3], 0)

    def test_glass_break_chance_single_loot_and_floor_preserved(self):
        for roll, hardware in ((1, 1), (100, 0)):
            e = self.engine()
            door = self.near(e, "door_glass")
            self.assertFalse(door.opaque)
            self.assertIn("glass", interaction_tags(door))
            self.assertFalse(door.passable)
            self.assertEqual(e.damage_cell(Position(20, 4), 4), 4)
            self.assertFalse(door.destroyed)
            with patch.object(e.dice, "roll", return_value=[roll]):
                self.assertEqual(e.damage_cell(Position(20, 4), 1), 1)
            drops = Counter(i.id for p, i in e.state.items if (p.x, p.y) == (20, 4))
            self.assertEqual(drops["tiles:glass_shards"], 2)
            self.assertEqual(drops["furniture_hardware"], hardware)
            self.assertEqual(e.state.level.terrain.tiles[4][20], "base:floor")
            self.assertTrue(e.state.walkable(Position(20, 4)))
            e = self.reload(e)
            before = len(e.state.items)
            e.damage_cell(Position(20, 4), 999)
            e.collect_door_remains()
            self.assertEqual(len(e.state.items), before)

    def test_glass_dismantle_pause_save_and_whole_sheets(self):
        e = self.engine()
        self.near(e, "glass_dismantle")
        self.assertTrue(e.interact("glass_dismantle", "dismantle").performed)
        self.assertTrue(e.advance_craft().performed)
        self.assertTrue(e.pause_craft().performed)
        e = self.reload(e)
        self.assertEqual(e.state.level.object_states["glass_dismantle"].progress, 1)
        self.assertTrue(e.interact("glass_dismantle", "dismantle").performed)
        for _ in range(2):
            self.assertTrue(e.advance_craft().performed)
        self.assertIsNone(e._door("glass_dismantle"))
        drops = Counter(i.id for p, i in e.state.items if (p.x, p.y) == (8, 13))
        self.assertEqual(
            drops, Counter({"tiles:glass_sheet": 2, "furniture_hardware": 1})
        )
        self.assertEqual(e.state.turns, 3)
        self.assertEqual(e.state.level.terrain.tiles[13][8], "base:floor")
        e = self.reload(e)
        self.assertIsNone(e._door("glass_dismantle"))

    def test_transition_requires_explicit_open_and_does_not_retrigger_on_step(self):
        e = self.engine()
        door = self.near(e, "door_dungeon")
        before = e.state.turns
        result = e.interact("door_dungeon", "open")
        self.assertFalse(result.performed)
        self.assertIn("Подтвердите", result.message)
        self.assertEqual(e.state.turns, before)
        destination = door.destination
        door.destination = None
        self.assertFalse(e.interact("door_dungeon", "open_transition").performed)
        self.assertFalse(door.opened)
        door.destination = destination
        self.assertTrue(e.interact("door_dungeon", "open_transition").performed)
        self.assertEqual(e.state.level.ref, "tiles:doors_annex")
        self.assertEqual(e.state.turns, before + 1)
        self.near(e, "return")
        self.assertTrue(e.interact("return", "open_transition").performed)
        e = self.reload(e)
        self.assertEqual(e.state.level.ref, "tiles:doors_lab")
        self.near(e, "door_dungeon")
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertEqual(e.state.level.ref, "tiles:doors_lab")
        self.assertFalse(e.interact("door_dungeon", "open_transition").performed)

    def test_variants_curtain_symbols_and_prison(self):
        e = self.engine()
        for instance in e.state.level.doors:
            d = instance.door
            p = instance.placement
            self.assertFalse(e.state.walkable(Position(p.x, p.y)))
            if d.access == "normal" and not d.travel:
                d.locked = False
                self.near(e, p.id)
                self.assertTrue(e.interact(p.id, "open").performed)
                self.assertTrue(e.state.walkable(Position(p.x, p.y)))
                cells = e.state.level.render_cells(e.state)
                self.assertEqual(
                    cells[p.y][p.x].symbol, instance.definition.state_symbols["open"]
                )
        curtain = Position(16, 13)
        self.assertTrue(e.state.walkable(curtain))
        self.assertTrue(e.state.level.terrain.blocks_sight[13][16])
        self.assertEqual(e._door("door_prison").door.max_hp, 100)
        self.assertFalse(e._door("door_slotted").door.opaque)
        self.assertFalse(e._door("door_window").door.opaque)

    def test_authoring_validation_and_mechanism_refusal_are_free(self):
        for data in (
            {"access": "unique_key"},
            {"access": "magic", "locked": True},
            {"destination": "tiles:doors_lab"},
        ):
            with self.assertRaises(ValidationError):
                DoorSpec.model_validate(data)
        e = self.engine()
        level = e.state.level
        lever = next(p for p in level.definition.objects if p.id == "lever")
        bad = lever.model_copy(
            update={"overrides": {"mechanism_targets": ["missing_door"]}}
        )
        doc = level.definition.model_copy(
            update={
                "objects": [
                    bad if p.id == "lever" else p for p in level.definition.objects
                ]
            }
        )
        documents = {**self.store.documents, ("maps", "tiles:doors_lab"): doc}
        with self.assertRaises(ContentError):
            self.store.validate_references(documents, self.store.manifests)
        bad = lever.model_copy(
            update={"overrides": {"mechanism_targets": ["door_golden"]}}
        )
        level.definition = level.definition.model_copy(
            update={
                "objects": [
                    bad if p.id == "lever" else p for p in level.definition.objects
                ]
            }
        )
        e.state.position = Position(10, 12)
        self.assertFalse(e.interact("lever", "activate_mechanism").performed)
        self.assertEqual(e.state.turns, 0)

    def test_all_atlas_cells_assigned_and_native_interaction_confirms_transition(self):
        expected = {
            442,
            443,
            444,
            445,
            446,
            447,
            448,
            449,
            450,
            451,
            452,
            496,
            497,
            498,
            499,
            544,
            545,
            548,
            549,
            550,
            551,
            552,
            553,
        }
        cells = set()
        for (category, ref), doc in self.store.documents.items():
            if (
                category != "objects"
                or not ref.startswith("tiles:door_")
                and ref != "tiles:curtain"
            ):
                continue
            for symbol in [doc.symbol, *doc.state_symbols.values()]:
                c, r = self.store.get("symbols", symbol).source.coordinates
                cells.add(r * 49 + c + 1)
        self.assertEqual(cells, expected)
        e = self.engine()
        self.near(e, "door_dungeon")
        c = Controller(
            42,
            store=self.store,
            catalog=e.catalog,
            test_map=True,
            map_ref="tiles:doors_lab",
        )
        c.engine, c.view, c.point_id = e, View.INTERACTION, "door_dungeon"
        self.assertIn("подтвердить переход", "\n".join(popup_content(c)[2]))
        for width, height in [(80, 25), (160, 50)]:
            self.assertEqual(len(render(c, width, height)), height)
        c.handle("1")
        self.assertEqual(e.state.level.ref, "tiles:doors_annex")


if __name__ == "__main__":
    unittest.main()
