"""Shared lock resolution, nearby service art and persistent container state."""

from copy import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import MapDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.locks import LOCK_COLORS, LOCK_DC
from tuidungeon.presentation.tui import Controller, View
from tuidungeon.world.maps import Position


class LockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="locks_test",
            name="Замки",
            width=12,
            height=7,
            tiles=[["base:floor"] * 12 for _ in range(7)],
            walkability=[[True] * 12 for _ in range(7)],
            blocks_sight=[[False] * 12 for _ in range(7)],
            ambient_light="bright",
            spawn={"x": 2, "y": 2},
            doors=[
                dict(
                    id="door",
                    ref="base:door_wood",
                    x=3,
                    y=2,
                    overrides={"brush": {"door": {"locked": True}}},
                )
            ],
            objects=[
                dict(
                    id="box",
                    ref="base:cabinet",
                    x=2,
                    y=3,
                    overrides={
                        "storage": {
                            "personal": True,
                            "lock": {"locked": True, "key_tag": "chest_key"},
                            "contents": [{"item": "base:spellbook", "quantity": 1}],
                        }
                    },
                )
            ],
        )
        self.make()

    def make(self):
        self.store.documents["maps", "base:locks_test"] = MapDocument.model_validate(
            self.raw
        )
        self.e = SessionFactory(self.store).session("base:locks_test", seed=42)
        return self.e

    def box(self):
        return self.e.state.level.containers[0]

    def tools(self, ref="thieves_tools"):
        item = Equipment.create(self.e.catalog.equipment[ref])
        self.e.state.hero.inventory.append(item)
        return item

    def cell(self, x, y):
        return self.e.render_cells((x, y, 1, 1))[0][0]

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_quality_colors_dc_and_complexity_are_shared_by_doors_and_containers(self):
        self.tools()
        for quality, dc in LOCK_DC.items():
            for complexity, turns in [("simple", 1), ("complex", 10)]:
                with self.subTest(quality=quality, complexity=complexity):
                    door = self.e._door("door").door
                    box = self.box().lock
                    for lock in [door, box]:
                        lock.locked = True
                        lock.lock_quality = quality
                        lock.lock_complexity = complexity
                        self.assertEqual((lock.lock_dc, lock.lock_turns), (dc, turns))
                    for p in [(3, 2), (2, 3)]:
                        cell = self.cell(*p)
                        self.assertEqual(cell.foreground, LOCK_COLORS[quality])
                        expected = (
                            self.store.snapshot()
                            .lock_indicator(complexity, "base")[1]
                            .symbol
                        )
                        self.assertEqual(cell.symbol, expected)
                        self.assertTrue(cell.service_indicator)
        self.assertEqual(self.e.state.turns, 0)

    def test_marker_disappears_when_far_or_unlocked_without_changing_geometry(self):
        self.assertTrue(self.cell(3, 2).service_indicator)
        self.assertFalse(self.e.state.walkable(Position(3, 2)))
        self.e.state.position = Position(1, 1)
        self.assertFalse(getattr(self.cell(3, 2), "service_indicator", False))
        self.assertEqual(self.cell(3, 2).symbol, "base:door_wood_closed")
        self.e.state.position = Position(2, 2)
        self.e._door("door").door.locked = False
        self.assertFalse(getattr(self.cell(3, 2), "service_indicator", False))
        self.box().lock.locked = False
        self.assertFalse(getattr(self.cell(2, 3), "service_indicator", False))
        self.assertFalse(self.e.state.walkable(Position(2, 3)))

    def test_diagonal_reach_and_no_reveal_in_darkness(self):
        self.e.state.position = Position(1, 2)
        self.assertTrue(self.cell(2, 3).service_indicator)
        self.raw["ambient_light"] = "dark"
        self.make()
        self.assertFalse(getattr(self.cell(3, 2), "service_indicator", False))
        self.assertFalse(getattr(self.cell(2, 3), "service_indicator", False))
        self.raw["ambient_light"] = "dim"
        self.make()
        self.assertEqual(self.cell(3, 2).foreground, LOCK_COLORS["normal"])

    def test_locked_container_rejects_open_take_and_deposit_without_changing_items(
        self,
    ):
        box = self.box()
        book = box.items[0]
        hero = self.e.state.hero
        before = list(hero.inventory)
        self.assertFalse(self.e.open_container("box").performed)
        self.assertIsNone(self.e.storage_at("box"))
        self.assertFalse(self.e.transfer_storage("box", book.instance_id).performed)
        self.assertFalse(
            self.e.transfer_storage(
                "box", before[0].instance_id, deposit=True
            ).performed
        )
        self.assertEqual(box.items, [book])
        self.assertEqual(hero.inventory, before)
        text = " ".join(self.e.inspect_cell(Position(2, 3)))
        self.assertIn("заперт", text)
        self.assertNotIn("Содержимое:", text)

    def test_simple_pick_needs_tools_and_uses_plain_d20_without_advantage(self):
        self.assertFalse(self.e.interact("box", "pick_container_lock").performed)
        tools = self.tools()
        door_choices = self.e._door("door").available_choices(self.e.state.hero)
        hint = next(choice.text for choice in door_choices if choice.id == "pick")
        self.assertIn("10/10", hint)
        self.assertIn("−1 прочность", hint)
        with (
            patch.object(self.e.dice, "roll", return_value=(20,)),
            patch.object(self.e.dice, "check", wraps=self.e.dice.check) as check,
        ):
            result = self.e.interact("box", "pick_container_lock")
            self.assertTrue(result.performed, result.message)
            self.assertEqual(check.call_args.args[1], 15)
            self.assertFalse(check.call_args.kwargs.get("advantage", False))
        self.assertFalse(self.box().locked)
        self.assertEqual(tools.durability, 10)
        self.assertEqual(self.e.state.turns, 1)
        self.assertTrue(self.e.open_container("box").performed)
        self.assertFalse(getattr(self.cell(2, 3), "service_indicator", False))

    def test_locked_fixture_cannot_bypass_lock_with_take_light(self):
        self.raw["objects"][0] = dict(
            id="box",
            ref="base:torch_wall",
            x=2,
            y=3,
            overrides={"storage": {"lock": {"key_tag": "chest_key"}}},
        )
        self.make()
        choices = self.e.world_object("box").available_choices(self.e.state.hero)
        self.assertIn("pick_container_lock", {choice.id for choice in choices})
        self.assertNotIn("take_light", {choice.id for choice in choices})
        self.assertFalse(self.e.fixture_action("box", "take_light").performed)
        self.tools("chest_key")
        self.assertTrue(self.e.interact("box", "unlock_container_key").performed)
        self.assertTrue(self.e.fixture_action("box", "take_light").performed)

    def test_failed_pick_stays_locked_and_key_is_not_consumed(self):
        tools = self.tools()
        with patch.object(self.e.dice, "roll", return_value=(1,)):
            self.assertTrue(self.e.interact("box", "pick_container_lock").performed)
        self.assertTrue(self.box().locked)
        self.assertEqual(tools.durability, 9)
        self.assertTrue(self.cell(2, 3).service_indicator)
        self.assertFalse(self.e.interact("box", "unlock_container_key").performed)
        key = self.tools("chest_key")
        self.assertTrue(self.e.interact("box", "unlock_container_key").performed)
        self.assertFalse(self.box().locked)
        self.assertIn(key, self.e.state.hero.inventory)

    def test_complex_container_failure_wears_once_and_broken_tools_stay_broken(self):
        self.raw["objects"][0]["overrides"]["storage"]["lock"]["lock_complexity"] = (
            "complex"
        )
        self.make()
        tools = self.tools()
        tools.durability = 1
        self.e.interact("box", "pick_container_lock")
        for _ in range(9):
            self.e.advance_lockpick()
            self.assertEqual(tools.durability, 1)
        with patch.object(self.e.dice, "roll", return_value=(1,)):
            result = self.e.advance_lockpick()
        self.assertIn("0/10", result.message)
        self.assertIn("сломаны", result.message)
        self.assertTrue(self.box().locked)
        self.assertTrue(tools.broken)
        self.reload()
        tools = next(i for i in self.e.state.hero.inventory if i.id == "thieves_tools")
        self.assertEqual(tools.durability, 0)
        before = self.e.state.turns
        self.assertFalse(self.e.interact("box", "pick_container_lock").performed)
        self.assertEqual(self.e.state.turns, before)

    def test_complex_pick_cancel_save_load_and_remaining_turns(self):
        self.raw["objects"][0]["overrides"]["storage"]["lock"]["lock_complexity"] = (
            "complex"
        )
        self.make()
        self.tools()
        result = self.e.interact("box", "pick_container_lock")
        self.assertEqual(result.minutes, 0)
        for _ in range(3):
            self.e.advance_lockpick()
        self.reload()
        self.assertEqual(
            (self.e.lockpick_attempt.target_kind, self.e.lockpick_attempt.progress),
            ("container", 3),
        )
        with patch.object(self.e.dice, "roll", return_value=(20,)):
            for _ in range(7):
                self.assertTrue(self.e.advance_lockpick().performed)
        self.assertFalse(self.box().locked)
        self.assertEqual(self.e.state.turns, 10)
        self.reload()
        self.assertFalse(self.box().locked)
        self.box().lock.locked = True
        self.e.interact("box", "pick_container_lock")
        self.e.advance_lockpick()
        turns = self.e.state.turns
        self.e.cancel_lockpick()
        self.assertTrue(self.box().locked)
        self.assertEqual(self.e.state.turns, turns)

    def test_tool_loss_and_container_destruction_interrupt_work(self):
        self.raw["objects"][0]["overrides"]["storage"]["lock"]["lock_complexity"] = (
            "complex"
        )
        self.make()
        tool = self.tools()
        self.e.interact("box", "pick_container_lock")
        self.e.state.hero.inventory.remove(tool)
        self.assertFalse(self.e.advance_lockpick().performed)
        self.assertIsNone(self.e.lockpick_attempt)
        self.tools()
        self.e.interact("box", "pick_container_lock")
        self.e.damage_world_objects(Position(2, 3), 100, "bludgeoning")
        self.assertFalse(self.e.advance_lockpick().performed)
        self.assertIsNone(self.e.lockpick_attempt)

    def test_lifting_locked_container_preserves_lock_state_and_nested_contents(self):
        self.assertTrue(self.e.lift_furniture("box").performed)
        item = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertTrue(item.furniture.container_spec.lock.locked)
        self.reload()
        item = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertTrue(self.e.place_furniture(item, Position(2, 3)).performed)
        self.assertTrue(self.box().locked)
        self.assertEqual(len(self.box().items), 1)
        self.tools("chest_key")
        self.e.interact("box", "unlock_container_key")
        self.assertTrue(self.e.lift_furniture("box").performed)
        self.reload()
        item = next(i for i in self.e.state.hero.inventory if i.furniture)
        self.assertFalse(item.furniture.container_spec.lock.locked)

    def test_old_save_without_container_lock_state_keeps_old_access(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            data = json.loads(repo.path.read_text())
            data["levels"][0]["containers"]["box"].pop("locked")
            repo.path.write_text(json.dumps(data))
            loaded = repo.load(store=self.store)
            self.assertTrue(loaded.open_container("box").performed)

    def test_controller_opens_lock_dialog_and_uses_existing_progress_hud(self):
        self.raw["doors"] = []
        self.raw["objects"][0]["overrides"]["storage"]["lock"]["lock_complexity"] = (
            "complex"
        )
        self.make()
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="base:locks_test",
            test_map=True,
        )
        c.engine.state.hero.inventory.append(
            Equipment.create(c.engine.catalog.equipment["thieves_tools"])
        )
        c.handle("enter")
        self.assertEqual(c.view, View.INTERACTION)
        point = c.engine.nearby_points()[0]
        choices = point.available_choices(c.engine.state.hero)
        self.assertNotIn("open_storage", {choice.id for choice in choices})
        c.handle(
            str(
                next(
                    i
                    for i, choice in enumerate(choices, 1)
                    if choice.id == "pick_container_lock"
                )
            )
        )
        self.assertIsNotNone(c.engine.lockpick_attempt)
        c.handle("space")
        self.assertEqual(c.engine.lockpick_attempt.progress, 1)
        c.handle("backspace")
        self.assertIsNone(c.engine.lockpick_attempt)

    def test_service_tiles_can_be_replaced_by_pack_and_duplicates_are_rejected(self):
        self.store.documents.pop(("tiles", "tiles:service_lock_simple"), None)
        source = self.store.get("tiles", "base:service_lock_simple")
        self.store.documents["tiles", "tiles:my_lock"] = source.model_copy(
            update={"id": "my_lock"}
        )
        self.store.validate_references(self.store.documents, self.store.manifests)
        self.assertEqual(
            self.store.snapshot().lock_indicator("simple", "base")[0], "tiles:my_lock"
        )
        self.store.documents["tiles", "tiles:duplicate_lock"] = source.model_copy(
            update={"id": "duplicate_lock"}
        )
        with self.assertRaisesRegex(ContentError, "повторный индикатор"):
            self.store.validate_references(self.store.documents, self.store.manifests)


if __name__ == "__main__":
    unittest.main()
