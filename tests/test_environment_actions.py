"""Sleeping places, closed storage, finite water and paid environment work."""

from copy import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository, actor_record, restore_actor
from tuidungeon.content.packs import PackStore
from tuidungeon.content.migrations import migrate_map
from tuidungeon.content.schemas import MapDocument
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.storage import item_stacks
from tuidungeon.world.maps import Position
from tuidungeon.presentation.tui import (
    Controller,
    View,
    popup_content,
    popup_layout,
    handle_click,
    render,
)


class EnvironmentActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PackStore()

    def setUp(self):
        self.store = copy(self.source)
        self.store.documents = dict(self.source.documents)
        self.raw = dict(
            id="actions_lab",
            name="Действия окружения",
            width=18,
            height=10,
            tiles=[["base:floor"] * 18 for _ in range(10)],
            walkability=[[True] * 18 for _ in range(10)],
            blocks_sight=[[False] * 18 for _ in range(10)],
            ambient_light="bright",
            spawn=dict(x=2, y=2),
            objects=[
                dict(id="bed", ref="base:bed", x=3, y=2),
                dict(id="puddle", ref="base:puddle", x=11, y=2),
                dict(id="rubble", ref="base:rubble_large", x=3, y=6),
                dict(id="barricade", ref="base:barricade", x=7, y=6),
                dict(id="torch", ref="base:torch_wall", x=11, y=6),
                dict(id="lamp", ref="base:lantern", x=15, y=6),
                dict(id="candle", ref="base:candle", x=11, y=8),
            ],
            points_of_interest=[
                dict(
                    id="crate",
                    ref="base:terrain_crate_closed",
                    x=7,
                    y=2,
                    overrides={
                        "storage": {
                            "contents": [{"item": "base:bandage", "quantity": 2}]
                        }
                    },
                )
            ],
        )
        self.start()

    def start(self):
        self.store.documents["maps", "dev:actions_lab"] = MapDocument.model_validate(
            self.raw
        )
        self.e = SessionFactory(self.store).session("dev:actions_lab", seed=42)
        self.e.state.hero.inventory.clear()

    def add(self, ref):
        item = Equipment.create(self.e.catalog.equipment[ref])
        self.e.state.hero.inventory.append(item)
        return item

    def near(self, identifier):
        obj = self.e.world_object(identifier)
        self.e.state.position = Position(obj.placement.x - 1, obj.placement.y)
        return obj

    def reload(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = SaveRepository(Path(directory) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def finish(self):
        while self.e.active_craft:
            self.assertTrue(self.e.advance_craft().performed)

    def illumination(self, value):
        self.e.state.level.definition = self.e.state.level.definition.model_copy(
            update={"ambient_light": value, "lights": []}
        )
        self.store.documents["maps", "dev:actions_lab"] = self.store.get(
            "maps", "dev:actions_lab"
        ).model_copy(update={"ambient_light": value, "lights": []})
        self.e.state.level.authored_definition = self.store.get(
            "maps", "dev:actions_lab"
        )

    def test_dark_crate_can_be_found_opened_and_looted_without_false_feedback(self):
        self.near("crate")
        self.illumination("dark")
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        self.assertIn("crate", [p.placement.id for p in self.e.nearby_points()])
        result = self.e.open_container("crate")
        self.assertFalse(result.performed)
        self.assertIn("монтировка", result.message)
        self.add("crowbar")
        self.assertTrue(self.e.open_container("crate").performed)
        self.reload()
        c = self.e.storage_at("crate")
        self.assertIsNotNone(c)
        self.assertTrue(
            self.e.transfer_storage("crate", c.items[0].instance_id, 2).performed
        )
        self.assertEqual(c.items, [])
        self.assertFalse(any(e["kind"] == "light_denied" for e in self.e.events))

    def test_dark_destruction_salvages_less_than_bright_dismantling_preserves_loot(
        self,
    ):
        self.near("crate")
        self.illumination("dark")
        crate = self.e.world_object("crate")
        p = Position(crate.placement.x, crate.placement.y)
        original_ids = {
            i.instance_id
            for container in self.e.state.level.containers
            if container.placement.id == "crate"
            for i in container.items
        }
        self.assertTrue(self.e.interact("crate", "break_object").performed)
        self.assertEqual(self.e.state.turns, 1)
        self.e.damage_world_objects(p, 999, "bludgeoning")
        broken = [i for q, i in self.e.state.items if (q.x, q.y) == (p.x, p.y)]
        broken_wood = sum(i.id == "wood" for i in broken)
        self.assertEqual(broken_wood, 1)
        self.assertTrue(original_ids.issubset({i.instance_id for i in broken}))
        self.assertEqual(self.e.state.level.definition.tiles[p.y][p.x], "base:floor")
        self.reload()
        self.assertIsNone(self.e.world_object("crate"))
        self.assertFalse(self.e.interact("crate", "break_object").performed)
        self.assertEqual(self.e.damage_world_objects(p, 999, "bludgeoning"), 0)
        self.start()
        self.near("crate")
        self.assertTrue(self.e.start_dismantle("crate").performed)
        self.finish()
        self.assertEqual(
            sum(
                i.id == "wood"
                for q, i in self.e.state.items
                if (q.x, q.y) == (p.x, p.y)
            ),
            3,
        )

    def test_furniture_needs_bright_light_and_work_pauses_without_losing_progress(self):
        target = self.near("bed")
        for ambient in ("dark", "dim"):
            self.illumination(ambient)
            result = self.e.start_dismantle("bed")
            self.assertFalse(result.performed)
            self.assertEqual(self.e.events[-1]["kind"], "light_denied")
            self.assertEqual(
                (target.state.progress, target.state.total, self.e.state.turns),
                (0, 0, 0),
            )
        self.illumination("bright")
        self.assertTrue(self.e.start_dismantle("bed").performed)
        self.assertTrue(self.e.advance_craft().performed)
        self.illumination("dim")
        self.assertFalse(self.e.advance_craft().performed)
        self.assertIsNone(self.e.active_craft)
        self.assertEqual((target.state.progress, self.e.state.turns), (1, 1))
        self.reload()
        self.illumination("bright")
        self.assertTrue(self.e.start_dismantle("bed").performed)
        self.finish()
        self.assertIsNone(self.e.world_object("bed"))

    def test_light_feedback_is_modal_in_both_layouts_and_restores_underlying_view(self):
        self.near("bed")
        self.illumination("dark")
        c = Controller(
            42,
            store=self.store,
            catalog=self.e.catalog,
            map_ref="dev:actions_lab",
            test_map=True,
        )
        c.engine, c.view = self.e, View.EXPLORE
        c.open_interaction()
        target = self.e.world_object("bed")
        choices = target.available_choices(self.e.state.hero)
        c.handle(
            str(
                next(
                    i + 1
                    for i, choice in enumerate(choices)
                    if choice.id == "dismantle"
                )
            )
        )
        self.assertIn("кромешной тьме", c.feedback)
        self.assertIn("кромешной тьме", " ".join(popup_content(c)[1]))
        turns = self.e.state.turns
        c.handle("right")
        self.assertEqual(self.e.state.turns, turns)
        for size in ((80, 24), (160, 50)):
            self.assertIn("Недостаточно света", "\n".join(render(c, *size)))
        c.handle("enter")
        self.assertIsNone(c.feedback)
        c.view = View.CRAFT
        c.message = self.e.start_craft("base:craft_torch").message
        self.assertIsNotNone(c.feedback)
        title, rect, _, hits = popup_layout(c, 80, 24)
        self.assertEqual(title, "Недостаточно света")
        self.assertTrue(handle_click(c, rect.x + 3, rect.y + hits[0][1] + 1, 80, 24))
        self.assertIsNone(c.feedback)
        self.assertEqual(c.view, View.CRAFT)

    def test_furniture_work_pauses_on_the_turn_its_torch_burns_out(self):
        target = self.near("bed")
        self.illumination("dark")
        torch = self.add("torch")
        torch.equipped = torch.lit = True
        torch.fuel_minutes = 1
        self.assertTrue(self.e.start_dismantle("bed").performed)
        self.assertTrue(self.e.advance_craft().performed)
        self.assertEqual(
            (target.state.progress, self.e.state.turns, torch.fuel_minutes), (1, 1, 0)
        )
        self.assertIsNone(self.e.active_craft)
        self.assertTrue(any(e["kind"] == "light_denied" for e in self.e.events))
        self.assertIsNotNone(self.e.world_object("bed"))

    def test_interactions_have_eight_green_directions_and_do_not_reach_through_corners(
        self,
    ):
        import tcod
        from tuidungeon.presentation.window import draw, PALETTE

        self.raw["objects"] = [dict(id="chair", ref="base:chair", x=4, y=4)]
        self.raw["points_of_interest"] = []
        self.start()
        c = Controller(
            42,
            store=self.store,
            catalog=self.e.catalog,
            map_ref="dev:actions_lab",
            test_map=True,
        )
        c.engine = self.e
        for dx, dy, arrow in (
            (-1, -1, "↖"),
            (0, -1, "↑"),
            (1, -1, "↗"),
            (-1, 0, "←"),
            (1, 0, "→"),
            (-1, 1, "↙"),
            (0, 1, "↓"),
            (1, 1, "↘"),
        ):
            self.e.state.position = Position(4 - dx, 4 - dy)
            c.open_interaction()
            c.point_id = None
            self.assertEqual(popup_content(c)[2], [f"[{arrow}] Стул"])
            console = tcod.console.Console(80, 24)
            draw(console, c)
            rect = popup_layout(c, 80, 24)[1]
            ys, xs = (
                console.ch[rect.y : rect.y + rect.height, rect.x : rect.x + rect.width]
                == ord(arrow)
            ).nonzero()
            positions = [
                (rect.y + y, rect.x + x)
                for y, x in zip(ys, xs)
                if console.ch[rect.y + y, rect.x + x - 1] == ord("[")
            ]
            self.assertEqual(len(positions), 1)
            self.assertEqual(tuple(console.fg[positions[0]]), PALETTE[10])
        self.e.state.position = Position(3, 3)
        blocked = [list(row) for row in self.e.state.level.definition.walkability]
        blocked[3][4] = False
        self.e.state.level.definition = self.e.state.level.definition.model_copy(
            update={"walkability": blocked}
        )
        self.assertNotIn("chair", [p.placement.id for p in self.e.nearby_points()])

    def test_long_rest_requires_deployed_sleeping_place_and_denial_changes_nothing(
        self,
    ):
        self.e.state.position = Position(1, 8)
        hero = self.e.state.hero
        hero.hp = 1
        bedroll = self.add("bedroll")
        self.assertFalse(self.e.apply(Action.REST).performed)
        self.assertEqual(
            (hero.hp, self.e.state.turns, self.e.state.clock.elapsed_minutes),
            (1, 0, 480),
        )
        self.assertTrue(self.e.place_item(bedroll, self.e.state.position).performed)
        self.assertTrue(self.e.apply(Action.REST).performed)
        self.assertEqual(hero.hp, hero.max_hp)
        self.near("bed")
        self.assertTrue(self.e.can_long_rest())
        self.e.damage_world_objects(Position(3, 2), 100, "bludgeoning")
        self.assertFalse(self.e.can_long_rest())
        self.assertTrue(self.e.apply(Action.SHORT_REST).performed)

    def test_closed_crate_requires_crowbar_and_opening_survives_loading(self):
        self.near("crate")
        self.assertFalse(self.e.open_container("crate").performed)
        self.assertIsNone(self.e.storage_at("crate"))
        self.assertFalse(self.e.interact("crate", "examine").performed)
        self.assertNotIn(
            "examine",
            [
                c.id
                for c in self.e.world_object("crate").available_choices(
                    self.e.state.hero
                )
            ],
        )
        bar = self.add("crowbar")
        self.assertTrue(self.e.open_container("crate").performed)
        self.assertIsNone(bar.durability)
        self.e.state.hero.inventory.remove(bar)
        self.reload()
        container = self.e.storage_at("crate")
        self.assertIsNotNone(container)
        self.assertTrue(
            self.e.transfer_storage(
                "crate", container.items[0].instance_id, 2
            ).performed
        )
        self.assertEqual(container.items, [])

    def test_search_rewards_require_explicit_property(self):
        self.raw["points_of_interest"][0]["overrides"]["storage"].update(
            search_contents=True, open_tool=None
        )
        self.start()
        self.near("crate")
        self.assertIn(
            "examine",
            [
                c.id
                for c in self.e.world_object("crate").available_choices(
                    self.e.state.hero
                )
            ],
        )
        self.assertTrue(self.e.interact("crate", "examine").performed)
        self.assertFalse(self.e.interact("crate", "examine").performed)

    def test_puddle_has_finite_saved_portions_and_preserves_floor(self):
        self.near("puddle")
        flask = self.add("water_flask")
        flask.liquid_kind = None
        flask.liquid_portions = 0
        self.assertTrue(
            self.e.water_action(flask.instance_id, "fill", target="puddle").performed
        )
        self.assertEqual((flask.liquid_kind, flask.liquid_portions), ("dirty_water", 1))
        self.assertEqual(self.e.world_object("puddle").state.water_portions, 1)
        self.reload()
        bag = self.add("waterskin")
        bag.liquid_kind = None
        bag.liquid_portions = 0
        self.assertTrue(
            self.e.water_action(bag.instance_id, "fill", target="puddle").performed
        )
        self.assertEqual(bag.liquid_portions, 1)
        self.assertIsNone(self.e.world_object("puddle"))
        self.assertEqual(self.e.state.level.definition.tiles[2][11], "base:floor")
        self.reload()
        self.assertIsNone(self.e.world_object("puddle"))

    def test_rubble_thirty_turns_by_hand_or_ten_without_pickaxe_wear(self):
        target = self.near("rubble")
        self.assertTrue(self.e.start_dismantle("rubble").performed)
        self.assertEqual(target.state.total, 30)
        self.finish()
        self.assertEqual(self.e.state.turns, 30)
        self.assertTrue(self.e.state.walkable(Position(3, 6)))
        self.start()
        target = self.near("rubble")
        pick = self.add("pickaxe")
        self.e.start_dismantle("rubble")
        self.assertEqual(target.state.total, 10)
        self.e.advance_craft()
        self.e.pause_craft()
        self.assertIsNone(pick.durability)
        self.reload()
        pick = next(i for i in self.e.state.hero.inventory if i.id == "pickaxe")
        self.e.start_dismantle("rubble")
        with patch.object(self.e.dice, "roll", return_value=(4,)) as dice:
            self.finish()
        dice.assert_not_called()
        self.assertEqual((self.e.state.turns, pick.durability), (10, None))
        self.assertEqual(self.e.state.level.definition.tiles[6][3], "base:floor")

    def test_removing_barricade_does_not_wear_crowbar(self):
        self.near("barricade")
        bar = self.add("crowbar")
        self.e.start_dismantle("barricade")
        self.finish()
        self.assertEqual((self.e.state.turns, bar.durability), (1, None))
        self.assertIsNone(self.e.world_object("barricade"))
        self.assertTrue(self.e.state.walkable(Position(7, 6)))

    def test_torch_holder_keeps_identity_fuel_and_empty_state(self):
        self.near("torch")
        container = next(
            c for c in self.e.state.level.containers if c.placement.id == "torch"
        )
        item = container.items[0]
        identity = item.instance_id
        self.assertTrue(self.e.interact("torch", "take_light").performed)
        self.assertIs(item, self.e.state.hero.inventory[-1])
        self.assertFalse(item.lit or item.equipped)
        self.assertEqual(item.fuel_minutes, 60)
        self.assertEqual(container.items, [])
        self.assertTrue(self.e.interact("torch", "mount_light").performed)
        self.assertEqual(container.items[0].fuel_minutes, 59)
        self.reload()
        container = next(
            c for c in self.e.state.level.containers if c.placement.id == "torch"
        )
        self.assertEqual(
            (container.items[0].instance_id, container.items[0].fuel_minutes),
            (identity, 59),
        )
        self.e.apply(Action.SHORT_REST)
        self.assertEqual(container.items, [])
        self.assertIsNotNone(self.e.world_object("torch"))
        self.reload()
        self.assertEqual(
            next(
                c for c in self.e.state.level.containers if c.placement.id == "torch"
            ).items,
            [],
        )

    def test_floor_lamp_can_be_picked_up_dropped_and_picked_up_again(self):
        obj = self.near("lamp")
        position = Position(obj.placement.x, obj.placement.y)
        self.assertEqual(
            self.e.render_cells((position.x, position.y, 1, 1))[0][0].char, "○"
        )
        self.assertTrue(self.e.interact("lamp", "take_light").performed)
        item = self.e.state.hero.inventory[-1]
        self.assertEqual((item.id, item.fuel_minutes), ("lamp", 60))
        self.assertIsNone(self.e.world_object("lamp"))
        self.assertTrue(self.e.manage_equipment(item, True).performed)
        self.assertTrue(item.shining)
        dropped = self.e.state.position
        self.assertTrue(self.e.place_item(item, self.e.state.position).performed)
        self.e.state.position = position
        self.assertEqual(
            self.e.render_cells((dropped.x, dropped.y, 1, 1))[0][0].char, "○"
        )
        self.reload()
        self.assertEqual(
            self.e.render_cells((dropped.x, dropped.y, 1, 1))[0][0].char, "○"
        )
        item = self.e.state.items[-1][1]
        self.e.state.position = dropped
        self.assertTrue(self.e.pickup_item().performed)
        self.assertIs(item, self.e.state.hero.inventory[-1])
        self.reload()
        self.assertIsNone(self.e.world_object("lamp"))

    def test_legacy_fixture_has_no_permanent_light_after_pickup(self):
        self.raw["ambient_light"] = "dark"
        self.raw["objects"] = [dict(id="torch", ref="base:torch_wall", x=3, y=2)]
        light = dict(x=3, y=2, radius=6, bright_radius=3, enabled=True)
        self.raw["lights"] = [dict(light, id="tile_lights_3_2")]
        migrated = migrate_map(self.raw)
        self.assertEqual(migrated["lights"], [])
        self.assertEqual(migrate_map(migrated), migrated)
        self.assertEqual(len(self.raw["lights"]), 1)
        self.raw = migrated
        self.start()
        self.assertGreater(self.e.lighting.level_at(self.e.state.position), 0)
        self.assertTrue(self.e.interact("torch", "take_light").performed)
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        self.reload()
        self.assertEqual(self.e.lighting.level_at(self.e.state.position), 0)
        self.raw["lights"] = [dict(light, id="authored_light")]
        self.assertEqual(len(migrate_map(self.raw)["lights"]), 1)

    def test_candle_pickup_preserves_fuel_and_survives_save(self):
        self.near("candle")
        self.e.apply(Action.WAIT)
        container = next(
            c for c in self.e.state.level.containers if c.placement.id == "candle"
        )
        item = container.items[0]
        remaining, identity = item.fuel_minutes, item.instance_id
        self.assertTrue(self.e.interact("candle", "take_light").performed)
        self.assertIsNone(self.e.world_object("candle"))
        self.assertIs(item, self.e.state.hero.inventory[-1])
        self.assertEqual(item.fuel_minutes, remaining)
        self.assertFalse(item.lit)
        self.reload()
        candle = next(i for i in self.e.state.hero.inventory if i.id == "candle")
        self.assertEqual(
            (candle.instance_id, candle.fuel_minutes), (identity, remaining)
        )

    def test_burned_candle_disappears_without_removing_floor(self):
        self.e.apply(Action.SHORT_REST)
        self.assertIsNone(self.e.world_object("candle"))
        self.assertEqual(self.e.state.level.definition.tiles[8][11], "base:floor")
        self.reload()
        self.assertIsNone(self.e.world_object("candle"))

    def test_gold_is_a_stack_with_weight_transfer_throw_and_save(self):
        hero = self.e.state.hero
        hero.gold = 50
        stack = item_stacks(hero.inventory)[0]
        self.assertEqual(
            (stack.quantity, stack.first.id, stack.weight), (50, "gold", 0.5)
        )
        self.assertEqual(hero.carried_weight, 0.5)
        self.raw["points_of_interest"][0]["overrides"]["storage"].update(personal=True)
        self.start()
        hero = self.e.state.hero
        hero.gold = 50
        self.near("crate")
        self.add("crowbar")
        self.e.open_container("crate")
        coin = next(i for i in hero.inventory if i.id == "gold")
        self.assertTrue(
            self.e.transfer_storage(
                "crate", coin.instance_id, 20, deposit=True
            ).performed
        )
        self.assertEqual(hero.gold, 30)
        self.reload()
        hero = self.e.state.hero
        container = self.e.storage_at("crate")
        coin = next(i for i in container.items if i.id == "gold")
        self.assertTrue(
            self.e.transfer_storage("crate", coin.instance_id, 20).performed
        )
        self.assertEqual(hero.gold, 50)
        coin = next(i for i in hero.inventory if i.id == "gold")
        target = Position(6, 3)
        self.assertTrue(self.e.place_item(coin, target, throwing=True).performed)
        self.assertEqual(hero.gold, 49)
        self.e.state.position = target
        self.assertTrue(self.e.pickup_item().performed)
        self.assertEqual(hero.gold, 50)
        self.reload()
        self.assertEqual(self.e.state.hero.gold, 50)
        self.assertEqual(actor_record(self.e.state.hero).gold, 0)

    def test_legacy_gold_counter_becomes_coins_once(self):
        hero = self.e.state.hero
        record = actor_record(hero).model_copy(update={"gold": 50})
        restore_actor(hero, record, self.e.catalog)
        self.assertEqual((hero.gold, hero.carried_weight), (50, 0.5))
        self.reload()
        self.assertEqual(self.e.state.hero.gold, 50)

    def test_gold_can_be_reserved_cancelled_and_consumed_by_a_real_recipe(self):
        self.e = SessionFactory(self.store).session(
            "dev:actions_lab", character_class="dev:roadmap_tester", seed=42
        )
        hero = self.e.state.hero
        hero.inventory.clear()
        hero.gold = 10
        self.add("jeweler_tools")
        self.add("alchemy_reagent")
        self.assertTrue(self.e.start_craft("base:craft_focus", variant=1).performed)
        self.assertEqual(hero.gold, 0)
        work = self.e.active_craft
        self.e.pause_craft()
        self.assertTrue(self.e.cancel_craft(work).performed)
        self.assertEqual(hero.gold, 10)
        self.assertTrue(self.e.start_craft("base:craft_focus", variant=1).performed)
        self.finish()
        self.assertEqual(hero.gold, 0)
        self.assertEqual(sum(i.id == "arcane_focus" for i in hero.inventory), 1)


if __name__ == "__main__":
    unittest.main()
