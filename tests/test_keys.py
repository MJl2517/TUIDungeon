"""Level-bound keys and authored unique locks share the real world commands."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, item_record, restore_item
from tuidungeon.content.packs import PackStore, ContentError, validate_storage
from tuidungeon.content.schemas import EquipmentDocument, LockSpec
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.keys import key_matches
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.inventory import item_details
from tuidungeon.presentation.tui import Controller, View, popup_content
from tuidungeon.world.maps import Position


class KeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def engine(self):
        return self.factory.session(
            "tiles:keys_lab", character_class="dev:empty_tester", seed=42
        )

    def collect(self, e):
        keys = {}
        for p, item in list(e.state.items):
            if item.definition.key_kind:
                e.state.position = Position(p.x, p.y)
                self.assertTrue(e.pickup_item().performed)
                keys[item.definition.key_kind] = item
        return keys

    def go(self, e, target):
        e.state.position = Position(12, 8)
        self.assertTrue(e.apply(Action.EAST).performed)
        self.assertEqual(e.state.level.ref, target)

    def unlock(self, e, identifier, kind):
        e.state.position = Position(
            5 if kind == "door" else 8, 6 if identifier.startswith("unique") else 3
        )
        return (
            e.interact_door(identifier, "use_key")
            if kind == "door"
            else e.interact_container_lock(identifier, "unlock_container_key")
        )

    def test_types_origin_unique_priority_and_failed_actions_are_free(self):
        e = self.engine()
        keys = self.collect(e)
        door = e._door("ordinary_door").door
        chest = next(
            c.lock
            for c in e.state.level.containers
            if c.placement.id == "ordinary_chest"
        )
        self.assertTrue(key_matches(keys["door"], door, "door", e.state.level.ref))
        self.assertFalse(
            key_matches(keys["container"], door, "door", e.state.level.ref)
        )
        self.assertTrue(
            key_matches(keys["container"], chest, "container", e.state.level.ref)
        )
        self.assertEqual(keys["door"].key_level, "tiles:keys_lab")
        self.assertIn("Ключи: первый уровень", "\n".join(item_details(keys["door"])))
        hero = e.state.hero
        for kind, wrong in (("door", keys["container"]), ("container", keys["door"])):
            hero.inventory[:] = [wrong]
            before = e.state.turns, hero.carried_weight
            self.assertFalse(
                self.unlock(
                    e, "ordinary_door" if kind == "door" else "ordinary_chest", kind
                ).performed
            )
            self.assertEqual((e.state.turns, hero.carried_weight), before)
        hero.inventory[:] = [keys["door"], keys["container"]]
        self.assertFalse(self.unlock(e, "unique_door", "door").performed)
        self.assertFalse(self.unlock(e, "unique_chest", "container").performed)
        self.assertTrue(self.unlock(e, "ordinary_door", "door").performed)
        self.assertTrue(self.unlock(e, "ordinary_chest", "container").performed)
        hero.inventory.append(keys["unique"])
        wrong = Equipment.create(
            replace(keys["unique"].definition, key_code="OTHER123")
        )
        self.assertFalse(
            key_matches(wrong, e._door("unique_door").door, "door", e.state.level.ref)
        )
        self.assertTrue(self.unlock(e, "unique_door", "door").performed)
        self.assertTrue(self.unlock(e, "unique_chest", "container").performed)
        self.assertEqual(len(hero.inventory), 3)

    def test_cross_level_drop_storage_and_save_keep_origin_and_unique_code(self):
        e = self.engine()
        keys = self.collect(e)
        origin_ids = {k: i.instance_id for k, i in keys.items()}
        self.go(e, "tiles:keys_annex")
        self.assertFalse(self.unlock(e, "ordinary_door", "door").performed)
        self.assertFalse(self.unlock(e, "ordinary_chest", "container").performed)
        self.assertTrue(self.unlock(e, "unique_door", "door").performed)
        self.assertTrue(self.unlock(e, "unique_chest", "container").performed)
        self.assertTrue(e.place_item(keys["door"], e.state.position).performed)
        self.assertTrue(e.pickup_item().performed)
        self.assertEqual(keys["door"].key_level, "tiles:keys_lab")
        e.state.position = Position(2, 6)
        self.assertTrue(e.open_container("key_stash").performed)
        self.assertTrue(
            e.transfer_storage(
                "key_stash", keys["door"].instance_id, deposit=True
            ).performed
        )
        self.assertTrue(
            e.transfer_storage("key_stash", keys["door"].instance_id).performed
        )
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "keys.json")
            repo.save(e)
            e = repo.load(store=self.store)
        for kind, identifier in origin_ids.items():
            item = next(
                i for i in e.state.hero.inventory if i.instance_id == identifier
            )
            self.assertEqual(
                item.key_level, None if kind == "unique" else "tiles:keys_lab"
            )
            if kind == "unique":
                self.assertEqual(item.definition.key_code, "KEYS2026")
        self.assertFalse(e._door("unique_door").door.locked)
        e._door("unique_door").door.locked = True
        self.assertTrue(self.unlock(e, "unique_door", "door").performed)
        local = self.collect(e)
        self.assertEqual(local["door"].key_level, "tiles:keys_annex")
        self.assertTrue(self.unlock(e, "ordinary_door", "door").performed)
        self.assertTrue(self.unlock(e, "ordinary_chest", "container").performed)
        self.go(e, "tiles:keys_lab")
        e.state.hero.inventory[:] = [local["door"], local["container"]]
        self.assertFalse(self.unlock(e, "ordinary_door", "door").performed)
        e.state.hero.inventory.append(keys["door"])
        self.assertTrue(self.unlock(e, "ordinary_door", "door").performed)

    def test_container_authored_codes_furniture_and_stacks_preserve_key_identity(self):
        e = self.engine()
        c = next(c for c in e.state.level.containers if c.placement.id == "key_stash")
        unique = next(i for i in c.items if i.definition.key_kind == "unique")
        self.assertEqual(unique.definition.key_code, "KEYS2026")
        self.assertEqual(unique.template["key_code"], "KEYS2026")
        e.state.position = Position(2, 6)
        self.assertTrue(e.lift_furniture("key_stash").performed)
        cargo = next(i for i in e.state.hero.inventory if i.furniture)
        restored = restore_item(item_record(cargo), e.catalog)
        self.assertEqual(restored.furniture.items[0].definition.key_code, "KEYS2026")
        self.assertEqual(restored.furniture.items[1].key_level, "tiles:keys_lab")
        d = e.catalog.equipment["tiles:key_door"]
        first = Equipment.create(d, level_ref="tiles:keys_lab")
        second = Equipment.create(d, level_ref="tiles:keys_annex")
        same = Equipment.create(d, level_ref="tiles:keys_lab")
        self.assertEqual(
            sorted(s.quantity for s in item_stacks([first, second, same])), [1, 2]
        )
        other = Equipment.create(replace(unique.definition, key_code="OTHER123"))
        self.assertEqual(len(item_stacks([unique, other])), 2)
        e.state.position = Position(8, 6)
        self.assertTrue(e.lift_furniture("unique_chest").performed)
        locked_cargo = next(
            i
            for i in e.state.hero.inventory
            if i.furniture and i.furniture.container_spec.lock
        )
        self.assertEqual(
            locked_cargo.furniture.container_spec.lock.key_code, "KEYS2026"
        )
        self.go(e, "tiles:keys_annex")
        self.assertTrue(e.place_furniture(locked_cargo, Position(3, 4)).performed)
        moved = next(
            c
            for c in e.state.level.containers
            if (c.placement.x, c.placement.y) == (3, 4)
        )
        e.state.hero.inventory.append(Equipment.create(unique.definition))
        self.assertTrue(
            e.interact_container_lock(
                moved.placement.id, "unlock_container_key"
            ).performed
        )

    def test_authoring_validation_and_legacy_item_saves(self):
        self.assertEqual(LockSpec(key_code=" keys2026 ").key_code, "KEYS2026")
        for code in ("", "../secret", "x", "A" * 17):
            with self.assertRaises(ValueError):
                LockSpec(key_code=code)
        raw = self.store.get("equipment", "tiles:key_door").model_dump(mode="json")
        with self.assertRaises(ValueError):
            EquipmentDocument.model_validate(dict(raw, key_code="KEYS2026"))
        # Validate a real authored container through the pack reference boundary.
        from tuidungeon.content.schemas import MODELS

        raw = self.store.get("objects", "base:cabinet").model_dump(mode="json")
        raw["storage"]["contents"] = [dict(item="tiles:key_door", key_code="KEYS2026")]
        with self.assertRaises(ContentError):
            validate_storage(
                MODELS["objects"].model_validate(raw), self.store.documents
            )
        item = Equipment.create(self.factory.catalog.equipment["sword"])
        record = item_record(item)
        from tuidungeon.application.saves import ItemRecord

        old = record.model_dump()
        old.pop("key_level")
        old.pop("key_level_name")
        self.assertIsNone(
            restore_item(ItemRecord.model_validate(old), self.factory.catalog).key_level
        )

    def test_inventory_key_action_opens_existing_lock_interaction_without_spending_time(
        self,
    ):
        e = self.engine()
        keys = self.collect(e)
        e.state.position = Position(5, 3)
        c = Controller(
            42,
            store=self.store,
            catalog=e.catalog,
            test_map=True,
            map_ref="tiles:keys_lab",
        )
        c.engine = e
        c.open_item(keys["door"])
        self.assertEqual(popup_content(c)[2][0], "Выбрать замок рядом")
        before = e.state.turns
        c.handle("1")
        self.assertEqual(c.view, View.INTERACTION)
        self.assertEqual(e.state.turns, before)
        choices = e._door("ordinary_door").available_choices(e.state.hero)
        c.handle(
            str(
                next(i for i, choice in enumerate(choices, 1) if choice.id == "use_key")
            )
        )
        self.assertFalse(e._door("ordinary_door").door.locked)
        self.assertEqual(e.state.turns, before + 1)


if __name__ == "__main__":
    unittest.main()
