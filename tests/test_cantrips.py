"""Charges, cast validation, timed world effects and reproducible spell rolls."""

from dataclasses import replace
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tuidungeon.application.creation import CharacterCreation, CreationStep
from tuidungeon.application.engine import Engine, Action
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.catalog import default_catalog
from tuidungeon.content.schemas import SpellDocument
from tuidungeon.domain.actors import Hero
from tuidungeon.domain.actions import ActionContext, SpellSource, scaled_spell_effects
from tuidungeon.domain.damage import DamageProfile
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import Dice
from tuidungeon.domain.spellcasting import world_spell_parameters
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.menus import ActionMenu
from tuidungeon.presentation.inventory import InventoryBrowser, item_details
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.tui import Controller, View, render, popup_content
from tuidungeon.world.maps import Position, DungeonMap
from tuidungeon.world.state import GameState


class CantripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = default_catalog()

    def engine(self, choices=("light", "fire_bolt", "mending"), seed=4):
        hero = Hero.create(
            "dwarf",
            "wizard",
            Stats((12, 12, 14, 16, 10, 10)),
            catalog=self.catalog,
            cantrips=choices,
        )
        return Engine(
            GameState(hero, DungeonMap((".........",) * 9), Position(4, 4)),
            random.Random(seed),
        )

    def cast(self, engine, identifier, target=None, **kwargs):
        return engine.cast_spell(identifier, SpellSource.CLASS, target, **kwargs)

    def test_class_choice_requires_exact_unique_allowed_cantrips(self):
        for choices in (
            ("light",),
            ("light", "light", "mending"),
            ("light", "mending", "magic_missile"),
        ):
            with self.assertRaises(ValueError):
                self.engine(choices)
        self.assertEqual(
            len([s for s in self.engine().state.hero.known_spells if s.level == 0]), 3
        )

    def test_charges_use_score_slots_and_racial_resources_are_independent(self):
        e = self.engine()
        h = e.state.hero
        self.assertEqual((h.cantrip_uses, h.max_cantrip_uses), (16, 16))
        self.assertTrue(self.cast(e, "light", h.inventory[0]).performed)
        self.assertEqual(
            (h.cantrip_uses, h.spell_slots, e.state.turns), (15, {1: 2}, 1)
        )
        h.consume_class_slot("detect_magic")
        e.apply(Action.SHORT_REST)
        self.assertEqual((h.cantrip_uses, h.spell_slots[1]), (16, 1))
        h.cantrip_uses = 1
        e.apply(Action.REST)
        self.assertEqual((h.cantrip_uses, h.spell_slots[1]), (16, 2))

    def test_short_rest_nonpositive_modifier_does_not_spend_charges(self):
        e = self.engine()
        e.state.hero.stats = Stats((10, 10, 10, 8, 10, 10))
        e.state.hero.cantrip_uses = 3
        e.apply(Action.SHORT_REST)
        self.assertEqual(e.state.hero.cantrip_uses, 3)

    def test_invalid_or_exhausted_cast_does_not_roll_or_advance_time(self):
        e = self.engine()
        before = e.dice.rng.getstate()
        for identifier, target in (
            ("light", None),
            ("mending", e.state.hero.inventory[0]),
            ("fire_bolt", Position(8, 8)),
            ("missing", None),
        ):
            self.assertFalse(self.cast(e, identifier, target).performed)
        e.state.hero.cantrip_uses = 0
        self.assertFalse(self.cast(e, "light", e.state.hero.inventory[0]).performed)
        self.assertEqual((e.state.turns, e.dice.rng.getstate()), (0, before))

    def test_light_follows_item_drop_recast_and_expires_after_ten_subsequent_turns(
        self,
    ):
        e = self.engine()
        first, second = e.state.hero.inventory[:2]
        self.cast(e, "light", first)
        self.assertIn("glowing", first.tags)
        self.assertEqual(first.glow.remaining_turns, 10)
        self.assertEqual(e.magic_effects[0].turns, 10)
        self.assertEqual(e.lighting.level_at(Position(6, 4)), 2)
        self.assertIs(e.lighting, e.lighting)
        e.place_item(first, e.state.position)
        e.apply(Action.EAST)
        self.assertEqual(e.magic_lights()[0][0], Position(4, 4))
        self.assertIn("Свечение", "\n".join(e.inspect_cell(Position(4, 4))))
        self.cast(e, "light", second)
        self.assertIsNone(first.glow)
        self.assertNotIn("glowing", first.tags)
        self.assertIn("glowing", second.tags)
        self.assertEqual(len(e.magic_effects), 1)
        self.assertEqual(e.magic_lights()[0][0], e.state.position)
        for _ in range(9):
            e.apply(Action.WAIT)
        self.assertEqual(e.magic_effects[0].turns, 1)
        e.apply(Action.WAIT)
        self.assertFalse(e.magic_effects)
        self.assertIsNone(second.glow)
        self.assertNotIn("glowing", second.tags)
        self.assertEqual(e.lighting.level_at(Position(6, 4)), 0)

    def test_light_property_is_visible_searchable_and_does_not_change_template_or_stack(self):
        e = self.engine()
        hero = e.state.hero
        item = hero.inventory[0]
        twin = Equipment.create(item.definition)
        twin.equipped = item.equipped
        hero.inventory.append(twin)
        self.assertEqual(len(item_stacks([item, twin])), 1)
        self.cast(e, "light", item)
        self.assertNotIn("glowing", item.definition.tags)
        self.assertIsNone(twin.glow)
        self.assertEqual(len(item_stacks([item, twin])), 2)
        self.assertIn("[свет:10]", item_stacks([item])[0].label)
        details = "\n".join(item_details(item))
        for text in ("glowing", "Свечение (Свет)", "осталось 10 ход.", "яркий радиус 3", "общий 6 кл."):
            self.assertIn(text, details)
        browser = InventoryBrowser(query="свечение")
        self.assertEqual([row.item for row in browser.rows(hero) if row.item], [item])
        e.apply(Action.WAIT)
        self.assertEqual(item.glow.remaining_turns, 9)
        e.apply(Action.REST)
        self.assertIsNone(item.glow)
        self.assertNotIn("glowing", item.tags)
        self.assertEqual(browser.rows(hero), [])
        self.assertEqual(len(item_stacks([item, twin])), 1)

    def test_light_tags_and_property_are_rebuilt_for_ground_item_after_load(self):
        e = self.engine()
        item = e.state.hero.inventory[0]
        self.cast(e, "light", item)
        e.place_item(item, e.state.position)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "ground-glow.json")
            repo.save(e)
            loaded = repo.load(self.catalog)
        restored = next(i for _, i in loaded.state.items if i.instance_id == item.instance_id)
        self.assertEqual(restored.glow, item.glow)
        self.assertIn("glowing", restored.tags)
        with patch.object(loaded, "_find_magic_item", side_effect=AssertionError("Repeated item scan")):
            loaded.magic_lights()
            loaded.apply(Action.WAIT)
        self.assertEqual(restored.glow.remaining_turns, item.glow.remaining_turns - 1)

    def test_light_takes_no_hand_and_menu_navigation_is_free(self):
        e = self.engine()
        h = e.state.hero
        before_hands = h.hands_used
        self.cast(e, "light", h.inventory[0])
        self.assertEqual(h.hands_used, before_hands)
        c = Controller(3)
        c.engine, c.view = e, View.EXPLORE
        before = (e.state.turns, e.state.clock.elapsed_minutes, h.cantrip_uses)
        c.open_magic()
        c.choose_spell(2)
        self.assertEqual(c.action_menu, ActionMenu.SPELL_ITEM)
        c.handle("down")
        c.handle("backspace")
        self.assertEqual(
            (e.state.turns, e.state.clock.elapsed_minutes, h.cantrip_uses), before
        )

    def test_repair_broken_tools_one_and_weapon_d4_without_consuming_slots(self):
        e = self.engine()
        for identifier, before, expected in (("thieves_tools", 0, 1), ("dagger", 1, 5)):
            item = Equipment.create(self.catalog.equipment[identifier])
            e.state.hero.inventory.append(item)
            item.durability = before
            with patch.object(e.dice, "roll", return_value=(4,)):
                self.assertTrue(self.cast(e, "mending", item).performed)
            self.assertEqual(item.durability, min(item.definition.durability, expected))
        self.assertEqual(e.state.hero.spell_slots, {1: 2})

    def test_repair_targets_exclude_indestructible_and_intact_items_but_include_tools(self):
        e = self.engine()
        h = e.state.hero
        tools = [
            Equipment.create(self.catalog.equipment[identifier])
            for identifier in ("crowbar", "thieves_tools", "master_lockpicks")
        ]
        for item in tools:
            item.wear(1)
        tools[1].durability = 0
        intact = Equipment.create(self.catalog.equipment["crowbar"])
        h.inventory.extend([intact, *tools])
        before = (e.state.turns, h.cantrip_uses, e.dice.rng.getstate())
        self.assertEqual(e.spell_item_targets(self.catalog.spells["mending"]), tools)
        self.assertEqual(e.spell_item_targets(self.catalog.spells["light"]), h.inventory)
        for item in h.inventory:
            if item not in tools:
                self.assertFalse(self.cast(e, "mending", item).performed)
        self.assertEqual((e.state.turns, h.cantrip_uses, e.dice.rng.getstate()), before)
        for item in tools:
            durability = item.durability
            self.assertTrue(self.cast(e, "mending", item).performed)
            self.assertEqual(item.durability, durability + 1)
        self.assertEqual(e.spell_item_targets(self.catalog.spells["mending"]), [tools[1]])

    def test_repair_menu_pagination_and_numbers_use_filtered_inventory(self):
        e = self.engine()
        tools = [Equipment.create(self.catalog.equipment["crowbar"]) for _ in range(8)]
        for item in tools:
            item.durability = 0
        e.state.hero.inventory.extend(tools)
        c = Controller(3)
        c.engine, c.view = e, View.EXPLORE
        c.open_magic()
        c.choose_spell(next(i for i, (s, _) in enumerate(c.spell_options) if s.id == "mending"))
        self.assertEqual(c.spell_items, tools)
        self.assertEqual(popup_content(c)[2], ["Ломик (0/5)"] * 6)
        c.handle("pagedown")
        self.assertEqual(c.page, 1)
        self.assertEqual(popup_content(c)[2], ["Ломик (0/5)"] * 2)
        c.handle("2")
        self.assertEqual([i.durability for i in tools], [0] * 7 + [1])
        self.assertEqual(e.state.turns, 1)

    def test_empty_repair_menu_explains_and_does_not_consume_resources(self):
        e = self.engine()
        c = Controller(3)
        c.engine, c.view = e, View.EXPLORE
        c.open_magic()
        c.choose_spell(next(i for i, (s, _) in enumerate(c.spell_options) if s.id == "mending"))
        before = (e.state.turns, e.state.hero.cantrip_uses)
        self.assertEqual(c.spell_items, [])
        self.assertIn("Нет повреждённых предметов с прочностью", "\n".join(popup_content(c)[1]))
        c.handle("pagedown")
        c.handle("1")
        self.assertEqual((c.page, e.state.turns, e.state.hero.cantrip_uses), (0, *before))
        c.handle("backspace")
        self.assertEqual(c.action_menu, ActionMenu.MAGIC)

    def test_projectile_miss_spends_charge_and_hit_uses_type_defenses(self):
        e = self.engine()
        self.cast(e, "light", e.state.hero.inventory[0])
        p = Position(5, 4)
        monster = e.add_monster("goblin", p).monster
        monster.max_hp = monster.hp = 100
        monster.innate_damage_profile = DamageProfile(resistances={"fire"})
        with patch.object(e.dice, "roll", side_effect=[(1,)]):
            result = self.cast(e, "fire_bolt", p)
        self.assertTrue(result.performed)
        self.assertFalse(result.success)
        self.assertEqual(
            (monster.hp, e.state.hero.cantrip_uses, e.state.turns), (100, 14, 2)
        )
        with patch.object(e.dice, "roll", side_effect=[(20,), (9,)]):
            result = self.cast(e, "fire_bolt", p)
        self.assertTrue(result.success)
        self.assertEqual(monster.hp, 96)
        self.assertEqual(result.check.modifier, 5)

    def test_combat_poison_spray_con_save_success_avoids_damage(self):
        e = self.engine(("poison_spray", "toll_the_dead", "acid_splash"))
        h = e.state.hero
        target = e.add_monster("goblin", Position(5, 4)).monster
        ctx = ActionContext(e.dice, target, spell_id="poison_spray")
        with patch.object(e.dice, "roll", side_effect=[(20,)]):
            result = h.perform("magic", ctx, e.actions)
        self.assertFalse(result.success)
        self.assertTrue(result.performed)
        self.assertEqual(result.check.difficulty, 13)
        self.assertEqual(h.cantrip_uses, 15)
        with patch.object(e.dice, "roll", side_effect=[(1,), (6,)]):
            result = h.perform("magic", ctx, e.actions)
        self.assertTrue(result.success)
        self.assertEqual(result.effects[0].damage_type, "poison")

    def test_scaling_and_toll_the_dead_wounded_die(self):
        e = self.engine()
        h = e.state.hero
        target = e.add_monster("goblin", Position(5, 4)).monster
        spell = self.catalog.spells["toll_the_dead"]
        for level, count in ((1, 1), (4, 1), (5, 2), (11, 3), (17, 4)):
            h.level = level
            self.assertEqual(
                scaled_spell_effects(spell, h, target)[0].dice.count, count
            )
        self.assertEqual(scaled_spell_effects(spell, h, target)[0].dice.sides, 8)
        target.hp -= 1
        self.assertEqual(scaled_spell_effects(spell, h, target)[0].dice.sides, 12)

    def test_acid_splash_resolves_two_targets_independently(self):
        e = self.engine(("acid_splash", "light", "mending"))
        a = e.add_monster("goblin", Position(5, 4)).monster
        b = e.add_monster("goblin", Position(5, 5)).monster
        with patch.object(e.dice, "roll", side_effect=[(1,), (3,), (20,)]):
            result = e.state.hero.perform(
                "magic",
                ActionContext(e.dice, a, spell_id="acid_splash", targets=(a, b)),
                e.actions,
            )
        self.assertEqual((a.hp, b.hp), (a.max_hp - 3, b.max_hp))
        self.assertEqual(len(result.effects), 1)
        self.assertEqual(e.state.hero.cantrip_uses, 15)

    def test_concentration_replacement_damage_failure_and_rest(self):
        e = self.engine(("dancing_lights", "light", "mending"))
        self.cast(e, "dancing_lights", Position(5, 4))
        old = e.state.hero.concentration_id
        self.cast(e, "dancing_lights", Position(4, 5))
        self.assertNotEqual(old, e.state.hero.concentration_id)
        self.assertEqual(len(e.magic_effects), 1)
        self.assertEqual(e.magic_effects[0].turns, 5)
        e.state.hero.max_hp = e.state.hero.hp = 100
        with patch.object(e.dice, "roll", return_value=(1,)):
            e.damage_cell(e.state.position, 25, "force")
        self.assertEqual(e.events[-1]["difficulty"], 12)
        self.assertFalse(e.state.hero.concentration_id)
        self.assertFalse(e.magic_lights())
        self.cast(e, "dancing_lights", Position(5, 4))
        e.apply(Action.SHORT_REST)
        self.assertFalse(e.magic_effects)
        self.assertFalse(e.state.hero.concentration_id)

    def test_concentration_uses_actual_damage_and_immunity_never_rolls(self):
        e = self.engine(("dancing_lights", "light", "mending"))
        h = e.state.hero
        self.cast(e, "dancing_lights", Position(5, 4))
        h.innate_damage_profile = DamageProfile(immunities={"fire"})
        with patch.object(e.dice, "roll") as rng:
            e.damage_cell(e.state.position, 100, "fire")
            rng.assert_not_called()
        self.assertTrue(h.concentration_id)
        e.damage_cell(e.state.position, 100, "force")
        self.assertFalse(e.magic_lights())

    def test_hand_brings_light_item_without_second_charge_and_expires(self):
        e = self.engine(("mage_hand", "light", "mending"))
        item = e.state.hero.inventory[0]
        e.place_item(item, e.state.position)
        self.cast(e, "mage_hand", e.state.position)
        charge = e.state.hero.cantrip_uses
        result = e.use_magic_hand(e.state.position)
        self.assertTrue(result.performed)
        self.assertIn(item, e.state.hero.inventory)
        self.assertEqual(e.state.hero.cantrip_uses, charge)
        for _ in range(4):
            e.apply(Action.WAIT)
        self.assertIsNone(e.active_hand)

    def test_saving_choice_charges_light_and_concentration_roundtrips(self):
        e = self.engine(("dancing_lights", "light", "mending"))
        self.cast(e, "light", e.state.hero.inventory[0])
        self.cast(e, "dancing_lights", Position(5, 4))
        with tempfile.TemporaryDirectory() as temp:
            repo = SaveRepository(Path(temp) / "save.json")
            repo.save(e)
            loaded = repo.load(self.catalog)
        self.assertEqual(loaded.state.hero.cantrip_uses, e.state.hero.cantrip_uses)
        self.assertEqual(loaded.state.hero.known_spells, e.state.hero.known_spells)
        self.assertEqual(loaded.magic_effects, e.magic_effects)
        self.assertEqual(loaded.magic_lights(), e.magic_lights())
        self.assertEqual(loaded.state.hero.inventory[0].glow, e.state.hero.inventory[0].glow)
        self.assertIn("glowing", loaded.state.hero.inventory[0].tags)
        self.assertEqual(loaded.dice.rng.getstate(), e.dice.rng.getstate())

    def test_creation_requires_three_choices_and_back_retains_selection(self):
        c = CharacterCreation(Dice(random.Random(1)), self.catalog)
        for number in (1, 2, 1, 2, 1, 2, 3, 4, 5, 6):
            c.select(number)
        self.assertEqual(c.step, CreationStep.CANTRIPS)
        c.select(7)
        self.assertEqual(c.step, CreationStep.CANTRIPS)
        for number in (1, 2, 3, 7):
            c.select(number)
        self.assertEqual(c.step, CreationStep.CONFIRM)
        c.back()
        self.assertEqual(c.cantrips, ["light", "fire_bolt", "mending"])
        c.select(7)
        self.assertEqual(c.select(1).cantrip_uses, c.preview().max_cantrip_uses)

    def test_schema_parameters_are_strict_and_available_to_editor(self):
        schema = SpellDocument.model_json_schema()
        self.assertIn("repair", schema["properties"]["world_effect"]["world_schemas"])
        for raw in (
            dict(
                world_effect="light", world_parameters={"radius": 2, "bright_radius": 3}
            ),
            dict(world_effect="repair", world_parameters={"equipment_dice": "bad"}),
            dict(resolution="save"),
            dict(world_effect="missing"),
        ):
            with self.assertRaises(ValidationError):
                SpellDocument(id="bad", name="Проверка", **raw)

    def test_dancing_lights_can_illuminate_unlit_floor_without_hiding_monster(self):
        e = self.engine(("dancing_lights", "light", "mending"))
        target = Position(7, 4)
        monster = e.add_monster("goblin", target)
        self.assertEqual(e.lighting.at(target), 0)
        self.assertTrue(self.cast(e, "dancing_lights", target).performed)
        self.assertEqual(e.lighting.level_at(target), 1)
        self.assertNotEqual(e.render_cells()[target.y][target.x].char, "*")
        self.assertGreater(monster.monster.hp, 0)

    def test_unimplemented_buffs_are_free_and_illusion_can_emit_noise(self):
        e = self.engine(("minor_illusion", "blade_ward", "true_strike"))
        before = e.dice.rng.getstate()
        for identifier in ("blade_ward", "true_strike"):
            self.assertFalse(self.cast(e, identifier).performed)
            result = e.state.hero.perform(
                "magic", ActionContext(e.dice, spell_id=identifier), e.actions
            )
            self.assertFalse(result.performed)
        self.assertEqual(
            (e.state.turns, e.state.hero.cantrip_uses, e.dice.rng.getstate()),
            (0, 16, before),
        )
        self.assertTrue(
            self.cast(e, "minor_illusion", Position(5, 4), option="noise").performed
        )
        self.assertTrue(any(event["kind"] == "noise" for event in e.events))

    def test_removed_light_item_does_not_make_save_unloadable(self):
        e = self.engine()
        item = e.state.hero.inventory[0]
        self.cast(e, "light", item)
        e.state.hero.inventory.remove(item)
        with tempfile.TemporaryDirectory() as temp:
            repo = SaveRepository(Path(temp) / "save.json")
            repo.save(e)
            loaded = repo.load(self.catalog)
        self.assertFalse(loaded.magic_effects)
        self.assertIsNone(item.glow)

    def test_new_world_mechanic_registers_parameters_and_handler(self):
        from tuidungeon.application.magic import world_spells, Noise
        from tuidungeon.domain.spellcasting import EmptyParameters

        try:
            world_spell_parameters.register("test_noise", EmptyParameters)
            world_spells.register("test_noise", Noise())
            e = self.engine()
            spell = replace(
                self.catalog.spells["light"],
                id="test_spell",
                target="self",
                world_effect="test_noise",
                world_parameters={},
            )
            e.state.hero.class_spells += (spell,)
            self.assertIn(
                "test_noise",
                SpellDocument.model_json_schema()["properties"]["world_effect"][
                    "world_schemas"
                ],
            )
            self.assertTrue(self.cast(e, "test_spell").performed)
        finally:
            world_spell_parameters.models.pop("test_noise", None)
            world_spells.handlers.pop("test_noise", None)

    def test_cursor_cancellation_and_render_do_not_spend_charge(self):
        e = self.engine()
        c = Controller(5)
        c.engine, c.view = e, View.EXPLORE
        c.open_magic()
        c.choose_spell(3)  # fire bolt after the two level-one spells
        self.assertEqual(c.view, View.SPELL_TARGET)
        c.handle("d")
        self.assertIn("применить", "\n".join(render(c, 80, 24)))
        c.handle("backspace")
        self.assertEqual(c.action_menu, ActionMenu.MAGIC)
        self.assertEqual((e.state.turns, e.state.hero.cantrip_uses), (0, 16))


class WorldCantripTests(unittest.TestCase):
    from tests.test_doors import DoorTests

    setup_map = DoorTests.setup_map

    @classmethod
    def setUpClass(cls):
        from tuidungeon.content.packs import PackStore

        cls.source = PackStore()

    def wizard(self, e, choices):
        from tuidungeon.application.factories import SessionFactory

        e.state.hero = SessionFactory(self.store).hero(
            character_class="base:wizard", cantrips=choices
        )

    def test_fire_tag_explicitly_ignites_and_cold_extinguishes(self):
        e = self.setup_map()
        self.wizard(e, ("fire_bolt", "ray_of_frost", "light"))
        target = Position(4, 2)
        original = next(s for s in e.state.hero.class_spells if s.id == "fire_bolt")
        e.state.hero.class_spells = tuple(
            replace(s, tags=frozenset()) if s is original else s
            for s in e.state.hero.class_spells
        )
        with patch.object(e.dice, "roll", side_effect=[(20,), (2,)]):
            e.cast_spell("fire_bolt", SpellSource.CLASS, target)
        self.assertFalse(self.instance.door.burning)
        self.assertEqual(self.instance.door.hp, 13)
        e.state.hero.class_spells = tuple(
            original if s.id == "fire_bolt" else s for s in e.state.hero.class_spells
        )
        with patch.object(e.dice, "roll", side_effect=[(20,), (1,)]):
            e.cast_spell("fire_bolt", SpellSource.CLASS, target)
        self.assertTrue(self.instance.door.burning)
        self.assertEqual(self.instance.door.hp, 7)
        with patch.object(e.dice, "roll", side_effect=[(20,), (1,)]):
            e.cast_spell("ray_of_frost", SpellSource.CLASS, target)
        self.assertFalse(self.instance.door.burning)
        self.assertEqual(self.instance.door.hp, 6)

    def test_hand_opens_unlocked_door_but_cannot_pick_locked_door(self):
        e = self.setup_map(locked=True)
        self.wizard(e, ("mage_hand", "light", "mending"))
        e.cast_spell("mage_hand", SpellSource.CLASS, e.state.position)
        self.assertFalse(e.use_magic_hand(Position(4, 2)).performed)
        self.assertEqual(e.state.turns, 1)
        self.instance.door.locked = False
        self.assertTrue(e.use_magic_hand(Position(4, 2)).performed)
        self.assertTrue(self.instance.door.opened)
        self.assertEqual(e.state.hero.cantrip_uses, e.state.hero.max_cantrip_uses - 1)

    def test_browser_and_engine_share_rolls_costs_and_reset_state(self):
        from tuidungeon.tooling.sessions import TestSession
        from tuidungeon.application.factories import SessionFactory

        self.setup_map()
        options = dict(
            map_ref="base:door_test",
            character_class="base:wizard",
            seed=19,
            cantrips=["light", "fire_bolt", "mending"],
        )
        browser = TestSession(self.store, options)
        engine = SessionFactory(self.store).session(**options)
        for command in ("fire_bolt", "fire_bolt"):
            state = browser.command("cast", spell_id=command, x=4, y=2)
            engine.cast_spell(command, SpellSource.CLASS, Position(4, 2))
            self.assertEqual(state["turns"], engine.state.turns)
            self.assertEqual(
                state["hero"]["cantrip_uses"], engine.state.hero.cantrip_uses
            )
            self.assertEqual(
                browser.engine.state.level.doors[0].door.hp,
                engine.state.level.doors[0].door.hp,
            )
            self.assertEqual(browser.engine.events[-1], engine.events[-1])
        browser.reset()
        self.assertEqual(browser.engine.state.level.doors[0].door.hp, 15)
        self.assertEqual(
            browser.engine.state.hero.cantrip_uses,
            browser.engine.state.hero.max_cantrip_uses,
        )


if __name__ == "__main__":
    unittest.main()
