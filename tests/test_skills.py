"""SRD 5.2.1 skill grants, checks, creation choices and save compatibility."""

from dataclasses import replace
from copy import copy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.creation import CharacterCreation, CreationStep
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import (
    ActorRecord,
    SaveRepository,
    actor_record,
    restore_actor,
)
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import ClassDocument, ChallengeDocument
from tuidungeon.domain.actors import Hero
from tuidungeon.domain.challenges import TextChallenge
from tuidungeon.domain.definitions import ChallengeChoice, ChallengeDefinition
from tuidungeon.domain.rules import Ability, Dice
from tuidungeon.domain.skills import SKILLS
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.tui import Controller, hero_lines, render


class SkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.catalog = cls.store.runtime_catalog()

    def hero(self, character_class="warrior", **kwargs):
        return Hero.create(
            "human",
            character_class,
            Stats((12, 14, 10, 16, 10, 8)),
            catalog=self.catalog,
            **kwargs,
        )

    def test_class_background_race_grants_and_duplicates_have_distinct_choices(self):
        for name, count, background in (
            ("warrior", 2, "soldier"),
            ("rogue", 4, "thief"),
            ("wizard", 2, "sage"),
        ):
            hero = self.hero(name, background=background)
            self.assertEqual(len(hero.skill_proficiencies), count + 2)
            self.assertTrue(
                set(self.catalog.backgrounds[background].skills)
                <= hero.skill_proficiencies
            )
        race = replace(self.catalog.races["human"], skills=("athletics", "nature"))
        hero = Hero.create(
            race,
            "warrior",
            Stats((10,) * 6),
            catalog=self.catalog,
            background="soldier",
        )
        self.assertEqual(len(hero.skill_proficiencies), 6)
        self.assertTrue(
            {"nature", "athletics", "intimidation"} <= hero.skill_proficiencies
        )
        with self.assertRaisesRegex(ValueError, "повторяться"):
            self.hero(skills=("acrobatics", "acrobatics"))

    def test_skill_modifiers_expertise_and_proficiency_tiers(self):
        hero = self.hero(
            "rogue",
            skills=("acrobatics", "athletics", "stealth", "perception"),
            expertise=("stealth", "perception"),
        )
        for level, bonus in (
            (1, 2),
            (4, 2),
            (5, 3),
            (8, 3),
            (9, 4),
            (12, 4),
            (13, 5),
            (16, 5),
            (17, 6),
            (20, 6),
        ):
            hero.level = level
            self.assertEqual(hero.proficiency_bonus, bonus)
            self.assertEqual(
                hero.skill_bonus("stealth"),
                hero.stats.modifier(Ability.DEXTERITY) + 2 * bonus,
            )
            self.assertEqual(
                hero.skill_bonus("athletics"),
                hero.stats.modifier(Ability.STRENGTH) + bonus,
            )
            self.assertEqual(
                hero.skill_bonus("medicine"), hero.stats.modifier(Ability.WISDOM)
            )
        self.assertEqual(
            hero.passive_skill("perception", advantage=True),
            15 + hero.skill_bonus("perception"),
        )
        self.assertEqual(
            hero.passive_skill("perception", advantage=True, disadvantage=True),
            10 + hero.skill_bonus("perception"),
        )

    def test_tool_proficiency_is_independent_of_skills_and_expertise(self):
        hero = self.hero("wizard")
        hero.tool_proficiencies.add("alchemist_tools")
        dice = Dice(random.Random(3))
        check = hero.ability_check(
            dice, Ability.INTELLIGENCE, 10, skill="arcana", tool="alchemist_tools"
        )
        self.assertFalse(check.advantage)
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.INTELLIGENCE) + 2)
        hero.expertise.add("arcana")
        check = hero.ability_check(
            dice, Ability.INTELLIGENCE, 10, skill="arcana", tool="alchemist_tools"
        )
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.INTELLIGENCE) + 2)
        self.assertFalse(check.advantage)
        check = hero.ability_check(
            dice, Ability.INTELLIGENCE, 10, skill="arcana", tool="smith_tools"
        )
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.INTELLIGENCE))
        check = hero.ability_check(dice, Ability.STRENGTH, 10, skill="arcana")
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.STRENGTH) + 4)
        check = hero.ability_check(
            dice, Ability.INTELLIGENCE, 10, skill="medicine", tool="alchemist_tools"
        )
        self.assertFalse(check.advantage)
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.INTELLIGENCE) + 2)

        hero.tool_expertise.add("alchemist_tools")
        check = hero.ability_check(
            dice, Ability.INTELLIGENCE, 10, skill="medicine", tool="alchemist_tools"
        )
        self.assertEqual(check.modifier, hero.stats.modifier(Ability.INTELLIGENCE) + 4)
        self.assertFalse(check.advantage)
        choice = ChallengeChoice(
            "brew", "Сварить", ability=Ability.INTELLIGENCE, tool="alchemist_tools"
        )
        result = TextChallenge(
            ChallengeDefinition("brew", "Испытание", "", (choice,))
        ).resolve("brew", hero, dice)
        self.assertEqual(
            result.check.modifier, hero.stats.modifier(Ability.INTELLIGENCE) + 4
        )
        self.assertEqual(hero.expertise, {"arcana"})
        definition = replace(
            self.catalog.classes["wizard"],
            tool_expertise=frozenset({"alchemist_tools"}),
        )
        granted = Hero.create(
            "human", definition, Stats((10,) * 6), catalog=self.catalog
        )
        self.assertIn("alchemist_tools", granted.tool_proficiencies)
        self.assertIn("alchemist_tools", granted.tool_expertise)
        self.assertEqual(len(granted.skill_proficiencies), 2)

    def test_explicit_challenge_skill_uses_proficiency_and_natural_twenty_is_not_automatic(
        self,
    ):
        hero = self.hero("wizard")
        choice = ChallengeChoice(
            "study",
            "Изучить",
            ability=Ability.INTELLIGENCE,
            difficulty=12,
            skill="arcana",
        )
        challenge = TextChallenge(
            ChallengeDefinition("study", "Книга", "Книга", (choice,))
        )
        with patch.object(random.Random, "randint", return_value=7):
            check = challenge.resolve("study", hero, Dice(random.Random())).check
        self.assertEqual(check.total, 7 + hero.skill_bonus("arcana"))
        with patch.object(random.Random, "randint", return_value=20):
            self.assertFalse(
                hero.ability_check(
                    Dice(random.Random()), Ability.INTELLIGENCE, 40, skill="arcana"
                ).success
            )

    def test_authored_tool_expertise_and_tool_challenge_compile_independently(self):
        store = copy(self.store)
        store.documents = dict(store.documents)
        raw = store.get("classes", "base:wizard").model_dump(mode="json")
        raw["tool_expertise"] = ["alchemist_tools"]
        store.documents["classes", "base:wizard"] = ClassDocument.model_validate(raw)
        store.documents["challenges", "base:tool_trial"] = (
            ChallengeDocument.model_validate(
                {
                    "id": "tool_trial",
                    "name": "Испытание",
                    "text": "Приготовьте состав.",
                    "choices": [
                        {
                            "id": "brew",
                            "text": "Приготовить",
                            "ability": "intelligence",
                            "tool": "alchemist_tools",
                            "difficulty": 12,
                        }
                    ],
                }
            )
        )
        catalog = store.runtime_catalog()
        hero = Hero.create("human", "wizard", Stats((10,) * 6), catalog=catalog)
        result = TextChallenge(catalog.challenges["tool_trial"]).resolve(
            "brew", hero, Dice(random.Random(42))
        )
        self.assertEqual(result.check.modifier, 4)
        self.assertIn("alchemist_tools", hero.tool_proficiencies)
        self.assertEqual(len(hero.skill_proficiencies), 2)
        self.assertFalse(hero.expertise)

    def test_creation_requires_player_skill_choices_and_expertise(self):
        creation = CharacterCreation(Dice(random.Random(42)), self.catalog)
        creation.select(1)
        creation.select(3)  # Rogue.
        index = next(i for i, b in enumerate(creation.options) if b.id == "thief")
        creation.change_page(index // 6)
        creation.select(index % 6 + 1)
        self.assertEqual(creation.step, CreationStep.SKILLS)
        creation.select(7)
        self.assertEqual(creation.step, CreationStep.SKILLS)
        self.assertFalse(creation.rolls)
        for n in (1, 2, 3, 4, 7):
            creation.select(n)
        self.assertEqual(creation.step, CreationStep.EXPERTISE)
        for n in (1, 2, 7):
            creation.select(n)
        self.assertEqual(creation.step, CreationStep.ROLL)
        creation.select(2)
        for n in range(1, 7):
            creation.select(n)
        hero = creation.select(1)
        self.assertEqual(len(hero.skill_proficiencies), 6)
        self.assertEqual(len(hero.expertise), 2)
        self.assertIn("Бонус мастерства: +2", hero_lines(hero))
        c = Controller(42, test_map=True, test_class="rogue")
        c.handle("2")
        for _ in range(8):
            c.handle("pagedown")
        self.assertIn("Выживание", "\n".join(render(c, 80, 24)))

    def test_skills_save_roundtrip_old_records_and_invalid_expertise(self):
        engine = SessionFactory(self.store).session(
            "tiles:vegetation_lab",
            character_class="base:rogue",
            background="base:thief",
        )
        hero = engine.state.hero
        hero.level = 9
        hero.tool_proficiencies.add("lockpicks")
        hero.tool_expertise.add("lockpicks")
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "skills.json")
            repo.save(engine)
            restored = repo.load(store=self.store).state.hero
        self.assertEqual(restored.skill_proficiencies, hero.skill_proficiencies)
        self.assertEqual(restored.expertise, hero.expertise)
        self.assertEqual(restored.tool_expertise, {"lockpicks"})
        self.assertEqual(restored.proficiency_bonus, 4)
        raw = actor_record(hero).model_dump()
        raw.pop("skill_proficiencies")
        raw.pop("expertise")
        raw.pop("tool_expertise")
        fresh = self.hero("rogue", background="thief")
        restore_actor(fresh, ActorRecord.model_validate(raw), self.catalog)
        self.assertEqual(len(fresh.skill_proficiencies), 6)
        raw.update(skill_proficiencies=["stealth"], expertise=["arcana"])
        with self.assertRaisesRegex(ValueError, "Экспертиза"):
            restore_actor(fresh, ActorRecord.model_validate(raw), self.catalog)
        raw.update(expertise=[], tool_proficiencies=[], tool_expertise=["lockpicks"])
        with self.assertRaisesRegex(ValueError, "Экспертиза инструмента"):
            restore_actor(fresh, ActorRecord.model_validate(raw), self.catalog)
        self.assertEqual(len(SKILLS), 18)


if __name__ == "__main__":
    unittest.main()
