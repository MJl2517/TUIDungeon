"""Crafting ownership, light gates, persistence, content and client parity."""

from copy import copy
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from pydantic import ValidationError
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.engine import Action
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.schemas import MapDocument, RecipeDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.storage import item_stacks
from tuidungeon.presentation.tui import (
    Controller,
    View,
    render,
    popup_content,
    popup_layout,
    handle_click,
)
from tuidungeon.presentation.crafting import craft_layout
from tuidungeon.world.maps import Position


class CraftingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.engine = SessionFactory(self.store).session("dev:crafting_lab", seed=42)

    def rebuild(self, ambient="bright", extra_recipe=None):
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw.update(ambient_light=ambient, lights=[])
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        if extra_recipe:
            self.store.documents["recipes", "dev:test_recipe"] = (
                RecipeDocument.model_validate(extra_recipe)
            )
        self.engine = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        return self.engine

    def inventory(self, item_id, quantity=1):
        items = [
            Equipment.create(self.engine.catalog.equipment[item_id])
            for _ in range(quantity)
        ]
        self.engine.state.hero.inventory.extend(items)
        return items

    def test_all_basic_recipes_produce_working_items_and_correct_time(self):
        for ref, result, turns, quantity in [
            ("craft_torch", "torch", 2, 1),
            ("craft_bandage", "bandage", 1, 1),
            ("craft_rope", "improvised_rope", 3, 1),
            ("craft_club", "club", 2, 1),
            ("craft_stake", "stake", 1, 1),
            ("craft_tinder", "tinder", 1, 2),
        ]:
            with self.subTest(ref=ref):
                engine = self.rebuild()
                old = Counter(i.id for i in engine.state.hero.inventory)
                self.assertTrue(engine.start_craft("base:" + ref).performed)
                self.assertFalse(engine.apply(Action.EAST).performed)
                self.assertEqual(engine.state.turns, 0)
                for _ in range(turns):
                    self.assertTrue(engine.advance_craft().performed)
                self.assertEqual(engine.state.turns, turns)
                self.assertEqual(engine.state.clock.elapsed_minutes, 480 + turns)
                self.assertEqual(
                    Counter(i.id for i in engine.state.hero.inventory)[result],
                    old[result] + quantity,
                )
                self.assertFalse(engine.active_craft)
                self.assertFalse(engine.advance_craft().performed)
                if result == "torch":
                    torch = engine.state.hero.inventory[-1]
                    self.assertEqual(torch.fuel_minutes, 60)
                    engine.state.position = Position(15, 8)
                    self.assertEqual(engine.lighting.level_at(engine.state.position), 2)
                    # This test has bright ambient light; turn it off for actual use.
                    engine.state.level.definition = (
                        engine.state.level.definition.model_copy(
                            update={"ambient_light": "dark"}
                        )
                    )
                    self.assertEqual(engine.lighting.level_at(engine.state.position), 0)
                    for equipped in list(engine.state.hero.inventory):
                        if equipped.equipped:
                            engine.manage_equipment(equipped, False)
                    self.assertTrue(engine.manage_equipment(torch, True).performed)
                    self.assertEqual(torch.fuel_minutes, 59)
                    self.assertEqual(engine.lighting.level_at(engine.state.position), 2)
                if result == "bandage":
                    hero = engine.state.hero
                    hero.hp -= 5
                    self.assertTrue(engine.use_item(hero.inventory[-1]).performed)
                    self.assertEqual(hero.hp, hero.max_hp - 1)
                if result in ("club", "stake"):
                    self.assertIsNotNone(
                        engine.state.hero.inventory[-1].definition.weapon_damage
                    )

    def test_physical_darkness_dim_basic_and_bright_professional(self):
        raw = dict(
            id="test_recipe",
            name="Профессиональная работа",
            category="smith",
            basic_known=True,
            variants=[
                dict(ingredients=[dict(items=["base:wood"], quantity=1)], turns=2)
            ],
            result=[dict(item="base:stake")],
        )
        for light, basic, professional in (
            ("dark", False, False),
            ("dim", True, False),
            ("bright", True, True),
        ):
            e = self.rebuild(light, raw)
            self.assertEqual(e.assess_craft("base:craft_torch").available, basic)
            self.assertEqual(e.assess_craft("dev:test_recipe").available, professional)
            before = (
                e.state.turns,
                len(
                    next(
                        c
                        for c in e.state.level.containers
                        if c.placement.id == "materials"
                    ).items
                ),
                e.dice.rng.getstate(),
            )
            if not basic:
                self.assertFalse(e.start_craft("base:craft_torch").performed)
                self.assertEqual(
                    before,
                    (
                        e.state.turns,
                        len(
                            next(
                                c
                                for c in e.state.level.containers
                                if c.placement.id == "materials"
                            ).items
                        ),
                        e.dice.rng.getstate(),
                    ),
                )
                # The player's navigation marker remains visible in physical darkness.
                self.assertGreater(e.lighting.at(e.state.position), 0)

    def test_light_expiration_pauses_and_retains_progress_then_resume(self):
        e = self.rebuild("dark")
        hero = e.state.hero
        for i in hero.inventory:
            i.equipped = False
        torch = next(i for i in hero.inventory if i.id == "torch")
        torch.equipped = torch.lit = True
        torch.fuel_minutes = 1
        self.assertTrue(e.start_craft("base:craft_torch").performed)
        identifier = e.active_craft
        self.assertTrue(e.advance_craft().performed)
        self.assertEqual(e.workpiece(identifier).work.progress, 1)
        self.assertIsNone(e.active_craft)
        self.assertFalse(e.resume_craft(identifier).performed)
        self.assertEqual(e.state.turns, 1)
        lamp = next(
            i
            for i in hero.inventory
            if i.definition.light and i.definition.light.fuel_tag
        )
        self.assertTrue(e.manage_equipment(lamp, True).performed)
        self.assertTrue(e.resume_craft(identifier).performed)
        self.assertTrue(e.advance_craft().performed)
        self.assertIsNone(e.workpiece(identifier))

    def test_reservation_refund_ground_container_and_unique_stack(self):
        e = self.engine
        container = next(
            c for c in e.state.level.containers if c.placement.id == "materials"
        )
        wood = next(i for i in container.items if i.id == "wood")
        cloth = next(i for i in container.items if i.id == "cloth")
        old_ids = {i.instance_id for i in container.items}
        self.assertTrue(e.start_craft("base:craft_torch").performed)
        identifier = e.active_craft
        item = e.workpiece(identifier)
        self.assertEqual(
            [i.instance_id for i in item.work.ingredients],
            [wood.instance_id, cloth.instance_id],
        )
        self.assertAlmostEqual(item.weight, 0.6)
        self.assertFalse(
            e.transfer_storage(
                container.placement.id, identifier, deposit=True
            ).performed
        )
        e.advance_craft()
        e.pause_craft()
        self.assertTrue(
            e.transfer_storage(
                container.placement.id, identifier, deposit=True
            ).performed
        )
        self.assertIsNone(e.workpiece(identifier))
        self.assertTrue(
            e.transfer_storage(container.placement.id, identifier).performed
        )
        self.assertEqual(e.workpiece(identifier).work.progress, 1)
        self.assertTrue(
            e.place_item(e.workpiece(identifier), e.state.position).performed
        )
        self.assertTrue(e.pickup_item().performed)
        self.assertTrue(e.cancel_craft(identifier).performed)
        self.assertIn(wood, e.state.hero.inventory)
        self.assertIn(cloth, e.state.hero.inventory)
        now = {i.instance_id for i in container.items + e.state.hero.inventory}
        self.assertTrue(old_ids.issubset(now))
        self.assertFalse(e.cancel_craft(identifier).performed)
        for _ in range(2):
            e.start_craft("base:craft_torch")
            e.pause_craft()
        works = [i for i in e.state.hero.inventory if i.work]
        self.assertEqual(len(works), 2)
        self.assertEqual(len(item_stacks(works)), 2)

    def test_tools_proficiency_stations_and_alternatives_are_independent(self):
        raw = dict(
            id="test_recipe",
            name="Проверка требований",
            category="smith",
            basic_known=True,
            variants=[
                dict(
                    ingredients=[
                        dict(items=["base:wood", "base:cloth"], quantity=1),
                        dict(items=["base:wood"], quantity=1),
                    ],
                    tools=["smith_tools"],
                    proficiencies=["smith_tools"],
                    stations=[["craft_forge", "craft_oven"], ["craft_anvil"]],
                    turns=2,
                )
            ],
            result=[dict(item="base:stake")],
        )
        e = self.rebuild(extra_recipe=raw)
        reasons = e.assess_craft("dev:test_recipe").reasons
        self.assertEqual(len(reasons), 4)
        self.inventory("smith_tools")
        self.assertEqual(len(e.assess_craft("dev:test_recipe").reasons), 3)
        e.state.hero.tool_proficiencies.add("smith_tools")
        self.assertEqual(len(e.assess_craft("dev:test_recipe").reasons), 2)
        # A point's authored tags can provide station requirements independently.
        mapraw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        mapraw["points_of_interest"][0]["overrides"]["tags"] = [
            "craft_oven",
            "craft_anvil",
            "storage",
        ]
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            mapraw
        )
        e = SessionFactory(self.store).session("dev:crafting_lab", seed=42)
        self.engine = e
        self.inventory("smith_tools")
        e.state.hero.tool_proficiencies.add("smith_tools")
        container = next(
            c for c in e.state.level.containers if c.placement.id == "materials"
        )
        container.items[:] = [i for i in container.items if i.id == "wood"][:1] + [
            i for i in container.items if i.id == "cloth"
        ][:1]
        self.assertTrue(e.start_craft("dev:test_recipe").performed)
        self.assertEqual(
            Counter(i.id for i in e.workpiece(e.active_craft).work.ingredients),
            {"wood": 1, "cloth": 1},
        )
        e.pause_craft()
        e.state.position = Position(7, 3)
        identifier = next(i.instance_id for i in e.state.hero.inventory if i.work)
        self.assertFalse(e.resume_craft(identifier).performed)

    def test_tool_speed_does_not_grant_proficiency_and_unknown_recipe_is_denied(self):
        e = self.engine
        self.assertEqual(
            e.assess_craft("base:craft_torch")
            .recipe.variants[e.assess_craft("base:craft_torch").variant]
            .turns,
            2,
        )
        self.inventory("carpenter_tools")
        self.assertFalse(e.state.hero.tool_proficiencies)
        a = e.assess_craft("base:craft_torch")
        self.assertEqual(a.recipe.variants[a.variant].turns, 1)
        e.state.hero.known_recipes.remove("base:craft_torch")
        self.assertFalse(e.start_craft("base:craft_torch").performed)
        self.assertFalse(e.start_craft("base:does_not_exist").performed)
        self.assertFalse(e.start_craft("base:craft_torch", 999).performed)

    def test_save_load_snapshot_refund_and_invalid_nested_inputs(self):
        e = self.engine
        e.state.hero.tool_proficiencies.add("smith_tools")
        e.start_craft("base:craft_torch")
        identifier = e.active_craft
        e.advance_craft()
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(e)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            loaded = repo.load(store=self.store)
            self.assertIsNone(loaded.active_craft)
            self.assertEqual(loaded.workpiece(identifier).work.progress, 1)
            self.assertIn("smith_tools", loaded.state.hero.tool_proficiencies)
            self.assertTrue(loaded.resume_craft(identifier).performed)
            self.assertTrue(loaded.advance_craft().performed)
            work = next(i for i in raw["hero"]["inventory"] if i["work"])
            work["work"]["progress"] = 2
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                repo.load(store=self.store)
            work["work"]["progress"] = 1
            work["work"]["ingredients"][0]["instance_id"] = raw["hero"]["inventory"][0][
                "instance_id"
            ]
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                repo.load(store=self.store)

    def test_controller_work_dialog_filters_and_inventory_resume(self):
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.handle("c")
        self.assertEqual(c.view, View.CRAFT)
        self.assertEqual(
            len(c.craft.entries(c.engine)),
            sum(e["category"] == c.craft.category for e in c.engine.craft_list()),
        )
        self.assertEqual(popup_content(c)[2], [])
        self.assertIn("РЕЗУЛЬТАТ", "\n".join(render(c, 100, 28)))
        self.assertIn("Вес:", "\n".join(render(c, 100, 28)))
        c.handle("tab")
        self.assertEqual(c.craft.filter, "available")
        c.handle("tab")
        self.assertEqual(c.craft.filter, "all")
        c.handle("f")
        for key in "факел":
            c.handle(key)
        c.handle("enter")
        self.assertEqual(c.craft.assessment(c.engine).recipe.name, "Факел")
        self.assertIn("Мешок", "\n".join(popup_content(c)[1]))
        c.handle("enter")
        identifier = c.engine.active_craft
        self.assertEqual(c.view, View.EXPLORE)
        self.assertIsNone(popup_layout(c, 100, 28))
        self.assertIn("Space /", "\n".join(render(c, 100, 28)))
        import tcod.event as events
        from tuidungeon.presentation.window import handle_event

        repeated = events.KeyDown(
            sym=events.KeySym.RIGHT,
            scancode=events.Scancode.RIGHT,
            mod=events.Modifier.NONE,
            repeat=True,
        )
        self.assertFalse(handle_event(c, repeated))
        self.assertEqual(c.engine.workpiece(identifier).work.progress, 0)
        c.handle("right")
        self.assertEqual(c.engine.workpiece(identifier).work.progress, 1)
        for w, h in ((80, 24), (100, 28), (140, 40)):
            self.assertTrue(all(len(r) == w for r in render(c, w, h)))
        c.handle("escape")
        self.assertIsNone(c.engine.active_craft)
        self.assertEqual(c.view, View.EXPLORE)
        c.selected_item = c.engine.workpiece(identifier)
        c.item_return_view = View.EXPLORE
        c.view = View.ITEM
        c.handle("1")
        self.assertEqual(c.view, View.CRAFT)
        c.handle("1")
        c.handle("space")
        self.assertIsNone(c.engine.workpiece(identifier))
        self.assertIn("Изготовлено", c.message)
        c.handle("m")
        self.assertEqual(c.view, View.EXPLORE)

    def test_many_recipes_categories_search_mouse_and_result_details(self):
        source = self.store.get("recipes", "base:craft_torch")
        for n in range(45):
            self.store.documents["recipes", f"dev:sample_{n}"] = source.model_copy(
                update={
                    "id": f"sample_{n}",
                    "name": f"Рецепт {n:02}",
                    "category": "smith",
                }
            )
        c = Controller(
            42,
            store=self.store,
            catalog=self.store.runtime_catalog(),
            map_ref="dev:crafting_lab",
            test_map=True,
        )
        c.handle("c")
        for _ in c.craft.categories(c.engine):
            if c.craft.category == "smith":
                break
            c.handle("right")
        self.assertEqual(c.craft.category, "smith")
        c.handle("end")
        for width, height in ((80, 24), (100, 28), (140, 40)):
            screen = render(c, width, height)
            self.assertTrue(all(len(row) == width for row in screen))
            _, rect, rows, _, hits = craft_layout(c, width, height)
            self.assertIn("Рецепт 44", "\n".join(rows))
            self.assertGreater(c.craft.page, 0)
            self.assertLessEqual(len(rows), rect.height - 2)
        for _ in c.craft.categories(c.engine):
            if c.craft.category == "basic":
                break
            c.handle("left")
        self.assertEqual(c.craft.category, "basic")
        self.assertTrue(
            all(e["category"] == "basic" for e in c.craft.entries(c.engine))
        )
        c.handle("f")
        for char in "факел":
            c.handle(char)
        c.handle("enter")
        self.assertTrue(
            any(row[1] and row[1]["name"] == "Факел" for row in c.craft.rows(c.engine))
        )
        _, rect, _, _, hits = craft_layout(c, 100, 28)
        row, _, index = next(
            h
            for h in hits
            if h[1] == "select"
            and c.craft.rows(c.engine)[h[2]][1]
            and c.craft.rows(c.engine)[h[2]][1]["ref"] == "base:craft_torch"
        )
        handle_click(c, rect.x + 3, rect.y + row + 1, 100, 28)
        self.assertEqual(c.craft.assessment(c.engine).ref, "base:craft_torch")
        self.assertEqual(c.engine.state.turns, 0)
        result = c.craft.assessment(c.engine).payload(c.engine.catalog)["result"][0]
        self.assertEqual(result["light"]["burn_minutes"], 60)
        self.assertEqual(result["weight"], c.engine.catalog.equipment["torch"].weight)
        self.assertTrue(result["description"])

    def test_recipe_statuses_ingredient_colors_methods_and_condition_checks(self):
        e = self.rebuild()
        for container in e.state.level.containers:
            container.items.clear()
        e.state.items.clear()
        e.state.hero.inventory.clear()
        self.inventory("cloth")
        self.inventory("wood", 3)
        c = Controller(42, store=self.store, map_ref="dev:crafting_lab", test_map=True)
        c.engine = e
        c.handle("c")
        c.craft.recipe_ref = "base:craft_bandage"
        details, _, _ = c.craft.details(e)
        self.assertIn("2 Тряпка | у вас: 1", details)
        self.assertEqual(c.craft._detail_colors["2 Тряпка | у вас: 1"], 11)
        _, _, rows, _, _ = craft_layout(c, 140, 40)
        self.assertIn("X Бинт", "\n".join(rows))
        self.assertIn("V Факел", "\n".join(rows))
        self.assertIn("Условия изготовления:", details)
        self.assertIn("V Тусклый или яркий свет", details)
        from tcod.console import Console
        from tuidungeon.presentation.window import draw, PALETTE

        console = Console(140, 40)
        draw(console, c)
        _, rect, _, _, _ = craft_layout(c, 140, 40)
        row, column, _, color, _ = next(
            span for span in c.craft.colors if "2 Тряпка" in span[2]
        )
        self.assertEqual(
            tuple(console.rgb[rect.y + row + 1, rect.x + column + 2]["fg"]),
            PALETTE[color],
        )
        c.craft.recipe_ref = "base:craft_torch"
        details, _, _ = c.craft.details(e)
        self.assertIn("Вручную: 2 хода · выбран [B]", details)
        self.assertIn("С инструментами плотника: 1 ход", details)
        self.assertEqual(c.craft._detail_colors["1 Древесина | у вас: 3"], 10)
        e.state.hero.inventory[:] = [
            i for i in e.state.hero.inventory if i.id != "cloth"
        ]
        details, _, _ = c.craft.details(e)
        self.assertEqual(c.craft._detail_colors["1 Тряпка | у вас: 0"], 9)
        e.state.hero.known_recipes.add("base:craft_healing_potion")
        e.state.hero.tool_proficiencies.add("alchemist_tools")
        card = e.assess_craft("base:craft_healing_potion").payload(e.catalog)
        conditions = {r["name"]: r["met"] for r in card["conditions"]}
        self.assertTrue(conditions["Владение: Алхимические принадлежности"])
        self.assertFalse(conditions["Наличие: Алхимические принадлежности"])
        self.assertFalse(conditions["Наличие рядом: Алхимический стол"])
        self.inventory("alchemist_tools")
        card = e.assess_craft("base:craft_healing_potion").payload(e.catalog)
        self.assertTrue(
            next(
                r["met"]
                for r in card["conditions"]
                if r["name"].startswith("Наличие: Алхимические")
            )
        )
        self.assertEqual(e.state.turns, 0)

    def test_ground_source_priority_distance_and_old_save_defaults(self):
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw["equipment"] = [
            dict(id="cloth_here", ref="base:cloth", x=3, y=3),
            dict(id="cloth_side", ref="base:cloth", x=4, y=3),
            dict(id="cloth_diagonal", ref="base:cloth", x=4, y=4),
            dict(id="cloth_far", ref="base:cloth", x=5, y=3),
        ]
        self.store.documents["maps", "dev:crafting_lab"] = MapDocument.model_validate(
            raw
        )
        self.engine = e = SessionFactory(self.store).session(
            "dev:crafting_lab", seed=42
        )
        next(
            c for c in e.state.level.containers if c.placement.id == "materials"
        ).items.clear()
        wood = self.inventory("wood")[0]
        a = e.assess_craft("base:craft_torch")
        self.assertEqual(a.ingredients[1]["available"], 2)
        self.assertEqual([i.instance_id for i, _, _ in a.selected][0], wood.instance_id)
        self.assertTrue(a.ingredients[1]["sources"][0]["source"].endswith("(3, 3)"))
        e.start_craft("base:craft_torch")
        identifier = e.active_craft
        e.advance_craft()
        e.pause_craft()
        e.place_item(e.workpiece(identifier), e.state.position)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(e)
            loaded = repo.load(store=self.store)
            self.assertTrue(loaded.pickup_item().performed)
            self.assertEqual(loaded.workpiece(identifier).work.progress, 1)
            self.assertTrue(loaded.resume_craft(identifier).performed)
            self.assertTrue(loaded.advance_craft().performed)
            # Missing new fields in an older save retain character starting knowledge.
            repo.save(loaded)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            raw.pop("active_craft")
            raw["hero"].pop("tool_proficiencies")
            raw["hero"].pop("known_recipes")
            for i in raw["hero"]["inventory"]:
                i.pop("work", None)
            repo.path.write_text(json.dumps(raw), encoding="utf-8")
            old = repo.load(store=self.store)
            self.assertEqual(
                len(old.craft_list()),
                sum(r.basic_known for r in old.catalog.recipes.values()),
            )
            self.assertFalse(old.state.hero.tool_proficiencies)
        artisan = SessionFactory(self.store).session(
            "dev:crafting_lab", seed=42, background="base:artisan"
        )
        self.assertEqual(
            artisan.state.hero.tool_proficiencies, {"carpenter_tools", "smith_tools"}
        )
        self.assertEqual(artisan.assess_craft("base:craft_torch").variant, 0)

    def test_recipe_validation_and_new_category_links(self):
        for updates in (
            {"variants": []},
            {"result": []},
            {"variants": [{"turns": 0}]},
            {"result": [{"item": "not_a_ref"}]},
        ):
            with self.assertRaises(ValidationError):
                RecipeDocument.model_validate(
                    {"id": "bad", "name": "Неверно", **updates}
                )
        documents = dict(self.source.documents)
        documents["recipes", "base:broken"] = RecipeDocument(
            id="broken", name="Ошибка", result=[{"item": "base:absent_item"}]
        )
        with self.assertRaises(ContentError):
            self.store.validate_references(documents, self.store.manifests)
