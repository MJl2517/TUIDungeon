"""Shared visibility, hand occupancy and fuel measured in game minutes."""

from scripts.testing import fixture_store, lay_bedroll

from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from pydantic import ValidationError

from tuidungeon.application.engine import Action, Engine
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.catalog import ContentCatalog, DEFAULT_ROOT
from tuidungeon.content.schemas import Cell, EquipmentDocument, MapDocument
from tuidungeon.domain.actions import SpellSource
from tuidungeon.domain.equipment import Equipment
from tuidungeon.presentation.inventory import item_details
from tuidungeon.presentation.tui import Controller, Layout, draw_colors, render
from tuidungeon.world.lighting import DIM_LIGHT_HINT, LightField, line_of_sight
from tuidungeon.world.maps import DungeonMap, Position
from tuidungeon.world.state import GameState


class LightingFixture(unittest.TestCase):
    def setUp(self):
        self.store = fixture_store()
        self.factory = SessionFactory(self.store)
        self.engine = self.factory.session("base:crypt", seed=42)
        self.hero = self.engine.state.hero

    def item(self, name):
        return next(i for i in self.hero.inventory if i.id == name)

    def free_hand(self):
        self.hero.unequip(self.item("shield"))


class FuelTests(LightingFixture):
    def test_full_hands_reject_light_without_spending_time_or_oil(self):
        lamp, oil = self.item("lamp"), self.item("oil")
        self.assertEqual(self.hero.hands_used, 2)
        result = self.engine.manage_equipment(lamp, True)
        self.assertFalse(result.performed)
        self.assertIn("руку", result.message)
        self.assertEqual(
            (oil.charges, lamp.fuel_minutes, lamp.lit, self.engine.state.turns),
            (1, 0, False, 0),
        )
        self.assertTrue(self.item("sword").equipped)
        self.assertTrue(self.item("shield").equipped)
        self.free_hand()
        self.assertTrue(self.engine.manage_equipment(lamp, True).performed)
        self.assertEqual(
            (self.hero.hands_used, oil.charges, lamp.fuel_minutes), (2, 0, 59)
        )
        self.assertFalse(self.hero.equip(self.item("shield")))
        self.assertTrue(
            self.hero.equip(Equipment.create(self.item("sword").definition)) is False
        )

    def test_torch_burns_exactly_sixty_game_minutes_and_cannot_be_refilled(self):
        self.free_hand()
        torch = self.item("torch")
        self.assertEqual(torch.fuel_minutes, 60)
        self.engine.manage_equipment(torch, True)
        self.assertEqual(torch.fuel_minutes, 59)
        before = torch.fuel_minutes
        self.engine.apply(Action.NORTH)
        self.engine.apply(Action.NORTH)
        self.engine.apply(Action.NORTH)  # Wall: time and fuel stay unchanged.
        self.assertEqual(torch.fuel_minutes, before - 2)
        for _ in range(57):
            self.engine.apply(Action.WAIT)
        self.assertEqual(
            (self.engine.state.clock.elapsed_minutes, torch.fuel_minutes, torch.lit),
            (540, 0, False),
        )
        self.assertFalse(torch.equipped)
        self.assertFalse(any(i is torch for i in self.hero.inventory))
        self.assertEqual(self.hero.hands_used, 1)
        self.assertEqual(self.engine.events[-1]["kind"], "light")
        before = self.engine.state.turns
        self.assertFalse(self.engine.manage_equipment(torch, True).performed)
        self.assertEqual(self.engine.state.turns, before)

    def test_lamp_requires_oil_only_when_empty_and_unequip_pauses_fuel(self):
        self.free_hand()
        lamp, oil = self.item("lamp"), self.item("oil")
        self.hero.inventory.remove(oil)
        self.assertFalse(self.engine.manage_equipment(lamp, True).performed)
        self.assertEqual(
            (lamp.equipped, lamp.lit, self.engine.state.turns), (False, False, 0)
        )
        self.hero.inventory.append(oil)
        self.engine.manage_equipment(lamp, True)
        self.engine.manage_equipment(lamp, False)
        self.assertEqual(lamp.fuel_minutes, 59)
        lay_bedroll(self.engine)
        self.engine.apply(Action.REST)
        self.assertEqual(lamp.fuel_minutes, 59)
        self.engine.manage_equipment(lamp, True)
        self.assertEqual((oil.charges, lamp.fuel_minutes), (0, 58))
        self.engine.apply(Action.SHORT_REST)
        self.assertEqual((lamp.fuel_minutes, lamp.lit), (0, False))
        self.assertFalse(self.engine.manage_equipment(lamp, True).performed)
        second_oil = Equipment.create(oil.definition)
        self.hero.inventory.append(second_oil)
        self.assertTrue(self.engine.manage_equipment(lamp, True).performed)
        self.assertEqual((second_oil.charges, lamp.fuel_minutes), (0, 59))

    def test_lamp_consumes_portions_and_relights_in_hand_after_save(self):
        from tuidungeon.presentation.tui import popup_layout

        c = Controller(
            42,
            store=self.store,
            catalog=self.factory.catalog,
            map_ref="base:crypt",
            test_map=True,
        )
        engine, hero = c.engine, c.engine.state.hero
        lamp, oil, shield = (
            next(i for i in hero.inventory if i.id == ref)
            for ref in ("lamp", "oil", "shield")
        )
        hero.unequip(shield)
        c.open_item(lamp)
        c.handle("1")
        self.assertEqual((oil.charges, lamp.fuel_minutes), (0, 59))
        self.assertFalse(any(i is oil for i in hero.inventory))
        self.assertIn("порция масла", c.message)
        for _ in range(59):
            engine.apply(Action.WAIT)
        self.assertEqual((lamp.equipped, lamp.lit, lamp.fuel_minutes), (True, False, 0))
        before = engine.state.turns
        c.handle("1")
        self.assertEqual(engine.state.turns, before)
        self.assertTrue(lamp.equipped)
        self.assertIn("масло", c.message)
        second_oil = Equipment.create(oil.definition)
        hero.inventory.append(second_oil)
        with tempfile.TemporaryDirectory() as directory:
            repository = SaveRepository(Path(directory) / "lamp.json")
            repository.save(engine)
            c.engine = repository.load(store=self.store)
        lamp = next(i for i in c.engine.state.hero.inventory if i.id == "lamp")
        c.open_item(lamp)
        self.assertIn("Заправить и зажечь", " ".join(popup_layout(c, 100, 28)[2]))
        c.handle("1")
        self.assertEqual((lamp.equipped, lamp.lit, lamp.fuel_minutes), (True, True, 59))
        self.assertEqual(c.engine.state.turns, before + 1)
        self.assertFalse(any(i.id == "oil" for i in c.engine.state.hero.inventory))
        c.handle("1")  # Extinguishing preserves the remaining fuel.
        c.handle("1")  # Relighting a partly filled lamp needs no more oil.
        self.assertEqual((lamp.lit, lamp.fuel_minutes), (True, 58))
        c.engine.apply(Action.SHORT_REST)
        self.assertIn("Снять из руки", " ".join(popup_layout(c, 100, 28)[2]))
        c.handle("5")
        self.assertFalse(lamp.equipped)

    def test_sneaking_and_failed_actions_use_game_minutes_not_turns(self):
        self.free_hand()
        torch = self.item("torch")
        self.engine.manage_equipment(torch, True)
        self.engine.toggle_sneaking()
        self.engine.apply(Action.EAST)
        self.assertEqual(torch.fuel_minutes, 57)
        self.engine.apply(Action.WEST)
        self.assertEqual(torch.fuel_minutes, 55)
        self.engine.apply(Action.WEST)
        self.assertEqual(torch.fuel_minutes, 53)
        self.engine.apply(Action.WEST)
        self.assertEqual(torch.fuel_minutes, 51)
        self.engine.apply(Action.WEST)  # Boundary wall; no fuel spent.
        self.assertEqual(torch.fuel_minutes, 51)
        self.assertFalse(self.engine.use_item(self.item("sword")).performed)
        self.assertEqual(torch.fuel_minutes, 51)

    def test_two_handed_item_and_weapon_replacement_respect_capacity(self):
        sword = self.item("sword")
        other = Equipment.create(sword.definition)
        self.hero.inventory.append(other)
        self.assertTrue(self.hero.equip(other))
        self.assertFalse(sword.equipped)
        self.assertEqual(self.hero.hands_used, 2)
        two_handed = Equipment.create(replace(sword.definition, hands=2))
        self.hero.inventory.append(two_handed)
        self.assertFalse(self.hero.equip(two_handed))
        self.free_hand()
        self.assertTrue(self.hero.equip(two_handed))
        self.assertEqual(self.hero.hands_used, 2)
        self.assertFalse(self.hero.equip(self.item("torch")))

    def test_dropped_flame_lights_ground_and_stowing_it_extinguishes(self):
        self.free_hand()
        torch = self.item("torch")
        self.engine.manage_equipment(torch, True)
        self.engine.place_item(torch, self.engine.state.position)
        self.assertTrue(torch.shining)
        self.assertFalse(torch.equipped)
        self.assertEqual((self.hero.hands_used, torch.fuel_minutes), (1, 58))
        self.assertGreater(self.engine.lighting.at(Position(6, 3)), 0)
        self.engine.pickup_item()
        self.assertFalse(torch.lit)
        self.assertEqual(torch.fuel_minutes, 58)


class VisibilityTests(LightingFixture):
    def open_room(self):
        return Engine(
            GameState(
                self.hero,
                DungeonMap(tuple("." * 24 for _ in range(14))),
                Position(10, 6),
            ),
            random.Random(42),
        )

    def test_look_range_uses_wisdom_and_visible_walls_block_inspection(self):
        from tuidungeon.domain.stats import Stats

        self.hero.stats = Stats((10, 10, 10, 10, 3, 10))
        engine = self.open_room()
        self.free_hand()
        engine.manage_equipment(self.item("torch"), True)
        self.assertEqual(engine.look_range, 3)
        self.assertTrue(engine.can_look_at(Position(13, 6)))
        self.assertTrue(engine.can_look_at(Position(13, 9)))
        self.assertFalse(engine.can_look_at(Position(14, 6)))
        self.assertNotIn("Пол.", engine.inspect_cell(Position(14, 6)))
        engine = Engine(
            GameState(
                self.hero, DungeonMap((".......", "...#...", ".......")), Position(1, 1)
            ),
            random.Random(42),
        )
        self.assertTrue(engine.can_look_at(Position(3, 1)))
        self.assertFalse(engine.can_look_at(Position(4, 1)))
        self.assertIn("не видна", " ".join(engine.inspect_cell(Position(4, 1))))
        before = engine.state.turns, engine.state.clock.elapsed_minutes
        for y in range(engine.state.dungeon.height):
            for x in range(engine.state.dungeon.width):
                engine.can_look_at(Position(x, y))
        self.assertEqual(
            (engine.state.turns, engine.state.clock.elapsed_minutes), before
        )

    def test_dark_wall_floor_and_cells_behind_them_are_indistinguishable(self):
        self.hero.inventory.clear()
        for rows in (
            (".......", ".......", "......."),
            (".......", "..#....", "......."),
        ):
            engine = Engine(
                GameState(self.hero, DungeonMap(rows), Position(1, 1)),
                random.Random(42),
            )
            for x in range(2, 7):
                position = Position(x, 1)
                self.assertTrue(engine.can_look_at(position))
                self.assertEqual(
                    engine.inspect_cell(position)[1:],
                    ["Клетка не видна: темно или обзор закрыт."],
                )

    def test_radius_follows_hero_and_bright_dim_hidden_have_distinct_cells(self):
        engine = self.open_room()
        self.free_hand()
        torch = self.item("torch")
        self.assertEqual(engine.lighting.at(Position(13, 6)), 0)
        engine.manage_equipment(torch, True)
        self.assertEqual(
            [engine.lighting.at(Position(x, 6)) for x in (13, 16, 17)], [2, 1, 0]
        )
        cells = engine.render_cells()
        self.assertEqual(cells[6][13].char, ".")
        self.assertEqual(cells[6][16].foreground, 8)
        self.assertEqual(cells[6][17].char, " ")
        engine.apply(Action.EAST)
        self.assertEqual(engine.lighting.at(Position(17, 6)), 1)
        self.assertEqual(engine.state.dungeon.rows[6][17], ".")

    def test_opaque_wall_visible_but_blocks_light_and_closed_corners(self):
        blocks = [[False] * 7 for _ in range(5)]
        for row in blocks:
            row[3] = True
        start = Position(1, 2)
        self.assertTrue(line_of_sight(start, Position(3, 2), blocks))
        self.assertFalse(line_of_sight(start, Position(4, 2), blocks))
        corner = [[False, True], [True, False]]
        self.assertFalse(line_of_sight(Position(0, 0), Position(1, 1), corner))
        engine = Engine(
            GameState(
                self.hero, DungeonMap((".......", ".#.....", ".......")), Position(0, 0)
            ),
            random.Random(0),
        )
        self.free_hand()
        engine.manage_equipment(self.item("torch"), True)
        self.assertEqual(engine.lighting.at(Position(1, 1)), 2)
        self.assertEqual(engine.lighting.at(Position(2, 2)), 0)

    def test_all_inner_wall_faces_and_corners_are_visible_within_light_radius(self):
        engine = Engine(
            GameState(
                self.hero,
                DungeonMap(
                    ("#########", "#.......#", "#.......#", "#.......#", "#########")
                ),
                Position(4, 2),
            ),
            random.Random(42),
        )
        self.free_hand()
        engine.manage_equipment(self.item("lamp"), True)
        light = engine.lighting
        for y, row in enumerate(engine.state.dungeon.rows):
            for x, char in enumerate(row):
                if char == "#":
                    with self.subTest(x=x, y=y):
                        self.assertGreater(light.at(Position(x, y)), 0)
                        self.assertEqual(engine.render_cells()[y][x].char, "#")
        # Adjacent cells of a solid wall expose its surface, but nothing behind it.
        blocks = [[False, False, True, True] for _ in range(5)]
        for y in range(5):
            self.assertTrue(line_of_sight(Position(0, 2), Position(2, y), blocks))
            self.assertFalse(line_of_sight(Position(0, 2), Position(3, y), blocks))
        # Shallow angles previously hit a neighboring wall center before this cell.
        blocks = [[x < 2 for x in range(9)] for _ in range(24)]
        for y in range(24):
            self.assertTrue(line_of_sight(Position(3, 3), Position(1, y), blocks))
            self.assertFalse(line_of_sight(Position(3, 3), Position(0, y), blocks))

    def test_wall_light_is_visible_only_on_the_illuminated_side(self):
        for rows, dark, lit, wall, adjacent in (
            (
                ("....#....",) * 9,
                Position(1, 2),
                Position(7, 2),
                Position(4, 4),
                Position(3, 4),
            ),
            (
                (".........",) * 4 + ("#########",) + (".........",) * 4,
                Position(2, 1),
                Position(2, 7),
                Position(4, 4),
                Position(4, 3),
            ),
        ):
            with self.subTest(rows=rows):
                engine = Engine(
                    GameState(self.hero, DungeonMap(rows), dark), random.Random(42)
                )
                torch = Equipment.create(self.item("torch").definition)
                torch.lit = True
                engine.state.items.append((lit, torch))
                hidden = engine.lighting
                self.assertEqual(hidden.at(wall), 0)
                self.assertEqual(hidden.level_at(wall), 0)
                self.assertEqual(engine.render_cells()[wall.y][wall.x].char, " ")
                self.assertIn("не видна", " ".join(engine.inspect_cell(wall)))
                # Moving the observer must reuse physical light, but select the other face.
                engine.state.position = lit
                visible = engine.lighting
                self.assertIs(visible.illumination, hidden.illumination)
                self.assertIs(visible.wall_illumination, hidden.wall_illumination)
                self.assertGreater(visible.at(wall), 0)
                self.assertGreater(visible.level_at(wall), 0)
                self.assertEqual(engine.render_cells()[wall.y][wall.x].char, "#")
                engine.state.position = dark
                self.assertEqual(engine.lighting.at(wall), 0)
                engine.state.position = adjacent
                # Touch-range navigation is dim, never light from the other room.
                self.assertEqual(engine.lighting.at(wall), 1)
                self.assertEqual(engine.lighting.level_at(wall), 0)
                self.assertIn("не видна", " ".join(engine.inspect_cell(wall)))

    def test_different_wall_faces_keep_their_own_light_strength(self):
        state = GameState(self.hero, DungeonMap(("....#....",) * 9), Position(1, 4))
        sources = ((Position(2, 4), 6, 3), (Position(7, 4), 6, 1))
        wall = Position(4, 4)
        bright = LightField.calculate(state, sources=(), magic_sources=sources)
        self.assertEqual(bright.level_at(wall), 2)
        state.position = Position(7, 4)
        dim = LightField.calculate(
            state,
            sources=(),
            illumination=bright.illumination,
            wall_illumination=bright.wall_illumination,
        )
        self.assertEqual(dim.at(wall), 1)
        self.assertEqual(dim.level_at(wall), 1)

    def test_dim_background_art_and_black_backgrounds_are_preserved(self):
        original = [Cell(char=" ", background=c) for c in (7, 8, 15, 255, 196, 0, None)]
        shaded = LightField([[1] * len(original)]).shade([original])[0]
        for before, after in zip(original, shaded):
            self.assertEqual(after.char, before.char)
            if before.background not in (None, 0):
                self.assertNotIn(after.background, (None, 0))
            else:
                self.assertEqual(after.background, before.background)
        self.assertEqual(
            [c.background for c in original], [7, 8, 15, 255, 196, 0, None]
        )

    def test_inspection_distinguishes_light_from_navigation_and_obstructed_view(self):
        engine = self.open_room()
        self.assertEqual(engine.lighting.at(engine.state.position), 2)
        self.assertEqual(engine.lighting.level_at(engine.state.position), 0)
        self.assertIn(
            "Освещение: полная тьма", engine.inspect_cell(engine.state.position)
        )
        for position in (Position(11, 6), Position(20, 6)):
            self.assertIn("не видна", " ".join(engine.inspect_cell(position)))
        self.free_hand()
        engine.manage_equipment(self.item("torch"), True)
        self.assertIn("Освещение: яркий свет", engine.inspect_cell(Position(13, 6)))
        dim = engine.inspect_cell(Position(16, 6))
        self.assertIn("Освещение: тусклый свет", dim)
        self.assertIn(DIM_LIGHT_HINT, dim)
        self.assertIn("не видна", " ".join(engine.inspect_cell(Position(17, 6))))
        self.assertIn("Пол.", dim)
        turns, time = engine.state.turns, engine.state.clock.elapsed_minutes
        engine.inspect_cell(Position(16, 6))
        self.assertEqual(
            (engine.state.turns, engine.state.clock.elapsed_minutes), (turns, time)
        )

    def test_hidden_lit_cell_discloses_neither_light_nor_objects(self):
        engine = self.factory.session("base:crypt")
        engine.state.level.definition = engine.state.level.definition.model_copy(
            update={"ambient_light": "bright"}
        )
        monster = engine.state.monsters[0]
        self.assertEqual(engine.lighting.at(monster.position), 0)
        text = engine.inspect_cell(monster.position)
        self.assertIn("не видна", " ".join(text))
        self.assertNotIn("Освещение:", " ".join(text))
        self.assertNotIn(monster.monster.name, " ".join(text))

    def test_map_ambient_and_static_lights_use_sight_mask_not_walkability(self):
        state = self.engine.state
        original = state.level.definition
        doc = original.model_dump()
        doc["ambient_light"] = "dark"
        doc["lights"] = [
            {"id": "wall_light", "x": 0, "y": 3, "radius": 8, "bright_radius": 4}
        ]
        # Wall-mounted lights are valid; this mask can be painted independently.
        doc["blocks_sight"] = [[False] * original.width for _ in range(original.height)]
        state.level.definition = MapDocument.model_validate(doc)
        self.assertEqual(self.engine.lighting.at(Position(5, 3)), 1)
        doc["blocks_sight"][3][4] = True
        state.level.definition = MapDocument.model_validate(doc)
        self.assertEqual(self.engine.lighting.at(Position(5, 3)), 0)
        self.assertTrue(state.dungeon.walkable(Position(4, 3)))
        doc["blocks_sight"][3][4] = False
        state.level.definition = MapDocument.model_validate(doc)
        for ambient, expected in (("dim", 1), ("bright", 2)):
            state.level.definition = state.level.definition.model_copy(
                update={"ambient_light": ambient, "lights": []}
            )
            self.assertEqual(self.engine.lighting.at(Position(15, 3)), expected)
        self.assertEqual(original.ambient_light, "dark")
        self.assertEqual(original.lights, [])

    def test_inspection_and_magic_cannot_reveal_or_target_unseen_monsters(self):
        engine = self.factory.session("base:crypt", character_class="base:wizard")
        monster = engine.state.monsters[0]
        self.assertEqual(engine.lighting.at(monster.position), 0)
        self.assertNotIn(
            monster.monster.name, " ".join(engine.inspect_cell(monster.position))
        )
        result = engine.cast_spell("magic_missile", SpellSource.CLASS, monster.monster)
        self.assertFalse(result.performed)
        self.assertEqual((engine.state.turns, engine.state.hero.spell_slots[1]), (0, 2))
        self.assertEqual(
            engine.render_cells()[monster.position.y][monster.position.x].char, " "
        )


class RoofTests(LightingFixture):
    def covered_room(self, ambient="bright", lights=(), wall=False):
        doc = MapDocument(
            id="crypt",
            name="Дом в деревне",
            width=12,
            height=8,
            spawn={"x": 2, "y": 3},
            ambient_light=ambient,
            tiles=[["base:floor"] * 12 for _ in range(8)],
            walkability=[[True] * 12 for _ in range(8)],
            blocks_sight=[[wall and x == 4 for x in range(12)] for _ in range(8)],
            roof=[[x < 8 for x in range(12)] for _ in range(8)],
            lights=list(lights),
        )
        self.store.documents[("maps", "base:crypt")] = doc
        self.factory = SessionFactory(self.store)
        return self.factory.session("base:crypt", seed=42)

    def test_roof_removes_only_ambient_light_and_preserves_floor_and_movement(self):
        for ambient, strength in (("dim", 1), ("bright", 2)):
            engine = self.covered_room(ambient)
            self.assertEqual(engine.lighting.level_at(Position(5, 3)), 0)
            self.assertEqual(engine.lighting.level_at(engine.state.position), 0)
            self.assertEqual(engine.lighting.level_at(Position(8, 3)), strength)
            self.assertEqual(engine.lighting.at(Position(5, 3)), 0)
            self.assertEqual(engine.state.level.definition.tiles[3][5], "base:floor")
            self.assertTrue(engine.state.dungeon.walkable(Position(5, 3)))
            self.assertTrue(engine.apply(Action.EAST).performed)

    def test_static_and_carried_light_work_under_roof_on_bright_map(self):
        source = {"id": "lantern", "x": 1, "y": 3, "radius": 6, "bright_radius": 2}
        engine = self.covered_room(lights=[source])
        self.assertEqual(engine.lighting.level_at(Position(3, 3)), 2)
        self.assertEqual(engine.lighting.level_at(Position(5, 3)), 1)
        engine = self.covered_room()
        hero = engine.state.hero
        hero.unequip(next(i for i in hero.inventory if i.id == "shield"))
        torch = next(i for i in hero.inventory if i.id == "torch")
        self.assertTrue(engine.manage_equipment(torch, True).performed)
        self.assertEqual(engine.lighting.level_at(engine.state.position), 2)
        self.assertEqual(torch.fuel_minutes, 59)
        engine.manage_equipment(torch, False)
        self.assertEqual(engine.lighting.level_at(engine.state.position), 0)

    def test_roof_keeps_wall_sides_dark_and_light_cannot_cross_wall(self):
        engine = self.covered_room(
            wall=True,
            lights=[{"id": "lantern", "x": 1, "y": 3, "radius": 8, "bright_radius": 4}],
        )
        self.assertEqual(engine.lighting.level_at(Position(4, 3)), 2)
        self.assertEqual(engine.lighting.level_at(Position(5, 3)), 0)
        engine.state.position = Position(6, 3)
        self.assertEqual(engine.lighting.level_at(Position(4, 3)), 0)

    def test_roof_roundtrips_in_save_and_invalid_dimensions_are_rejected(self):
        engine = self.covered_room()
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(engine)
            restored = repo.load(self.factory.catalog, self.store)
            self.assertEqual(
                restored.state.level.definition.roof, engine.state.level.definition.roof
            )
            self.assertEqual(restored.lighting.level_at(Position(5, 3)), 0)
            self.assertEqual(restored.lighting.level_at(Position(8, 3)), 2)
        raw = engine.state.level.definition.model_dump(mode="json")
        raw["roof"] = [[True]]
        with self.assertRaises(ValidationError):
            MapDocument.model_validate(raw)
        raw.pop("roof")
        old = MapDocument.model_validate(raw)
        self.assertEqual(old.roof, [[False] * 12 for _ in range(8)])
        with self.assertRaises(TypeError):
            old.roof[0][0] = True


class LightingPersistenceTests(LightingFixture):
    def test_torches_disappear_on_ground_on_other_levels_and_after_loading_old_save(
        self,
    ):
        self.free_hand()
        torch = self.item("torch")
        self.engine.manage_equipment(torch, True)
        self.engine.place_item(torch, self.engine.state.position)
        current = self.engine.state
        other = self.factory.state("base:dungeon", self.hero)
        self.engine.levels[other.level.ref] = other
        self.engine.state = other
        self.engine.apply(Action.SHORT_REST)
        self.assertFalse(any(i is torch for _, i in current.items))
        self.assertFalse(torch.equipped or torch.lit)
        self.assertTrue(any(i.id == "lamp" for i in self.hero.inventory))
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            # Reproduce a save from the previous implementation with a spent torch.
            expired = Equipment.create(torch.definition)
            expired.fuel_minutes = 0
            self.hero.inventory.append(expired)
            repo.save(self.engine)
            restored = repo.load(self.factory.catalog, self.store)
            self.assertFalse(any(i.consumed for i in restored.state.hero.inventory))
            self.assertFalse(
                any(
                    i.consumed
                    for state in restored.levels.values()
                    for _, i in state.items
                )
            )

    def test_last_minute_torch_equipping_returns_to_inventory_and_frees_hand(self):
        controller = Controller(
            42,
            catalog=self.factory.catalog,
            map_ref="base:crypt",
            store=self.store,
            test_map=True,
        )
        hero = controller.engine.state.hero
        hero.unequip(next(i for i in hero.inventory if i.id == "shield"))
        torch = next(i for i in hero.inventory if i.id == "torch")
        torch.fuel_minutes = 1
        controller.open_item(torch)
        controller.handle("1")
        self.assertIsNone(controller.selected_item)
        self.assertFalse(any(i is torch for i in hero.inventory))
        self.assertEqual(hero.hands_used, 1)
        self.assertIn("Сгорел", controller.message)
        render(controller, 80, 24)

    def test_save_keeps_fuel_in_inventory_and_on_ground_and_old_items_load(self):
        self.free_hand()
        torch, lamp = self.item("torch"), self.item("lamp")
        self.engine.manage_equipment(torch, True)
        self.engine.place_item(torch, self.engine.state.position)
        self.engine.manage_equipment(lamp, True)
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.engine)
            restored = repo.load(self.factory.catalog, self.store)
            loaded_lamp = next(
                i for i in restored.state.hero.inventory if i.id == "lamp"
            )
            loaded_torch = next(i for _, i in restored.state.items if i.id == "torch")
            self.assertEqual((loaded_lamp.fuel_minutes, loaded_lamp.lit), (59, True))
            self.assertEqual(
                (loaded_torch.fuel_minutes, loaded_torch.lit),
                (torch.fuel_minutes, True),
            )
            self.assertEqual(restored.render_cells(), self.engine.render_cells())
            lay_bedroll(restored)
            restored.apply(Action.REST)
            self.assertFalse(loaded_lamp.lit or loaded_torch.lit)
            self.assertTrue(lamp.lit and torch.lit)
            # Saves produced before lighting had neither these fields nor map defaults.
            data = json.loads(repo.path.read_text())
            for level in data["levels"]:
                level["definition"].pop("roof", None)
            for item in data["hero"]["inventory"]:
                item.pop("lit")
                item.pop("fuel_minutes")
            repo.path.write_text(json.dumps(data))
            restored = repo.load(self.factory.catalog, self.store)
            self.assertFalse(any(i.lit for i in restored.state.hero.inventory))

    def test_invalid_saved_fuel_and_hand_occupancy_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.engine)
            original = json.loads(repo.path.read_text())
            for mutation in ("fuel", "hands"):
                data = json.loads(json.dumps(original))
                torch = next(
                    i for i in data["hero"]["inventory"] if i["definition"] == "torch"
                )
                if mutation == "fuel":
                    torch["fuel_minutes"] = 61
                else:
                    torch["equipped"] = True
                repo.path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    repo.load(self.factory.catalog, self.store)

    def test_tui_item_controls_and_menus_do_not_burn_fuel(self):
        controller = Controller(
            42,
            catalog=self.factory.catalog,
            map_ref="base:crypt",
            store=self.store,
            test_map=True,
        )
        hero = controller.engine.state.hero
        shield, lamp = (
            next(i for i in hero.inventory if i.id == key) for key in ("shield", "lamp")
        )
        controller.open_item(shield)
        controller.handle("1")
        controller.handle("backspace")
        controller.open_item(lamp)
        controller.handle("1")
        self.assertEqual(lamp.fuel_minutes, 59)
        controller.handle("2")
        controller.handle("pagedown")
        controller.handle("backspace")
        controller.handle("backspace")
        controller.handle("2")
        controller.handle("right")
        controller.handle("backspace")
        self.assertEqual((lamp.fuel_minutes, controller.engine.state.turns), (59, 2))
        text = "\n".join(render(controller, 80, 24))
        self.assertIn("Свет: 59м", text)
        self.assertIn("Руки заняты: 2/2", text)
        self.assertIn("59/60", " ".join(item_details(lamp)))

    def test_monochrome_terminal_uses_dim_attribute_and_cannot_repaint_hidden_cells(
        self,
    ):
        controller = Controller(
            42,
            catalog=self.factory.catalog,
            map_ref="base:crypt",
            store=self.store,
            test_map=True,
        )
        curses = SimpleNamespace(A_DIM=8, error=RuntimeError)
        colors = SimpleNamespace(curses=curses, attribute=lambda fg, bg: 0)
        screen = Mock()
        draw_colors(screen, controller, 80, 24, colors)
        self.assertTrue(
            any(call.args[-1] == curses.A_DIM for call in screen.addstr.call_args_list)
        )
        rect = Layout.for_size(80, 24).main
        hidden = screen.addstr.call_args_list[0]
        self.assertEqual(hidden.args[:2], (rect.y + 1, rect.x + 1))
        self.assertEqual(hidden.args[2], " ")

    def test_json_schemas_and_legacy_catalog_validate_light_contract(self):
        self.assertEqual(
            ContentCatalog.load(DEFAULT_ROOT).equipment["lamp"].light.fuel_tag,
            "lamp_oil",
        )
        doc = self.store.get("equipment", "base:torch").model_dump()
        for change in (
            {"hands": 0},
            {"light": {"radius": 3, "bright_radius": 4}},
            {"light": {"burn_minutes": 0}},
        ):
            with self.assertRaises(ValidationError):
                EquipmentDocument.model_validate({**doc, **change})
        self.assertIn("light", EquipmentDocument.model_json_schema()["properties"])
        self.assertIn("lights", MapDocument.model_json_schema()["properties"])


if __name__ == "__main__":
    unittest.main()
