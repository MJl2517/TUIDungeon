from copy import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, item_record, restore_item
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import MapDocument, RecipeDocument, EquipmentDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import CheckResult
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.tui import Controller, View, render
from tuidungeon.world.maps import Position


class ArcaneCraftingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw.update(ambient_light="bright", lights=[])
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.e = SessionFactory(self.store).session(
            "dev:crafting_lab",
            character_class="base:wizard",
            cantrips=["base:light", "base:mending", "base:fire_bolt"],
            background="dev:master_artisan",
            seed=42,
        )
        self.e.state.hero.inventory.clear()
        self.e.state.position = Position(17, 12)

    def add(self, ref, n=1):
        items = [Equipment.create(self.e.catalog.equipment[ref]) for _ in range(n)]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def start(self, ref, **kw):
        result = self.e.start_craft("base:" + ref, **kw)
        self.assertTrue(result.performed, result.message)
        return self.e.active_craft

    def finish(self):
        for _ in range(20):
            if not self.e.active_craft:
                return
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)
        self.fail("unfinished work")

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_ink_inscription_reader_and_save(self):
        self.add("calligrapher_tools")
        pigment = self.add("pigment")
        resin = self.add("binding_resin")
        pot = self.add("clay_pot")
        pot.liquid_kind = "clean_water"
        pot.liquid_portions = 1
        work = self.start("mix_ink", target=pot.instance_id)
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        pot = next(i for i in self.e.state.hero.inventory if i.id == "clay_pot")
        self.assertEqual(pot.liquid_portions, 0)
        self.assertEqual(pot.weight, pot.definition.weight)
        self.assertNotIn(
            pigment.instance_id, [i.instance_id for i in self.e.state.hero.inventory]
        )
        self.assertNotIn(
            resin.instance_id, [i.instance_id for i in self.e.state.hero.inventory]
        )
        self.add("writing_paper")
        self.start("write_inscription")
        self.finish()
        page = next(i for i in self.e.state.hero.inventory if i.id == "inscribed_page")
        c = Controller(42, store=self.store, catalog=self.e.catalog)
        c.engine = self.e
        c.selected_item = page
        c.view = View.ITEM
        c.handle("1")
        self.assertEqual(c.view, View.READING)
        self.assertEqual(c.reading.text.title, "Памятка путнику")
        self.e.use_item(page)
        self.assertEqual(len(self.e.read_notes), 1)
        self.reload()
        self.assertEqual(len(self.e.read_notes), 1)
        self.assertEqual(
            next(iter(self.e.read_notes.values())).text.pages[1],
            page.definition.reading.pages[1],
        )

    def test_scribing_requires_real_knowledge_and_light_and_refunds(self):
        h = self.e.state.hero
        self.add("calligrapher_tools")
        self.add("writing_paper")
        self.add("ink")
        self.add("alchemy_reagent")
        original = list(h.inventory)
        spells = h.class_spells
        h.class_spells = ()
        self.add("scroll_light")
        a = self.e.assess_craft("base:scribe_light")
        self.assertTrue(any("знать заклинание" in r for r in a.reasons))
        self.assertFalse(self.e.start_craft("base:scribe_light").performed)
        self.assertEqual(self.e.state.turns, 0)
        h.class_spells = spells
        h.tool_proficiencies.remove("calligrapher_tools")
        self.assertFalse(self.e.start_craft("base:scribe_light").performed)
        h.tool_proficiencies.add("calligrapher_tools")
        work = self.start("scribe_light")
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertTrue(self.e.cancel_craft(work).performed)
        self.assertTrue(all(i in h.inventory for i in original))
        # A professional recipe cannot be resumed in dim light.
        work = self.start("scribe_light")
        self.e.pause_craft()
        raw = self.e.state.level.definition.model_dump(mode="json")
        raw.update(ambient_light="dim", lights=[])
        self.e.state.level.definition = MapDocument.model_validate(raw)
        self.assertFalse(self.e.resume_craft(work).performed)

    def test_scroll_validation_resource_and_one_use(self):
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        h = self.e.state.hero
        h.cantrip_uses = 0
        h.spell_slots = {}
        scroll = self.add("scroll_light")
        target = self.add("stone")
        source = "scroll:" + scroll.instance_id
        self.assertFalse(self.e.cast_spell("light", source, None).performed)
        self.assertFalse(self.e.cast_spell("mending", source, target).performed)
        self.assertFalse(self.e.cast_spell("light", source, scroll).performed)
        self.assertEqual(scroll.charges, 1)
        self.assertEqual(self.e.state.turns, 0)
        self.assertTrue(self.e.cast_spell("light", source, target).performed)
        self.assertTrue(target.glow)
        self.assertNotIn(scroll, h.inventory)
        self.assertEqual(h.cantrip_uses, 0)
        self.assertEqual(h.spell_slots, {})
        self.assertFalse(self.e.cast_spell("light", source, target).performed)
        self.assertEqual(self.e.state.turns, 1)
        self.reload()
        target = next(i for i in self.e.state.hero.inventory if i.id == "stone")
        self.assertTrue(target.glow)

    def test_scroll_craft_pause_save_finish_and_native_target_menu(self):
        self.add("calligrapher_tools")
        self.add("writing_paper")
        self.add("ink")
        self.add("alchemy_reagent")
        work = self.start("scribe_mending")
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        scroll = next(
            i for i in self.e.state.hero.inventory if i.id == "scroll_mending"
        )
        target = self.add("dagger")
        target.durability -= 5
        c = Controller(42, store=self.store, catalog=self.e.catalog)
        c.engine = self.e
        c.selected_item = scroll
        c.view = View.ITEM
        c.handle("1")
        self.assertEqual(c.selected_spell[1], "scroll:" + scroll.instance_id)
        c.cast_selected(target)
        self.assertGreater(target.durability, target.definition.durability - 5)
        self.assertNotIn(scroll, self.e.state.hero.inventory)
        for w, h in [(80, 24), (100, 28), (140, 40)]:
            render(c, w, h)

    def test_improvised_result_preview_risk_save_refund_and_finish(self):
        self.add("wood")
        self.add("plant_fiber")
        a = self.e.assess_craft("base:craft_club", 1)
        payload = a.payload(self.e.catalog)
        self.assertEqual(payload["result"][0]["name"], "Связанная дубинка")
        self.assertEqual(payload["check"]["difficulty"], 8)
        work = self.start("craft_club", variant=1)
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        self.assertTrue(self.e.resume_craft(work).performed)
        with patch.object(self.e.dice, "check", return_value=CheckResult(1, 0, 8)):
            self.finish()
        self.assertEqual(self.e.workpiece(work).work.progress, 0)
        self.assertFalse(
            any(i.id == "improvised_club" for i in self.e.state.hero.inventory)
        )
        self.assertTrue(self.e.resume_craft(work).performed)
        with patch.object(self.e.dice, "check", return_value=CheckResult(20, 0, 8)):
            self.finish()
        result = next(
            i for i in self.e.state.hero.inventory if i.id == "improvised_club"
        )
        self.assertEqual(result.durability, 4)
        self.assertEqual(result.definition.weapon_damage.sides, 4)
        self.assertFalse(self.e.advance_craft().performed)

    def test_experiment_discovery_once_only_after_finish(self):
        h = self.e.state.hero
        h.known_recipes.difference_update(
            {"base:craft_rune_dagger", "base:craft_rune_leather"}
        )
        self.add("alchemist_tools")
        self.add("alchemy_reagent")
        self.add("uncut_gem")
        self.assertFalse(
            any(r["ref"] == "base:craft_rune_dagger" for r in self.e.craft_list())
        )
        work = self.start("experiment_binding")
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        self.assertNotIn("base:craft_rune_dagger", self.e.state.hero.known_recipes)
        self.assertTrue(self.e.resume_craft(work).performed)
        self.finish()
        self.assertIn("base:craft_rune_dagger", self.e.state.hero.known_recipes)
        self.assertEqual(self.e.learn_recipes(["base:craft_rune_dagger"]), [])
        self.assertEqual(
            sum(i.id == "arcane_dust" for i in self.e.state.hero.inventory), 1
        )
        self.reload()
        self.assertIn("base:craft_rune_leather", self.e.state.hero.known_recipes)

    def test_permanent_gear_focus_and_rare_materials(self):
        h = self.e.state.hero
        base = h.spell_attack_bonus
        f = self.add("arcane_focus", 2)
        for i in h.inventory:
            i.equipped = True
        self.assertEqual(h.spell_attack_bonus, base + 1)
        f.durability = 0
        self.assertEqual(h.spell_attack_bonus, base + 1)
        h.inventory[-1].durability = 0
        self.assertEqual(h.spell_attack_bonus, base)
        h.inventory.clear()
        armor = self.add("rune_leather")
        h.equip(armor)
        self.assertEqual(h.armor_class, 13)
        dragon = self.add("dragon_leather")
        h.equip(dragon)
        self.assertEqual(h.damage_profile.resolve(10, "fire").resolved_amount, 5)
        rune = self.add("rune_dagger")
        self.assertEqual(rune.definition.weapon_damage.bonus, 1)
        self.reload()
        self.assertEqual(self.e.state.hero.armor_class, 13)
        self.assertEqual(
            self.e.state.hero.damage_profile.resolve(10, "fire").resolved_amount, 5
        )
        self.e.state.hero.inventory.clear()
        self.add("carpenter_tools")
        self.add("ironwood")
        self.start("craft_ironwood_club")
        self.finish()
        club = next(i for i in self.e.state.hero.inventory if i.id == "ironwood_club")
        self.assertEqual(club.durability, 30)
        self.assertTrue(all(i.id != "ironwood" for i in self.e.state.hero.inventory))
        self.assertEqual(
            len(
                item_stacks(
                    [
                        Equipment.create(self.e.catalog.equipment["ironwood"]),
                        Equipment.create(self.e.catalog.equipment["wood"]),
                    ]
                )
            ),
            2,
        )

    def test_schemas_and_work_boundaries(self):
        with self.assertRaises(ValidationError):
            EquipmentDocument(id="bad_scroll", cast_spell="base:light")
        with self.assertRaises(ValidationError):
            EquipmentDocument(id="bad_focus", spell_bonus=1)
        with self.assertRaises(ValidationError):
            RecipeDocument(
                id="bad_variant",
                variants=[dict(ingredients=[dict(items=["base:wood"])], result=[])],
            )
        raw = self.store.get("equipment", "base:scroll_light").model_dump(mode="json")
        raw["cast_spell"] = "base:daylight"
        docs = dict(self.store.documents)
        docs["equipment", "base:scroll_light"] = EquipmentDocument.model_validate(raw)
        with self.assertRaises(ContentError):
            self.store.validate_references(docs, self.store.manifests)
        self.add("wood")
        self.add("plant_fiber")
        work = self.start("craft_club", variant=1)
        record = item_record(self.e.workpiece(work))
        raw = record.model_dump(mode="json")
        raw["work"]["recipe"]["variants"][1]["result"][0]["item"] = "base:missing_item"
        with self.assertRaises(ValueError):
            restore_item(type(record).model_validate(raw), self.e.catalog)


if __name__ == "__main__":
    unittest.main()
