"""Behavioral tests for content-backed actors, items, actions and situations."""

from dataclasses import replace
import inspect
import random
import unittest

from tuidungeon.application.creation import CharacterCreation, CreationStep
from tuidungeon.application.engine import Action, Engine
from tuidungeon.content.catalog import ContentCatalog
from tuidungeon.domain.actions import ActionContext, ActionRegistry, CharacterAction, ActionOutcome, SpellSource
from tuidungeon.domain.actors import Character, Hero, Monster
from tuidungeon.domain.challenges import Challenge, TextChallenge
from tuidungeon.domain.definitions import EffectSpec
from tuidungeon.domain.effects import EffectHandler, EffectOutcome, EffectRegistry
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import Ability, Dice
from tuidungeon.domain.stats import Stats
from tuidungeon.world.maps import Position


class FixedRng:
    def __init__(self, *values):
        self.values = iter(values)

    def randint(self, low, high):
        value = next(self.values)
        if not low <= value <= high:
            raise AssertionError(f"Scripted dice {value} outside {low}..{high}")
        return value


class ExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = ContentCatalog.load()

    def hero(self, character_class="warrior", race="human", **kwargs):
        return Hero.create(race, character_class, Stats((12, 14, 12, 14, 12, 14)), catalog=self.catalog, **kwargs)

    def item(self, content_id):
        return Equipment.create(self.catalog.equipment[content_id])

    def test_character_and_challenge_are_abstract(self):
        self.assertTrue(inspect.isabstract(Character))
        self.assertTrue(inspect.isabstract(Challenge))
        self.assertIsInstance(self.hero(), Character)
        self.assertIsInstance(Monster.create("goblin", catalog=self.catalog), Character)

    def test_monster_instances_share_template_but_not_runtime_state(self):
        first = Monster.create("goblin", catalog=self.catalog)
        second = Monster.create("goblin", catalog=self.catalog)
        self.assertEqual((first.hp, first.max_hp, first.armor_class, first.speed, first.initiative), (7, 7, 13, 2, 3))
        self.assertEqual(first.modifiers[Ability.STRENGTH], -1)
        self.assertEqual(first.roll_initiative(Dice(FixedRng(10))), 13)
        first.take_damage(3)
        first.conditions["poisoned"] = 2
        self.assertEqual(second.hp, 7)
        self.assertEqual(second.conditions, {})
        self.assertEqual(self.catalog.monsters["goblin"].hit_points, 7)
        self.assertEqual(first.special_actions[0].id, "dirty_strike")

    def test_weight_armor_equipping_breakage_and_repair(self):
        hero = self.hero()
        self.assertEqual(hero.armor_class, 18)
        self.assertEqual(hero.carried_weight, 26.5)
        self.assertEqual(hero.max_carry_weight, 65)
        armor = next(item for item in hero.inventory if item.id == "mail")
        armor.wear(100)
        self.assertTrue(armor.broken)
        self.assertEqual(hero.armor_class, 14)  # Natural 12 plus shield 2.
        self.assertNotIn("metal", hero.tags)
        armor.repair(100)
        self.assertEqual(armor.durability, 80)
        self.assertEqual(hero.armor_class, 18)
        leather = self.item("leather")
        hero.inventory.append(leather)
        self.assertTrue(hero.equip(leather))
        self.assertFalse(armor.equipped)
        self.assertEqual(hero.armor_class, 14)
        self.assertFalse(hero.equip(self.item("shield")))
        hero.carry_per_strength = 1
        self.assertTrue(hero.overloaded)
        for operation in (armor.wear, armor.repair):
            with self.assertRaises(ValueError):
                operation(-1)

    def test_healing_item_limits_hp_and_cannot_be_reused(self):
        hero = self.hero()
        potion = self.item("healing_potion")
        hero.inventory.append(potion)
        hero.hp -= 2
        result = hero.use_item(potion, Dice(FixedRng(4, 4)))
        self.assertEqual((result.performed, result.effects[0].amount, hero.hp), (True, 2, hero.max_hp))
        self.assertEqual(potion.charges, 0)
        self.assertFalse(potion.usable)
        self.assertFalse(hero.use_item(potion, Dice(FixedRng())).performed)
        self.assertEqual(hero.max_hp, self.hero().max_hp)

    def test_damage_heal_and_end_turn_have_defined_bounds(self):
        hero = self.hero()
        self.assertEqual(hero.take_damage(100), hero.max_hp)
        self.assertEqual(hero.hp, 0)
        self.assertEqual(hero.heal(100), hero.max_hp)
        self.assertEqual(hero.hp, hero.max_hp)
        hero.conditions = {"dodging": 1, "poisoned": 3}
        hero.end_turn()
        self.assertEqual(hero.conditions, {"poisoned": 2})
        with self.assertRaises(ValueError):
            hero.take_damage(-1)
        with self.assertRaises(ValueError):
            hero.heal(-1)

    def test_advantage_disadvantage_and_cancellation(self):
        self.assertEqual(Dice(FixedRng(3, 17)).check(10, 12, advantage=True).roll, 17)
        self.assertEqual(Dice(FixedRng(3, 17)).check(10, 12, disadvantage=True).roll, 3)
        result = Dice(FixedRng(10)).check(10, 12, advantage=True, disadvantage=True)
        self.assertEqual(result.rolls, (10,))
        self.assertFalse(result.advantage)
        self.assertFalse(result.disadvantage)

    def test_attack_hits_misses_and_dodge_gives_disadvantage(self):
        hero = self.hero()
        monster = Monster.create("goblin", catalog=self.catalog)
        miss = hero.attack(monster, Dice(FixedRng(1)))
        self.assertTrue(miss.performed)
        self.assertFalse(miss.success)
        self.assertEqual(monster.hp, 7)
        self.assertTrue(monster.dodge(Dice(FixedRng())).performed)
        miss = hero.attack(monster, Dice(FixedRng(20, 1)))
        self.assertTrue(miss.check.disadvantage)
        self.assertFalse(miss.success)
        monster.end_turn()
        hit = hero.attack(monster, Dice(FixedRng(20, 3)))
        self.assertTrue(hit.success)
        self.assertEqual(hit.effects[0].amount, 4)  # Sword 3 plus STR modifier 1.
        self.assertEqual(monster.hp, 3)
        self.assertFalse(hero.attack(monster, Dice(FixedRng()), weapon_id="missing").performed)

    def test_monster_special_attack_applies_condition_only_on_hit(self):
        monster = Monster.create("goblin", catalog=self.catalog)
        hero = self.hero()
        miss = monster.attack(hero, Dice(FixedRng(1)), action_id="dirty_strike")
        self.assertFalse(miss.success)
        self.assertNotIn("poisoned", hero.conditions)
        hit = monster.attack(hero, Dice(FixedRng(20, 2)), action_id="dirty_strike")
        self.assertTrue(hit.success)
        self.assertEqual(hero.conditions["poisoned"], 2)
        self.assertEqual(hero.hp, hero.max_hp - 4)

    def test_stealth_and_influence_actions(self):
        hero = self.hero("rogue")
        monster = Monster.create("goblin", catalog=self.catalog)
        self.assertFalse(hero.stealth(Dice(FixedRng(1)), 15).success)
        self.assertNotIn("hidden", hero.conditions)
        self.assertTrue(hero.stealth(Dice(FixedRng(20)), 15).success)
        self.assertIn("hidden", hero.conditions)
        hit = hero.attack(monster, Dice(FixedRng(1, 20, 1)))
        self.assertTrue(hit.check.advantage)
        self.assertTrue(hero.influence(Dice(FixedRng(20)), 15, monster).success)
        self.assertEqual(monster.conditions["persuaded"], 2)

    def test_magic_validates_before_spending_and_uses_separate_pools(self):
        hero = self.hero("wizard", "elf")
        monster = Monster.create("goblin", catalog=self.catalog)
        self.assertFalse(hero.cast("missing", Dice(FixedRng())).performed)
        self.assertFalse(hero.cast("magic_missile", Dice(FixedRng())).performed)
        self.assertEqual(hero.spell_slots[1], 2)
        self.assertTrue(hero.cast("detect_magic", Dice(FixedRng()), source=SpellSource.RACIAL).performed)
        self.assertEqual(hero.racial_uses, 0)
        self.assertEqual(hero.spell_slots[1], 2)
        self.assertFalse(hero.cast("detect_magic", Dice(FixedRng()), source=SpellSource.RACIAL).performed)
        result = hero.cast("magic_missile", Dice(FixedRng(1, 1, 1)), monster)
        self.assertEqual(result.effects[0].amount, 6)
        self.assertEqual((hero.spell_slots[1], monster.hp), (1, 1))
        hero.restore_after_rest()
        self.assertEqual((hero.spell_slots[1], hero.racial_uses, hero.conditions), (2, 1, {}))

    def test_background_adds_tags_and_equipment_without_mutating_definitions(self):
        hero = self.hero("wizard", background="scholar")
        self.assertEqual(hero.background.id, "scholar")
        self.assertIn("scholar", hero.tags)
        self.assertEqual(len(hero.inventory), 7)
        self.assertEqual(len(self.hero("wizard").inventory), 6)

    def test_challenge_missing_tools_has_no_cost_or_consequences(self):
        hero = self.hero()
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("pick_lock", hero, Dice(FixedRng()))
        self.assertEqual((result.performed, result.minutes, hero.gold, hero.hp), (False, 0, 0, hero.max_hp))
        self.assertFalse(challenge.completed)
        self.assertFalse(challenge.resolve("missing", hero, Dice(FixedRng())).performed)

    def test_tool_advantage_rewards_and_no_repeated_rewards(self):
        hero = self.hero("rogue")
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("pick_lock", hero, Dice(FixedRng(1, 20)))
        self.assertTrue(result.success)
        self.assertTrue(result.check.advantage)
        self.assertEqual((hero.gold, hero.experience), (10, 15))
        self.assertFalse(challenge.resolve("pick_lock", hero, Dice(FixedRng())).performed)
        self.assertEqual((hero.gold, hero.experience), (10, 15))

    def test_automatic_tools_skip_dice_and_broken_tools_grant_nothing(self):
        hero = self.hero()
        tool = self.item("master_lockpicks")
        hero.inventory.append(tool)
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("pick_lock", hero, Dice(FixedRng()))
        self.assertTrue(result.success)
        self.assertIsNone(result.check)
        tool.wear(100)
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("pick_lock", hero, Dice(FixedRng()))
        self.assertFalse(result.performed)

    def test_challenge_failure_applies_only_failure_effects(self):
        hero = self.hero()
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("force", hero, Dice(FixedRng(1)))
        self.assertTrue(result.performed)
        self.assertFalse(result.success)
        self.assertEqual((hero.hp, hero.gold, hero.experience), (hero.max_hp - 3, 0, 0))

    def test_challenge_tag_benefits_and_automatic_key_choice(self):
        hero = self.hero(background="scholar")
        challenge = TextChallenge(self.catalog.challenges["ruined_shrine"])
        self.assertTrue(challenge.resolve("read", hero, Dice(FixedRng(1, 20))).check.advantage)
        hero.inventory.append(self.item("chest_key"))
        challenge = TextChallenge(self.catalog.challenges["locked_chest"])
        result = challenge.resolve("use_key", hero, Dice(FixedRng()))
        self.assertTrue(result.success)
        self.assertIsNone(result.check)

    def test_engine_placements_block_movement_and_challenges_spend_time_once(self):
        engine = Engine.new_game(self.hero(), random.Random(42))
        monster = engine.add_monster("goblin", Position(4, 3))
        self.assertFalse(engine.apply(Action.EAST).performed)
        self.assertEqual(engine.state.turns, 0)
        with self.assertRaises(ValueError):
            engine.add_monster("goblin", Position(4, 3))
        with self.assertRaises(ValueError):
            engine.add_monster("goblin", Position(0, 0))
        self.assertFalse(engine.resolve_challenge("locked_chest", "pick_lock").performed)
        self.assertEqual(engine.state.turns, 0)
        engine.state.hero.inventory.append(self.item("chest_key"))
        self.assertTrue(engine.resolve_challenge("locked_chest", "use_key").performed)
        self.assertEqual((engine.state.turns, engine.state.clock.elapsed_minutes), (1, 481))
        self.assertFalse(engine.resolve_challenge("locked_chest", "use_key").performed)
        monster.monster.hp = 0
        self.assertTrue(engine.apply(Action.EAST).performed)

    def test_engine_action_preserves_new_dodge_until_next_turn(self):
        engine = Engine.new_game(self.hero(), random.Random(42))
        self.assertTrue(engine.perform_character_action("dodge", ActionContext(engine.dice)).performed)
        self.assertEqual(engine.state.hero.conditions, {"dodging": 1})
        self.assertEqual(engine.state.turns, 1)
        engine.apply(Action.WAIT)
        self.assertEqual(engine.state.hero.conditions, {})
        result = engine.perform_character_action("magic", ActionContext(engine.dice, spell_id="missing"))
        self.assertFalse(result.performed)
        self.assertEqual(engine.state.turns, 2)

    def test_engine_item_usage_counts_only_successful_use(self):
        engine = Engine.new_game(self.hero(), random.Random(42))
        potion = self.item("healing_potion")
        self.assertFalse(engine.use_item(potion).performed)
        self.assertEqual(engine.state.turns, 0)
        engine.state.hero.inventory.append(potion)
        engine.state.hero.take_damage(4)
        self.assertTrue(engine.use_item(potion).performed)
        self.assertEqual((engine.state.turns, engine.state.clock.elapsed_minutes), (1, 481))
        self.assertFalse(engine.use_item(potion).performed)
        self.assertEqual(engine.state.turns, 1)

    def test_new_conditions_are_preserved_on_actual_target(self):
        engine = Engine.new_game(self.hero(), random.Random(42))
        monster = Monster.create("goblin", catalog=self.catalog)
        result = engine.perform_character_action("dodge", ActionContext(engine.dice, monster))
        self.assertTrue(result.performed)
        self.assertEqual(engine.state.hero.conditions, {"dodging": 1})
        self.assertEqual(monster.conditions, {})

    def test_unconscious_character_cannot_act_or_use_items(self):
        engine = Engine.new_game(self.hero(), random.Random(42))
        potion = self.item("healing_potion")
        engine.state.hero.inventory.append(potion)
        engine.state.hero.hp = 0
        self.assertFalse(engine.apply(Action.WAIT).performed)
        self.assertFalse(engine.perform_character_action("dodge", ActionContext(engine.dice)).performed)
        self.assertFalse(engine.use_item(potion).performed)
        self.assertEqual((engine.state.turns, potion.charges), (0, 1))

    def test_content_defined_class_and_race_appear_in_creation_without_enum_edits(self):
        catalog = ContentCatalog.load()
        catalog.races["halfling"] = replace(catalog.races["human"], id="halfling", name="Полурослик", order=3)
        catalog.classes["ranger"] = replace(catalog.classes["rogue"], id="ranger", name="Следопыт", order=3)
        creation = CharacterCreation(Dice(random.Random(42)), catalog)
        creation.select(4)
        creation.select(4)
        creation.select(1)
        creation.select(2)
        for number in range(1, 7):
            creation.select(number)
        hero = creation.select(1)
        self.assertEqual((hero.race.id, hero.character_class.id), ("halfling", "ranger"))

    def test_large_content_selection_pages_are_navigable(self):
        catalog = ContentCatalog.load()
        for index in range(10):
            content_id = f"new_class_{index}"
            catalog.classes[content_id] = replace(catalog.classes["warrior"], id=content_id, order=10 + index)
        creation = CharacterCreation(Dice(random.Random(42)), catalog)
        creation.select(1)
        self.assertEqual(creation.page_count, 3)
        creation.select(9)
        self.assertEqual(creation.selection_page, 1)
        creation.select(8)
        self.assertEqual(creation.selection_page, 0)
        creation.select(9)
        selected = creation.visible_options[0].id
        creation.select(1)
        self.assertEqual(creation.step, CreationStep.BACKGROUND)
        creation.select(1)
        self.assertEqual(creation.step, CreationStep.ROLL)
        self.assertEqual(creation.character_class.id, selected)

    def test_new_effect_and_action_handlers_are_registerable(self):
        class SparkEffect(EffectHandler):
            def apply(self, effect, target, dice):
                return EffectOutcome("spark", target.take_damage(effect.amount))

        class SaluteAction(CharacterAction):
            def execute(self, definition, actor, context, effects):
                return ActionOutcome(True, True, "Салют!")

        effects = EffectRegistry.default()
        effects.register("spark", SparkEffect())
        hero = self.hero()
        self.assertEqual(effects.apply_all((EffectSpec("spark", 2),), hero, Dice(FixedRng()))[0].amount, 2)
        registry = ActionRegistry.default(effects)
        registry.register("salute", SaluteAction())
        definition = replace(self.catalog.actions["dodge"], kind="salute")
        self.assertEqual(registry.execute(definition, hero, ActionContext(Dice(FixedRng()))).message, "Салют!")
        with self.assertRaises(ValueError):
            effects.register("spark", SparkEffect())
        old_hp = hero.hp
        with self.assertRaises(ValueError):
            effects.apply_all((EffectSpec("damage", 2), EffectSpec("unknown")), hero, Dice(FixedRng()))
        self.assertEqual(hero.hp, old_hp)


if __name__ == "__main__":
    unittest.main()
