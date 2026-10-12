"""End-to-end checks for paid crafts, construction, traps and single-use remains."""

from copy import copy
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.application.engine import Action
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.domain.actors import Monster
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import CheckResult
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position


class CraftingExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw.update(ambient_light="bright", lights=[])
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        self.e.state.hero.known_recipes.update(self.e.catalog.recipes)
        self.e.state.hero.tool_proficiencies.update(
            i
            for r in self.e.catalog.recipes.values()
            for v in r.variants
            for i in v.proficiencies
        )
        self.e.state.position = Position(17, 12)

    def add(self, ref, n=1):
        items = [Equipment.create(self.e.catalog.equipment[ref]) for _ in range(n)]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def finish(self):
        for _ in range(20):
            if not self.e.active_craft:
                return
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        self.fail("work did not finish")

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def start(self, ref, **kw):
        result = self.e.start_craft("base:" + ref, **kw)
        self.assertTrue(result.performed, result.message)
        return self.e.active_craft

    def test_barricade_pause_save_geometry_and_no_source_mutation(self):
        source = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        self.add("wood", 3)
        self.assertFalse(
            self.e.start_craft("base:build_barricade", destination=(26, 7)).performed
        )
        self.assertEqual(self.e.state.turns, 0)
        work = self.start("build_barricade", destination=(18, 12))
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        self.assertFalse(self.e.state.walkable(Position(18, 12)))
        self.assertTrue(self.e.state.level.terrain.blocks_sight[12][18])
        self.reload()
        self.assertFalse(self.e.state.walkable(Position(18, 12)))
        self.e.damage_world_objects(Position(18, 12), 100, "fire")
        self.assertTrue(self.e.state.walkable(Position(18, 12)))
        self.assertEqual(self.e.state.level.definition.tiles[12][18], "base:floor")
        self.assertEqual(
            self.store.get("maps", "dev:crafting_lab").model_dump(mode="json"), source
        )

    def test_trap_disarm_dismantle_craft_install_trigger_and_save(self):
        self.e.state.position = Position(29, 7)
        self.add("tinker_tools")
        self.assertFalse(self.e.start_dismantle("lab_improvised_trap").performed)
        with patch.object(self.e.dice, "check", return_value=CheckResult(20, 0, 10)):
            self.assertTrue(self.e.interact("lab_improvised_trap", "disarm").performed)
        self.reload()
        trap = next(
            t
            for t in self.e.state.level.traps
            if t.placement.id == "lab_improvised_trap"
        )
        self.assertTrue(trap.disabled)
        self.assertTrue(self.e.start_dismantle(trap.placement.id).performed)
        self.finish()
        self.assertFalse(self.e.start_dismantle(trap.placement.id).performed)
        self.start(
            "craft_trap"
        )  # Inputs come directly from the dismantled trap on the ground.
        self.finish()
        kit = next(i for i in self.e.state.hero.inventory if i.id == "trap_kit")
        self.start("install_trap", destination=(28, 7))
        self.assertNotIn(kit, self.e.state.hero.inventory)
        self.finish()
        self.reload()
        built = next(
            t
            for t in self.e.state.level.traps
            if t.placement.x == 28 and t.placement.y == 7
        )
        self.assertFalse(built.disabled)
        hp = self.e.state.hero.hp
        with patch.object(self.e.dice, "check", return_value=CheckResult(1, 0, 12)):
            self.assertTrue(self.e.apply(Action.WEST).performed)
        self.assertEqual(self.e.state.hero.hp, hp - 3)
        self.assertTrue(built.triggered)

    def test_disarm_missing_tool_darkness_and_explicit_failure(self):
        self.e.state.position = Position(29, 7)
        self.assertFalse(self.e.interact("lab_improvised_trap", "disarm").performed)
        self.assertEqual(self.e.state.turns, 0)
        self.assertFalse(self.e.interact("lab_improvised_trap", "disarm").performed)
        self.add("improvised_lockpicks")
        hp = self.e.state.hero.hp
        with patch.object(self.e.dice, "check", return_value=CheckResult(1, 0, 10)):
            result = self.e.interact("lab_improvised_trap", "disarm")
        self.assertTrue(result.performed)
        self.assertIn("Провал", result.message)
        self.assertEqual(self.e.state.hero.hp, hp - 3)
        self.assertFalse(self.e.world_object("lab_improvised_trap").original.disabled)
        self.e.state.level.definition = self.e.state.level.definition.model_copy(
            update={"ambient_light": "dark"}
        )
        before = self.e.state.turns
        self.assertFalse(self.e.interact("lab_improvised_trap", "disarm").performed)
        self.assertEqual(self.e.state.turns, before)

    def test_door_brace_identity_open_close_destroy_and_save(self):
        self.e.state.position = Position(29, 3)
        stake = self.add("stake")
        stake.wear(2)
        identifier = stake.instance_id
        self.assertTrue(self.e.interact("lab_brace_door", "brace").performed)
        self.assertNotIn(stake, self.e.state.hero.inventory)
        self.assertFalse(self.e.interact("lab_brace_door", "open").performed)
        self.reload()
        self.assertEqual(self.e._door("lab_brace_door").brace.instance_id, identifier)
        self.assertTrue(self.e.interact("lab_brace_door", "unbrace").performed)
        stake = next(
            i for i in self.e.state.hero.inventory if i.instance_id == identifier
        )
        self.assertEqual(stake.durability, 8)
        self.assertTrue(self.e.interact("lab_brace_door", "open").performed)
        self.assertTrue(self.e.interact("lab_brace_door", "brace").performed)
        self.assertFalse(self.e.interact("lab_brace_door", "close").performed)
        door = self.e._door("lab_brace_door")
        door.door.hp = 0
        self.e.collect_door_remains()
        self.e.collect_door_remains()
        self.assertEqual(
            sum(i.instance_id == identifier for _, i in self.e.state.items), 1
        )
        self.reload()
        self.assertIsNone(self.e._door("lab_brace_door").brace)

    def test_ram_advantage_and_pole_reach_requires_clear_cell(self):
        self.e.state.position = Position(29, 3)
        self.add("battering_ram").equipped = True
        with patch.object(
            self.e.dice, "check", return_value=CheckResult(1, 0, 10)
        ) as check:
            self.e.interact("lab_brace_door", "force")
            self.assertTrue(check.call_args.kwargs["advantage"])
        self.e.state.hero.inventory.clear()
        self.e.state.position = Position(20, 7)
        self.assertFalse(self.e.start_dismantle("lab_branches").performed)
        pole = self.add("wooden_pole")
        pole.equipped = True
        original = self.e.state.level.definition
        raw = original.model_dump(mode="json")
        raw["walkability"][7][21] = False
        self.e.state.level.definition = MapDocument.model_validate(raw)
        self.assertFalse(self.e.start_dismantle("lab_branches").performed)
        self.e.state.level.definition = original
        self.assertTrue(self.e.start_dismantle("lab_branches").performed)
        self.assertEqual(self.e.world_object("lab_branches").state.total, 1)
        self.finish()
        self.assertIsNone(self.e.world_object("lab_branches"))

    def test_barricade_burns_lights_extinguishes_and_preserves_floor(self):
        self.store.documents["maps", "dev:crafting_lab"] = self.store.get(
            "maps", "dev:crafting_lab"
        ).model_copy(update={"ambient_light": "dark"})
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        self.e.state.position = Position(25, 7)
        source = self.add("flint_and_steel")
        target = Position(26, 7)
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        self.assertTrue(self.e.ignite_cell(source, target).performed)
        self.assertTrue(self.e.world_object("lab_barricade").state.burning)
        self.assertEqual(self.e.world_object("lab_barricade").state.hp, 25)
        self.assertGreater(self.e.lighting.level_at(self.e.state.position), 0)
        self.reload()
        self.assertTrue(self.e.world_object("lab_barricade").state.burning)
        source = next(
            i for i in self.e.state.hero.inventory if i.id == "flint_and_steel"
        )
        self.assertFalse(self.e.start_dismantle("lab_barricade").performed)
        original = self.e.state
        other = SessionFactory(self.store).state("dev:reading_room", original.hero)
        other.clock = original.clock
        self.e.levels["dev:reading_room"] = other
        self.e.state = other
        self.e.apply(Action.WAIT)
        self.e.state = original
        self.e.levels.pop("dev:reading_room")
        self.assertEqual(self.e.world_object("lab_barricade").state.hp, 20)
        pot = self.add("cooking_pot")
        pot.liquid_kind, pot.liquid_portions = "clean_water", 3
        self.assertTrue(
            self.e.water_action(pot.instance_id, "splash", position=target).performed
        )
        self.assertFalse(self.e.world_object("lab_barricade").state.burning)
        self.assertEqual(self.e.world_object("lab_barricade").state.hp, 20)
        self.assertTrue(self.e.ignite_cell(source, target).performed)
        for _ in range(4):
            self.e.apply(Action.WAIT)
        self.assertIsNone(self.e.world_object("lab_barricade"))
        self.assertTrue(self.e.state.walkable(target))
        self.assertEqual(self.e.state.level.definition.tiles[7][26], "base:floor")
        self.reload()
        self.assertIsNone(self.e.world_object("lab_barricade"))

    def test_bodies_five_turns_or_two_with_knife_and_single_loot(self):
        for identifier, x, fast in (
            ("lab_wolf", 18, False),
            ("lab_snake", 22, True),
            ("lab_spider", 26, True),
        ):
            self.e.state.position = Position(x - 1, 3)
            if fast and not any(i.id == "dagger" for i in self.e.state.hero.inventory):
                self.add("dagger")
            self.assertTrue(self.e.start_dismantle(identifier).performed)
            self.assertEqual(
                self.e.world_object(identifier).state.total, 2 if fast else 5
            )
            self.e.advance_craft()
            self.e.pause_craft()
            self.reload()
            self.assertTrue(self.e.start_dismantle(identifier).performed)
            before = len(self.e.state.items)
            self.finish()
            self.assertGreater(len(self.e.state.items), before)
            self.assertFalse(self.e.start_dismantle(identifier).performed)
            self.reload()
            self.assertIsNone(self.e.world_object(identifier))
            self.assertTrue(self.e.state.walkable(Position(x, 3)))
            self.assertEqual(self.e.state.level.definition.tiles[3][x], "base:floor")

    def test_venom_requires_kit_proficiency_and_cancel_refunds(self):
        gland = self.add("poison_gland")
        self.assertFalse(self.e.start_craft("base:extract_venom").performed)
        kit = self.add("poisoner_kit")
        self.e.state.hero.tool_proficiencies.remove("poisoner_kit")
        self.assertFalse(self.e.start_craft("base:extract_venom").performed)
        self.assertIn(gland, self.e.state.hero.inventory)
        self.assertEqual(self.e.state.turns, 0)
        self.e.state.hero.learn_tool_proficiency("poisoner_kit")
        work = self.start("extract_venom")
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertTrue(self.e.cancel_craft(work).performed)
        self.assertIn(gland, self.e.state.hero.inventory)
        self.assertIn(kit, self.e.state.hero.inventory)
        self.start("extract_venom")
        self.finish()
        self.assertEqual(
            sum(i.id == "simple_poison" for i in self.e.state.hero.inventory), 1
        )

    def test_weapon_poison_pause_save_stacks_miss_and_hit_once(self):
        weapon = self.add("dagger")
        other = self.add("dagger")
        self.add("simple_poison")
        self.add("poisoner_kit")
        work = self.start("coat_weapon", target=weapon.instance_id)
        self.e.pause_craft()
        self.assertIn(weapon, self.e.state.hero.inventory)
        self.assertEqual(weapon.poison_damage, 0)
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        self.assertEqual(weapon.poison_damage, 2)
        from tuidungeon.domain.tags import interaction_tags

        self.assertIn("poison", interaction_tags(weapon))
        self.assertEqual(len(item_stacks([weapon, other])), 2)
        identifier = weapon.instance_id
        self.reload()
        weapon = next(
            i for i in self.e.state.hero.inventory if i.instance_id == identifier
        )
        self.assertEqual(weapon.poison_damage, 2)
        weapon.equipped = True
        target = Monster.create("goblin", catalog=self.e.catalog)
        target.hp = 100
        with patch.object(self.e.dice, "check", return_value=CheckResult(1, 0, 20)):
            self.assertFalse(self.e.state.hero.attack(target, self.e.dice).success)
        self.assertEqual(weapon.poison_damage, 2)
        with patch.object(self.e.dice, "check", return_value=CheckResult(20, 0, 1)):
            result = self.e.state.hero.attack(target, self.e.dice)
        self.assertTrue(result.success)
        self.assertEqual(weapon.poison_damage, 0)
        self.assertEqual(result.effects[-1].damage_type, "poison")

    def test_jeweler_appraisal_persists_on_exact_item_and_not_definition(self):
        gem = self.add("uncut_gem", 2)
        self.add("jeweler_tools")
        self.assertNotIn("25", gem.name)
        self.start("appraise_gem", target=gem.instance_id)
        self.finish()
        self.assertIn("25 зол.", gem.name)
        self.assertEqual(
            len(
                item_stacks(
                    [i for i in self.e.state.hero.inventory if i.id == "uncut_gem"]
                )
            ),
            2,
        )
        self.reload()
        self.assertEqual(sum(i.appraised for i in self.e.state.hero.inventory), 1)
        self.assertFalse(
            Equipment.create(self.e.catalog.equipment["uncut_gem"]).appraised
        )

    def test_save_rejects_duplicate_brace_and_invalid_poison(self):
        self.e.state.position = Position(29, 3)
        self.add("stake")
        self.assertTrue(self.e.interact("lab_brace_door", "brace").performed)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            brace = next(
                level["door_braces"]["lab_brace_door"]
                for level in raw["levels"]
                if "lab_brace_door" in level["door_braces"]
            )
            raw["hero"]["inventory"].append(brace)
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                repo.load(store=self.store)
            self.add("wood").poison_damage = 2
            repo.save(self.e)
            with self.assertRaises(ValueError):
                repo.load(store=self.store)

    def test_native_disarm_and_work_controls(self):
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        self.e.state.position = Position(29, 7)
        self.add("tinker_tools")
        with patch.object(self.e.dice, "check", return_value=CheckResult(20, 0, 10)):
            self.assertTrue(self.e.interact("lab_improvised_trap", "disarm").performed)
        self.assertTrue(
            next(
                t
                for t in self.e.state.level.traps
                if t.placement.id == "lab_improvised_trap"
            ).disabled
        )
        c = Controller(42, store=self.store, catalog=self.e.catalog)
        c.engine, c.view = self.e, View.EXPLORE
        self.assertTrue(self.e.start_dismantle("lab_improvised_trap").performed)
        turns = self.e.state.turns
        c.handle(" ")
        self.assertEqual(self.e.state.turns, turns + 1)
        c.handle("escape")
        self.assertIsNone(self.e.active_craft)
        for w, h in ((80, 24), (140, 40)):
            rows = render(c, w, h)
            self.assertEqual(len(rows), h)
            self.assertTrue(all(len(row) == w for row in rows))


if __name__ == "__main__":
    unittest.main()
