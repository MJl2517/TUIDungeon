"""Signals change the real map, survive saves and never remotely fire a trap."""

from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import Placement, MODELS
from tuidungeon.world.maps import Position
from tuidungeon.presentation.tui import Controller, View, popup_content, render


class MechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()

    def engine(self):
        return SessionFactory(self.store).session(
            "tiles:mechanisms_lab", character_class="dev:empty_tester", seed=42
        )

    def toggle(self, e):
        e.state.position = Position(2, 3)
        result = e.interact_world("lever", "activate_mechanism")
        self.assertTrue(result.performed, result.message)
        self.assertEqual(result.minutes, 1)

    def reload(self, e):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "game.json")
            repo.save(e)
            return repo.load(store=self.store)

    def test_toggle_geometry_light_graphics_and_floor(self):
        e = self.engine()
        level = e.state.level
        original = self.store.get("maps", level.ref).model_dump(mode="json")
        before = level.cells[3][3].symbol
        self.assertFalse(e.state.walkable(Position(7, 3)))
        self.assertFalse(e.state.walkable(Position(17, 3)))
        self.assertTrue(level.terrain.blocks_sight[3][17])
        self.assertEqual(e.lighting.level_at(Position(13, 3)), 1)
        self.toggle(e)
        self.assertNotEqual(level.cells[3][3].symbol, before)
        self.assertTrue(e.state.walkable(Position(7, 3)))
        self.assertTrue(e.state.walkable(Position(17, 3)))
        self.assertFalse(level.terrain.blocks_sight[3][17])
        self.assertEqual(level.cells[3][17].char, ".")
        self.assertEqual(e.lighting.level_at(Position(13, 3)), 2)
        self.assertEqual(e.lighting.level_at(Position(20, 7)), 2)
        self.toggle(e)
        self.assertEqual(level.cells[3][3].symbol, before)
        self.assertFalse(e.state.walkable(Position(17, 3)))
        self.assertEqual(e.lighting.level_at(Position(13, 3)), 1)
        self.assertEqual(
            original, self.store.get("maps", level.ref).model_dump(mode="json")
        )

    def test_plate_is_pressed_only_while_hero_stands_on_it(self):
        e = self.engine()
        e.state.position = Position(2, 7)
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertTrue(e.state.level.object_states["plate"].mechanism_on)
        self.assertTrue(e._door("gate").door.opened)
        e.apply(Action.WAIT)
        self.assertTrue(e._door("gate").door.opened)
        e.apply(Action.WEST)
        self.assertFalse(e.state.level.object_states["plate"].mechanism_on)
        self.assertFalse(e._door("gate").door.opened)

    def test_multiple_sources_are_or_and_survive_reload(self):
        e = self.engine()
        self.toggle(e)
        e.state.position = Position(3, 7)
        e.sync_mechanisms()
        e = self.reload(e)
        self.assertTrue(e.state.level.object_states["plate"].mechanism_on)
        e.apply(Action.WEST)
        self.assertTrue(e._door("gate").door.opened)
        self.toggle(e)
        self.assertFalse(e._door("gate").door.opened)
        e = self.reload(e)
        self.assertFalse(e.state.level.traps[0].triggered)
        self.assertTrue(e.state.level.traps[0].disabled)

    def test_trap_arms_without_firing_and_one_shot_is_not_reset(self):
        e = self.engine()
        trap = e.state.level.traps[0]
        self.assertTrue(trap.disabled)
        self.toggle(e)
        self.assertFalse(trap.disabled)
        self.assertFalse(trap.triggered)
        e.state.position = Position(9, 3)
        e.apply(Action.EAST)
        self.assertTrue(trap.triggered)
        events = sum(event.get("kind") == "trap" for event in e.events)
        self.toggle(e)
        self.toggle(e)
        e.state.position = Position(9, 3)
        e.apply(Action.EAST)
        self.assertEqual(events, sum(event.get("kind") == "trap" for event in e.events))
        e = self.reload(e)
        self.assertTrue(e.state.level.traps[0].triggered)

    def test_closing_waits_for_occupied_cells(self):
        e = self.engine()
        self.toggle(e)
        e.state.position = Position(7, 3)
        e.state.level.object_states["lever"].mechanism_on = False
        e.sync_mechanisms()
        self.assertTrue(e._door("gate").door.opened)
        e.apply(Action.EAST)
        self.assertFalse(e._door("gate").door.opened)
        self.toggle(e)
        e.state.position = Position(17, 3)
        e.state.level.object_states["lever"].mechanism_on = False
        e.sync_mechanisms()
        self.assertTrue(e.state.walkable(e.state.position))
        e.apply(Action.EAST)
        self.assertFalse(e.state.walkable(Position(17, 3)))

    def test_travel_releases_plate_and_preserves_lever(self):
        e = self.engine()
        e.state.position = Position(3, 7)
        e.sync_mechanisms()
        old = e.state
        e._travel_to("base:crypt")
        self.assertFalse(old.level.object_states["plate"].mechanism_on)
        self.assertFalse(old.level.doors[0].door.opened)
        e._travel_to("tiles:mechanisms_lab")
        self.toggle(e)
        e._travel_to("base:crypt")
        e = self.reload(e)
        e._travel_to("tiles:mechanisms_lab")
        self.assertTrue(e._door("gate").door.opened)

    def test_initially_on_and_independent_channels(self):
        e = self.engine()
        level = e.state.level
        lever = level.definition.objects[0]
        level.definition = level.definition.model_copy(
            update={
                "objects": [
                    lever.model_copy(
                        update={
                            "overrides": {
                                "mechanism": {"initially_on": True},
                                "mechanism_targets": ["gate"],
                            }
                        }
                    ),
                    *level.definition.objects[1:],
                ]
            }
        )
        level.object_states.clear()
        e.sync_mechanisms()
        self.assertTrue(e._door("gate").door.opened)
        self.assertEqual(e.lighting.level_at(Position(13, 3)), 1)

    def test_invalid_links_codes_and_legacy_compatibility(self):
        original = self.store.get("maps", "tiles:mechanisms_lab")
        for target in ("missing", "lever"):
            raw = original.model_dump(mode="json")
            raw["objects"][0]["overrides"]["mechanism_targets"] = [target]
            doc = MODELS["maps"].model_validate(raw)
            candidate = dict(self.store.documents)
            candidate["maps", "tiles:mechanisms_lab"] = doc
            with self.assertRaises(ContentError):
                PackStore.validate_references(candidate, self.store.manifests)
        with self.assertRaises(ValueError):
            Placement(id="x", ref="tiles:pressure_plate", activation_code="bad code")
        e = SessionFactory(self.store).session(
            "tiles:doors_lab", character_class="dev:empty_tester", seed=42
        )
        # Old open-only levers retain their semantics (also covered by test_tiles_doors).
        self.assertTrue(
            any(
                o.definition.mechanism_targets and not o.definition.mechanism
                for o in e.world_objects()
            )
        )

    def test_native_interaction_and_atlas_states(self):
        c = Controller(
            seed=42,
            store=self.store,
            map_ref="tiles:mechanisms_lab",
            test_map=True,
            test_class="dev:empty_tester",
        )
        c.handle("enter")
        self.assertIs(c.view, View.INTERACTION)
        self.assertIn("Включить рычаг", popup_content(c)[2])
        c.handle("1")
        self.assertTrue(c.engine._door("gate").door.opened)
        self.assertEqual(len(render(c, 60, 20)), 20)
        lever = self.store.get("objects", "tiles:signal_lever")
        plate = self.store.get("objects", "tiles:pressure_plate")
        self.assertEqual(
            set(lever.state_symbols.values()) | set(plate.state_symbols.values()),
            {f"tiles:cell_{n:04}" for n in range(492, 496)},
        )

    def test_plate_arms_trap_before_entry_processing(self):
        e = self.engine()
        level = e.state.level
        trap = level.traps[0]
        trap.placement = trap.placement.model_copy(update={"x": 3, "y": 7})
        level.definition = level.definition.model_copy(
            update={"traps": [trap.placement]}
        )
        e.state.position = Position(2, 7)
        e.apply(Action.EAST)
        self.assertTrue(trap.triggered)
        self.assertFalse(trap.disabled)


if __name__ == "__main__":
    unittest.main()
