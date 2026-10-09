"""Damage arithmetic and end-to-end authoring, equipment and save contracts."""

from copy import copy
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest

from pydantic import ValidationError

from tests.test_extension import FixedRng
from tests import test_doors as door_fixtures
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import (
    Effect,
    MonsterDocument,
    DamageDefenses,
    MapDocument,
)
from tuidungeon.domain.actors import Hero, Monster
from tuidungeon.domain.damage import DAMAGE_TYPES, DAMAGE_GROUPS, DamageProfile
from tuidungeon.domain.definitions import EffectSpec
from tuidungeon.domain.doors import Door
from tuidungeon.domain.effects import EffectRegistry
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import Dice
from tuidungeon.domain.stats import Stats
from tuidungeon.world.maps import Position


class DamageRulesTests(unittest.TestCase):
    def test_thirteen_types_and_disjoint_groups(self):
        self.assertEqual(len(DAMAGE_TYPES), 13)
        self.assertEqual(set().union(*DAMAGE_GROUPS.values()), DAMAGE_TYPES)
        self.assertEqual(sum(map(len, DAMAGE_GROUPS.values())), 13)

    def test_resistance_rounds_down_vulnerability_doubles_and_immunity_wins(self):
        for kind in DAMAGE_TYPES:
            with self.subTest(kind=kind):
                self.assertEqual(DamageProfile().resolve(5, kind).resolved_amount, 5)
                profile = DamageProfile(resistances={kind})
                self.assertEqual(profile.resolve(5, kind).resolved_amount, 2)
                self.assertEqual(profile.resolve(1, kind).resolved_amount, 0)
                profile = DamageProfile(vulnerabilities={kind})
                self.assertEqual(profile.resolve(5, kind).resolved_amount, 10)
                profile = profile.merge(
                    DamageProfile(resistances={kind}, immunities={kind})
                )
                self.assertEqual(profile.resolve(5, kind).resolved_amount, 0)

    def test_overlapping_groups_do_not_stack_and_opposites_cancel_before_rounding(self):
        profile = DamageProfile(resistances={"fire", "elemental"})
        self.assertEqual(profile.resolve(7, "fire").resolved_amount, 3)
        self.assertEqual(profile.merge(profile).resolve(7, "fire").resolved_amount, 3)
        profile = profile.merge(DamageProfile(vulnerabilities={"fire"}))
        result = profile.resolve(7, "fire")
        self.assertEqual((result.resolved_amount, result.response), (7, "cancelled"))
        self.assertEqual(profile.resolve(7, "cold").resolved_amount, 3)
        self.assertEqual(profile.resolve(7, "piercing").resolved_amount, 7)

    def test_invalid_values_and_groups_cannot_be_damage_types(self):
        for amount, kind in (
            (-1, "fire"),
            (1.5, "fire"),
            (True, "fire"),
            (1, "physical"),
            (1, "ice"),
        ):
            with self.subTest(amount=amount, kind=kind), self.assertRaises(ValueError):
                DamageProfile().resolve(amount, kind)
        with self.assertRaises(ValueError):
            DamageProfile(immunities={"unknown"})
        for raw in (
            dict(kind="heal", damage_type="fire"),
            dict(kind="damage", damage_type="physical"),
        ):
            with self.assertRaises(ValidationError):
                Effect.model_validate(raw)
        self.assertEqual(
            DamageDefenses(resistances=["physical"]).resistances, ["physical"]
        )

    def test_door_materials_use_same_resolver_and_pickaxe_is_a_source_trait(self):
        stone = Door(material="stone", max_hp=30, hp=30)
        self.assertEqual(stone.take_damage(4, "piercing"), 0)
        self.assertEqual(stone.take_damage(4, "piercing", source_tags={"pickaxe"}), 4)
        self.assertEqual(stone.take_damage(4, "fire", source_tags={"pickaxe"}), 0)
        with self.assertRaises(ValueError):
            stone.take_damage(4, None)
        for material in ("bars", "steel"):
            self.assertEqual(Door(material=material).take_damage(4, "acid"), 8)
        self.assertEqual(Door(material="adamantine").take_damage(100, "force"), 0)


class DamageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.catalog = cls.store.runtime_catalog()

    def hero(self):
        return Hero.create("human", "warrior", Stats((12,) * 6), catalog=self.catalog)

    def test_each_component_is_resolved_separately_and_does_not_apply_statuses(self):
        hero = self.hero()
        hero.hp = hero.max_hp = 100
        hero.innate_damage_profile = DamageProfile(
            resistances={"fire"}, immunities={"poison"}
        )
        effects = tuple(
            EffectSpec("damage", 5, damage_type=kind)
            for kind in ("fire", "cold", "poison")
        )
        results = EffectRegistry.default().apply_all(
            effects, hero, Dice(random.Random(1))
        )
        self.assertEqual([r.amount for r in results], [2, 5, 0])
        self.assertEqual(hero.hp, 93)
        self.assertEqual(hero.conditions, {})
        self.assertEqual(results[0].payload()["raw_amount"], 5)
        self.assertEqual(results[2].response, "immune")
        hero.hp = 1
        outcome = EffectRegistry.default().apply_all(
            (effects[1],), hero, Dice(random.Random(1))
        )[0]
        self.assertEqual(
            (outcome.raw_amount, outcome.resolved_amount, outcome.amount), (5, 5, 1)
        )

    def test_race_class_and_equipped_usable_items_combine_defenses(self):
        hero = self.hero()
        race = replace(hero.race, damage_profile=DamageProfile(resistances={"fire"}))
        character_class = replace(
            hero.character_class, damage_profile=DamageProfile(vulnerabilities={"cold"})
        )
        hero = Hero.create(
            race, character_class, Stats((12,) * 6), catalog=self.catalog
        )
        item = Equipment.create(
            replace(
                self.catalog.equipment["shield"],
                durability=5,
                damage_profile=DamageProfile(immunities={"acid"}),
            )
        )
        hero.inventory.append(item)
        self.assertEqual(hero.damage_profile.resolve(4, "acid").resolved_amount, 4)
        self.assertTrue(hero.equip(item))
        self.assertEqual(hero.take_damage(4, "acid"), 0)
        self.assertEqual(hero.damage_profile.resolve(4, "fire").resolved_amount, 2)
        self.assertEqual(hero.damage_profile.resolve(4, "cold").resolved_amount, 8)
        item.wear(5)
        self.assertEqual(hero.damage_profile.resolve(4, "acid").resolved_amount, 4)

    def test_attacks_use_weapon_type_and_target_definition(self):
        hero = self.hero()
        hero.inventory.clear()
        target = Monster.create("skeleton", catalog=self.catalog)
        for weapon_id, expected in (("dagger", 1), ("sword", 3), ("staff", 6)):
            hero.inventory.clear()
            weapon = Equipment.create(self.catalog.equipment[weapon_id], equipped=True)
            hero.inventory.append(weapon)
            target.hp = target.max_hp
            result = hero.attack(target, Dice(FixedRng(20, 2)))
            self.assertTrue(result.success)
            self.assertEqual(result.effects[0].amount, expected)
            self.assertEqual(result.effects[0].damage_type, weapon.damage_type)
        self.assertEqual(target.take_damage(100, "poison"), 0)

    def test_legacy_effects_remain_untyped_and_no_general_undead_rules(self):
        target = Monster.create("skeleton", catalog=self.catalog)
        self.assertEqual(target.take_damage(3), 3)
        self.assertEqual(target.take_damage(3, "radiant"), 3)
        hero = self.hero()
        before = hero.hp
        hero.take_damage(2, "acid")
        self.assertEqual(hero.hp, before - 2)
        self.assertEqual(hero.armor_class, self.hero().armor_class)

    def test_schema_compilation_and_save_roundtrip(self):
        store = copy(self.store)
        store.documents = dict(self.store.documents)
        raw = self.store.get("monsters", "base:goblin").model_dump(mode="json")
        raw["damage_profile"] = dict(resistances=["elemental"], immunities=["psychic"])
        store.documents["monsters", "base:goblin"] = MonsterDocument.model_validate(raw)
        store.documents["maps", "base:damage_save"] = MapDocument(
            id="damage_save",
            name="Проверка сохранения защиты",
            width=8,
            height=7,
            tiles=[["base:floor"] * 8 for _ in range(7)],
            walkability=[[True] * 8 for _ in range(7)],
            blocks_sight=[[False] * 8 for _ in range(7)],
            spawn={"x": 2, "y": 2},
            ambient_light="bright",
        )
        engine = SessionFactory(store).session("base:damage_save", seed=42)
        monster = engine.add_monster("goblin", Position(2, 5)).monster
        self.assertEqual(monster.take_damage(3, "psychic"), 0)
        self.assertEqual(monster.take_damage(3, "fire"), 1)
        engine.state.hero.innate_damage_profile = DamageProfile(
            resistances={"physical"}
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SaveRepository(Path(directory) / "save.json")
            repository.save(engine)
            restored = repository.load(store=store)
            self.assertEqual(
                restored.state.monsters[0].monster.take_damage(3, "psychic"), 0
            )
            self.assertEqual(
                restored.state.hero.damage_profile.resolve(
                    5, "slashing"
                ).resolved_amount,
                2,
            )
            saved = json.loads(repository.path.read_text())
            # Legacy records use defenses from their current definitions.
            saved["hero"].pop("damage_profile")
            repository.path.write_text(json.dumps(saved), encoding="utf-8")
            old = repository.load(store=store)
            self.assertEqual(
                old.state.hero.damage_profile.resolve(5, "slashing").resolved_amount, 5
            )


class ExplicitIgnitionTests(unittest.TestCase):
    setup_map = door_fixtures.DoorTests.setup_map

    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def test_ordinary_fire_does_not_ignite_but_explicit_ignition_does(self):
        engine = self.setup_map()
        target = Position(4, 2)
        self.assertEqual(engine.damage_cell(target, 2, "fire"), 2)
        self.assertFalse(self.instance.door.burning)
        self.assertEqual(engine.damage_cell(target, 2, "fire", ignite=True), 2)
        self.assertTrue(self.instance.door.burning)

    def test_invalid_damage_cannot_consume_oil_and_fire_uses_character_defenses(self):
        engine = self.setup_map()
        target = engine.state.position
        engine.state.oil[target] = 5
        with self.assertRaises(ValueError):
            engine.damage_cell(target, 3, "unknown")
        self.assertEqual(engine.state.oil[target], 5)
        engine.state.hero.innate_damage_profile = DamageProfile(immunities={"fire"})
        hp = engine.state.hero.hp
        engine.damage_cell(target, 3, "fire")
        self.assertEqual(engine.state.hero.hp, hp)
        self.assertNotIn(target, engine.state.oil)


if __name__ == "__main__":
    unittest.main()
