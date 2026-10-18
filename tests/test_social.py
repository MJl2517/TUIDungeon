"""Acceptance routes for stationary NPCs, finite trade and staged quests."""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from tuidungeon.application.factories import SessionFactory
from tuidungeon.application.saves import SaveRepository
from tuidungeon.content.packs import PackStore, ContentError
from tuidungeon.content.compiler import ContentSnapshot
from tuidungeon.content.schemas import QuestObjective
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.rules import CheckResult, Ability
from tuidungeon.world.maps import Position
from tuidungeon.presentation.tui import Controller, View, render, handle_click
from tuidungeon.presentation.social import social_layout


class SocialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PackStore()
        cls.factory = SessionFactory(cls.store)

    def setUp(self):
        self.e = self.factory.session(
            "dev:npc_lab", character_class="dev:empty_tester", seed=42
        )

    def give(self, ref, count=1):
        items = [
            Equipment.create(self.e.catalog.equipment[ref.removeprefix("base:")])
            for _ in range(count)
        ]
        self.e.state.hero.inventory.extend(items)
        return items[0]

    def near(self, identifier):
        n = self.e.npc_at(identifier)
        self.e.state.position = Position(n.placement.x, n.placement.y + 1)
        self.assertTrue(self.e.open_dialogue(identifier).performed)
        return n

    def reload(self):
        with tempfile.TemporaryDirectory() as path:
            repo = SaveRepository(Path(path) / "save.json")
            repo.save(self.e)
            self.e = repo.load(store=self.store)

    def test_dark_conversation_obstacles_and_occupancy(self):
        e = self.e
        level = e.state.level
        level.definition = level.definition.model_copy(update={"ambient_light": "dark"})
        self.assertEqual(e.lighting.level_at(e.state.position), 0)
        self.assertTrue(e.open_dialogue("speaker").performed)
        self.assertFalse(e.state.walkable(Position(4, 3)))
        self.assertFalse(e._world_destination(Position(4, 3)))
        self.assertIsNone(e.world_object("speaker"))
        self.assertIn("speaker", [n.placement.id for n in e.nearby_points()])
        self.near("merchant")
        wood = next(i for i in e.npc_at("merchant").items if i.id == "wood")
        self.give("base:gold", 100)
        turns = e.state.turns
        self.assertFalse(e.trade("merchant", wood.instance_id).performed)
        self.assertEqual(e.state.turns, turns)
        e.state.position = Position(5, 4)
        masks = [list(r) for r in level.definition.walkability]
        masks[3][5] = False
        level.definition = level.definition.model_copy(update={"walkability": masks})
        self.assertFalse(e.open_dialogue("speaker").performed)

    def test_bargain_exactly_1440_minutes_and_saved_independently(self):
        e = self.e
        with patch.object(
            e.dice, "check", return_value=CheckResult(15, 2, 15)
        ) as check:
            n = self.near("merchant")
            first = n.bargain.copy()
            at = e.state.clock.elapsed_minutes
            e.state.clock.advance(1439)
            e.open_dialogue("merchant")
            self.assertEqual(n.bargain, first)
            self.assertEqual(check.call_count, 1)
            e.state.clock.advance(1)
            # A shop read never triggers a reroll, even after expiry.
            wood = next(i for i in n.items if i.id == "wood")
            e.trade_price(n, wood)
            self.assertEqual(check.call_count, 1)
            e.open_dialogue("merchant")
            self.assertEqual(check.call_count, 2)
            self.assertEqual(n.bargain["at"], at + 1440)
        self.reload()
        e = self.e
        with patch.object(e.dice, "check", return_value=CheckResult(1, 0, 15)) as check:
            e.open_dialogue("merchant")
            self.assertEqual(check.call_count, 0)
            self.near("furniture_buyer")
            self.assertEqual(check.call_count, 1)
            self.assertFalse(e.npc_at("furniture_buyer").bargain["success"])
            self.assertTrue(e.npc_at("merchant").bargain["success"])

    def test_bargain_uses_proficiency_and_expertise(self):
        e = self.e
        hero = e.state.hero
        hero.skill_proficiencies.add("persuasion")
        npc = self.near("merchant")
        expected = hero.stats.modifier(Ability.CHARISMA) + hero.proficiency_bonus
        self.assertEqual(npc.bargain["modifier"], expected)
        hero.expertise.add("persuasion")
        e.state.clock.advance(1440)
        e.open_dialogue("merchant")
        self.assertEqual(npc.bargain["modifier"], expected + hero.proficiency_bonus)

    def test_finite_trade_money_ids_rejections_and_rounding(self):
        e = self.e
        n = self.near("merchant")
        n.bargain.update(success=True, roll=20)
        self.give("base:gold", 100)
        wood = next(i for i in n.items if i.id == "wood")
        self.assertEqual(e.trade_price(n, wood), 6)
        self.assertEqual(e.trade_price(n, wood, selling=True), 3)
        coins_before = {
            i.instance_id for i in n.items + e.state.hero.inventory if i.id == "gold"
        }
        turns = e.state.turns
        self.assertTrue(e.trade("merchant", wood.instance_id, 2).performed)
        self.assertEqual(e.state.turns, turns + 1)
        self.assertIn(wood, e.state.hero.inventory)
        self.assertEqual(e.state.hero.gold, 88)
        self.assertTrue(
            e.trade("merchant", wood.instance_id, 2, selling=True).performed
        )
        self.assertEqual(e.state.hero.gold, 94)
        self.assertEqual(
            coins_before,
            {i.instance_id for i in n.items + e.state.hero.inventory if i.id == "gold"},
        )
        self.assertFalse(e.trade("merchant", wood.instance_id, 10000).performed)
        self.assertFalse(e.trade("merchant", wood.instance_id, True).performed)
        dagger = next(i for i in n.items if i.id == "dagger")
        dagger.durability = dagger.definition.durability // 2
        self.assertEqual(e.trade_price(n, dagger), 9)
        self.assertEqual(e.trade_price(n, dagger, selling=True), 5)
        n.bargain.update(success=False, roll=1)
        self.assertEqual(e.trade_price(n, dagger), 11)
        self.assertEqual(e.trade_price(n, dagger, selling=True), 4)
        self.reload()
        self.assertFalse(self.e.npc_at("merchant").bargain["success"])

    def test_furniture_sell_save_repurchase_and_place(self):
        e = self.e
        e.state.position = Position(2, 4)
        self.assertTrue(e.lift_furniture("chair").performed)
        chair = next(i for i in e.state.hero.inventory if i.furniture)
        chair.furniture.state.hp = 10
        identifier = chair.instance_id
        n = self.near("furniture_buyer")
        n.bargain.update(success=True, roll=20)
        self.assertEqual(e.trade_price(n, chair, selling=True), 11)
        self.assertTrue(e.trade("furniture_buyer", identifier, selling=True).performed)
        self.reload()
        e = self.e
        n = e.npc_at("furniture_buyer")
        sold = next(i for i in n.items if i.instance_id == identifier)
        self.assertEqual(sold.furniture.state.hp, 10)
        self.give("base:gold", 30)
        self.assertTrue(e.trade("furniture_buyer", identifier).performed)
        self.assertTrue(e.place_furniture(sold, Position(11, 4)).performed)
        self.assertEqual(e.world_object("chair").state.hp, 10)

    def test_dialogue_once_checks_conditions_and_recipe_rewards(self):
        e = self.e
        self.near("speaker")
        turns = e.state.turns
        with patch.object(
            e.dice, "check", return_value=CheckResult(20, 0, 15)
        ) as check:
            self.assertTrue(e.choose_dialogue("speaker", "topic:secret").performed)
            self.assertTrue(e.choose_dialogue("speaker", "topic:secret").performed)
            self.assertEqual(check.call_count, 1)
        self.assertEqual(e.state.hero.gold, 3)
        self.assertEqual(e.state.turns, turns + 1)
        self.assertTrue(e.choose_dialogue("speaker", "topic:lesson").performed)
        self.assertFalse(e.choose_dialogue("speaker", "topic:lesson").performed)
        self.reload()
        with patch.object(self.e.dice, "check") as check:
            self.e.choose_dialogue("speaker", "topic:secret")
            check.assert_not_called()
        self.near("quest_giver")
        self.assertNotIn(
            "topic:active", {c.id for c in self.e.dialogue_choices("quest_giver")}
        )
        self.e.choose_dialogue("quest_giver", "accept:dev:npc_trial")
        self.assertIn(
            "topic:active", {c.id for c in self.e.dialogue_choices("quest_giver")}
        )

    def test_quest_route_and_single_reward_after_reload(self):
        e = self.e
        # Events before accepting do not satisfy future stages.
        self.near("speaker")
        self.near("quest_giver")
        self.assertTrue(
            e.choose_dialogue("quest_giver", "accept:dev:npc_trial").performed
        )
        self.assertEqual(e.quests["dev:npc_trial"]["counts"], {})
        self.near("speaker")
        e.state.position = Position(3, 5)
        self.assertTrue(e.interact("instructions", "read_note").performed)
        self.assertEqual(e.quests["dev:npc_trial"]["stage"], 1)
        e.state.position = Position(5, 5)
        self.assertTrue(e.start_dismantle("flower").performed)
        self.assertEqual(e.quests["dev:npc_trial"]["stage"], 1)
        self.assertTrue(e.advance_craft().performed)
        self.assertEqual(e.quests["dev:npc_trial"]["stage"], 2)
        self.give("base:wood", 4)
        self.give("base:cloth")
        self.assertTrue(e.start_craft("base:craft_torch", 1).performed)
        e.advance_craft()
        self.assertEqual(e.quests["dev:npc_trial"]["counts"].get("torch", 0), 0)
        e.advance_craft()
        self.assertEqual(e.quests["dev:npc_trial"]["counts"]["torch"], 1)
        e.state.position = Position(3, 8)
        e.refresh_quests()
        self.assertEqual(e.quests["dev:npc_trial"]["stage"], 3)
        self.reload()
        e = self.e
        self.near("quest_giver")
        self.assertTrue(
            e.choose_dialogue("quest_giver", "report:dev:npc_trial").performed
        )
        self.assertEqual(e.quest_status("dev:npc_trial"), "completed")
        self.assertEqual(e.state.hero.gold, 25)
        self.assertIn("base:craft_bandage", e.state.hero.known_recipes)
        self.assertFalse(
            e.choose_dialogue("quest_giver", "report:dev:npc_trial").performed
        )
        self.reload()
        self.assertEqual(self.e.state.hero.gold, 25)

    def test_windows_keyboard_mouse_and_small_layout(self):
        c = Controller(
            seed=42,
            store=self.store,
            map_ref="dev:npc_lab",
            test_map=True,
            test_class="dev:empty_tester",
        )
        c.social.open(c, "speaker")
        self.assertIs(c.view, View.DIALOGUE)
        c.handle("enter")
        self.assertIn("торговец", c.social.answer)
        for size in ((80, 24), (140, 48)):
            rows = render(c, *size)
            self.assertEqual(len(rows), size[1])
            self.assertTrue(all(len(r) == size[0] for r in rows))
        _, rect, _, _ = social_layout(c, 100, 34)
        self.assertTrue(handle_click(c, rect.x + 3, rect.y + 2, 100, 34))
        c.handle("escape")
        c.handle("j")
        c.handle("1")
        self.assertIs(c.view, View.QUESTS)
        self.assertIn("Пока нет заданий", "\n".join(render(c, 100, 34)))

    def test_invalid_content_references_are_rejected(self):
        docs = dict(self.store.documents)
        quest = docs["quests", "dev:npc_trial"].model_copy(deep=True)
        quest = quest.model_copy(
            update={
                "stages": [
                    *quest.stages[:-1],
                    quest.stages[-1].model_copy(
                        update={
                            "report_to": quest.stages[-1].report_to.model_copy(
                                update={"npc_id": "missing"}
                            )
                        }
                    ),
                ]
            }
        )
        docs["quests", "dev:npc_trial"] = quest
        with self.assertRaises(ContentError):
            PackStore.validate_references(docs, self.store.manifests)

    def test_trade_failures_are_atomic_and_weight_counts_payment(self):
        e = self.e
        n = self.near("merchant")
        wood = next(i for i in n.items if i.id == "wood")
        before = [i.instance_id for i in n.items]
        turns = e.state.turns
        self.assertFalse(e.trade("merchant", wood.instance_id).performed)
        self.assertEqual(before, [i.instance_id for i in n.items])
        self.give("base:gold", 100)
        with patch.object(
            type(e.state.hero),
            "max_carry_weight",
            new_callable=lambda: property(lambda _: 0.001),
        ):
            self.assertFalse(e.trade("merchant", wood.instance_id).performed)
        self.assertEqual(e.state.hero.gold, 100)
        self.assertEqual(e.state.turns, turns)
        hero_wood = self.give("base:wood")
        n.items[:] = [i for i in n.items if i.id != "gold"]
        self.assertFalse(
            e.trade("merchant", hero_wood.instance_id, selling=True).performed
        )
        self.assertIn(hero_wood, e.state.hero.inventory)

    def test_quest_report_rechecks_items_and_defers_overweight_reward(self):
        e = self.e
        self.near("quest_giver")
        e.choose_dialogue("quest_giver", "accept:dev:npc_trial")
        progress = e.quests["dev:npc_trial"]
        progress.update(stage=3, counts={})
        self.assertFalse(
            e.choose_dialogue("quest_giver", "report:dev:npc_trial").performed
        )
        self.give("base:wood", 2)
        before = [i.instance_id for i in e.state.hero.inventory]
        with patch.object(
            type(e.state.hero),
            "max_carry_weight",
            new_callable=lambda: property(lambda _: 0.001),
        ):
            self.assertFalse(
                e.choose_dialogue("quest_giver", "report:dev:npc_trial").performed
            )
        self.assertEqual(before, [i.instance_id for i in e.state.hero.inventory])
        self.assertEqual(e.state.hero.gold, 0)
        self.assertEqual(progress["status"], "active")
        self.assertTrue(
            e.choose_dialogue("quest_giver", "report:dev:npc_trial").performed
        )
        self.assertIsNotNone(
            e.finish_quest_stage("dev:npc_trial", reporter="quest_giver")
        )
        self.assertEqual(e.state.hero.gold, 25)

    def test_old_save_without_new_state_loads(self):
        engine = self.factory.session(
            "dev:reading_room", character_class="dev:empty_tester"
        )
        with tempfile.TemporaryDirectory() as path:
            repo = SaveRepository(Path(path) / "old.json")
            repo.save(engine)
            raw = json.loads(repo.path.read_text(encoding="utf-8"))
            raw.pop("quests")
            for level in raw["levels"]:
                level.pop("npcs")
                if level["definition"]:
                    level["definition"].pop("npcs", None)
            repo.path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            restored = repo.load(store=self.store)
        self.assertEqual(restored.quests, {})
        self.assertEqual(restored.state.level.npcs, [])

    def test_shop_keyboard_quantity_and_confirmation(self):
        c = Controller(
            seed=42,
            store=self.store,
            map_ref="dev:npc_lab",
            test_map=True,
            test_class="dev:empty_tester",
        )
        c.engine.state.position = Position(8, 4)
        c.engine.state.hero.gold = 100
        c.social.open(c, "merchant")
        c.handle("enter")
        self.assertIs(c.view, View.TRADE)
        c.handle("enter")
        self.assertIsNotNone(c.social.pending)
        c.handle("right")
        self.assertEqual(c.social.quantity, 2)
        self.assertIn("Итого:", "\n".join(render(c, 100, 34)))
        c.handle("enter")
        self.assertIsNone(c.social.pending)
        self.assertEqual(sum(i.id == "wood" for i in c.engine.state.hero.inventory), 2)
        c.handle("escape")
        self.assertIs(c.view, View.DIALOGUE)

    def test_world_goals_count_only_completed_dismantling_and_destruction(self):
        for kind in ("dismantle", "break_object"):
            with self.subTest(kind=kind):
                self.setUp()
                e = self.e
                quest = e.quest_def("dev:npc_trial")
                stage = quest.stages[-1].model_copy(
                    update={
                        "objectives": [
                            QuestObjective(
                                id="chair",
                                kind=kind,
                                map_ref="dev:npc_lab",
                                target_id="chair",
                            )
                        ]
                    }
                )
                docs = dict(e.state.level.store.documents)
                docs["quests", "dev:npc_trial"] = quest.model_copy(
                    update={"stages": [stage]}
                )
                e.state.level.store = ContentSnapshot.create(docs)
                self.near("quest_giver")
                e.choose_dialogue("quest_giver", "accept:dev:npc_trial")
                e.state.position = Position(2, 4)
                if kind == "dismantle":
                    self.give("base:carpenter_tools")
                    self.assertTrue(e.start_dismantle("chair").performed)
                    self.assertEqual(e.quests["dev:npc_trial"]["counts"], {})
                    while e.active_craft:
                        self.assertTrue(e.advance_craft().performed)
                else:
                    e.damage_world_objects(Position(2, 5), 100, "bludgeoning")
                self.assertEqual(e.quests["dev:npc_trial"]["counts"]["chair"], 1)


if __name__ == "__main__":
    unittest.main()
