"""Semantic traits are separate from tool permissions and runtime conditions."""

import json
import unittest

from scripts.tag_gameplay import collect_updates, inventory
from tuidungeon.application.factories import SessionFactory
from tuidungeon.content.catalog import ContentCatalog, DEFAULT_ROOT
from tuidungeon.content.compiler import compile_definition
from tuidungeon.content.packs import PackStore, PROJECT_ROOT
from tuidungeon.content.schemas import (
    ActionDocument,
    EquipmentDocument,
    RaceDocument,
    SpellDocument,
)
from tuidungeon.domain.actors import Monster
from tuidungeon.domain.definitions import EquipmentDefinition, EffectSpec
from tuidungeon.domain.doors import Door
from tuidungeon.domain.equipment import Equipment, ItemGlow
from tuidungeon.domain.liquids import VesselDefinition, spend_liquid
from tuidungeon.domain.tags import (
    TAG_CATALOG,
    TAG_GROUPS,
    interaction_tags,
    liquid_tags,
)


class GameplayTagsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.catalog = cls.store.runtime_catalog()

    def test_catalog_coverage_and_idempotence(self):
        self.assertEqual(collect_updates(), [])
        rows = inventory()
        self.assertEqual(
            {r["category"] for r in rows},
            {
                "equipment",
                "spells",
                "actions",
                "monsters",
                "tiles",
                "objects",
                "points_of_interest",
                "traps",
                "challenges",
                "races",
                "classes",
                "backgrounds",
                "recipes",
            },
        )
        self.assertEqual(len({(r["category"], r["ref"]) for r in rows}), len(rows))
        self.assertEqual(
            sum(len(group) for group in TAG_GROUPS.values()), len(TAG_CATALOG)
        )
        saved = json.loads(
            (PROJECT_ROOT / "docs/gameplay-tags.json").read_text(encoding="utf8")
        )
        self.assertEqual(saved["tags"], TAG_CATALOG)
        self.assertEqual(saved["content"], json.loads(json.dumps(rows)))
        self.assertGreater(len(rows), 600)

    def test_materials_are_explicit_and_independent(self):
        for ref, tags in {
            "sword": {"metal"},
            "pickaxe": {"metal", "wooden", "flammable"},
            "waterskin": {"leather", "vessel"},
            "water_flask": {"glass", "vessel", "fragile"},
            "cooking_pot": {"metal", "iron", "heat_safe"},
            "poison_herb": {"organic", "plants", "poison", "flammable"},
        }.items():
            self.assertTrue(tags <= interaction_tags(self.catalog.equipment[ref]), ref)
        for ref, tag in [
            ("spellbook", "magic"),
            ("terrain_artifact_legendary", "holy"),
            ("terrain_artifact_unidentified", "cursed"),
        ]:
            self.assertNotIn(tag, interaction_tags(self.catalog.equipment[ref]))
        self.assertNotIn(
            "edible", interaction_tags(self.store.get("tiles", "base:mushroom"))
        )
        self.assertNotIn(
            "flammable",
            interaction_tags(
                EquipmentDefinition(
                    "protected", "Защищённое дерево", tags=frozenset({"wooden"})
                )
            ),
        )

    def test_breakage_preserves_material_not_permission(self):
        item = Equipment.create(self.catalog.equipment["dagger"])
        item.wear(item.durability)
        self.assertNotIn("blade", item.tags)
        self.assertTrue(
            {"metal", "state_broken", "repairable"} <= interaction_tags(item)
        )

    def test_contents_do_not_leak_into_empty_or_refilled_vessel(self):
        definition = EquipmentDefinition(
            "poison_vial",
            "Яд",
            tags=frozenset({"glass"}),
            properties=(
                EffectSpec("damage", amount=2, damage_type="poison"),
                EffectSpec("condition", condition="poisoned"),
            ),
            vessel=VesselDefinition(initial_kind="poisoned_water", initial_portions=1),
        )
        item = Equipment.create(definition)
        self.assertTrue(
            {"liquid", "water", "poison", "applies_poison", "damage", "condition"}
            <= interaction_tags(item)
        )
        self.assertFalse(
            {"poison", "damage", "condition", "liquid"}
            & interaction_tags(item, include_contents=False)
        )
        spend_liquid(item, 1)
        self.assertFalse(
            {"poison", "damage", "condition", "applies_poison", "liquid"}
            & interaction_tags(item)
        )
        self.assertTrue({"glass", "state_empty"} <= interaction_tags(item))
        item.liquid_kind, item.liquid_portions = "holy_water", 1
        self.assertTrue(
            {"holy", "water", "liquid", "state_filled"} <= interaction_tags(item)
        )
        self.assertFalse({"poison", "magic"} & interaction_tags(item))
        self.assertEqual(liquid_tags(None), frozenset())

    def test_effects_do_not_invent_side_effects(self):
        self.assertEqual(
            interaction_tags(EffectSpec("damage", amount=3, damage_type="fire")),
            {"damage", "fire"},
        )
        poison = interaction_tags(self.catalog.spells["poison_spray"])
        self.assertTrue({"magic", "damage", "poison"} <= poison)
        self.assertNotIn("applies_poison", poison)
        self.assertTrue(
            {"attack", "piercing", "poison", "applies_poison"}
            <= interaction_tags(self.catalog.monsters["goblin"].special_actions[0])
        )
        self.assertNotIn("cold", interaction_tags(self.catalog.spells["chill_touch"]))
        self.assertIn("necrotic", interaction_tags(self.catalog.spells["chill_touch"]))
        self.assertNotIn(
            "holy",
            interaction_tags(EffectSpec("damage", amount=3, damage_type="radiant")),
        )
        self.assertEqual(interaction_tags(EffectSpec("gold", amount=3)), {"reward"})
        self.assertNotIn(
            "light_source", interaction_tags(self.catalog.spells["daylight"])
        )

    def test_body_does_not_inherit_inventory_or_attacks(self):
        engine = SessionFactory(self.store).session("base:dungeon")
        hero = engine.state.hero
        hero.inventory[:] = [
            Equipment.create(self.catalog.equipment["torch"]),
            Equipment.create(self.catalog.equipment["oil"]),
        ]
        hero.conditions["poisoned"] = 2
        self.assertTrue({"wooden", "flammable"} <= hero.tags)
        self.assertTrue(
            {"humanoid", "organic", "living", "state_poisoned"}
            <= interaction_tags(hero)
        )
        self.assertFalse({"wooden", "flammable", "poison"} & interaction_tags(hero))
        goblin = Monster.create("goblin", catalog=self.catalog)
        goblin.conditions["frightened"] = 2
        self.assertIn("state_frightened", interaction_tags(goblin))
        self.assertNotIn("poison", interaction_tags(goblin))
        self.assertTrue(
            {"bone", "undead"}
            <= interaction_tags(Monster.create("skeleton", catalog=self.catalog))
        )

    def test_world_capabilities_and_live_campfire(self):
        engine = SessionFactory(self.store).session("dev:crafting_lab")
        objects = [
            engine.world_object(p.id) for p in engine.state.level.definition.objects
        ]
        bench = next(o for o in objects if o and o.definition.id == "workbench")
        self.assertTrue(
            {"wooden", "destructible", "repairable", "station"}
            <= interaction_tags(bench)
        )
        bench.definition = self.store.get("objects", "base:campfire")
        bench.state.fuel_minutes = 10
        self.assertNotIn("heat", interaction_tags(bench))
        bench.state.lit = True
        self.assertTrue(
            {"heat", "state_burning", "state_glowing"} <= interaction_tags(bench)
        )
        self.assertNotIn(
            "destructible", interaction_tags(self.store.get("tiles", "base:wall"))
        )
        self.assertIn(
            "readable",
            interaction_tags(self.store.get("points_of_interest", "base:stone_tablet")),
        )
        self.assertNotIn(
            "readable",
            interaction_tags(self.store.get("points_of_interest", "base:terrain_book")),
        )

    def test_glow_and_door_state_are_not_fire_damage(self):
        torch = Equipment.create(self.catalog.equipment["torch"])
        self.assertIn("ignite", interaction_tags(torch))
        self.assertNotIn("state_burning", interaction_tags(torch))
        self.assertFalse(torch.can_ignite)
        torch.glow = ItemGlow(2, 6, 3)
        self.assertTrue(
            {"magic", "state_glowing", "light_source"} <= interaction_tags(torch)
        )
        self.assertNotIn("state_burning", interaction_tags(torch))
        door = Door(locked=True)
        self.assertTrue(
            {"wooden", "destructible", "door", "state_locked", "state_closed"}
            <= interaction_tags(door)
        )
        door.hp = 0
        self.assertTrue({"state_broken", "state_open"} <= interaction_tags(door))
        self.assertNotIn("state_locked", interaction_tags(door))

    def test_schema_and_legacy_custom_tags(self):
        action = ActionDocument(
            id="sacred",
            name="Освящённый удар",
            tags=["holy", "custom_trait"],
            damage="1d4",
        )
        self.assertTrue(
            {"holy", "custom_trait", "bludgeoning"}
            <= interaction_tags(compile_definition("actions", "base:sacred", action))
        )
        race = RaceDocument(id="custom", name="Народ", tags=["stone"])
        self.assertIn("stone", compile_definition("races", "base:custom", race).tags)
        for cls in (ActionDocument, RaceDocument, EquipmentDocument, SpellDocument):
            schema = cls.model_json_schema()["properties"]["tags"]
            self.assertIn("stone", schema["tag_labels"])
            self.assertNotIn("state_burning", schema["tag_labels"])
            self.assertIn("tag_groups", schema)
        old = ContentCatalog.load(DEFAULT_ROOT)
        self.assertIn("humanoid", old.races["human"].tags)
        self.assertIn("metal", old.equipment["sword"].tags)


if __name__ == "__main__":
    unittest.main()
