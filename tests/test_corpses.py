"""Remains are overlays with one owner for loot, including after save/load."""

from copy import copy
import json
from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.migrations import migrate_map
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.world.maps import Position


class CorpseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="corpse_test",
            name="Останки",
            width=8,
            height=8,
            tiles=[["base:floor"] * 8 for _ in range(8)],
            walkability=[[True] * 8 for _ in range(8)],
            blocks_sight=[[False] * 8 for _ in range(8)],
            spawn=dict(x=2, y=2),
            ambient_light="bright",
            objects=[
                dict(
                    id="body",
                    ref="base:corpse",
                    x=3,
                    y=2,
                    overrides={
                        "storage": {
                            "contents": [{"item": "base:bandage", "quantity": 2}]
                        }
                    },
                )
            ],
            monsters=[
                dict(
                    id="enemy",
                    ref="base:goblin",
                    x=5,
                    y=2,
                    overrides={"inventory": ["base:dagger", "base:torch"]},
                )
            ],
        )
        self.start(self.raw)

    def start(self, raw):
        self.store.documents["maps", "dev:corpse_test"] = MapDocument.model_validate(
            migrate_map(raw)
        )
        self.e = SessionFactory(self.store).session("dev:corpse_test", seed=42)

    def reload(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_authored_body_loot_persists_and_does_not_replace_floor(self):
        e = self.e
        body = e.storage_at("body")
        self.assertTrue(e.state.walkable(Position(3, 2)))
        self.assertIn(
            "Открыть контейнер",
            [c.text for c in e.world_object("body").available_choices(e.state.hero)],
        )
        identity = body.items[0].instance_id
        self.assertTrue(e.transfer_storage("body", identity, 2).performed)
        self.assertFalse(e.transfer_storage("body", identity).performed)
        self.reload()
        self.assertEqual(self.e.storage_at("body").items, [])
        self.assertEqual(self.e.state.level.definition.tiles[2][3], "base:floor")
        self.assertIsNotNone(self.e.world_object("body"))

    def test_dead_actor_inventory_moves_once_and_destroyed_corpse_stays_destroyed(self):
        e = self.e
        enemy = e.state.monsters[0].monster
        identities = {i.instance_id for i in enemy.inventory}
        torch = next(i for i in enemy.inventory if i.id == "torch")
        torch.equipped = torch.lit = True
        fuel = torch.fuel_minutes
        enemy.hp = 0
        e.apply(Action.WAIT)
        self.assertEqual(enemy.inventory, [])
        self.assertTrue(e.state.monsters[0].corpse_created)
        corpse = next(c for c in e.state.level.containers if c.placement.id != "body")
        identifier = corpse.placement.id
        self.assertEqual({i.instance_id for i in corpse.items}, identities)
        self.assertFalse(torch.equipped or torch.lit)
        self.assertEqual(torch.fuel_minutes, fuel)
        self.e.state.position = Position(4, 2)
        self.assertTrue(
            e.transfer_storage(identifier, corpse.items[0].instance_id).performed
        )
        self.reload()
        corpse = self.e.storage_at(identifier)
        self.assertEqual(len(corpse.items), 1)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            saved = json.loads(repo.path.read_text(encoding="utf-8"))
            saved["levels"][0]["containers"].pop(identifier)
            repo.path.write_text(json.dumps(saved), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "контейнеров"):
                repo.load(store=self.store)
        self.assertNotIn("HP: 0", " ".join(self.e.inspect_cell(Position(5, 2))))
        self.e.damage_world_objects(Position(5, 2), 100, "bludgeoning")
        self.e.apply(Action.WAIT)
        self.reload()
        self.e.apply(Action.WAIT)
        self.assertIsNone(self.e.world_object(identifier))
        self.assertEqual(len(self.e.state.level.containers), 1)
        owned = [*self.e.state.hero.inventory, *(i for _, i in self.e.state.items)]
        self.assertTrue(identities.issubset({i.instance_id for i in owned}))

    def test_all_old_remains_tiles_migrate_to_inspectable_containers(self):
        for name in (
            "bones",
            "bones_pile",
            "carcass",
            "corpse",
            "remains",
            "skeleton_large",
            "skeleton_remains",
            "skull",
        ):
            with self.subTest(name=name):
                raw = {**self.raw, "objects": [], "monsters": []}
                raw["tiles"] = [["base:floor"] * 8 for _ in range(8)]
                raw["tiles"][2][3] = "base:" + name
                self.start(raw)
                self.assertEqual(
                    self.e.state.level.definition.tiles[2][3], "base:floor"
                )
                self.assertEqual(len(self.e.nearby_containers()), 1)
                self.assertEqual(
                    self.e.nearby_containers()[0].placement.ref, "base:" + name
                )
                self.assertIn(
                    self.store.get("objects", "base:" + name).name,
                    self.e.inspect_cell(Position(3, 2)),
                )

    def test_butchering_drops_remaining_container_loot_without_losing_floor(self):
        raw = {**self.raw, "monsters": []}
        raw["objects"] = [{**self.raw["objects"][0], "ref": "base:wolf_remains"}]
        self.start(raw)
        container = self.e.storage_at("body")
        bandages = {i.instance_id for i in container.items}
        self.assertTrue(
            self.e.transfer_storage("body", container.items[0].instance_id).performed
        )
        self.assertTrue(self.e.start_dismantle("body").performed)
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)
        self.assertIsNone(self.e.storage_at("body"))
        self.assertEqual(self.e.state.level.definition.tiles[2][3], "base:floor")
        owned = [*self.e.state.hero.inventory, *(i for _, i in self.e.state.items)]
        self.assertEqual(sum(i.instance_id in bandages for i in owned), 2)
        self.assertEqual(sum(i.id == "raw_meat" for _, i in self.e.state.items), 2)
        self.reload()
        self.assertIsNone(self.e.world_object("body"))

    def test_legacy_save_with_remains_floor_and_no_container_record_loads(self):
        raw = {**self.raw, "objects": [], "monsters": []}
        raw["tiles"][2][3] = "base:corpse"
        self.start(raw)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            saved = json.loads(repo.path.read_text(encoding="utf-8"))
            level = saved["levels"][0]
            level.update(definition=raw, world=raw, containers={})
            repo.path.write_text(json.dumps(saved), encoding="utf-8")
            self.e = repo.load(store=self.store)
        self.assertEqual(len(self.e.nearby_containers()), 1)
        self.assertEqual(self.e.nearby_containers()[0].items, [])


if __name__ == "__main__":
    unittest.main()
