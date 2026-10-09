"""Single-source content, old documents, geometry and save compatibility."""

from copy import copy, deepcopy
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from scripts.audit_content import audit
from scripts.import_tileset import install
from scripts.migrate_content import migrate
from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import ItemRecord, SaveRepository, restore_item
from tuidungeon.content.migrations import compatibility, migrate_document, migrate_map
from tuidungeon.content.packs import DEFAULT_PACKS, PROJECT_ROOT, PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.domain.definitions import DiceExpression
from tuidungeon.world.maps import Position


class ContentRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def legacy_map(self):
        raw = dict(
            id="revision",
            name="Миграция",
            width=10,
            height=5,
            tiles=[["base:floor"] * 10 for _ in range(5)],
            walkability=[[True] * 10 for _ in range(5)],
            blocks_sight=[[False] * 10 for _ in range(5)],
            spawn=dict(x=1, y=1),
            ambient_light="bright",
            equipment=[
                dict(
                    id="loot",
                    ref="base:terrain_decor_sword",
                    x=2,
                    y=1,
                    overrides={"weight": 3.0},
                )
            ],
        )
        for x, ref in (
            (2, "decor_sword"),
            (3, "table"),
            (4, "bookcase"),
            (5, "spikes_hidden"),
            (6, "torch_wall"),
            (7, "door_wood"),
        ):
            source = compatibility()["tiles"]["base:" + ref]["legacy"]
            raw["tiles"][1][x] = "base:" + ref
            raw["walkability"][1][x] = source["walkable"]
            raw["blocks_sight"][1][x] = source["blocks_sight"]
        return raw

    def store_for(self, raw):
        store = copy(self.source)
        store.documents = dict(store.documents)
        store.documents["maps", "base:revision"] = MapDocument.model_validate(
            migrate_map(raw)
        )
        store.validate_references(store.documents, store.manifests)
        return store

    def test_native_library_has_no_copies_and_explicit_item_types(self):
        self.assertEqual(audit(self.source)["errors"], [])
        for (category, ref), doc in self.source.documents.items():
            if category == "equipment":
                self.assertIsNotNone(doc.category, ref)
            if category == "tiles":
                self.assertFalse(any(doc.brush.model_dump().values()), ref)
        for ref, record in compatibility()["tiles"].items():
            self.assertNotIn(("tiles", ref), self.source.documents)
            self.assertIn((record["category"], record["ref"]), self.source.documents)

    def test_migration_is_idempotent_preserves_instances_and_underlying_floor(self):
        raw = self.legacy_map()
        original = deepcopy(raw)
        migrated = migrate_map(raw)
        self.assertEqual(raw, original)
        self.assertEqual(migrated, migrate_map(migrated))
        self.assertEqual(len(migrated["equipment"]), 1)
        loot = migrated["equipment"][0]
        self.assertEqual(
            (loot["id"], loot["ref"], loot["overrides"]["weight"]),
            ("loot", "base:sword", 3.0),
        )
        self.assertEqual(loot["overrides"]["weapon_damage"], "1d6")
        self.assertEqual(migrated["tiles"][1][2:8], ["base:floor"] * 6)
        store = self.store_for(raw)
        engine = SessionFactory(store).session("base:revision")
        terrain = engine.state.level.terrain
        self.assertFalse(terrain.walkability[1][3])
        self.assertFalse(terrain.walkability[1][4])
        self.assertFalse(terrain.blocks_sight[1][3])
        self.assertTrue(terrain.blocks_sight[1][4])
        self.assertFalse(terrain.walkability[1][7])
        self.assertIn("Стол", " ".join(engine.inspect_cell(Position(3, 1))))
        self.assertNotIn("шип", " ".join(engine.inspect_cell(Position(5, 1))).lower())
        self.assertTrue(engine.apply(Action.EAST).performed)
        self.assertTrue(engine.pickup_item().performed)
        engine.apply(Action.WEST)
        self.assertEqual(engine.render_cells((2, 1, 1, 1))[0][0].char, ".")

    def test_old_save_definition_and_item_resources_remain_loadable(self):
        raw = self.legacy_map()
        store = self.store_for(raw)
        engine = SessionFactory(store).session("base:revision", seed=42)
        with tempfile.TemporaryDirectory() as directory:
            repository = SaveRepository(Path(directory) / "save.json")
            repository.save(engine)
            saved = json.loads(repository.path.read_text())
            saved["levels"][0]["definition"] = raw
            # Earlier migration versions retained redundant properties. They
            # describe the same map and must not invalidate the save.
            current = store.get("maps", "base:revision").model_dump(mode="json")
            current["equipment"][0]["overrides"]["slot"] = "weapon"
            store.documents["maps", "base:revision"] = MapDocument.model_validate(
                current
            )
            repository.path.write_text(json.dumps(saved))
            restored = repository.load(store=store)
            self.assertEqual(
                restored.state.level.definition, store.get("maps", "base:revision")
            )
            changed = deepcopy(current)
            changed["equipment"][0]["overrides"]["weight"] = 4.0
            store.documents["maps", "base:revision"] = MapDocument.model_validate(
                changed
            )
            with self.assertRaisesRegex(ValueError, "Карта изменена"):
                repository.load(store=store)
        record = ItemRecord(
            definition="terrain_decor_sword",
            instance_id="old",
            equipped=False,
            durability=18,
        )
        item = restore_item(record, self.source.runtime_catalog())
        self.assertEqual(
            (item.id, item.instance_id, item.durability), ("sword", "old", 18)
        )
        self.assertEqual(item.definition.weapon_damage, DiceExpression.parse("1d6"))
        self.assertEqual(item.definition.durability, 30)

    def test_reference_migration_preserves_narrative_and_plugin_parameters(self):
        raw = {
            "starting_items": ["base:terrain_decor_dagger"],
            "description": "base:terrain_decor_dagger",
            "params": {"item": "base:terrain_decor_dagger"},
        }
        migrated = migrate_document(raw, "classes")
        self.assertEqual(migrated["starting_items"], ["base:dagger"])
        self.assertEqual(migrated["description"], raw["description"])
        self.assertEqual(migrated["params"], raw["params"])

    def test_import_does_not_resurrect_copies_and_disk_migration_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "packs"
            shutil.copytree(DEFAULT_PACKS, root)
            self.assertEqual(
                install(
                    PROJECT_ROOT / "docs/reference/tui_dungeon_tileset_colored.txt",
                    root / "base",
                ),
                0,
            )
            path = root / "base/maps/revision.json"
            original = json.dumps(self.legacy_map(), ensure_ascii=False).encode()
            path.write_bytes(original)
            backup = Path(directory) / "backup"
            count, _ = migrate(root, backup, write=True)
            self.assertEqual(count, 1)
            self.assertEqual(
                (backup / "base/maps/revision.json").read_bytes(), original
            )
            self.assertEqual(migrate(root, backup, write=True), (0, None))
            self.assertFalse(audit(PackStore(root))["errors"])


if __name__ == "__main__":
    unittest.main()
