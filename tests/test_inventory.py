"""Inventory navigation, resource transfers and persistent ground instances."""

from scripts.testing import fixture_store

from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from tuidungeon.domain.storage import item_stacks

from tuidungeon.application.engine import Engine
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, item_record
from tuidungeon.content.schemas import EquipmentDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.inventory import InventoryBrowser, item_details
from tuidungeon.presentation.tui import (
    Controller,
    Layout,
    View,
    render,
    popup_layout,
)
from tuidungeon.world.maps import DungeonMap, Position
from tuidungeon.world.state import GameState


class InventoryFixture(unittest.TestCase):
    def setUp(self):
        self.store = fixture_store()
        self.factory = SessionFactory(self.store)
        self.engine = self.factory.session("base:crypt", seed=42)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.saves = SaveRepository(Path(self.directory.name) / "save.json")


class GroundItemTests(InventoryFixture):
    def test_drop_quantity_is_atomic_preserves_selected_instance_and_costs_one_turn(
        self,
    ):
        e, hero = self.engine, self.engine.state.hero
        items = [
            Equipment.create(self.factory.catalog.equipment["healing_potion"])
            for _ in range(4)
        ]
        different = Equipment.create(items[0].definition)
        different.charges = 0
        hero.inventory = items + [different]
        before = list(hero.inventory)
        for quantity in (0, -1, True, 1.5, 5):
            self.assertFalse(
                e.place_item(items[2], e.state.position, quantity=quantity).performed
            )
            self.assertEqual(hero.inventory, before)
            self.assertEqual(e.state.turns, 0)
        self.assertFalse(
            e.place_item(
                items[2], e.state.position, throwing=True, quantity=2
            ).performed
        )
        self.assertTrue(e.place_item(items[2], e.state.position, quantity=3).performed)
        self.assertEqual(e.state.turns, 1)
        self.assertIs(e.state.items[-3][1], items[2])
        self.assertEqual(
            {i.instance_id for _, i in e.state.items[-3:]},
            {i.instance_id for i in items[:3]},
        )
        self.assertEqual(hero.inventory, [items[3], different])
        self.assertTrue(all(i.charges == 1 for _, i in e.state.items[-3:]))

    def test_drop_equipped_item_changes_armor_and_pickup_keeps_instance_resources(self):
        engine, hero = self.engine, self.engine.state.hero
        armor = next(i for i in hero.inventory if i.definition.slot == "armor")
        armor.equipped = True
        armor.wear(3)
        previous_ac, weight = hero.armor_class, hero.carried_weight
        self.assertTrue(engine.place_item(armor, engine.state.position).performed)
        self.assertFalse(armor.equipped)
        self.assertNotIn(armor, hero.inventory)
        self.assertLess(hero.armor_class, previous_ac)
        self.assertEqual(hero.carried_weight, weight - armor.weight)
        self.assertIs(engine.state.items[-1][1], armor)
        self.assertTrue(engine.pickup_item().performed)
        self.assertIs(hero.inventory[-1], armor)
        self.assertFalse(armor.equipped)
        self.assertEqual(armor.durability, armor.definition.durability - 3)
        self.assertEqual(engine.state.turns, 2)

    def test_duplicate_templates_transfer_exact_selected_instance(self):
        hero = self.engine.state.hero
        first = Equipment.create(self.factory.catalog.equipment["healing_potion"])
        second = Equipment.create(first.definition)
        hero.inventory = [first, second]
        self.engine.place_item(second, self.engine.state.position)
        self.assertIs(hero.inventory[0], first)
        self.assertIs(self.engine.state.items[-1][1], second)

    def test_throw_range_edges_and_failures_do_not_spend_time_or_lose_item(self):
        engine, state = self.engine, self.engine.state
        item = state.hero.inventory[0]
        start, radius = state.position, engine.throw_range
        self.assertEqual(radius, 3)
        result = engine.place_item(
            item, Position(start.x + radius, start.y), throwing=True
        )
        self.assertTrue(result.performed)
        other = state.hero.inventory[0]
        for target in (
            Position(start.x + radius + 1, start.y),
            Position(0, 0),
            Position(-1, 3),
        ):
            result = engine.place_item(other, target, throwing=True)
            self.assertFalse(result.performed)
            self.assertEqual(result.minutes, 0)
        self.assertFalse(
            engine.place_item(other, Position(start.x + 1, start.y)).performed
        )
        self.assertTrue(any(i is other for i in state.hero.inventory))
        self.assertEqual(state.turns, 1)
        self.assertEqual(state.clock.elapsed_minutes, 481)

    def test_throw_cannot_cross_walls_corners_or_hit_monsters(self):
        hero = self.engine.state.hero
        hero.stats = Stats((20, 10, 10, 10, 10, 10))
        dungeon = DungeonMap(("#######", "#.....#", "#.###.#", "#.....#", "#######"))
        engine = Engine(GameState(hero, dungeon, Position(1, 1)), random.Random(0))
        item = hero.inventory[0]
        self.assertFalse(
            engine.place_item(item, Position(3, 3), throwing=True).performed
        )
        monster = engine.add_monster("goblin", Position(2, 1))
        self.assertFalse(
            engine.place_item(item, monster.position, throwing=True).performed
        )
        self.assertEqual(engine.state.turns, 0)
        self.assertTrue(
            engine.place_item(item, Position(1, 3), throwing=True).performed
        )

    def test_low_strength_dead_hero_and_foreign_items(self):
        hero = self.engine.state.hero
        hero.stats = Stats((3, 10, 10, 10, 10, 10))
        self.assertEqual(self.engine.throw_range, 0)
        item = hero.inventory[0]
        foreign = Equipment.create(item.definition)
        self.assertFalse(
            self.engine.place_item(foreign, self.engine.state.position).performed
        )
        self.assertFalse(
            self.engine.place_item(item, Position(4, 3), throwing=True).performed
        )
        hero.hp = 0
        self.assertFalse(
            self.engine.place_item(item, self.engine.state.position).performed
        )
        self.assertFalse(self.engine.pickup_item().performed)
        self.assertEqual(self.engine.state.turns, 0)

    def test_dropped_and_authored_items_survive_save_and_independent_sessions(self):
        state = self.engine.state
        potion = Equipment.create(self.factory.catalog.equipment["healing_potion"])
        potion.charges = 0
        potion.liquid_kind, potion.liquid_portions, potion.liquid_effects = None, 0, ()
        state.hero.inventory.append(potion)
        state.position = Position(4, 3)
        self.engine.place_item(potion, state.position)
        expected = [
            (p.id, p.ref, p.x, p.y, item.instance_id, item.charges)
            for p, item in state.items
        ]
        self.saves.save(self.engine)
        loaded = self.saves.load(self.factory.catalog, self.store)
        self.assertEqual(
            [
                (p.id, p.ref, p.x, p.y, item.instance_id, item.charges)
                for p, item in loaded.state.items
            ],
            expected,
        )
        loaded.state.position = Position(4, 3)
        self.assertIn(potion.name, " ".join(loaded.inspect_cell(Position(4, 3))))
        self.assertTrue(loaded.pickup_item().performed)
        self.assertEqual(
            loaded.state.hero.inventory[-1].instance_id, potion.instance_id
        )
        self.assertEqual(loaded.state.hero.inventory[-1].charges, 0)
        self.assertEqual(
            len(self.factory.session("base:crypt").state.items), len(state.items) - 1
        )

    def test_legacy_map_supports_ground_items_and_save(self):
        engine = Engine.new_game(self.engine.state.hero, random.Random(5))
        item = engine.state.hero.inventory[0]
        engine.place_item(item, engine.state.position)
        self.saves.save(engine)
        loaded = self.saves.load(self.factory.catalog)
        self.assertEqual(loaded.state.items[0][1].instance_id, item.instance_id)
        self.assertTrue(loaded.pickup_item().performed)

    def test_old_save_ground_format_remains_readable(self):
        self.saves.save(self.engine)
        raw = json.loads(self.saves.path.read_text(encoding="utf-8"))
        raw["levels"][0].pop("ground_items")
        raw["levels"][0]["items"] = {
            p.id: item_record(i).model_dump(mode="json")
            for p, i in self.engine.state.items
        }
        self.saves.path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = self.saves.load(self.factory.catalog, self.store)
        self.assertEqual(len(loaded.state.items), len(self.engine.state.items))

    def test_invalid_ground_position_and_duplicate_instance_save_are_rejected(self):
        item = self.engine.state.hero.inventory[0]
        self.engine.place_item(item, self.engine.state.position)
        self.saves.save(self.engine)
        original = json.loads(self.saves.path.read_text(encoding="utf-8"))
        raw = json.loads(json.dumps(original))
        raw["levels"][0]["ground_items"][-1]["position"] = [0, 0]
        self.saves.path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.saves.load(self.factory.catalog, self.store)
        raw = json.loads(json.dumps(original))
        raw["hero"]["inventory"].append(raw["levels"][0]["ground_items"][-1]["item"])
        self.saves.path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.saves.load(self.factory.catalog, self.store)


class InventoryNavigationTests(InventoryFixture):
    def test_q_drop_stack_in_sidebar_and_inventory_quantity_cancel_and_save(self):
        c = self.controller
        e, hero = c.engine, c.engine.state.hero
        wood = [
            Equipment.create(self.factory.catalog.equipment["wood"]) for _ in range(12)
        ]
        different = Equipment.create(wood[0].definition)
        different.contaminated = True
        hero.inventory[:] = wood + [different]
        c.inventory.query = "wood"
        c.inventory.selected = 1
        for sheet in (False, True):
            if sheet:
                c.handle("i")
            origin = c.view
            before = e.state.turns, [i.instance_id for i in hero.inventory]
            c.handle("Q")
            self.assertEqual(c.view, View.DROP)
            self.assertEqual(c.drop_maximum, 12 if not sheet else 9)
            for width, height in ((80, 24), (120, 36)):
                self.assertIn("Количество: 1 /", "\n".join(render(c, width, height)))
            c.handle("end")
            c.handle("right")
            self.assertEqual(int(c.drop_quantity), c.drop_maximum)
            c.handle("home")
            c.handle("left")
            self.assertEqual(c.drop_quantity, "1")
            c.handle("backspace")
            c.handle("0")
            c.handle("enter")
            self.assertEqual(c.view, View.DROP)
            c.handle("escape")
            self.assertEqual(c.view, origin)
            self.assertEqual(
                before, (e.state.turns, [i.instance_id for i in hero.inventory])
            )
            c.handle("q")
            c.handle("3")
            c.handle("enter")
            self.assertEqual(c.view, origin)
            self.assertEqual(e.state.turns, before[0] + 1)
            self.assertEqual(len(hero.inventory), len(before[1]) - 3)
            self.assertTrue(any(i is different for i in hero.inventory))
            self.assertTrue(c.running)
        dropped = {i.instance_id for _, i in e.state.items[-6:]}
        self.saves.save(e)
        loaded = self.saves.load(store=self.store)
        self.assertEqual({i.instance_id for _, i in loaded.state.items[-6:]}, dropped)
        self.assertTrue(
            all(
                p.x == e.state.position.x and p.y == e.state.position.y
                for p, _ in loaded.state.items[-6:]
            )
        )

    def test_q_single_item_header_and_item_menu_share_drop_action(self):
        c = self.controller
        hero = c.engine.state.hero
        coin = Equipment.create(self.factory.catalog.equipment["gold"])
        hero.inventory[:] = [coin]
        c.inventory.query = "gold"
        c.inventory.selected = 0
        c.handle("q")  # Category headings do not drop anything or quit.
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.engine.state.turns, 0)
        c.inventory.selected = 1
        c.handle("q")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIs(c.engine.state.items[-1][1], coin)
        self.assertEqual(c.engine.state.turns, 1)
        self.assertTrue(c.running)
        hero.inventory[:] = [
            Equipment.create(self.factory.catalog.equipment["wood"]) for _ in range(2)
        ]
        c.open_item(hero.inventory[0])
        c.handle("2")
        c.handle("q")
        self.assertEqual(c.view, View.DROP)
        c.handle("escape")
        c.open_item(hero.inventory[0])
        c.handle("4")
        self.assertEqual(c.view, View.DROP)
        c.handle("end")
        c.handle("enter")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertFalse(hero.inventory)
        self.assertEqual(c.engine.state.turns, 2)

    def setUp(self):
        super().setUp()
        self.controller = Controller(
            42,
            catalog=self.factory.catalog,
            store=self.store,
            map_ref="base:crypt",
            test_map=True,
        )

    def test_equal_items_share_rows_without_losing_instances_or_state(self):
        c = self.controller
        hero = c.engine.state.hero
        wood = [
            Equipment.create(self.factory.catalog.equipment["wood"]) for _ in range(12)
        ]
        potions = [
            Equipment.create(self.factory.catalog.equipment["healing_potion"])
            for _ in range(3)
        ]
        potions[-1].charges = 0
        (
            potions[-1].liquid_kind,
            potions[-1].liquid_portions,
            potions[-1].liquid_effects,
        ) = (
            None,
            0,
            (),
        )
        torches = [
            Equipment.create(self.factory.catalog.equipment["torch"]) for _ in range(2)
        ]
        torches[-1].fuel_minutes = 20
        hero.inventory[:] = wood + potions + torches
        ids = [i.instance_id for i in hero.inventory]
        browser = c.inventory
        items = [r for r in browser.rows(hero) if r.item]
        self.assertEqual(sorted(r.quantity for r in items), [1, 1, 1, 2, 12])
        self.assertEqual([i.instance_id for i in hero.inventory], ids)
        browser.query = "wood"
        for sheet in (False, True):
            c.view = View.CHARACTER if sheet else View.EXPLORE
            c.sheet_section = 1
            text = "\n".join(render(c, 100, 28))
            self.assertIn("Древесина x12", text)
        hero.hp = 1
        self.assertTrue(c.engine.use_item(potions[0]).performed)
        potion_stacks = [
            s for s in item_stacks(hero.inventory) if s.first.id == "healing_potion"
        ]
        self.assertEqual(
            sorted((s.first.charges, s.quantity) for s in potion_stacks),
            [(0, 2), (1, 1)],
        )
        self.assertEqual([i.instance_id for i in hero.inventory], ids)

    def test_remaining_durability_is_visible_in_sidebar_and_sheet_even_for_long_names(
        self,
    ):
        c = self.controller
        definition = replace(
            self.factory.catalog.equipment["arcane_focus"],
            name="Очень длинное название магического фокуса",
            slot="hand",
            hands=1,
        )
        tools = Equipment.create(definition)
        tools.wear(4)
        c.engine.state.hero.inventory.append(tools)
        for item in c.engine.state.hero.inventory:
            if item.hands:
                c.engine.state.hero.unequip(item)
        self.assertTrue(c.engine.state.hero.equip(tools))
        c.inventory.query = "фокуса"
        for width in (80, 100):
            for sheet in (False, True):
                c.view = View.CHARACTER if sheet else View.EXPLORE
                c.sheet_section = 1
                layout = Layout.for_size(width, 28)
                rect = layout.main if sheet else layout.sidebar
                rows = render(c, width, 28)
                text = "\n".join(row[rect.x : rect.x + rect.width] for row in rows)
                self.assertIn("(6/10)", text)
                self.assertIn("[*]", text)
        tools.wear(6)
        self.assertIn("(0/10)", "\n".join(render(c, 80, 28)))

    def test_categories_and_explicit_schema_category_support_old_packs(self):
        for item_id, category in (
            ("sword", "weapons"),
            ("shield", "armor"),
            ("healing_potion", "consumables"),
            ("thieves_tools", "tools"),
        ):
            item = Equipment.create(self.factory.catalog.equipment[item_id])
            self.assertEqual(item.category, category)
        raw = self.store.get("equipment", "base:sword").model_dump(mode="json")
        raw["category"] = "tools"
        document = EquipmentDocument.model_validate(raw)
        item = Equipment.create(
            replace(self.factory.catalog.equipment["sword"], category=document.category)
        )
        self.assertEqual(item.category, "tools")
        raw["category"] = "unknown"
        with self.assertRaises(ValueError):
            EquipmentDocument.model_validate(raw)

    def test_tools_have_separate_group_from_utility_gear(self):
        c = self.controller
        hero = c.engine.state.hero
        catalog = self.factory.catalog.equipment
        tools = [
            Equipment.create(catalog[name])
            for name in ("pickaxe", "crowbar", "thieves_tools")
        ]
        gear = [
            Equipment.create(catalog[name])
            for name in ("torch", "rope", "arcane_focus")
        ]
        hero.inventory[:] = tools + gear
        browser = c.inventory
        for category, items in (("tools", tools), ("gear", gear)):
            self.assertEqual(
                [
                    r.item
                    for r in browser.rows(hero)
                    if r.item and r.category == category
                ],
                items,
            )
            label = "Инструменты" if category == "tools" else "Снаряжение"
            for item in items:
                self.assertIn("Тип снаряжения: " + label, item_details(item))
            browser.query = label
            self.assertEqual([r.item for r in browser.rows(hero) if r.item], items)
            browser.query = ""
        browser.collapsed.add("tools")
        self.assertEqual([r.item for r in browser.rows(hero) if r.item], gear)
        for character in (False, True):
            c.view = View.CHARACTER if character else View.EXPLORE
            c.sheet_section = 1
            text = "\n".join(render(c, 100, 28))
            self.assertIn("+ Инструменты (3)", text)
            self.assertIn("- Снаряжение (3)", text)
            self.assertIn("Верёвка", text)
            self.assertNotIn("Ломик", text)
        self.assertEqual(hero.inventory, tools + gear)

    def test_page_arrows_do_not_change_sidebar_and_backspace_closes_sheet(self):
        c = self.controller
        c.handle("right")
        c.handle("2")
        for key, page in (("right", 1), ("right", 2), ("right", 0), ("left", 2)):
            c.handle(key)
            self.assertEqual(c.sheet_section, page)
            self.assertTrue(c.spells_tab)
            screen = render(c, 80, 24)
            self.assertIn("Квесты", screen[0])
            right = [row[53:79].strip() for row in screen[1:16]]
            self.assertFalse(any(right))
        c.handle("backspace")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.engine.state.turns, 0)

    def test_shared_search_captures_shortcuts_and_keeps_same_filter_in_sheet(self):
        c = self.controller
        c.handle("f")
        for key in "qmw2":
            c.handle(key)
        self.assertTrue(c.running)
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.inventory.query, "qmw2")
        for _ in range(4):
            c.handle("backspace")
        for key in "кольчуга":
            c.handle(key)
        c.handle("enter")
        matched = [
            row.item.name for row in c.inventory.rows(c.engine.state.hero) if row.item
        ]
        self.assertEqual(matched, ["Кольчуга"])
        c.handle("2")
        c.handle("right")
        self.assertIn("Кольчуга", "\n".join(render(c, 80, 24)))
        c.handle("enter")
        self.assertEqual(c.view, View.ITEM)
        self.assertEqual(c.item_return_view, View.CHARACTER)
        c.handle("backspace")
        c.handle("backspace")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertEqual(c.engine.state.turns, 0)

    def test_item_menu_sidebar_use_inspect_throw_cancel_and_drop(self):
        c = self.controller
        c.handle("i")
        c.handle("enter")
        self.assertEqual(c.view, View.ITEM)
        item, old = c.selected_item, c.selected_item.equipped
        c.handle("1")
        self.assertNotEqual(item.equipped, old)
        c.handle("2")
        self.assertEqual(c.view, View.ITEM_INSPECT)
        screen = render(c, 80, 24)
        rect = popup_layout(c, 80, 24)[1]
        self.assertIn("Осмотр предмета", screen[rect.y])
        self.assertIn("Тип снаряжения:", "\n".join(screen))
        self.assertIn("Урон: 1d8", "\n".join(screen))
        c.handle("backspace")
        c.handle("3")
        self.assertEqual(c.view, View.THROW)
        for _ in range(20):
            c.handle("right")
        self.assertEqual(
            c.look_position.x - c.engine.state.position.x, c.engine.throw_range
        )
        c.handle("backspace")
        self.assertEqual(c.engine.state.turns, 1)
        self.assertTrue(any(i is item for i in c.engine.state.hero.inventory))
        c.handle("4")
        self.assertEqual(c.view, View.CHARACTER)
        c.handle("escape")
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIs(c.engine.state.items[-1][1], item)
        c.handle("g")
        self.assertIs(c.engine.state.hero.inventory[-1], item)

    def test_consumable_usage_and_search_cancel_are_resource_safe(self):
        c = self.controller
        hero = c.engine.state.hero
        item = Equipment.create(self.factory.catalog.equipment["healing_potion"])
        hero.inventory.append(item)
        hero.hp = 1
        c.open_item(item)
        c.handle("1")
        self.assertEqual(item.charges, 0)
        self.assertGreater(hero.hp, 1)
        c.handle("1")
        self.assertEqual(c.engine.state.turns, 1)
        c.handle("backspace")
        c.handle("f")
        c.handle("s")
        c.handle("escape")
        self.assertEqual(c.inventory.query, "")

    def test_equipment_checkboxes_are_shared_and_consumables_have_no_checkbox(self):
        c = self.controller
        hero = c.engine.state.hero
        sword = next(item for item in hero.inventory if item.id == "sword")
        sword.equipped = True
        potion = Equipment.create(self.factory.catalog.equipment["healing_potion"])
        hero.inventory.append(potion)
        for character in (False, True):
            if character:
                c.handle("2")
                c.handle("right")
            screen = "\n".join(render(c, 80, 24))
            self.assertIn("[*] Меч", screen)
            sword.equipped = False
            self.assertIn("[ ] Меч", "\n".join(render(c, 80, 24)))
            self.assertNotIn("[ ] Зелье", screen)
            sword.equipped = True

    def test_long_inventory_scrolls_and_load_bar_stays_at_bottom_after_resize(self):
        c = self.controller
        hero = c.engine.state.hero
        hero.inventory += [
            Equipment.create(self.factory.catalog.equipment["sword"]) for _ in range(30)
        ]
        hero.stats = Stats((1, 10, 10, 10, 10, 10))
        for _ in range(60):
            c.handle("down")
        for width, height in ((80, 24), (100, 30)):
            screen = render(c, width, height)
            rect = Layout.for_size(width, height).sidebar
            self.assertIn("ПЕРЕГРУЗ", "\n".join(screen))
            self.assertIn("[", screen[rect.y + rect.height - 4][rect.x :])
            self.assertTrue(
                any(row[rect.x + 1] == ">" for row in screen[1 : rect.height - 1])
            )
            self.assertTrue(all(len(row) == width for row in screen))
        self.assertEqual(c.engine.state.turns, 0)

    def test_collapse_and_filter_reveal_items_without_changing_inventory(self):
        hero = self.engine.state.hero
        browser = InventoryBrowser(selected=0)
        before = list(hero.inventory)
        browser.activate(hero)
        self.assertIn("weapons", browser.collapsed)
        self.assertFalse(
            any(
                row.item and row.item.category == "weapons"
                for row in browser.rows(hero)
            )
        )
        browser.query = "меч"
        self.assertTrue(
            any(row.item and row.item.name == "Меч" for row in browser.rows(hero))
        )
        self.assertEqual(hero.inventory, before)

    def test_item_cards_show_only_applicable_stats_and_hide_internal_tags(self):
        catalog = self.factory.catalog.equipment
        cases = (
            (
                "wood",
                ("Вес:",),
                ("Урон:", "Стойкость:", "КД:", "Занимает рук:", "Заряды:"),
            ),
            ("torch", ("Топливо:", "Занимает рук: 1"), ("Урон:", "Стойкость:", "КД:")),
            ("sword", ("Урон: 1d8", "Стойкость:", "Занимает рук:"), ("КД:", "Заряды:")),
            ("mail", ("КД: 16", "Стойкость:"), ("Урон:", "Занимает рук:", "Заряды:")),
            ("shield", ("Бонус КД: +2", "Занимает рук: 1"), ("Урон:", "Заряды:")),
            (
                "bandage",
                ("Лечение: 4", "Заряды: 1/1"),
                ("Урон:", "КД:", "Стойкость:", "Занимает рук:"),
            ),
        )
        for name, present, absent in cases:
            with self.subTest(item=name):
                item = Equipment.create(
                    replace(
                        catalog[name],
                        tags=catalog[name].tags | {"cursed", "hidden_quest"},
                    )
                )
                for preview in (False, True):
                    text = "\n".join(item_details(item, preview=preview))
                    for field in present:
                        self.assertIn(field, text)
                    for field in (
                        *absent,
                        "Теги:",
                        "cursed",
                        "hidden_quest",
                        "Слот:",
                        "Нет.",
                        "Описание не задано",
                        "Особые свойства",
                        "Надето: нет",
                    ):
                        self.assertNotIn(field, text)
                    if name == "mail":
                        self.assertEqual(text.count("КД:"), 1)
        potion = Equipment.create(catalog["healing_potion"])
        potion.charges = 0
        potion.liquid_kind, potion.liquid_portions, potion.liquid_effects = None, 0, ()
        self.assertIn("Вместимость: 1 порция", item_details(potion))
        self.assertNotIn("Лечение: 2d4+2", item_details(potion))
        self.assertFalse(
            any(line.startswith("Заряды:") for line in item_details(potion))
        )
        sword = Equipment.create(catalog["sword"])
        sword.durability = 0
        self.assertIn("Стойкость: 0/50", item_details(sword))
        torch = Equipment.create(catalog["torch"])
        self.assertIn("Топливо: 60 мин.", item_details(torch, preview=True))
        self.assertNotIn("Свет: погашен", item_details(torch, preview=True))
        hero = self.engine.state.hero
        hero.inventory[:] = [
            Equipment.create(replace(catalog["wood"], tags=frozenset({"cursed"})))
        ]
        self.assertFalse(
            any(r.item for r in InventoryBrowser(query="cursed").rows(hero))
        )

    def test_details_include_effects_armor_tools_and_resource_limits(self):
        for name, text in (
            ("mail", "КД: 16"),
            ("healing_potion", "Лечение: 2d4+2"),
            ("master_lockpicks", "автоматический успех"),
        ):
            item = Equipment.create(self.factory.catalog.equipment[name])
            self.assertIn(text, "\n".join(item_details(item)))
