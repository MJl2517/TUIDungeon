"""Reading, journal navigation, persistence and Studio use the same note data."""

from copy import copy
import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument, ReadingText, PointDocument
from tuidungeon.presentation.tui import Controller, View, popup_content, render
from tuidungeon.world.maps import Position
from tuidungeon.world.state import ReadNote


class ReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        raw = self.store.get("maps", "dev:reading_room").model_dump(mode="json")
        raw["name"] = "Болота Свейга"
        raw["points_of_interest"][0]["overrides"] = {
            "reading": {
                "title": "Записки караванщика",
                "pages": [
                    "Первый абзац.\n\n" + "Длинная запись. " * 250,
                    "Последняя страница.",
                ],
            }
        }
        self.store.documents["maps", "dev:reading_room"] = MapDocument.model_validate(
            raw
        )
        self.c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:reading_room",
            test_map=True,
        )
        self.engine = self.c.engine
        self.point = self.engine.state.level.points[0]

    def read(self):
        self.engine.state.position = Position(3, 3)
        return self.engine.interact(self.point.placement.id, "read_note")

    def test_read_requires_proximity_and_snapshots_once_without_time(self):
        self.assertFalse(
            self.engine.interact(self.point.placement.id, "read_note").performed
        )
        self.assertFalse(self.engine.read_notes)
        self.engine.state.position = Position(3, 3)
        before = (
            self.engine.state.turns,
            self.engine.state.clock.elapsed_minutes,
            self.engine.dice.rng.getstate(),
        )
        self.assertEqual(
            [c.text for c in self.point.available_choices(self.engine.state.hero)],
            ["Прочесть"],
        )
        self.assertTrue(self.read().performed)
        self.assertTrue(self.read().performed)
        self.assertEqual(len(self.engine.read_notes), 1)
        note = next(iter(self.engine.read_notes.values()))
        self.assertEqual(note.location, "Болота Свейга")
        self.assertEqual(note.text.title, "Записки караванщика")
        self.assertEqual(
            (
                self.engine.state.turns,
                self.engine.state.clock.elapsed_minutes,
                self.engine.dice.rng.getstate(),
            ),
            before,
        )
        self.assertFalse(
            SessionFactory(self.store).session("dev:reading_room", seed=42).read_notes
        )

    def test_reader_and_journal_keyboard_pagination(self):
        c = self.c
        c.handle("d")
        c.handle("enter")
        self.assertEqual(c.view, View.INTERACTION)
        self.assertIn("Прочесть", popup_content(c)[2][0])
        c.handle("enter")
        self.assertEqual(c.view, View.READING)
        self.assertEqual(popup_content(c)[0], "Записки караванщика")
        for width, height in ((80, 24), (100, 28), (140, 40)):
            rows = render(c, width, height)
            self.assertTrue(all(len(row) == width for row in rows))
            self.assertGreater(c.reading_pages, 2)
            c.handle("right")
            self.assertEqual(c.reading_page, 1)
            c.handle("left")
            c.handle("left")
            self.assertEqual(c.reading_page, 0)
            for _ in range(c.reading_pages + 1):
                c.handle("right")
            self.assertIn("Последняя страница.", "\n".join(render(c, width, height)))
            c.reading_page = 0
        c.handle("escape")
        self.assertEqual(c.view, View.INTERACTION)
        c.handle("escape")
        c.handle("j")
        self.assertEqual(
            popup_content(c)[2],
            ["Квесты", "Записи", "Рецепты", "Бестиарий", "Личный дневник"],
        )
        c.handle("down")
        c.handle("enter")
        self.assertEqual(popup_content(c)[2], ["Записки караванщика — Болота Свейга"])
        turns = self.engine.state.turns
        c.handle("enter")
        self.assertEqual(c.view, View.READING)
        c.handle("escape")
        self.assertEqual(c.notebook_section, 1)
        c.handle("escape")
        c.handle("escape")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(self.engine.state.turns, turns)
        c.handle("l")
        self.assertEqual(c.view, View.JOURNAL)

    def test_records_pages_and_same_titles_at_different_locations(self):
        self.read()
        note = next(iter(self.engine.read_notes.values()))
        for index in range(8):
            other = ReadNote(
                map_ref="dev:reading_room",
                placement_id=f"other_{index}",
                location=f"Локация {index}",
                text=note.text,
            )
            self.engine.read_notes[(other.map_ref, other.placement_id)] = other
        c = self.c
        c.handle("j")
        c.handle("2")
        self.assertEqual(len(popup_content(c)[2]), 6)
        c.handle("pagedown")
        self.assertEqual(len(popup_content(c)[2]), 3)
        c.handle("pagedown")
        self.assertEqual(c.records_page, 1)
        c.handle("enter")
        self.assertEqual(c.view, View.READING)
        self.assertIn(
            c.reading.location, [n.location for n in self.engine.read_notes.values()]
        )

    def test_save_snapshot_old_saves_and_validation(self):
        self.read()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            saves = SaveRepository(path)
            saves.save(self.engine)
            raw = json.loads(path.read_text(encoding="utf-8"))
            loaded = saves.load(self.store.runtime_catalog(), self.store)
            self.assertEqual(loaded.read_notes, self.engine.read_notes)
            raw["read_notes"].append(raw["read_notes"][0])
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                saves.load(self.store.runtime_catalog(), self.store)
            del raw["read_notes"]
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertFalse(
                saves.load(self.store.runtime_catalog(), self.store).read_notes
            )
        for pages in ([], [" "], ["Bad\x1b[2J"]):
            with self.assertRaises(ValidationError):
                ReadingText(title="Текст", pages=pages)
        with self.assertRaises(ValidationError):
            PointDocument(id="empty", name="Пусто")
