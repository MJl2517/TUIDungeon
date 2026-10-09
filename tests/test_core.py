from collections import Counter, deque
import random
import unittest

from tuidungeon.creation import CharacterCreation, CreationStep
from tuidungeon.engine import Action, Engine, test_dungeon
from tuidungeon.models import (
    DETECT_MAGIC, MAGIC_MISSILE, DungeonMap, GameClock, GameState, Hero, Position, Stats,
)
from tuidungeon.rules import Ability, CharacterClass, Dice, Race, modifier


class DiceTests(unittest.TestCase):
    def test_seed_replays_complete_roll_sequence(self):
        first, second = Dice(random.Random(42)), Dice(random.Random(42))
        self.assertEqual(first.abilities(), second.abilities())
        self.assertEqual(first.check(15, 12), second.check(15, 12))
        self.assertEqual(first.roll(3, 8), second.roll(3, 8))

    def test_generation_drops_one_smallest_die(self):
        for seed in range(50):
            rolls = Dice(random.Random(seed)).abilities()
            self.assertEqual(len(rolls), 6)
            for roll in rolls:
                self.assertEqual(len(roll.dice), 4)
                self.assertTrue(all(1 <= value <= 6 for value in roll.dice))
                self.assertEqual(roll.discarded, min(roll.dice))
                self.assertEqual(roll.total, sum(sorted(roll.dice)[1:]))
                self.assertTrue(3 <= roll.total <= 18)

    def test_modifiers_round_negative_values_down(self):
        for score, expected in ((3, -4), (8, -1), (9, -1), (10, 0), (11, 0), (18, 4), (19, 4)):
            self.assertEqual(modifier(score), expected)

    def test_check_threshold_has_no_automatic_criticals(self):
        class FixedRng:
            def __init__(self, value):
                self.value = value

            def randint(self, low, high):
                return self.value

        self.assertTrue(Dice(FixedRng(10)).check(14, 12).success)
        self.assertFalse(Dice(FixedRng(10)).check(14, 13).success)
        self.assertTrue(Dice(FixedRng(1)).check(18, 5).success)
        self.assertFalse(Dice(FixedRng(20)).check(3, 30).success)

    def test_invalid_dice_are_rejected(self):
        for count, sides in ((0, 6), (-1, 6), (1, 1)):
            with self.assertRaises(ValueError):
                Dice(random.Random()).roll(count, sides)


class HeroTests(unittest.TestCase):
    def test_all_nine_combinations_have_correct_stats_hp_and_resources(self):
        base = Stats((12, 13, 13, 15, 10, 8))
        hit_dice = {CharacterClass.WARRIOR: 10, CharacterClass.WIZARD: 6, CharacterClass.ROGUE: 8}
        for race in Race:
            for character_class in CharacterClass:
                with self.subTest(race=race, character_class=character_class):
                    hero = Hero.create(race, character_class, base)
                    expected_stats = tuple(value + int(race is Race.HUMAN) for value in base.values)
                    self.assertEqual(hero.stats.values, expected_stats)
                    expected_hp = hit_dice[character_class] + modifier(expected_stats[2]) + int(race is Race.DWARF)
                    self.assertEqual((hero.hp, hero.max_hp, hero.level), (expected_hp, expected_hp, 1))
                    self.assertEqual((hero.gold, hero.experience), (0, 0))
                    self.assertEqual(len(hero.inventory), 6)
                    self.assertEqual(hero.spell_slots, {1: 2} if character_class is CharacterClass.WIZARD else {})
                    self.assertEqual(hero.racial_spell, DETECT_MAGIC if race is Race.ELF else None)
                    self.assertEqual(hero.racial_uses, int(race is Race.ELF))
        self.assertEqual(base.values, (12, 13, 13, 15, 10, 8))

    def test_minimum_hp_and_distinct_inventory(self):
        first = Hero.create(Race.ELF, CharacterClass.WIZARD, Stats((1,) * 6))
        second = Hero.create(Race.ELF, CharacterClass.WIZARD, Stats((1,) * 6))
        self.assertEqual(first.max_hp, 1)
        first.inventory.clear()
        self.assertEqual(len(second.inventory), 6)

    def test_elf_wizard_uses_independent_pools_without_duplicate_knowledge(self):
        hero = Hero.create(Race.ELF, CharacterClass.WIZARD, Stats((10,) * 6))
        self.assertEqual(tuple(s for s in hero.known_spells if s.level > 0), (MAGIC_MISSILE, DETECT_MAGIC))
        self.assertEqual(len([s for s in hero.known_spells if s.level == 0]), 3)
        self.assertTrue(hero.consume_racial_spell())
        self.assertFalse(hero.consume_racial_spell())
        self.assertEqual(hero.spell_slots, {1: 2})
        self.assertFalse(hero.consume_class_slot("nonexistent"))
        self.assertEqual(hero.spell_slots, {1: 2})
        self.assertTrue(hero.consume_class_slot(DETECT_MAGIC.id))
        self.assertTrue(hero.consume_class_slot(MAGIC_MISSILE.id))
        self.assertFalse(hero.consume_class_slot(MAGIC_MISSILE.id))
        self.assertEqual(hero.spell_slots, {1: 0})
        self.assertEqual(hero.max_spell_slots, {1: 2})
        hero.hp = 1
        hero.restore_after_rest()
        self.assertEqual(hero.hp, hero.max_hp)
        self.assertEqual(hero.spell_slots, {1: 2})
        self.assertEqual(hero.racial_uses, 1)

    def test_noncasters_cannot_spend_class_slots(self):
        for race in Race:
            hero = Hero.create(race, CharacterClass.WARRIOR, Stats((10,) * 6))
            self.assertFalse(hero.consume_class_slot(DETECT_MAGIC.id))
            self.assertEqual(hero.consume_racial_spell(), race is Race.ELF)

    def test_stats_require_six_positive_values(self):
        for values in ((), (10,) * 5, (10,) * 7, (0,) * 6):
            with self.assertRaises(ValueError):
                Stats(values)


class CreationTests(unittest.TestCase):
    def prepare(self):
        creation = CharacterCreation(Dice(random.Random(42)))
        creation.select(3)
        creation.select(2)
        creation.select(1)
        creation.select(2)
        return creation

    def test_distribution_preserves_every_result_and_order(self):
        creation = self.prepare()
        order = (6, 1, 4, 2, 5, 3)
        for number in order:
            creation.select(number)
        self.assertEqual(creation.step, CreationStep.CANTRIPS)
        for number in (1, 2, 3, 7):
            creation.select(number)
        self.assertEqual(creation.step, CreationStep.CONFIRM)
        hero = creation.select(1)
        expected = tuple(creation.rolls[index - 1].total for index in order)
        self.assertEqual(hero.stats.values, expected)
        self.assertEqual(Counter(hero.stats.values), Counter(roll.total for roll in creation.rolls))

    def test_duplicate_values_are_distinct_but_indices_cannot_repeat(self):
        creation = self.prepare()
        # Six tied rolls still represent six distinct available choices.
        creation.rolls = (creation.rolls[0],) * 6
        creation.select(1)
        creation.select(1)
        creation.select(0)
        creation.select(7)
        self.assertEqual(creation.assignments, [0])
        for number in range(2, 7):
            creation.select(number)
        self.assertEqual(len(creation.preview().stats.values), 6)

    def test_backspace_restores_previous_assignment_or_step(self):
        creation = self.prepare()
        creation.select(1)
        creation.select(2)
        creation.back()
        self.assertEqual(creation.assignments, [0])
        creation.select(2)
        for number in range(3, 7):
            creation.select(number)
        creation.back()
        self.assertEqual(creation.step, CreationStep.DISTRIBUTE)
        self.assertEqual(creation.assignments, [0, 1, 2, 3, 4])
        for _ in range(5):
            creation.back()
        self.assertEqual(creation.assignments, [])
        creation.back()
        self.assertEqual(creation.step, CreationStep.ROLL)
        creation.back()
        self.assertEqual(creation.step, CreationStep.BACKGROUND)
        creation.back()
        self.assertEqual(creation.step, CreationStep.CLASS)
        creation.back()
        self.assertEqual(creation.step, CreationStep.RACE)
        creation.back()
        self.assertEqual(creation.step, CreationStep.RACE)

    def test_reroll_at_confirmation_resets_distribution(self):
        creation = self.prepare()
        old_rolls = creation.rolls
        for number in range(1, 7):
            creation.select(number)
        for number in (1, 2, 3, 7):
            creation.select(number)
        creation.select(2)
        self.assertEqual(creation.step, CreationStep.ROLL)
        self.assertNotEqual(creation.rolls, old_rolls)
        self.assertEqual(creation.assignments, [])
        with self.assertRaises(ValueError):
            creation.preview()


class EngineTests(unittest.TestCase):
    def setUp(self):
        hero = Hero.create(Race.ELF, CharacterClass.WIZARD, Stats((10,) * 6))
        dungeon = DungeonMap(("#####", "#...#", "#.#.#", "#...#", "#####"))
        self.engine = Engine(GameState(hero, dungeon, Position(1, 1)), random.Random(42))

    def test_four_directions_wait_and_blocked_moves(self):
        state = self.engine.state
        for action in (Action.NORTH, Action.WEST):
            self.assertEqual(self.engine.apply(action).minutes, 0)
        self.assertEqual((state.position, state.turns, state.clock.elapsed_minutes), (Position(1, 1), 0, 480))
        for action in (Action.EAST, Action.WEST, Action.SOUTH, Action.NORTH, Action.WAIT):
            result = self.engine.apply(action)
            self.assertTrue(result.performed)
            self.assertEqual(result.minutes, 1)
        self.assertEqual((state.position, state.turns, state.clock.elapsed_minutes), (Position(1, 1), 5, 485))
        self.engine.apply(Action.EAST)
        blocked = self.engine.apply(Action.SOUTH)
        self.assertFalse(blocked.performed)
        self.assertEqual(state.position, Position(2, 1))

    def test_edges_of_unwalled_map_are_blocked(self):
        self.engine.state.dungeon = DungeonMap(("..", ".."))
        self.engine.state.position = Position(0, 0)
        self.assertFalse(self.engine.apply(Action.NORTH).performed)
        self.assertFalse(self.engine.apply(Action.WEST).performed)
        self.engine.state.position = Position(1, 1)
        self.assertFalse(self.engine.apply(Action.SOUTH).performed)
        self.assertFalse(self.engine.apply(Action.EAST).performed)
        self.assertEqual(self.engine.state.turns, 0)

    def test_rest_advances_eight_hours_one_turn_and_restores_resources(self):
        state = self.engine.state
        state.hero.hp = 1
        state.hero.consume_class_slot(MAGIC_MISSILE.id)
        state.hero.consume_racial_spell()
        state.clock = GameClock(23 * 60 + 30)
        result = self.engine.apply(Action.REST)
        self.assertEqual((result.performed, result.minutes, state.turns), (True, 480, 1))
        self.assertEqual((state.clock.day, state.clock.hour, state.clock.minute), (2, 7, 30))
        self.assertEqual(state.hero.hp, state.hero.max_hp)
        self.assertEqual(state.hero.spell_slots, {1: 2})
        self.assertEqual(state.hero.racial_uses, 1)

    def test_clock_midnight_and_time_of_day_boundaries(self):
        clock = GameClock(23 * 60 + 59)
        clock.advance(1)
        self.assertEqual((clock.day, clock.hour, clock.minute), (2, 0, 0))
        for hour, label in ((0, "Ночь"), (5, "Ночь"), (6, "Утро"), (11, "Утро"), (12, "День"), (17, "День"), (18, "Вечер"), (21, "Вечер"), (22, "Ночь")):
            self.assertEqual(GameClock(hour * 60).time_of_day, label)
        with self.assertRaises(ValueError):
            clock.advance(-1)

    def test_fixed_dungeon_all_floors_reachable_and_boundary_is_walled(self):
        dungeon = test_dungeon()
        floors = {Position(x, y) for y, row in enumerate(dungeon.rows) for x, cell in enumerate(row) if cell == "."}
        visited = {Position(3, 3)}
        queue = deque(visited)
        while queue:
            position = queue.popleft()
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                neighbor = Position(position.x + dx, position.y + dy)
                if dungeon.walkable(neighbor) and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        self.assertEqual(visited, floors)
        self.assertTrue(all(cell == "#" for cell in dungeon.rows[0] + dungeon.rows[-1]))
        self.assertTrue(all(row[0] == row[-1] == "#" for row in dungeon.rows))

    def test_invalid_maps_spawn_and_action_are_rejected(self):
        for rows in ((), ("",), ("..", "."), ("@.",)):
            with self.assertRaises(ValueError):
                DungeonMap(rows)
        with self.assertRaises(ValueError):
            GameState(self.engine.state.hero, self.engine.state.dungeon, Position(0, 0))
        with self.assertRaises(ValueError):
            self.engine.apply("north")


if __name__ == "__main__":
    unittest.main()

