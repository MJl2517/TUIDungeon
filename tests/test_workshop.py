"""Acceptance checks for liquid ownership, campfire turns and paid repairs."""

from copy import copy
from pathlib import Path
import json
import tempfile
import unittest
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument, RecipeDocument
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.storage import item_stacks
from tuidungeon.world.maps import Position
from tuidungeon.presentation.tui import Controller, View, render, popup_layout


class WorkshopTests(unittest.TestCase):
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
        self.e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.e.state.hero.inventory.clear()
        self.e.state.hero.known_recipes.update(self.e.catalog.recipes)

    def add(self, ref, n=1):
        items = [Equipment.create(self.e.catalog.equipment[ref]) for _ in range(n)]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def reload(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)
        return self.e

    def fill(self, item, portions=None):
        self.e.state.position = Position(3, 5)
        return self.e.water_action(
            item.instance_id, "fill", target="lab_water", portions=portions
        )

    def camp(self):
        self.e.state.position = Position(3, 3)
        self.add("wood", 2)
        self.add("tinder")
        self.add("flint_and_steel")
        result = self.e.start_craft("base:build_campfire", destination=(4, 3))
        self.assertTrue(result.performed, result.message)
        self.e.advance_craft()
        self.e.advance_craft()
        return next(
            o for o in self.e.world_objects() if getattr(o.definition, "campfire", None)
        )

    def finish(self):
        while self.e.active_craft:
            result = self.e.advance_craft()
            self.assertTrue(result.performed, result.message)

    def test_liquid_portions_mass_stacks_and_save(self):
        a, b = self.add("cooking_pot"), self.add("water_flask", 2)
        base = self.e.state.hero.carried_weight
        self.assertTrue(self.fill(a).performed)
        self.assertAlmostEqual(self.e.state.hero.carried_weight, base + 0.3)
        self.assertFalse(self.fill(a).performed)
        self.assertTrue(
            self.e.water_action(
                a.instance_id, "pour", target=b.instance_id, portions=1
            ).performed
        )
        self.assertEqual((a.liquid_portions, b.liquid_portions), (2, 1))
        self.assertEqual(
            len(
                item_stacks(
                    [
                        b,
                        next(
                            i
                            for i in self.e.state.hero.inventory
                            if i.id == "water_flask" and i is not b
                        ),
                    ]
                )
            ),
            2,
        )
        ids = a.instance_id, b.instance_id
        self.reload()
        a, b = [
            next(i for i in self.e.state.hero.inventory if i.instance_id == key)
            for key in ids
        ]
        self.assertEqual((a.liquid_portions, b.liquid_portions), (2, 1))
        self.assertTrue(self.e.water_action(a.instance_id, "empty").performed)
        self.assertIsNone(a.liquid_kind)
        self.assertEqual(a.weight, 0.5)
        b.liquid_kind = "clean_water"
        self.assertTrue(self.fill(a).performed)
        before = self.e.state.turns
        self.assertFalse(
            self.e.water_action(a.instance_id, "pour", target=b.instance_id).performed
        )
        self.assertEqual(self.e.state.turns, before)
        self.assertFalse(
            self.e.water_action(a.instance_id, "empty", portions=-1).performed
        )

    def test_second_identical_vessel_is_reserved_without_duplication(self):
        self.camp()
        first = self.add("cooking_pot")
        second = self.add("cooking_pot")
        for item in (first, second):
            item.liquid_kind, item.liquid_portions = "dirty_water", 3
        self.assertNotEqual(first, second)
        self.assertEqual(len(item_stacks([first, second])), 1)
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=second.instance_id).performed
        )
        work = self.e.workpiece(self.e.active_craft)
        self.assertIs(work.work.target, second)
        self.assertTrue(any(i is first for i in self.e.state.hero.inventory))
        self.assertFalse(any(i is second for i in self.e.state.hero.inventory))
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.e.resume_craft(work.instance_id)
        self.finish()
        pots = [i for i in self.e.state.hero.inventory if i.id == "cooking_pot"]
        self.assertEqual(
            {i.instance_id for i in pots}, {first.instance_id, second.instance_id}
        )
        self.assertEqual(len(pots), 2)
        self.assertEqual(
            next(i for i in pots if i.instance_id == first.instance_id).liquid_kind,
            "dirty_water",
        )
        self.assertEqual(
            next(i for i in pots if i.instance_id == second.instance_id).liquid_kind,
            "clean_water",
        )

    def test_drinking_potion_preserves_container_and_real_effect(self):
        p = self.add("healing_potion")
        hero = self.e.state.hero
        hero.hp = 1
        result = self.e.use_item(p)
        self.assertTrue(result.performed)
        self.assertGreater(hero.hp, 1)
        self.assertEqual(result.effects[0].kind, "heal")
        self.assertEqual((p.liquid_portions, p.charges), (0, 0))
        self.assertIn(p, hero.inventory)
        self.assertAlmostEqual(
            p.definition.weight + p.definition.vessel.initial_portions * 0.1, 0.2
        )
        self.assertFalse(self.e.use_item(p).performed)
        self.assertTrue(self.fill(p).performed)
        self.assertTrue(self.e.use_item(p).performed)
        self.assertIn("poisoned", hero.conditions)
        self.assertEqual(p.liquid_portions, 0)
        antidote = self.add("water_flask")
        antidote.liquid_kind, antidote.liquid_portions = "antidote", 1
        self.assertTrue(self.e.use_item(antidote).performed)
        self.assertNotIn("poisoned", hero.conditions)
        p.liquid_kind, p.liquid_portions = "healing_potion", 1
        # Direct domain callers use the same liquid consumption contract.
        hero.use_item(p, self.e.dice)
        self.assertEqual(p.liquid_portions, 0)

    def test_campfire_ownership_light_fuel_and_station_pause(self):
        fire = self.camp()
        self.assertEqual(fire.state.fuel_minutes, 60)
        self.assertIn("heat", self.e.craft_stations())
        p = self.add("cooking_pot")
        self.fill(p)
        self.e.state.position = Position(3, 3)
        fire.state.fuel_minutes = 1
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=p.instance_id).performed
        )
        self.assertTrue(self.e.advance_craft().performed)
        self.assertIsNone(self.e.active_craft)
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.assertEqual(work.work.progress, 1)
        self.assertEqual(work.work.target.liquid_kind, "dirty_water")
        self.assertNotIn("heat", self.e.craft_stations())
        self.assertFalse(self.e.resume_craft(work.instance_id).performed)
        self.e.cancel_craft(work.instance_id)
        self.add("wood")
        self.assertTrue(self.e.campfire_action(fire.placement.id, "refuel").performed)
        self.assertFalse(fire.state.lit)
        self.assertTrue(self.e.campfire_action(fire.placement.id, "ignite").performed)
        self.assertEqual(fire.state.fuel_minutes, 59)
        self.e.state.level.definition = self.e.state.level.definition.model_copy(
            update={"ambient_light": "dark", "lights": []}
        )
        self.assertGreater(self.e.lighting.level_at(Position(3, 3)), 0)
        fire.state.lit = False
        self.assertEqual(self.e.lighting.level_at(Position(3, 3)), 0)

    def test_recipe_water_types_heat_safe_and_cancel(self):
        self.camp()
        pot = self.add("cooking_pot")
        pot.liquid_kind, pot.liquid_portions = "salt_water", 3
        before = self.e.state.turns
        self.assertFalse(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        pot.liquid_kind = "poisoned_water"
        self.assertFalse(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        other = self.add("waterskin")
        other.liquid_kind, other.liquid_portions = "dirty_water", 2
        self.assertFalse(
            self.e.start_craft("base:boil_water", target=other.instance_id).performed
        )
        self.assertEqual(self.e.state.turns, before)
        pot.liquid_kind = "dirty_water"
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        work = self.e.workpiece(self.e.active_craft)
        self.assertAlmostEqual(work.weight, 0.8)
        self.assertNotIn(pot, self.e.state.hero.inventory)
        self.assertFalse(self.e.water_action(pot.instance_id, "empty").performed)
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.assertEqual(work.work.progress, 1)
        targetid = work.work.target.instance_id
        self.assertTrue(self.e.resume_craft(work.instance_id).performed)
        self.finish()
        pot = next(i for i in self.e.state.hero.inventory if i.instance_id == targetid)
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("clean_water", 3))
        self.assertFalse(self.e.advance_craft().performed)

    def test_water_washes_extinguishes_and_changes_only_live_floor(self):
        fire = self.camp()
        pot = self.add("cooking_pot")
        pot.liquid_kind, pot.liquid_portions = "clean_water", 3
        cloth = self.add("cloth")
        cloth.contaminated = True
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "wash", target=cloth.instance_id
            ).performed
        )
        self.assertFalse(cloth.contaminated)
        self.assertEqual(pot.liquid_portions, 2)
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "splash", position=Position(4, 3)
            ).performed
        )
        self.assertFalse(fire.state.lit)
        self.e.replace_surface(Position(3, 4), "base:soil")
        pot.liquid_kind, pot.liquid_portions = "clean_water", 3
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "splash", position=Position(3, 4)
            ).performed
        )
        self.assertEqual(self.e.state.level.definition.tiles[4][3], "base:mud")
        self.assertNotEqual(
            self.e.state.level.authored_definition.tiles[4][3], "base:mud"
        )
        self.reload()
        self.assertEqual(self.e.state.level.definition.tiles[4][3], "base:mud")
        self.assertFalse(
            next(
                o
                for o in self.e.world_objects()
                if getattr(o.definition, "campfire", None)
            ).state.lit
        )

    def test_repair_pause_equipping_cancel_and_object_binding(self):
        club = self.add("club")
        club.durability = 1
        self.add("carpenter_tools")
        wood = self.add("wood")
        self.assertTrue(
            self.e.start_craft("base:repair_wood", target=club.instance_id).performed
        )
        work = self.e.workpiece(self.e.active_craft)
        self.assertNotIn(club, self.e.state.hero.inventory)
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertEqual(club.durability, 1)
        self.assertIn(club, self.e.state.hero.inventory)
        club.equipped = True
        self.assertFalse(self.e.resume_craft(work.instance_id).performed)
        club.equipped = False
        self.assertTrue(self.e.resume_craft(work.instance_id).performed)
        self.e.pause_craft()
        self.reload()
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.assertTrue(self.e.cancel_craft(work.instance_id).performed)
        self.assertEqual(
            next(
                i
                for i in self.e.state.hero.inventory
                if i.instance_id == club.instance_id
            ).durability,
            1,
        )
        self.assertTrue(
            any(i.instance_id == wood.instance_id for i in self.e.state.hero.inventory)
        )
        club = next(
            i for i in self.e.state.hero.inventory if i.instance_id == club.instance_id
        )
        self.e.start_craft("base:repair_wood", target=club.instance_id)
        self.finish()
        self.assertEqual(club.durability, min(11, club.definition.durability))
        self.e.state.position = Position(3, 6)
        obj = self.e.world_object("lab_table")
        self.e.damage_world_objects(Position(4, 6), 5, "bludgeoning")
        damaged = obj.state.hp
        self.add("wood")
        self.assertTrue(
            self.e.start_craft("base:repair_wood_object", target="lab_table").performed
        )
        work = self.e.workpiece(self.e.active_craft)
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertEqual(obj.state.hp, damaged)
        self.e.state.position = Position(3, 3)
        self.assertFalse(self.e.resume_craft(work.instance_id).performed)
        self.e.state.position = Position(3, 6)
        self.e.resume_craft(work.instance_id)
        self.finish()
        self.assertGreater(obj.state.hp, damaged)

    def test_route_furniture_torch_fire_water_remedy_and_save(self):
        self.e.state.position = Position(3, 6)
        self.add("carpenter_tools")
        self.assertTrue(self.e.start_dismantle("lab_table").performed)
        self.finish()
        self.e.state.position = Position(4, 6)
        for _ in range(3):
            self.e.pickup_item()
        self.add("cloth")
        self.add("tinder")
        self.add("flint_and_steel")
        self.e.start_craft("base:craft_torch")
        self.finish()
        torch = next(i for i in self.e.state.hero.inventory if i.id == "torch")
        self.assertEqual(torch.definition.light.burn_minutes, 60)
        self.assertTrue(self.e.manage_equipment(torch, True).performed)
        self.e.state.position = Position(3, 3)
        self.assertTrue(
            self.e.start_craft("base:build_campfire", destination=(4, 3)).performed
        )
        self.finish()
        pot = self.add("cooking_pot")
        self.fill(pot)
        self.e.state.position = Position(3, 3)
        self.e.start_craft("base:boil_water", target=pot.instance_id)
        self.finish()
        self.add("medicinal_herb")
        self.add("cloth")
        self.e.start_craft("base:make_poultice", target=pot.instance_id)
        self.finish()
        self.assertEqual(pot.liquid_portions, 0)
        poultice = next(
            i for i in self.e.state.hero.inventory if i.id == "healing_poultice"
        )
        self.e.state.hero.hp = 1
        self.e.use_item(poultice)
        self.assertEqual(self.e.state.hero.hp, 5)
        self.add("medicinal_herb")
        self.e.start_craft("base:dry_herbs")
        self.e.advance_craft()
        self.e.pause_craft()
        self.reload()
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.assertEqual(work.work.progress, 1)
        self.e.resume_craft(work.instance_id)
        self.finish()
        self.assertEqual(
            sum(i.id == "dried_herbs" for i in self.e.state.hero.inventory), 1
        )

    def test_portion_capacities_transfer_and_single_portion_drinking(self):
        pot, skin, flask = [
            self.add(ref) for ref in ("cooking_pot", "waterskin", "water_flask")
        ]
        self.assertEqual(
            [i.definition.vessel.capacity_portions for i in (flask, skin, pot)],
            [1, 2, 3],
        )
        self.assertTrue(self.fill(pot).performed)
        pot.liquid_kind = "clean_water"
        weight = self.e.state.hero.carried_weight
        self.assertTrue(
            self.e.water_action(
                pot.instance_id, "pour", target=skin.instance_id
            ).performed
        )
        self.assertEqual((pot.liquid_portions, skin.liquid_portions), (1, 2))
        self.assertAlmostEqual(self.e.state.hero.carried_weight, weight)
        self.assertTrue(
            self.e.water_action(
                skin.instance_id, "pour", target=flask.instance_id
            ).performed
        )
        self.assertEqual((skin.liquid_portions, flask.liquid_portions), (1, 1))
        self.assertTrue(self.e.water_action(flask.instance_id, "drink").performed)
        self.assertEqual((flask.liquid_kind, flask.liquid_portions), (None, 0))
        before = self.e.state.turns
        for bad in (0, -1, 0.5, True):
            self.assertFalse(
                self.e.water_action(
                    pot.instance_id, "pour", target=flask.instance_id, portions=bad
                ).performed
            )
        self.assertEqual(self.e.state.turns, before)

    def test_map_targeting_clamps_cursor_cancels_freely_and_spends_one_portion(self):
        self.e.state.position = Position(3, 3)
        pot = self.add("cooking_pot")
        pot.liquid_kind, pot.liquid_portions = "clean_water", 3
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.engine = self.e
        before = self.e.state.turns
        c.open_item(pot)
        c.handle("5")
        choices = self.e.vessel_choices(pot)
        splash = next(
            i + 1 for i, choice in enumerate(choices) if choice["action"] == "splash"
        )
        self.assertNotIn("x", choices[splash - 1])
        c.handle(str(splash))
        self.assertEqual(c.view, View.LOOK)
        self.assertIsNone(popup_layout(c, 100, 28))
        for kind in ("splash", "move", "place"):
            c.target_furniture(kind, pot.instance_id)
            c.handle("right")
            c.handle("right")
            self.assertEqual(c.look_position, Position(4, 3))
            c.handle("down")
            c.handle("down")
            self.assertEqual(c.look_position, Position(4, 4))
            self.assertFalse(c.can_target_cell(Position(5, 3)))
            c.handle("escape")
            self.assertEqual(c.view, View.EXPLORE)
            self.assertIsNone(c.world_target)
        self.assertEqual((self.e.state.turns, pot.liquid_portions), (before, 3))
        self.assertFalse(
            self.e.water_action(
                pot.instance_id, "splash", position=Position(5, 3)
            ).performed
        )
        c.target_furniture("splash", pot.instance_id)
        c.handle("right")
        c.handle("down")
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual((self.e.state.turns, pot.liquid_portions), (before + 1, 2))

    def test_legacy_liquid_save_preserves_craft_progress_and_rejects_overfill(self):
        from tuidungeon.application.saves import ItemRecord, item_record, restore_item
        from tuidungeon.content.schemas import EquipmentDocument, Placement
        from tuidungeon.domain.liquids import LEGACY_VESSELS

        for ref, (old_capacity, capacity) in LEGACY_VESSELS.items():
            raw = self.store.get("equipment", "base:" + ref).model_dump(mode="json")
            vessel = raw["vessel"]
            vessel["capacity_ml"] = old_capacity
            vessel.pop("capacity_portions")
            vessel["initial_ml"] = old_capacity if vessel.pop("initial_portions") else 0
            document = EquipmentDocument.model_validate(raw)
            self.assertEqual(document.vessel.capacity_portions, capacity)
            item = self.add(ref)
            data = item_record(item).model_dump()
            data.pop("liquid_portions")
            data.update(liquid_kind="clean_water", liquid_ml=old_capacity)
            restored = restore_item(ItemRecord.model_validate(data), self.e.catalog)
            self.assertEqual(
                (restored.instance_id, restored.liquid_portions),
                (item.instance_id, capacity),
            )
            data["liquid_ml"] += 1
            with self.assertRaises(ValueError):
                ItemRecord.model_validate(data)
        placement = Placement.model_validate(
            dict(
                id="water",
                ref="base:cooking_pot",
                overrides=dict(vessel=dict(initial_kind="clean_water", initial_ml=100)),
            )
        )
        self.assertEqual(placement.overrides["vessel"]["initial_portions"], 1)
        self.camp()
        pot = self.add("cooking_pot")
        pot.liquid_kind, pot.liquid_portions = "dirty_water", 3
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        self.e.advance_craft()
        self.e.pause_craft()
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "old.json")
            repo.save(self.e)
            data = json.loads(repo.path.read_text(encoding="utf-8"))

            def old_units(value):
                if isinstance(value, dict):
                    if "liquid_portions" in value:
                        amount = value.pop("liquid_portions")
                        old, new = LEGACY_VESSELS.get(
                            value.get("definition", "").removeprefix("base:"), (250, 1)
                        )
                        value["liquid_ml"] = amount * old // new
                    if value.get("kind") == "liquid" and "portions" in value:
                        value["volume_ml"] = 500 if value.pop("portions") == 3 else 100
                    for child in value.values():
                        old_units(child)
                elif isinstance(value, list):
                    for child in value:
                        old_units(child)

            old_units(data)
            repo.path.write_text(json.dumps(data), encoding="utf-8")
            self.e = repo.load(store=self.store)
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.assertEqual((work.work.progress, work.work.target.liquid_portions), (1, 3))
        self.assertTrue(self.e.resume_craft(work.instance_id).performed)
        self.finish()
        pot = next(
            i for i in self.e.state.hero.inventory if i.instance_id == pot.instance_id
        )
        self.assertEqual((pot.liquid_kind, pot.liquid_portions), ("clean_water", 3))
        self.assertFalse(self.e.advance_craft().performed)

    def test_native_vessel_actions_and_target_cycle(self):
        self.camp()
        first = self.add("cooking_pot")
        second = self.add("cooking_pot")
        for item in (first, second):
            item.liquid_kind, item.liquid_portions = "dirty_water", 3
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.engine = self.e
        c.view = View.EXPLORE
        c.open_item(first)
        c.handle("5")
        self.assertEqual(c.view, View.LIQUID)
        self.assertIn("Действия с жидкостью", "\n".join(render(c, 80, 24)))
        c.handle("escape")
        self.assertEqual(c.view, View.ITEM)
        c.craft.open()
        c.craft.recipe_ref = "base:boil_water"
        c.view = View.CRAFT
        c.craft.assessment(self.e)
        c.handle("t")
        self.assertIs(c.craft.assessment(self.e).target, second)
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIs(self.e.workpiece(self.e.active_craft).work.target, second)
        c.handle(" ")
        self.assertEqual(self.e.workpiece(self.e.active_craft).work.progress, 1)
        c.handle("escape")
        self.assertIsNone(self.e.active_craft)

    def test_poured_custom_potion_keeps_effect_through_save(self):
        from dataclasses import replace
        from tuidungeon.domain.definitions import EffectSpec

        potion = Equipment.create(
            replace(
                self.e.catalog.equipment["healing_potion"],
                properties=(EffectSpec(kind="heal", amount=7),),
            )
        )
        self.e.state.hero.inventory.append(potion)
        flask = self.add("water_flask")
        self.assertTrue(
            self.e.water_action(
                potion.instance_id, "pour", target=flask.instance_id
            ).performed
        )
        self.assertEqual(potion.liquid_portions, 0)
        self.reload()
        flask = next(
            i for i in self.e.state.hero.inventory if i.instance_id == flask.instance_id
        )
        self.e.state.hero.hp = 1
        self.assertEqual(self.e.use_item(flask).effects[0].amount, 7)
        self.assertEqual(self.e.state.hero.hp, 8)
        self.assertEqual(flask.liquid_portions, 0)

    def test_professional_repair_checks_and_destroyed_station(self):
        sword = self.add("sword")
        sword.durability = 1
        self.add("metal")
        assessment = self.e.assess_craft("base:repair_metal", target=sword.instance_id)
        self.assertTrue(any("инструмента" in r for r in assessment.reasons))
        self.assertTrue(any("владения" in r for r in assessment.reasons))
        self.assertTrue(any("станция" in r for r in assessment.reasons))
        before = self.e.state.turns
        self.assertFalse(
            self.e.start_craft("base:repair_metal", target=sword.instance_id).performed
        )
        self.assertEqual(self.e.state.turns, before)
        self.add("smith_tools")
        self.e.state.hero.learn_tool_proficiency("smith_tools")
        self.e.state.position = Position(10, 4)
        self.assertTrue(
            self.e.start_craft("base:repair_metal", target=sword.instance_id).performed
        )
        self.e.advance_craft()
        self.e.pause_craft()
        work = next(i for i in self.e.state.hero.inventory if i.work)
        self.e.damage_world_objects(Position(10, 3), 100, "bludgeoning")
        self.assertFalse(self.e.resume_craft(work.instance_id).performed)
        self.assertEqual(sword.durability, 1)
        self.assertTrue(self.e.cancel_craft(work.instance_id).performed)

    def test_ignite_in_dark_and_break_water_vessel_against_fire(self):
        fire = self.camp()
        fire.state.lit = False
        self.e.state.level.definition = self.e.state.level.definition.model_copy(
            update={"ambient_light": "dark", "lights": []}
        )
        flint = next(
            i for i in self.e.state.hero.inventory if i.id == "flint_and_steel"
        )
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        self.assertTrue(self.e.ignite_cell(flint, Position(4, 3)).performed)
        self.assertTrue(fire.state.lit)
        flask = self.add("water_flask")
        flask.liquid_kind, flask.liquid_portions = "clean_water", 1
        self.assertTrue(
            self.e.place_item(flask, Position(4, 3), throwing=True).performed
        )
        self.assertFalse(fire.state.lit)
        self.assertFalse(
            any(i.instance_id == flask.instance_id for i in self.e.state.hero.inventory)
        )
        self.assertFalse(
            any(i.instance_id == flask.instance_id for _, i in self.e.state.items)
        )

    def test_native_liquid_work_and_author_validation(self):
        pot = self.add("cooking_pot")
        self.e.state.position = Position(3, 5)
        self.assertTrue(
            self.e.water_action(pot.instance_id, "fill", target="lab_water").performed
        )
        self.assertEqual(pot.liquid_portions, 3)
        self.camp()
        self.assertTrue(
            self.e.start_craft("base:boil_water", target=pot.instance_id).performed
        )
        self.assertIsNotNone(self.e.active_craft)
        self.assertFalse(self.e.water_action(pot.instance_id, "empty").performed)
        self.e.advance_craft()
        self.e.pause_craft()
        controller = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        controller.engine = self.e
        controller.view = View.EXPLORE
        render(controller, 80, 24)
        with self.assertRaises(ValueError):
            RecipeDocument.model_validate(
                dict(id="bad", name="bad", variants=[dict(ingredients=[])], result=[])
            )
        with self.assertRaises(ValueError):
            RecipeDocument.model_validate(
                dict(id="bad", name="bad", operation=dict(kind="liquid", liquids=[]))
            )
        # A discovered trap is neither a water source nor a repairable object.
        trap = self.e.state.level.traps[0]
        trap.discovered = True
        self.e.state.position = Position(trap.placement.x - 1, trap.placement.y)
        self.assertFalse(self.e.fill_at_source(trap.placement.id).performed)
        self.e.craft_targets(
            self.e.catalog.recipes["base:repair_wood_object"].operation
        )
        from tuidungeon.application.saves import item_record, restore_item

        old = item_record(
            Equipment.create(self.e.catalog.equipment["healing_potion"])
        ).model_dump()
        for key in ("liquid_kind", "liquid_portions", "liquid_effects", "contaminated"):
            old.pop(key)
        from tuidungeon.application.saves import ItemRecord

        self.assertEqual(
            restore_item(
                ItemRecord.model_validate(old), self.e.catalog
            ).liquid_portions,
            1,
        )
        old["charges"] = 0
        self.assertEqual(
            restore_item(
                ItemRecord.model_validate(old), self.e.catalog
            ).liquid_portions,
            0,
        )

    def test_authored_storage_counts_initial_liquid_weight(self):
        from tuidungeon.content.packs import validate_storage
        from tuidungeon.content.schemas import WorldObjectDocument

        valid = WorldObjectDocument(
            id="small",
            name="Small",
            storage=dict(
                capacity=0.2,
                personal=True,
                contents=[dict(item="base:healing_potion", quantity=1)],
            ),
        )
        validate_storage(valid, self.store.documents)
        liquid = self.store.get("equipment", "base:cooking_pot").model_dump(mode="json")
        liquid["vessel"].update(initial_kind="clean_water", initial_portions=3)
        from tuidungeon.content.schemas import EquipmentDocument

        documents = dict(self.store.documents)
        documents["equipment", "base:cooking_pot"] = EquipmentDocument.model_validate(
            liquid
        )
        invalid = WorldObjectDocument(
            id="small",
            name="Small",
            storage=dict(
                capacity=0.75,
                personal=True,
                contents=[dict(item="base:cooking_pot", quantity=1)],
            ),
        )
        with self.assertRaises(ValueError):
            validate_storage(invalid, documents)

    def test_malformed_save_rejects_liquid_and_duplicate_target(self):
        p = self.add("cooking_pot")
        p.liquid_kind, p.liquid_portions = "dirty_water", 3
        self.camp()
        self.e.start_craft("base:boil_water", target=p.instance_id)
        with tempfile.TemporaryDirectory() as folder:
            repo = SaveRepository(Path(folder) / "save.json")
            repo.save(self.e)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            # Record helpers validate before a save can inject excess liquid.
            from tuidungeon.application.saves import item_record, restore_item

            record = item_record(p).model_copy(update={"liquid_portions": 4})
            with self.assertRaises(ValueError):
                restore_item(record, self.e.catalog)
            record = item_record(p).model_copy(update={"liquid_kind": "unknown"})
            with self.assertRaises(ValueError):
                restore_item(record, self.e.catalog)
            self.assertIsInstance(raw, dict)
            target = self.e.workpiece(self.e.active_craft).work.target
            self.e.state.hero.inventory.append(target)
            repo.save(self.e)
            with self.assertRaises(ValueError):
                repo.load(store=self.store)
