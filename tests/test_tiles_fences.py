"""Atlas fences use shared geometry, door rules, work and portable saves."""

from collections import Counter
from copy import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.domain.doors import Door
from tuidungeon.domain.equipment import Equipment
from tuidungeon.world.maps import Position
from tuidungeon.presentation.tui import Controller, View


class TilesFencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        # Studio authors can extend the demo; keep acceptance scenarios isolated.
        cls.store.documents = dict(cls.store.documents)
        document = cls.store.get("maps", "tiles:fences_lab")
        doors = [
            p.model_copy(update={"overrides": {}}) if p.id == "wood_gate" else p
            for p in document.doors
            if not p.id.startswith("copy_")
        ]
        cls.store.documents["maps", "tiles:fences_lab"] = document.model_copy(
            update={"doors": doors}
        )
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session("tiles:fences_lab", seed=42)

    def give(self, ref, quantity=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref]) for _ in range(quantity)
        ]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def near(self, identifier):
        target = self.e.world_work_target(identifier)
        self.e.state.position = Position(target.placement.x - 1, target.placement.y)
        return target

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def finish(self, identifier):
        result = self.e.interact(identifier, "dismantle")
        self.assertTrue(result.performed, result.message)
        turns = self.e.state.turns
        while self.e.active_craft:
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        return self.e.state.turns - turns

    def test_reviewed_symbols_match_atlas_pixels_and_test_map_coverage(self):
        expected = set(range(148, 155)) | set(range(197, 205))
        for n in expected:
            symbol = self.store.get("symbols", f"tiles:cell_{n:04d}")
            original = self.store.get(
                "symbols", f"base:kenney_{(n - 1) % 49}_{(n - 1) // 49}"
            )
            self.assertTrue(symbol.reviewed)
            self.assertEqual(symbol.pixels, original.pixels)
        placements = [
            *self.e.state.level.definition.objects,
            *self.e.state.level.definition.doors,
        ]
        for i, p in enumerate(placements):
            for q in placements[i + 1 :]:
                self.assertGreaterEqual(max(abs(p.x - q.x), abs(p.y - q.y)), 3)
        self.assertEqual(len(placements), 13)
        for category, ref in [
            ("objects", "tiles:metal_fence_low_arch"),
            ("recipes", "tiles:build_metal_fence_low_arch"),
            ("symbols", "tiles:cell_0511"),
        ]:
            self.assertNotIn((category, ref), self.store.documents)

    def test_low_fences_allow_hero_and_high_fences_block_without_blocking_light(self):
        for identifier in ("wood_fence_low", "metal_fence_low"):
            target = self.near(identifier)
            self.assertIn("blocks_domesticated", target.definition.tags)
            self.assertTrue(self.e.apply(Action.EAST).performed)
            self.assertEqual(self.e.state.position.x, target.placement.x)
        for identifier in (
            "wood_fence",
            "wood_fence_cross",
            "metal_fence",
            "metal_fence_damaged",
            "ornate_metal_fence",
        ):
            target = self.near(identifier)
            turns = self.e.state.turns
            self.assertFalse(self.e.apply(Action.EAST).performed)
            self.assertEqual(self.e.state.turns, turns)
            self.assertFalse(
                self.e.state.level.terrain.blocks_sight[target.placement.y][
                    target.placement.x
                ]
            )
        self.assertEqual(self.store.get("objects", "tiles:wood_fence").foreground, 11)
        self.assertEqual(self.store.get("objects", "tiles:metal_fence").foreground, 153)
        self.assertIsNone(self.store.get("objects", "tiles:metal_fence").brush.light)

    def test_dismantling_requires_material_tools_without_proficiency(self):
        self.near("wood_fence")
        self.e.state.hero.inventory.clear()
        self.give("crowbar")
        self.assertFalse(self.e.start_dismantle("wood_fence").performed)
        self.give("carpenter_tools")
        self.assertFalse(self.e.state.hero.tool_proficiencies)
        self.assertEqual(self.finish("wood_fence"), 3)
        self.assertIsNone(self.e.world_object("wood_fence"))
        self.near("metal_fence")
        self.assertFalse(self.e.start_dismantle("metal_fence").performed)
        self.give("tinker_tools")
        self.assertEqual(self.finish("metal_fence"), 3)
        self.assertEqual(
            Counter(i.id for p, i in self.e.state.items if p.x == 11 and p.y == 11)[
                "metal"
            ],
            2,
        )

    def test_gate_transmits_light_and_preserves_color_and_state_across_saves(self):
        self.near("wood_gate")
        gate = self.e._door("wood_gate")
        self.assertFalse(gate.door.passable)
        self.assertFalse(gate.door.opaque)
        self.assertEqual(gate.door.display_color(), 11)
        self.assertTrue(self.e.interact("wood_gate", "open").performed)
        self.assertTrue(gate.door.passable)
        self.reload()
        gate = self.e._door("wood_gate")
        self.assertTrue(gate.door.opened)
        self.assertTrue(gate.door.transmits_light)
        self.assertEqual(gate.door.foreground, 11)
        self.assertTrue(self.e.interact("wood_gate", "close").performed)
        self.assertFalse(gate.door.opaque)
        self.assertEqual(gate.definition.state_symbols["open"], "tiles:cell_0152")

    def test_dismantling_open_gate_and_progress_survive_save_without_duplicate_loot(
        self,
    ):
        self.near("wood_gate_open")
        self.give("carpenter_tools")
        self.assertTrue(self.e.start_dismantle("wood_gate_open").performed)
        self.e.advance_craft()
        self.reload()
        work = self.e.world_workpiece("world:wood_gate_open")
        self.assertEqual((work.work.progress, work.work.total), (1, 3))
        self.assertEqual(self.finish("wood_gate_open"), 2)
        self.assertIsNone(self.e._door("wood_gate_open"))
        self.reload()
        self.assertIsNone(self.e._door("wood_gate_open"))
        self.assertTrue(self.e.state.walkable(Position(11, 16)))
        count = Counter(i.id for p, i in self.e.state.items if (p.x, p.y) == (11, 16))
        self.assertEqual(count, {"wood": 2, "furniture_hardware": 1})
        self.e.collect_door_remains()
        self.assertEqual(
            count,
            Counter(i.id for p, i in self.e.state.items if (p.x, p.y) == (11, 16)),
        )

    def test_grille_cannot_open_or_force_and_bend_uses_dc15_without_crowbar_advantage(
        self,
    ):
        self.near("iron_grille")
        bar = self.give("crowbar")
        bar.equipped = True
        turns = self.e.state.turns
        with patch.object(self.e.dice, "check", wraps=self.e.dice.check) as check:
            for action in ("open", "pick", "force"):
                self.assertFalse(self.e.interact("iron_grille", action).performed)
            self.assertEqual(check.call_count, 0)
            self.assertEqual(self.e.state.turns, turns)
            self.assertTrue(self.e.interact("iron_grille", "bend").performed)
            self.assertEqual(check.call_args.args[1], 15)
            self.assertFalse(check.call_args.kwargs["advantage"])
        choices = {
            c.id
            for c in self.e._door("iron_grille").available_choices(self.e.state.hero)
        }
        self.assertNotIn("force", choices)
        self.assertNotIn("open", choices)
        self.assertIn("dismantle", choices)

    def test_grille_bent_initial_state_and_exact_ten_turn_dismantle(self):
        target = self.near("iron_grille_bent")
        self.assertTrue(target.original.door.passable)
        self.assertIn(
            "dismantle",
            {
                c.id
                for c in self.e.nearby_points()[0].available_choices(self.e.state.hero)
            },
        )
        self.give("tinker_tools")
        self.give("crowbar")
        self.assertEqual(self.finish("iron_grille_bent"), 10)
        self.reload()
        self.assertIsNone(self.e._door("iron_grille_bent"))

    def test_dismantle_pause_and_missing_tool_preserve_progress_without_time(self):
        self.near("iron_grille")
        tool = self.give("tinker_tools")
        self.assertTrue(self.e.start_dismantle("iron_grille").performed)
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertEqual(self.e.world_workpiece("world:iron_grille").work.progress, 1)
        self.e.state.hero.inventory.remove(tool)
        turns = self.e.state.turns
        self.assertFalse(self.e.start_dismantle("iron_grille").performed)
        self.assertEqual(self.e.state.turns, turns)
        self.give("tinker_tools")
        self.assertEqual(self.finish("iron_grille"), 9)

    def test_door_damage_during_work_has_one_hp_source_and_can_interrupt(self):
        self.near("iron_grille")
        self.give("tinker_tools")
        self.assertTrue(self.e.start_dismantle("iron_grille").performed)
        self.e._door("iron_grille").door.apply_acid(9)
        self.assertIsNone(self.e.state.level.object_states["iron_grille"].hp)
        self.e.advance_craft()
        self.assertIsNone(self.e.active_craft)
        self.assertTrue(self.e._door("iron_grille").door.destroyed)
        self.assertNotIn("iron_grille", self.e.state.level.object_states)
        self.reload()
        self.assertIsNone(self.e.world_work_target("iron_grille"))

    def test_overridden_door_hp_and_work_save_independently(self):
        store = copy(self.store)
        store.documents = dict(store.documents)
        raw = store.get("maps", "tiles:fences_lab").model_dump(mode="json")
        raw["doors"][0]["overrides"] = {"brush": {"door": {"hit_points": 40}}}
        store.documents["maps", "tiles:fences_lab"] = type(
            self.e.state.level.definition
        ).model_validate(raw)
        self.store = store
        self.e = SessionFactory(store).session("tiles:fences_lab", seed=42)
        self.near("wood_gate")
        self.give("carpenter_tools")
        self.e.start_dismantle("wood_gate")
        self.e.advance_craft()
        self.e.pause_craft()
        self.e._door("wood_gate").door.take_damage(7, "bludgeoning")
        self.reload()
        self.assertEqual(self.e._door("wood_gate").door.hp, 33)
        self.assertEqual(self.e.world_workpiece("world:wood_gate").work.progress, 1)
        self.assertEqual(self.finish("wood_gate"), 2)

    def test_metal_fences_and_bars_have_no_attack_action_or_hidden_command(self):
        for identifier in (
            "metal_fence",
            "metal_fence_damaged",
            "metal_fence_low",
            "ornate_metal_fence",
            "metal_gate",
            "iron_grille",
        ):
            target = self.near(identifier)
            point = target.original if target.category == "doors" else target
            self.assertFalse(
                {"attack", "break_object"}
                & {c.id for c in point.available_choices(self.e.state.hero)}
            )
            turns = self.e.state.turns
            with patch.object(self.e.dice, "roll", wraps=self.e.dice.roll) as roll:
                result = self.e.interact(
                    identifier,
                    "attack" if target.category == "doors" else "break_object",
                )
                self.assertFalse(result.performed)
                self.assertEqual(roll.call_count, 0)
            self.assertEqual(self.e.state.turns, turns)

    def test_space_opens_gate_in_exploration_and_interaction_with_short_description(
        self,
    ):
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="tiles:fences_lab",
            test_map=True,
        )
        c.engine.state.position = Position(4, 16)
        c.handle("space")
        self.assertTrue(c.engine._door("wood_gate").door.opened)
        self.assertEqual(c.engine.state.turns, 1)
        c.handle("space")
        self.assertFalse(c.engine._door("wood_gate").door.opened)
        self.assertEqual(c.engine.state.turns, 2)
        c.handle("enter")
        self.assertEqual(c.view, View.INTERACTION)
        text = c.engine._door("wood_gate").text
        self.assertNotIn("СЛ", text)
        self.assertNotIn("1d4", text)
        self.assertNotIn("Замок:", text)
        self.assertTrue(
            any(
                "СЛ" in choice.text
                for choice in c.engine._door("wood_gate").available_choices(
                    c.engine.state.hero
                )
            )
        )
        c.handle(" ")
        self.assertTrue(c.engine._door("wood_gate").door.opened)
        self.assertEqual(c.view, View.EXPLORE)
        c.handle("enter")
        c.handle("space")
        self.assertFalse(c.engine._door("wood_gate").door.opened)
        self.assertEqual(c.engine.state.turns, 4)
        c.engine.state.position = Position(4, 20)
        turns = c.engine.state.turns
        c.handle("space")
        self.assertEqual(c.engine.state.turns, turns)
        self.assertFalse(c.engine._door("iron_grille").door.passable)

    def test_space_cannot_close_occupied_gate_or_choose_between_two_doors(self):
        self.near("wood_gate")
        self.assertTrue(self.e.toggle_nearby_door().performed)
        self.e.state.position = Position(5, 16)
        turns = self.e.state.turns
        self.assertFalse(self.e.toggle_nearby_door().performed)
        self.assertTrue(self.e._door("wood_gate").door.opened)
        self.assertEqual(self.e.state.turns, turns)
        self.e.state.position = Position(4, 16)
        original = self.e._door("wood_gate_open")
        original.placement = original.placement.model_copy(update={"x": 4, "y": 15})
        self.e.state.level.doors[:] = list(self.e.state.level.doors)
        self.assertFalse(self.e.toggle_nearby_door().performed)
        self.assertEqual(self.e.state.turns, turns)

    def test_inspection_shows_title_once_including_legacy_duplicate_descriptions(self):
        target = self.near("ornate_metal_fence")
        p = Position(target.placement.x, target.placement.y)
        title = target.definition.name
        lines = self.e.inspect_cell(p)
        self.assertEqual(" ".join(lines).count(title), 1)
        legacy = target.definition.model_copy(
            update={"description": title + ". Старое описание."}
        )
        level = self.e.state.level
        level.definition = level.definition.model_copy(
            update={
                "objects": [
                    row.model_copy(
                        update={"overrides": {"description": legacy.description}}
                    )
                    if row.id == target.placement.id
                    else row
                    for row in level.definition.objects
                ]
            }
        )
        lines = self.e.inspect_cell(p)
        self.assertEqual(" ".join(lines).count(title), 1)
        self.assertIn("Старое описание.", lines)

    def test_acid_has_existing_double_damage_and_releases_passage(self):
        door = Door.from_spec(self.store.get("objects", "tiles:iron_grille").brush.door)
        self.assertEqual(door.apply_acid(6), 12)
        self.assertEqual(door.apply_acid(4), 8)
        self.assertTrue(door.destroyed)
        self.assertTrue(door.passable)

    def test_bridges_are_background_surfaces_without_object_work(self):
        for material in ("wood", "stone"):
            for form in ("suspended", "flat"):
                doc = self.store.get("tiles", f"tiles:{material}_bridge_{form}")
                self.assertTrue(doc.walkable)
                self.assertFalse(doc.blocks_sight)
                self.assertIsNone(doc.brush.door)
                self.assertFalse(hasattr(doc, "destruction"))

    def test_gate_crafting_places_live_door_and_save_preserves_it(self):
        self.e.state.hero.inventory.clear()
        self.give("carpenter_tools")
        self.give("wood", 2)
        self.give("furniture_hardware")
        result = self.e.start_craft("tiles:build_wood_gate", destination=(3, 3))
        self.assertTrue(result.performed, result.message)
        while self.e.active_craft:
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        gate = next(
            d
            for d in self.e.state.level.doors
            if d.placement.x == 3 and d.placement.y == 3
        )
        self.assertFalse(gate.door.passable)
        self.assertFalse(gate.door.opaque)
        identifier = gate.placement.id
        self.reload()
        self.assertTrue(self.e.interact(identifier, "open").performed)
        normal = self.store.get("recipes", "tiles:build_metal_fence").variants[0]
        ornate = self.store.get("recipes", "tiles:build_ornate_metal_fence").variants[0]
        self.assertGreater(ornate.turns, normal.turns)

    def test_gate_has_real_light_transmission_in_dark_level(self):
        store = copy(self.store)
        store.documents = dict(store.documents)
        raw = store.get("maps", "tiles:fences_lab").model_dump(mode="json")
        raw.update(
            ambient_light="dark",
            lights=[
                {"id": "test_light", "x": 4, "y": 16, "radius": 4, "bright_radius": 4}
            ],
        )
        store.documents["maps", "tiles:fences_lab"] = type(
            self.e.state.level.definition
        ).model_validate(raw)
        e = SessionFactory(store).session("tiles:fences_lab", seed=42)
        self.assertGreater(e.lighting.level_at(Position(6, 16)), 0)
        self.assertFalse(e.state.walkable(Position(5, 16)))


if __name__ == "__main__":
    unittest.main()
