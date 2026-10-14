import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tuidungeon.content.catalog import ContentCatalog, ContentError, DEFAULT_ROOT
from tuidungeon.presentation.symbols import ArtLibrary, GlyphTheme, TextArt
from tuidungeon.presentation.tui import Controller, render


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        shutil.copytree(DEFAULT_ROOT, self.root)

    def change(self, category, content_id, edit):
        path = self.root / category / f"{content_id}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        edit(value)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_loaded_definitions_cover_all_categories_and_art_references(self):
        catalog = ContentCatalog.load(self.root)
        for field in catalog.__dataclass_fields__:
            if (
                field != "recipes"
            ):  # Recipes are pack content, absent from the legacy archive.
                self.assertTrue(getattr(catalog, field), field)
        self.assertEqual(catalog.recipes, {})
        for monster in catalog.monsters.values():
            if monster.art:
                self.assertGreater(ArtLibrary().load(monster.art).width, 0)

    def test_file_errors_are_reported_with_path(self):
        edits = [
            ("monsters", "goblin", lambda obj: obj.update(hit_points=0)),
            ("monsters", "goblin", lambda obj: obj.update(speed=-1)),
            ("monsters", "goblin", lambda obj: obj.update(stats={"strength": 10})),
            (
                "monsters",
                "goblin",
                lambda obj: obj.update(stats=dict(obj["stats"], dexterity=True)),
            ),
            (
                "monsters",
                "goblin",
                lambda obj: obj.update(special_actions=[obj["special_actions"][0]] * 2),
            ),
            ("equipment", "sword", lambda obj: obj.update(weight=-1)),
            ("equipment", "sword", lambda obj: obj.update(weight=float("nan"))),
            ("equipment", "sword", lambda obj: obj.update(weapon_damage="0d6")),
            ("equipment", "sword", lambda obj: obj.update(durability=0)),
            ("equipment", "sword", lambda obj: obj.update(misspelled_tag=[])),
            (
                "equipment",
                "thieves_tools",
                lambda obj: obj.update(
                    check_aids=[{"check_tag": "lockpicking", "mode": "instant"}]
                ),
            ),
            (
                "classes",
                "warrior",
                lambda obj: obj.update(starting_items=["missing_sword"]),
            ),
            ("classes", "warrior", lambda obj: obj.update(actions=["missing_action"])),
            ("classes", "wizard", lambda obj: obj.update(spells=["missing_spell"])),
            ("classes", "wizard", lambda obj: obj.update(spell_slots={"10": 2})),
            ("spells", "magic_missile", lambda obj: obj.update(level=10)),
            ("spells", "magic_missile", lambda obj: obj.update(target="enemy")),
            (
                "spells",
                "magic_missile",
                lambda obj: obj["effects"][0].update(kind="typo"),
            ),
            ("actions", "dodge", lambda obj: obj.update(kind="typo")),
            ("races", "elf", lambda obj: obj.update(racial_spell="missing_spell")),
            ("races", "elf", lambda obj: obj.update(racial_uses=0)),
            ("races", "human", lambda obj: obj.update(schema_version=2)),
            ("challenges", "locked_chest", lambda obj: obj.update(choices=[])),
            ("challenges", "locked_chest", lambda obj: obj.update(repeatable="false")),
        ]
        for category, content_id, edit in edits:
            path = self.root / category / f"{content_id}.json"
            original = path.read_text(encoding="utf-8")
            with self.subTest(category=category, content_id=content_id, edit=edit):
                self.change(category, content_id, edit)
                with self.assertRaises(ContentError) as caught:
                    ContentCatalog.load(self.root)
                self.assertIn(str(path), str(caught.exception))
            path.write_text(original, encoding="utf-8")

    def test_duplicate_ids_and_duplicate_json_keys_are_rejected(self):
        first = self.root / "monsters" / "goblin.json"
        duplicate = self.root / "monsters" / "duplicate.json"
        duplicate.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(ContentError, "Повторный id"):
            ContentCatalog.load(self.root)
        duplicate.write_text(
            '{"schema_version": 1, "id": "first", "id": "second"}', encoding="utf-8"
        )
        with self.assertRaisesRegex(ContentError, "Повторное поле"):
            ContentCatalog.load(self.root)

    def test_new_json_class_is_available_to_controller(self):
        source = json.loads(
            (self.root / "classes" / "rogue.json").read_text(encoding="utf-8")
        )
        source.update(id="ranger", name="Следопыт", order=3)
        (self.root / "classes" / "ranger.json").write_text(
            json.dumps(source), encoding="utf-8"
        )
        controller = Controller(42, catalog=ContentCatalog.load(self.root))
        controller.handle("enter")
        controller.handle("1")
        self.assertIn("4) Следопыт", "\n".join(render(controller, 80, 24)))
        controller.handle("4")
        controller.handle("1")
        controller.handle("2")
        for key in "1234561":
            controller.handle(key)
        self.assertEqual(controller.engine.state.hero.character_class.id, "ranger")

    def test_every_authoring_template_can_be_loaded_in_its_category(self):
        categories = {
            "monster": "monsters",
            "equipment": "equipment",
            "armor": "equipment",
            "healing_item": "equipment",
            "spell": "spells",
            "action": "actions",
            "class": "classes",
            "race": "races",
            "background": "backgrounds",
            "challenge": "challenges",
        }
        template_root = Path(__file__).resolve().parents[1] / "docs" / "templates"
        for stem, category in categories.items():
            shutil.copyfile(
                template_root / f"{stem}.json", self.root / category / f"{stem}.json"
            )
        catalog = ContentCatalog.load(self.root)
        for stem, category in categories.items():
            self.assertIn(f"new_{stem}", getattr(catalog, category))

    def test_validate_command_does_not_require_a_terminal(self):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "tuidungeon",
                "--content-dir",
                str(self.root),
                "--validate-content",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("monsters: 2", process.stdout)
        self.change("monsters", "goblin", lambda value: value.update(hit_points=-1))
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "tuidungeon",
                "--content-dir",
                str(self.root),
                "--validate-content",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 1)
        self.assertIn("goblin.json", process.stderr)
        self.assertNotIn("Traceback", process.stderr)


class SymbolTests(unittest.TestCase):
    def test_unicode_theme_and_art_fallback(self):
        self.assertEqual(GlyphTheme.named("unicode").wall, "█")
        self.assertEqual(GlyphTheme.named("ascii").wall, "#")
        for style in ("ascii", "unicode"):
            self.assertGreater(ArtLibrary().load("goblin", style).height, 0)
        self.assertEqual(
            ArtLibrary().load("skeleton", "unicode"),
            ArtLibrary().load("skeleton", "ascii"),
        )
        self.assertEqual(TextArt(("12345", "abc")).fit(3, 1), ("123",))

    def test_wide_characters_combining_characters_and_control_codes_are_rejected(self):
        for character in ("界", "🙂", "\u0301", "\t", "\x1b"):
            with self.assertRaises(ValueError):
                TextArt((character,))
        with self.assertRaises(ValueError):
            ArtLibrary().load("../../file")
        with self.assertRaises(ValueError):
            ArtLibrary().load("goblin", "other")

    def test_unicode_rendering_keeps_sizes_and_game_rules(self):
        controller = Controller(42, symbols="unicode")
        controller.handle("enter")
        for key in "11112721234561":
            controller.handle(key)
        hero = controller.engine.state.hero
        hero.unequip(next(i for i in hero.inventory if i.id == "shield"))
        torch = next(i for i in hero.inventory if i.id == "torch")
        controller.engine.manage_equipment(torch, True)
        rows = render(controller, 80, 24)
        self.assertTrue(all(len(row) == 80 for row in rows))
        self.assertEqual(rows[0][0], "┌")
        self.assertIn("█", "\n".join(rows))
        controller.handle("d")
        self.assertEqual(controller.engine.state.turns, 2)


if __name__ == "__main__":
    unittest.main()
