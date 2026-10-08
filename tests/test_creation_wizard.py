"""Keyboard creation, class-bound backgrounds and gated event choices."""

from dataclasses import replace
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from tuidungeon.application.creation import CharacterCreation, CreationStep
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.catalog import ContentCatalog, ContentError
from tuidungeon.content.packs import PackStore, DEFAULT_PACKS, Referenced
from tuidungeon.domain.actors import Hero
from tuidungeon.domain.rules import Dice
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.tooling.sessions import TestSession
from tuidungeon.world.maps import Position


class CreationWizardTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ContentCatalog.load()

    def test_class_bound_backgrounds_apply_items_tags_and_skill_placeholders(self):
        for cls, background, name in (
            (1, "soldier", "Солдат"),
            (2, "sage", "Мудрец"),
            (3, "thief", "Вор"),
        ):
            with self.subTest(background=background):
                creation = CharacterCreation(Dice(random.Random(42)), self.catalog)
                creation.select(1)
                before = creation.dice.rng.getstate()
                creation.select(cls)
                self.assertEqual(creation.step, CreationStep.BACKGROUND)
                self.assertEqual([b.id for b in creation.options], [background])
                self.assertEqual(creation.dice.rng.getstate(), before)
                creation.select(1)
                creation.select(2)
                for number in range(1, 7):
                    creation.select(number)
                hero = creation.select(1)
                self.assertEqual(hero.background.name, name)
                self.assertEqual(len(hero.inventory), 8)
                self.assertEqual(hero.innate_tags, frozenset({background}))
                self.assertEqual(len(hero.background.skills), 2)
                plain = Hero.create(
                    hero.race,
                    hero.character_class,
                    Stats(tuple(r.total for r in creation.rolls)),
                    catalog=self.catalog,
                )
                self.assertEqual(hero.stats, plain.stats)
                self.assertEqual(hero.max_hp, plain.max_hp)

    def test_background_is_validated_for_direct_factory_call(self):
        factory = SessionFactory(PackStore())
        with self.assertRaisesRegex(ValueError, "недоступна"):
            factory.hero("base:human", "base:warrior", background="base:thief")
        self.assertEqual(
            factory.hero(
                "base:human", "base:wizard", background="base:sage"
            ).background.id,
            "sage",
        )

    def test_custom_class_with_no_bound_background_can_continue(self):
        custom = replace(
            self.catalog.classes["warrior"], id="knight", name="Рыцарь", order=3
        )
        self.catalog.classes[custom.id] = custom
        creation = CharacterCreation(Dice(random.Random(1)), self.catalog)
        creation.select(1)
        creation.select(4)
        self.assertEqual(creation.options, ())
        self.assertIn("без предыстории", creation.focused_button.label)
        creation.select(1)
        creation.select(2)
        for number in range(1, 7):
            creation.select(number)
        self.assertIsNone(creation.select(1).background)

    def test_back_navigation_preserves_rolls_and_explicit_reroll_resets_assignments(
        self,
    ):
        creation = CharacterCreation(Dice(random.Random(42)), self.catalog)
        for number in (1, 1, 1):
            creation.select(number)
        original, rng = creation.rolls, creation.dice.rng.getstate()
        creation.back()
        creation.back()
        creation.select(2)  # Change warrior to wizard.
        creation.select(1)
        self.assertEqual(creation.background.id, "sage")
        self.assertEqual(creation.rolls, original)
        self.assertEqual(creation.dice.rng.getstate(), rng)
        creation.select(2)
        creation.select(1)
        creation.back()
        creation.back()
        self.assertEqual(creation.step, CreationStep.ROLL)
        creation.select(1)
        self.assertNotEqual(creation.rolls, original)
        self.assertEqual(creation.assignments, [])

    def test_tied_rolls_remain_distinct_and_navigation_skips_used_values(self):
        creation = CharacterCreation(Dice(random.Random(1)), self.catalog)
        for number in (1, 1, 1, 2):
            creation.select(number)
        creation.rolls = (creation.rolls[0],) * 6
        for index in range(6):
            self.assertEqual(creation.focused_button.number, index + 1)
            creation.select(creation.focused_button.number)
        self.assertEqual(creation.assignments, list(range(6)))
        self.assertEqual(creation.step, CreationStep.CONFIRM)
        creation.back()
        self.assertEqual([b.number for b in creation.buttons], [6, 0])

    def test_creation_can_finish_with_wasd_enter_without_numeric_shortcuts(self):
        controller = Controller(42, catalog=self.catalog)
        controller.handle("enter")
        before = controller.rng.getstate()
        for key in ("s", "d", "a", "w"):
            controller.handle(key)
        self.assertEqual(controller.rng.getstate(), before)
        self.assertEqual(controller.creation.cursor, 0)
        for _ in range(11):
            controller.handle("enter")
        self.assertEqual(controller.view, View.EXPLORE)
        self.assertEqual(controller.engine.state.hero.background.id, "soldier")
        self.assertEqual(controller.engine.state.turns, 0)

    def test_back_button_and_long_help_support_resize_without_consuming_dice(self):
        self.catalog.races["human"] = replace(
            self.catalog.races["human"], description="Длинное объяснение. " * 100
        )
        c = Controller(42, catalog=self.catalog)
        c.handle("enter")
        rng = c.rng.getstate()
        first = render(c, 80, 24)
        self.assertGreater(c.creation_help_pages, 1)
        c.handle("h")
        self.assertNotEqual(first, render(c, 80, 24))
        self.assertTrue(all(len(row) == 100 for row in render(c, 100, 30)))
        c.handle("w")  # Wrap to the Back card.
        c.handle("enter")
        self.assertEqual(c.view, View.MAIN_MENU)
        self.assertEqual(c.rng.getstate(), rng)

    def test_background_help_and_confirmation_show_skills_and_tag(self):
        c = Controller(42, catalog=self.catalog)
        for key in ("enter", "1", "3"):
            c.handle(key)
        text = "\n".join(render(c, 80, 24))
        for expected in (
            "Вор",
            "Ловкость рук",
            "Скрытность",
            "thief",
            "Ломик",
            "Верёвка",
        ):
            self.assertIn(expected, text)
        for key in "12123456":
            c.handle(key)
        text = "\n".join(render(c, 80, 24))
        self.assertIn("Предыстория: Вор", text)
        self.assertIn("Теги предыстории: thief", text)


class BackgroundEventsTests(unittest.TestCase):
    def setUp(self):
        self.store = PackStore()
        self.factory = SessionFactory(self.store)

    def test_event_choices_are_identical_in_browser_and_tui_and_cannot_be_bypassed(
        self,
    ):
        for cls, background in (
            ("warrior", "soldier"),
            ("wizard", "sage"),
            ("rogue", "thief"),
        ):
            session = TestSession(
                self.store,
                dict(
                    map_ref="base:crypt",
                    character_class="base:" + cls,
                    background="base:" + background,
                    seed=42,
                ),
            )
            engine = session.engine
            point = next(
                p
                for p in engine.state.level.points
                if p.challenge.definition.id == "ruined_shrine"
            )
            engine.state.position = Position(point.placement.x, point.placement.y)
            browser = next(
                p for p in session.snapshot()["nearby"] if p["id"] == point.placement.id
            )
            available = [
                choice.id
                for choice in point.challenge.available_choices(engine.state.hero)
            ]
            self.assertEqual([c["id"] for c in browser["choices"]], available)
            self.assertIn(background + "_knowledge", available)
            forbidden = "thief_knowledge" if background != "thief" else "sage_knowledge"
            rng = engine.dice.rng.getstate()
            self.assertFalse(engine.interact(point.placement.id, forbidden).performed)
            self.assertEqual(engine.state.turns, 0)
            self.assertEqual(engine.dice.rng.getstate(), rng)
            controller = Controller(42, catalog=self.factory.catalog)
            controller.engine = engine
            controller.view = View.INTERACTION
            controller.point_id = point.placement.id
            text = "\n".join(render(controller, 80, 24))
            self.assertIn(engine.state.hero.background.name + ":", text)
            other = "Вор:" if background != "thief" else "Мудрец:"
            self.assertNotIn(other, text)
            controller.handle("3")  # First visible background-specific choice.
            self.assertTrue(point.challenge.completed)
            self.assertEqual(engine.state.turns, 1)

    def test_background_and_skills_survive_save_load(self):
        engine = self.factory.session(
            "base:crypt", character_class="base:wizard", background="base:sage", seed=9
        )
        with tempfile.TemporaryDirectory() as root:
            repository = SaveRepository(Path(root) / "save.json")
            repository.save(engine)
            loaded = repository.load(self.factory.catalog, self.store)
        self.assertEqual(loaded.state.hero.background, engine.state.hero.background)
        self.assertEqual(loaded.state.hero.inventory, engine.state.hero.inventory)
        self.assertIn("sage", loaded.state.hero.tags)

    def test_background_class_links_reject_missing_refs_and_block_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            packs = Path(root) / "packs"
            shutil.copytree(DEFAULT_PACKS, packs)
            store = PackStore(packs)
            raw = store.get("backgrounds", "base:soldier").model_dump(mode="json")
            version = store.versions[("backgrounds", "base:soldier")]
            raw["classes"] = ["base:missing"]
            with self.assertRaises(ContentError):
                store.save("backgrounds", "base:soldier", raw, version)
            with self.assertRaises(Referenced):
                store.delete(
                    "classes",
                    "base:warrior",
                    store.versions[("classes", "base:warrior")],
                )
            self.assertEqual(
                json.loads(
                    store.paths[("backgrounds", "base:soldier")].read_text(
                        encoding="utf-8"
                    )
                )["classes"],
                ["base:warrior"],
            )
