"""Local properties are validated, inherited, isolated and persist in saves."""

from copy import copy, deepcopy
import tempfile
from pathlib import Path
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.migrations import migrate_map
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import MapDocument
from tuidungeon.tooling.sessions import TestSession
from tuidungeon.world.maps import Position


class InstancePropertiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="instances",
            name="Экземпляры",
            width=12,
            height=6,
            tiles=[["base:floor"] * 12 for _ in range(6)],
            walkability=[[True] * 12 for _ in range(6)],
            blocks_sight=[[False] * 12 for _ in range(6)],
            spawn={"x": 1, "y": 1},
        )

    def session(self):
        self.store.documents["maps", "base:instances"] = MapDocument.model_validate(
            self.raw
        )
        self.store.validate_references(self.store.documents, self.store.manifests)
        return SessionFactory(self.store).session("base:instances", seed=42)

    def test_five_materials_have_independent_lock_and_geometry_properties(self):
        self.assertEqual(
            sum(
                1
                for (c, _), d in self.source.documents.items()
                if c == "objects" and d.brush.door
            ),
            5,
        )
        self.raw["doors"] = [
            dict(
                id="locked",
                ref="base:door_wood",
                x=2,
                y=1,
                overrides={
                    "brush": {
                        "door": {
                            "locked": True,
                            "lock_quality": "legendary",
                            "lock_complexity": "complex",
                            "hit_points": 50,
                        }
                    }
                },
            ),
            dict(
                id="open",
                ref="base:door_wood",
                x=4,
                y=1,
                overrides={"brush": {"door": {"state": "open"}}},
            ),
        ]
        engine = self.session()
        first, second = engine.state.level.doors
        self.assertEqual(
            (first.door.lock_dc, first.door.lock_turns, first.door.hp), (25, 10, 50)
        )
        self.assertTrue(second.door.passable)
        self.assertFalse(engine.apply(Action.EAST).performed)
        self.assertEqual(engine.render_cells((2, 1, 3, 1))[0][0].char, "X")
        self.assertFalse(self.source.get("objects", "base:door_wood").brush.door.locked)
        other = self.session()
        first.door.force_open()
        self.assertTrue(other.state.level.doors[0].door.locked)

    def test_traps_and_challenges_use_local_checks_and_consequences(self):
        self.raw["traps"] = [
            dict(
                id="trap",
                ref="base:spikes",
                x=2,
                y=1,
                overrides={
                    "name": "Особая ловушка",
                    "hidden": True,
                    "difficulty": 100,
                    "failure": [{"kind": "gold", "amount": 9}],
                },
            )
        ]
        self.raw["points_of_interest"] = [
            dict(
                id="chest",
                ref="base:chest",
                x=3,
                y=1,
                overrides={"name": "Особый сундук", "glyph": "C"},
                challenge_overrides={
                    "text": "Только этот сундук",
                    "choices": [
                        {
                            "id": "take",
                            "text": "Взять монеты",
                            "success": [{"kind": "gold", "amount": 17}],
                        }
                    ],
                },
            )
        ]
        engine = self.session()
        engine.apply(Action.EAST)
        self.assertEqual(engine.state.hero.gold, 9)
        self.assertEqual(
            engine.state.level.points[0].challenge.text, "Только этот сундук"
        )
        engine.interact("chest", "take")
        self.assertEqual(engine.state.hero.gold, 26)
        self.assertTrue(engine.state.level.points[0].challenge.completed)
        other = self.session()
        self.assertFalse(other.state.level.traps[0].triggered)
        self.assertFalse(other.state.level.points[0].challenge.completed)

    def test_equipment_properties_survive_pickup_drop_and_save_load(self):
        self.raw["equipment"] = [
            dict(
                id="tool",
                ref="base:thieves_tools",
                x=1,
                y=1,
                overrides={
                    "name": "Мастерские инструменты",
                    "weight": 0.25,
                    "durability": 30,
                    "glyph": "!",
                },
            )
        ]
        engine = self.session()
        item = engine.state.items[0][1]
        self.assertEqual(
            (item.name, item.weight, item.durability),
            ("Мастерские инструменты", 0.25, 30),
        )
        engine.pickup_item()
        item.wear(3)
        with tempfile.TemporaryDirectory() as directory:
            saves = SaveRepository(Path(directory) / "save.json")
            saves.save(engine)
            loaded = saves.load(store=self.store)
        restored = next(
            i for i in loaded.state.hero.inventory if i.instance_id == item.instance_id
        )
        self.assertEqual(
            (restored.name, restored.weight, restored.durability), (item.name, 0.25, 27)
        )
        loaded.place_item(restored, Position(1, 1))
        loaded.state.position = Position(2, 1)
        self.assertEqual(loaded.render_cells((1, 1, 1, 1))[0][0].char, "!")

    def test_monster_stats_actions_and_visuals_survive_save_load(self):
        self.raw["monsters"] = [
            dict(
                id="chief",
                ref="base:goblin",
                x=5,
                y=1,
                overrides={
                    "name": "Вождь",
                    "hit_points": 31,
                    "armor_class": 19,
                    "glyph": "G",
                    "stats": {"strength": 20},
                    "special_actions": [
                        {"id": "roar", "name": "Рёв", "kind": "special"}
                    ],
                },
            )
        ]
        engine = self.session()
        monster = engine.state.monsters[0].monster
        self.assertEqual(
            (monster.max_hp, monster.armor_class, monster.name), (31, 19, "Вождь")
        )
        self.assertEqual(monster.special_actions[0].name, "Рёв")
        monster.take_damage(4)
        with tempfile.TemporaryDirectory() as directory:
            saves = SaveRepository(Path(directory) / "save.json")
            saves.save(engine)
            restored = saves.load(store=self.store)
        self.assertEqual(restored.state.monsters[0].monster.hp, 27)
        self.assertEqual(restored.state.monsters[0].monster.armor_class, 19)
        self.assertEqual(
            restored.state.monsters[0].monster.special_actions[0].name, "Рёв"
        )
        self.assertEqual(restored.render_cells((5, 1, 1, 1))[0][0].char, "G")

    def test_invalid_overrides_and_references_rejected_before_play(self):
        for patch in (
            {"id": "other"},
            {"schema_version": 2},
            {"hit_points": -1},
            {"stats": {"strength": "20"}},
            {"unknown": True},
            {"actions": ["base:no_such_action"]},
            {"art": "base:no_such_art"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ContentError):
                self.raw["monsters"] = [
                    dict(id="bad", ref="base:goblin", x=5, y=1, overrides=patch)
                ]
                self.session()
        self.raw.pop("monsters")
        self.raw["doors"] = [dict(id="spawn_door", ref="base:door_wood", x=1, y=1)]
        with self.assertRaises(ContentError):
            self.session()
        self.raw["doors"][0]["overrides"] = {"brush": {"door": {"state": "open"}}}
        self.session()

    def test_browser_and_engine_share_instance_properties_and_reset(self):
        self.raw["points_of_interest"] = [
            dict(
                id="chest",
                ref="base:chest",
                x=2,
                y=1,
                challenge_overrides={
                    "choices": [
                        {
                            "id": "take",
                            "text": "Взять",
                            "success": [{"kind": "gold", "amount": 13}],
                        }
                    ]
                },
            )
        ]
        engine = self.session()
        browser = TestSession(self.store, {"map_ref": "base:instances", "seed": 42})
        engine.interact("chest", "take")
        browser.command("interact", "chest", "take")
        self.assertEqual(browser.engine.state.hero.gold, engine.state.hero.gold)
        browser.reset()
        self.assertEqual(browser.engine.state.hero.gold, 0)
        self.assertFalse(browser.engine.state.level.points[0].challenge.completed)

    def test_old_map_migration_keeps_presets_and_custom_values_without_mutation(self):
        old = deepcopy(self.raw)
        old["tiles"][1][2] = "base:door_wood_locked_legendary_complex"
        old["walkability"][1][2] = False
        old["doors"] = [
            dict(
                id="old",
                ref="base:door_open",
                x=4,
                y=1,
                overrides={"brush": {"door": {"hit_points": 75}}},
            )
        ]
        original = deepcopy(old)
        migrated = migrate_map(old)
        self.assertEqual(old, original)
        self.assertEqual(migrate_map(migrated), migrated)
        self.raw = migrated
        engine = self.session()
        opened, locked = engine.state.level.doors
        self.assertEqual((opened.door.opened, opened.door.hp), (True, 75))
        self.assertEqual((locked.door.lock_dc, locked.door.lock_turns), (25, 10))


if __name__ == "__main__":
    unittest.main()
