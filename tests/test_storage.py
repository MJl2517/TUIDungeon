"""Container ownership, capacities, persistence and the two-pane input contract."""

from copy import copy
import json
from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import ContentError, PackStore
from tuidungeon.content.schemas import MapDocument, WorldObjectDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import Ability
from tuidungeon.domain.actions import SpellSource
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.storage import storage_layout, storage_click
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position
from scripts.prepare_storage import CONTAINERS


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="storage_test",
            name="Контейнеры",
            width=10,
            height=6,
            tiles=[["base:floor"] * 10 for _ in range(6)],
            walkability=[[True] * 10 for _ in range(6)],
            blocks_sight=[[False] * 10 for _ in range(6)],
            spawn=dict(x=2, y=2),
            ambient_light="bright",
            objects=[
                dict(
                    id="private",
                    ref="base:cabinet",
                    x=3,
                    y=2,
                    overrides=dict(
                        storage=dict(
                            personal=True,
                            capacity=1000,
                            contents=[
                                dict(item="base:rations", quantity=4),
                                dict(item="base:torch", quantity=2),
                            ],
                        )
                    ),
                )
            ],
            points_of_interest=[
                dict(
                    id="loot",
                    ref="base:terrain_sack",
                    x=1,
                    y=2,
                    overrides=dict(
                        storage=dict(contents=[dict(item="base:oil", quantity=3)])
                    ),
                )
            ],
        )
        self.engine = self.make_engine()

    def make_engine(self):
        self.store.documents["maps", "base:storage_test"] = MapDocument.model_validate(
            self.raw
        )
        self.store.validate_references(self.store.documents, self.store.manifests)
        return SessionFactory(self.store).session("base:storage_test", seed=42)

    def test_tags_default_settings_and_all_actual_containers(self):
        doc = WorldObjectDocument(id="box", name="Ящик", tags=["storage"])
        self.assertEqual(doc.storage.capacity, 1000)
        self.assertFalse(doc.storage.personal)
        doc = WorldObjectDocument(id="box", name="Ящик", storage={"personal": True})
        self.assertIn("storage", doc.tags)
        for category, identifiers in CONTAINERS.items():
            for identifier in identifiers:
                self.assertIn(
                    "storage", self.source.get(category, "base:" + identifier).tags
                )
        self.assertNotIn("storage", self.source.get("equipment", "base:bedroll").tags)

    def test_item_glow_survives_container_and_load_without_emitting_outside(self):
        engine = SessionFactory(self.store).session(
            "base:storage_test", character_class="base:wizard"
        )
        item = next(i for i in engine.state.hero.inventory if i.id == "spellbook")
        self.assertTrue(engine.cast_spell("light", SpellSource.CLASS, item).performed)
        self.assertTrue(
            engine.transfer_storage("private", item.instance_id, deposit=True).performed
        )
        self.assertIn("glowing", item.tags)
        self.assertEqual(engine.magic_lights(), ())
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "glowing-container.json")
            repo.save(engine)
            loaded = repo.load(store=self.store)
        restored = next(
            i
            for i in loaded.storage_at("private").items
            if i.instance_id == item.instance_id
        )
        self.assertEqual(restored.glow, item.glow)
        self.assertEqual(loaded.magic_lights(), ())
        self.assertTrue(
            loaded.transfer_storage("private", restored.instance_id).performed
        )
        self.assertIn("glowing", restored.tags)
        self.assertEqual(loaded.magic_lights()[0][0], loaded.state.position)
        for _ in range(restored.glow.remaining_turns):
            loaded.apply(Action.WAIT)
        self.assertIsNone(restored.glow)
        self.assertNotIn("glowing", restored.tags)

    def test_initial_loot_is_independent_and_stateless_templates_stay_unchanged(self):
        other = self.make_engine()
        first, second = self.engine.storage_at("private"), other.storage_at("private")
        self.assertEqual(len(first.items), 6)
        self.assertNotEqual(first.instance_id, second.instance_id)
        self.assertTrue(
            set(i.instance_id for i in first.items).isdisjoint(
                i.instance_id for i in second.items
            )
        )
        result = self.engine.transfer_storage("private", first.items[0].instance_id, 2)
        self.assertTrue(result.performed)
        self.assertEqual((len(first.items), len(second.items)), (4, 6))
        self.assertEqual(
            self.source.get("objects", "base:cabinet").storage.contents, []
        )

    def test_loot_rejects_deposits_and_personal_stash_rejects_restock(self):
        hero = self.engine.state.hero
        item = hero.inventory[0]
        before = list(hero.inventory)
        result = self.engine.transfer_storage("loot", item.instance_id, deposit=True)
        self.assertFalse(result.performed)
        self.assertEqual(hero.inventory, before)
        with self.assertRaisesRegex(ValueError, "Личный"):
            self.engine.storage_at("private").replace_loot([])
        loot = self.engine.storage_at("loot")
        self.assertTrue(
            self.engine.transfer_storage("loot", loot.items[0].instance_id, 3).performed
        )
        self.assertEqual(loot.items, [])

    def test_capacity_and_invalid_commands_are_atomic(self):
        self.raw["objects"][0]["overrides"]["storage"] = dict(
            personal=True, capacity=0.1, contents=[]
        )
        engine = self.make_engine()
        hero, container = engine.state.hero, engine.storage_at("private")
        item = next(i for i in hero.inventory if i.weight > 0.1)
        for quantity in (True, 0, -1, 2, 1.5):
            self.assertFalse(
                engine.transfer_storage(
                    "private", item.instance_id, quantity, deposit=True
                ).performed
            )
        self.assertFalse(
            engine.transfer_storage("private", item.instance_id, deposit=True).performed
        )
        self.assertIs(
            next(i for i in hero.inventory if i.instance_id == item.instance_id), item
        )
        self.assertEqual(container.items, [])
        self.assertFalse(engine.transfer_storage("missing", item.instance_id).performed)
        self.assertEqual(engine.state.turns, 0)
        engine.state.position = Position(8, 5)
        self.assertFalse(
            engine.transfer_storage("private", item.instance_id, deposit=True).performed
        )

    def test_hero_capacity_and_zero_weight_items(self):
        hero = self.engine.state.hero
        container = self.engine.storage_at("private")
        # Exact boundary accepted; another item must remain in the source.
        hero.inventory.clear()
        item = container.items[0]
        hero.carry_per_strength = item.weight / hero.stats.score(Ability.STRENGTH)
        self.assertTrue(
            self.engine.transfer_storage("private", item.instance_id).performed
        )
        remaining = next(i for i in container.items if i.id == item.id)
        self.assertFalse(
            self.engine.transfer_storage("private", remaining.instance_id).performed
        )

    def test_stacks_distinguish_resources_and_variants_and_preserve_instances(self):
        container = self.engine.storage_at("private")
        torches = [i for i in container.items if i.id == "torch"]
        self.assertEqual(len(item_stacks(torches)), 1)
        torches[1].fuel_minutes -= 1
        self.assertEqual(len(item_stacks(torches)), 2)
        torches[1].fuel_minutes += 1
        torches[1].template = self.store.get("equipment", "base:torch").model_dump(
            mode="json"
        )
        torches[1].template["glyph"] = "!"
        self.assertEqual(len(item_stacks(torches)), 2)
        torch = torches[0]
        self.assertTrue(
            self.engine.transfer_storage("private", torch.instance_id).performed
        )
        hero = self.engine.state.hero
        for item in hero.inventory:
            item.equipped = False
        torch.equipped, torch.lit, torch.fuel_minutes = True, True, 17
        self.assertTrue(
            self.engine.transfer_storage(
                "private", torch.instance_id, deposit=True
            ).performed
        )
        self.assertIs(
            next(i for i in container.items if i.instance_id == torch.instance_id),
            torch,
        )
        self.assertEqual(
            (torch.equipped, torch.lit, torch.fuel_minutes), (False, False, 17)
        )
        self.assertEqual(self.engine.state.clock.elapsed_minutes, 480)

    def test_only_loot_can_be_restocked_and_items_are_validated(self):
        loot = self.engine.storage_at("loot")
        replacement = Equipment.create(self.engine.catalog.equipment["oil"])
        loot.replace_loot([replacement])
        self.assertEqual(loot.items, [replacement])
        with self.assertRaises(ValueError):
            loot.replace_loot([replacement, replacement])
        self.assertEqual(loot.items, [replacement])

    def test_visited_container_state_survives_transition_and_save(self):
        self.raw["transitions"] = [dict(id="exit", x=2, y=3, target="base:crypt")]
        engine = self.make_engine()
        loot = engine.storage_at("loot")
        engine.transfer_storage("loot", loot.items[0].instance_id, 3)
        self.assertTrue(engine.apply(Action.SOUTH).performed)
        self.assertEqual(engine.state.level.ref, "base:crypt")
        with tempfile.TemporaryDirectory() as directory:
            repository = SaveRepository(Path(directory) / "save.json")
            repository.save(engine)
            restored = repository.load(store=self.store)
        old = restored.levels["base:storage_test"].level
        self.assertEqual(
            next(c for c in old.containers if c.placement.id == "loot").items, []
        )

    def test_content_validates_capacity_and_references_in_local_properties(self):
        self.raw["objects"][0]["overrides"]["storage"]["capacity"] = 0.1
        with self.assertRaises(ContentError):
            self.make_engine()
        self.raw["objects"][0]["overrides"]["storage"]["capacity"] = 1000
        self.raw["objects"][0]["overrides"]["storage"]["contents"][0]["item"] = (
            "base:no_such_item"
        )
        with self.assertRaises(ContentError):
            self.make_engine()

    def test_save_empty_loot_personal_resources_and_duplicate_validation(self):
        loot, private = (
            self.engine.storage_at("loot"),
            self.engine.storage_at("private"),
        )
        self.engine.transfer_storage("loot", loot.items[0].instance_id, 3)
        sword = next(i for i in self.engine.state.hero.inventory if i.id == "sword")
        sword.durability -= 3
        self.engine.transfer_storage("private", sword.instance_id, deposit=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            repository = SaveRepository(path)
            repository.save(self.engine)
            restored = repository.load(store=self.store)
            self.assertEqual(restored.storage_at("loot").items, [])
            saved_sword = next(
                i for i in restored.storage_at("private").items if i.id == "sword"
            )
            self.assertEqual(
                (saved_sword.instance_id, saved_sword.durability, saved_sword.equipped),
                (sword.instance_id, sword.durability, False),
            )
            raw = json.loads(path.read_text())
            raw["levels"][0]["containers"]["private"]["items"].append(
                raw["hero"]["inventory"][0]
            )
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                repository.load(store=self.store)
        self.assertEqual(
            private.instance_id, restored.storage_at("private").instance_id
        )

    def test_two_pane_controller_slider_cancel_and_no_movement(self):
        c = Controller(store=self.store, catalog=self.engine.catalog)
        c.engine, c.view = self.engine, View.EXPLORE
        c.storage.open("private")
        c.view = View.STORAGE
        c.handle("enter")
        self.assertIsNotNone(c.storage.pending)
        c.handle("right")
        self.assertEqual(c.storage.quantity, 2)
        c.handle("backspace")
        self.assertIsNone(c.storage.pending)
        self.assertEqual(len(self.engine.storage_at("private").items), 6)
        c.handle("f5")
        c.handle("end")
        c.handle("enter")
        self.assertEqual(len(self.engine.storage_at("private").items), 2)
        c.handle("tab")
        self.assertEqual(c.storage.side, 0)
        for width, height in ((80, 24), (160, 50)):
            rows = render(c, width, height)
            self.assertEqual(len(rows), height)
            self.assertTrue(all(len(row) == width for row in rows))
            self.assertIn("F5", "\n".join(rows))
        self.assertEqual(self.engine.state.position, Position(2, 2))
        self.assertEqual(self.engine.state.turns, 0)
        c.handle("backspace")
        self.assertIs(c.view, View.EXPLORE)

    def test_click_slider_and_open_through_context(self):
        c = Controller(store=self.store, catalog=self.engine.catalog)
        c.engine, c.view = self.engine, View.EXPLORE
        self.engine.state.position = Position(4, 2)
        c.open_interaction()
        if c.view is View.INTERACTION:
            point = next(
                p for p in c.engine.nearby_points() if p.placement.id == c.point_id
            )
            c.handle(
                str(
                    next(
                        i + 1
                        for i, choice in enumerate(
                            point.available_choices(c.engine.state.hero)
                        )
                        if choice.id == "open_storage"
                    )
                )
            )
        self.assertIs(c.view, View.STORAGE)
        c.handle("enter")
        _, rect, rows, _ = storage_layout(c, 100, 30)
        index = len(rows) - 4
        start = rows[index].index("[") + 1
        storage_click(c, rect.x + 2 + start + 19, rect.y + 1 + index, 100, 30)
        self.assertEqual(c.storage.quantity, 4)


if __name__ == "__main__":
    unittest.main()
