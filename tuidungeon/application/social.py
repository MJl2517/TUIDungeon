"""NPC commands, finite trading and event-driven quest progress."""

from fractions import Fraction
from math import ceil, floor, fsum

from ..content.schemas import SocialReward
from ..domain.definitions import ChallengeChoice
from ..domain.equipment import Equipment
from ..domain.rules import Ability
from ..domain.skills import SKILLS
from ..domain.storage import item_stacks
from ..world.maps import Position


def item_ref(item):
    return item.id if ":" in item.id else "base:" + item.id


class SocialCommands:
    def social_result(self, performed, message, minutes=0):
        from .engine import ActionResult

        return ActionResult(performed, minutes, message)

    def npc_at(self, identifier):
        level = self.state.level
        return (
            next((n for n in level.npcs if n.placement.id == identifier), None)
            if level
            else None
        )

    def social_access(self, identifier):
        npc = self.npc_at(identifier)
        if self.state.hero.hp <= 0 or self.active_craft or self.lockpick_attempt:
            return None, "Сначала завершите или приостановите текущее действие."
        if not npc:
            return None, "NPC отсутствует."
        p = Position(npc.placement.x, npc.placement.y)
        if max(
            abs(p.x - self.state.position.x), abs(p.y - self.state.position.y)
        ) > 1 or not self._clear_throw_path(p, allow_target_door=True):
            return None, "Подойдите к NPC: разговор через преграду невозможен."
        return npc, None

    def nearby_npcs(self):
        return (
            [
                n
                for n in self.state.level.npcs
                if not self.social_access(n.placement.id)[1]
            ]
            if self.state.level
            else []
        )

    def open_dialogue(self, identifier):
        npc, error = self.social_access(identifier)
        if error:
            return self.social_result(False, error)
        now = self.state.clock.elapsed_minutes
        if npc.definition.trade and (
            npc.bargain is None or now - npc.bargain["at"] >= 1440
        ):
            check = self.state.hero.ability_check(
                self.dice,
                Ability.CHARISMA,
                npc.definition.trade.difficulty,
                skill="persuasion",
            )
            npc.bargain = dict(
                at=now,
                roll=check.roll,
                modifier=check.modifier,
                difficulty=check.difficulty,
                success=check.success,
            )
            self.events.append(
                dict(
                    kind="bargain",
                    message=npc.definition.name + ": " + self.bargain_text(npc),
                )
            )
        self.quest_event("talk", target_id=identifier)
        return self.social_result(True, npc.definition.greeting)

    def bargain_text(self, npc):
        b = npc.bargain
        if not b:
            return "Сначала поговорите с торговцем."
        percent = npc.definition.trade.percent
        remaining = max(0, b["at"] + 1440 - self.state.clock.elapsed_minutes)
        return (
            f"Убеждение: d20 {b['roll']} {b['modifier']:+} = {b['roll'] + b['modifier']}, СЛ {b['difficulty']}. "
            + (
                f"Покупки −{percent}%, продажи +{percent}%."
                if b["success"]
                else f"Покупки +{percent}%, продажи −{percent}%."
            )
            + (
                f" Осталось {remaining} мин."
                if remaining
                else " Новый бросок при следующем разговоре."
            )
        )

    def quest_def(self, ref):
        return self.state.level.store.get("quests", ref)

    def quest_status(self, ref):
        return self.quests.get(ref, {}).get("status", "available")

    def topic_visible(self, npc, topic):
        if topic.once and npc.topics.get(topic.id, {}).get("claimed"):
            return False
        for c in topic.conditions:
            if c.quest:
                progress = self.quests.get(c.quest)
                if c.status and self.quest_status(c.quest) != c.status:
                    return False
                if c.stage and (
                    not progress
                    or progress["status"] != "active"
                    or self.quest_def(c.quest).stages[progress["stage"]].id != c.stage
                ):
                    return False
            if (
                c.item
                and sum(item_ref(i) == c.item for i in self.state.hero.inventory)
                < c.quantity
            ):
                return False
            if c.topic:
                seen = npc.topics.get(c.topic)
                if (
                    not seen
                    or c.outcome != "seen"
                    and seen["success"] != (c.outcome == "success")
                ):
                    return False
        return True

    def dialogue_choices(self, identifier):
        npc, error = self.social_access(identifier)
        if error:
            return ()
        choices = [
            ChallengeChoice("topic:" + t.id, t.question, minutes=0)
            for t in npc.definition.topics
            if self.topic_visible(npc, t)
        ]
        if npc.definition.trade:
            choices.append(ChallengeChoice("trade", "Торговать", minutes=0))
        linked = {q.quest: q for q in npc.definition.quests}
        refs = list(linked)
        for ref, p in self.quests.items():
            if p["status"] == "active" and ref not in linked:
                stage = self.quest_def(ref).stages[p["stage"]]
                if stage.report_to and (
                    stage.report_to.map_ref,
                    stage.report_to.npc_id,
                ) == (self.state.level.ref, identifier):
                    refs.append(ref)
        for ref in refs:
            status = self.quest_status(ref)
            link = linked.get(ref)
            name = self.quest_def(ref).name
            if status == "available" and link:
                choices.append(
                    ChallengeChoice(
                        "accept:" + ref, link.offer + " — " + name, minutes=0
                    )
                )
            elif status == "active":
                stage = self.quest_def(ref).stages[self.quests[ref]["stage"]]
                choices.append(
                    ChallengeChoice(
                        "discuss:" + ref,
                        (link.discuss if link else "О задании") + " — " + name,
                        minutes=0,
                    )
                )
                if stage.report_to and (
                    stage.report_to.map_ref,
                    stage.report_to.npc_id,
                ) == (self.state.level.ref, identifier):
                    choices.append(
                        ChallengeChoice(
                            "report:" + ref,
                            (link.report if link else "Доложить о выполнении")
                            + " — "
                            + name,
                            minutes=0,
                        )
                    )
        return tuple(choices)

    def reward_items(self, reward):
        refs = [(e.item, e.quantity) for e in reward.items] + [
            ("base:gold", reward.gold)
        ]
        return [
            Equipment.create(
                self.catalog.equipment[ref.removeprefix("base:")],
                level_ref=self.state.level.ref,
                level_name=self.state.level.definition.name,
            )
            for ref, count in refs
            for _ in range(count)
        ]

    def grant_social_reward(self, reward, consumed=(), *, apply=False):
        hero = self.state.hero
        new = self.reward_items(reward)
        if (
            hero.carried_weight
            - fsum(i.weight for i in consumed)
            + fsum(i.weight for i in new)
            > hero.max_carry_weight + 1e-9
        ):
            return "Недостаточно свободной нагрузки для награды. Освободите инвентарь."
        if apply:
            for item in consumed:
                hero.inventory.remove(item)
            hero.inventory.extend(new)
            hero.experience += reward.experience
            self.learn_recipes(reward.learn_recipes)
        return None

    def choose_dialogue(self, identifier, choice_id):
        npc, error = self.social_access(identifier)
        if error:
            return self.social_result(False, error)
        if choice_id not in {c.id for c in self.dialogue_choices(identifier)}:
            return self.social_result(
                False, "Этот вопрос или действие сейчас недоступны."
            )
        kind, _, ref = choice_id.partition(":")
        link = next((q for q in npc.definition.quests if q.quest == ref), None)
        if kind == "accept":
            self.quests[ref] = dict(
                status="active",
                stage=0,
                counts={},
                giver_map=self.state.level.ref,
                giver_id=identifier,
            )
            self.refresh_quests()
            self.events.append(
                dict(
                    kind="quest", message="Принято задание: " + self.quest_def(ref).name
                )
            )
            return self.social_result(True, link.accept_answer)
        if kind == "discuss":
            return self.social_result(
                True,
                (link.discuss_answer + "\n\n" if link else "") + self.quest_text(ref),
            )
        if kind == "report":
            error = self.finish_quest_stage(ref, reporter=identifier)
            return self.social_result(
                not error, error or (link.report_answer if link else "Этап выполнен.")
            )
        if kind != "topic":
            return self.social_result(False, "Выберите действие в окне торговли.")
        topic = next(t for t in npc.definition.topics if t.id == ref)
        memory = npc.topics.get(ref)
        if memory and memory.get("claimed"):
            return self.social_result(True, memory["answer"])
        for reward in (topic.reward, topic.failure_reward):
            if error := self.grant_social_reward(reward):
                return self.social_result(False, error)
        minutes = 0
        if memory is None:
            success, result_text = True, ""
            if topic.check:
                skill = SKILLS[topic.check.skill]
                check = self.state.hero.ability_check(
                    self.dice, skill.ability, topic.check.difficulty, skill=skill.id
                )
                success = check.success
                result_text = f"{skill.name}: d20 {check.roll} {check.modifier:+} = {check.total}, СЛ {check.difficulty}.\n\n"
                minutes = 1
            memory = dict(
                success=success,
                claimed=False,
                answer=result_text
                + (topic.answer if success else topic.failure_answer),
            )
            npc.topics[ref] = memory
        reward = topic.reward if memory["success"] else topic.failure_reward
        self.grant_social_reward(reward, apply=True)
        memory["claimed"] = True
        self.refresh_quests()
        if minutes:
            self._advance(minutes)
        self.events.append(
            dict(kind="dialogue", message=npc.definition.name + ": " + topic.question)
        )
        return self.social_result(True, memory["answer"], minutes)

    def trade_rule(self, npc, item):
        if not npc.definition.trade or item_ref(item) == "base:gold":
            return None
        furniture = item.furniture
        tags = set(furniture.definition.tags if furniture else item.definition.tags)
        return next(
            (
                r
                for r in npc.definition.trade.rules
                if r.item == item_ref(item)
                and not furniture
                or r.furniture
                and furniture
                and r.furniture == furniture.placement.ref
                or r.tag
                and r.tag in tags
            ),
            None,
        )

    def trade_price(self, npc, item, *, selling=False):
        rule = self.trade_rule(npc, item)
        if not rule or not npc.bargain:
            return None
        ratios = [Fraction(1)]
        if item.durability is not None and item.definition.durability:
            ratios.append(Fraction(item.durability, item.definition.durability))
        if item.charges is not None and item.definition.charges:
            ratios.append(Fraction(item.charges, item.definition.charges))
        if (
            item.furniture
            and item.furniture.state.hp is not None
            and item.furniture.definition.destruction
        ):
            ratios.append(
                Fraction(
                    item.furniture.state.hp,
                    item.furniture.definition.destruction.max_hp,
                )
            )
        condition = min(ratios)
        direction = 1 if npc.bargain["success"] else -1
        pct = npc.definition.trade.percent * direction
        buy = max(1, ceil(rule.sell * condition * Fraction(100 - pct, 100)))
        sell = min(buy, floor(rule.buy * condition * Fraction(100 + pct, 100)))
        return sell if selling else buy

    def trade_item_denial(self, item):
        if item.equipped:
            return "Сначала снимите предмет."
        if (
            item.work
            or item.glow
            or item.lit
            or item.liquid_portions
            or item.furniture
            and (item.furniture.items or item.furniture.state.progress)
        ):
            return "Завершите работу, снимите временную магию, погасите и освободите предмет перед продажей."
        if any(m.item_id == item.instance_id for m in self.magic_effects):
            return "На предмете действует временная магия."
        return None

    def trade(self, identifier, item_id, quantity=1, *, selling=False):
        npc, error = self.social_access(identifier)
        if error:
            return self.social_result(False, error)
        if not npc.definition.trade or not npc.bargain:
            return self.social_result(False, "Сначала поговорите с торговцем.")
        if denial := self.light_denial():
            return denial
        if type(quantity) is not int or quantity < 1 or type(selling) is not bool:
            return self.social_result(False, "Неверное количество.")
        hero = self.state.hero
        source, target = (
            (hero.inventory, npc.items) if selling else (npc.items, hero.inventory)
        )
        stack = next(
            (s for s in item_stacks(source) if s.first.instance_id == item_id), None
        )
        if not stack or quantity > stack.quantity:
            return self.social_result(False, "Предметы отсутствуют.")
        moved = list(stack.items[:quantity])
        for item in moved:
            if error := self.trade_item_denial(item):
                return self.social_result(False, error)
        prices = [self.trade_price(npc, i, selling=selling) for i in moved]
        if any(p is None or selling and p <= 0 for p in prices):
            return self.social_result(False, "Торговец не принимает этот товар.")
        total = sum(prices)
        payer, payee = (
            (npc.items, hero.inventory) if selling else (hero.inventory, npc.items)
        )
        coins = [i for i in payer if item_ref(i) == "base:gold"]
        if len(coins) < total:
            return self.social_result(
                False,
                "Недостаточно золота у " + ("торговца." if selling else "игрока."),
            )
        payment = coins[:total]
        weight = hero.carried_weight + (
            fsum(i.weight for i in payment) - fsum(i.weight for i in moved)
        ) * (1 if selling else -1)
        if weight > hero.max_carry_weight + 1e-9:
            return self.social_result(
                False, "Недостаточно свободной нагрузки с учётом монет."
            )
        for item in moved:
            source.remove(item)
        target.extend(moved)
        for coin in payment:
            payer.remove(coin)
        payee.extend(payment)
        self._advance(1)
        message = f"{'Продано' if selling else 'Куплено'}: {stack.first.name} ×{quantity}, {total} зол."
        self.events.append(dict(kind="trade", message=message))
        return self.social_result(True, message, 1)

    def goal_count(self, objective, progress):
        if objective.kind == "bring":
            return min(
                objective.quantity,
                sum(
                    item_ref(i) == objective.item
                    and not i.equipped
                    and not i.work
                    and not i.furniture
                    for i in self.state.hero.inventory
                ),
            )
        if objective.kind == "visit" and self.state.level.ref == objective.map_ref:
            p = self.state.position
            if (
                objective.x <= p.x < objective.x + objective.width
                and objective.y <= p.y < objective.y + objective.height
            ):
                progress["counts"][objective.id] = objective.quantity
        return min(objective.quantity, progress["counts"].get(objective.id, 0))

    def finish_quest_stage(self, ref, *, reporter=None):
        progress = self.quests.get(ref)
        if not progress or progress["status"] != "active":
            return "Задание не активно."
        quest = self.quest_def(ref)
        stage = quest.stages[progress["stage"]]
        if stage.report_to and (
            (self.state.level.ref, reporter)
            != (stage.report_to.map_ref, stage.report_to.npc_id)
            or self.social_access(reporter)[1]
        ):
            return "Отчитаться нужно указанному NPC."
        if any(self.goal_count(o, progress) < o.quantity for o in stage.objectives):
            return "Не все цели этапа выполнены.\n" + self.quest_text(ref)
        consumed = []
        for o in stage.objectives:
            if o.kind == "bring" and o.consume:
                items = [
                    i
                    for i in self.state.hero.inventory
                    if item_ref(i) == o.item
                    and not i.equipped
                    and not i.work
                    and i not in consumed
                ]
                if len(items) < o.quantity:
                    return "Недостаточно предметов для передачи."
                consumed.extend(items[: o.quantity])
        final = progress["stage"] == len(quest.stages) - 1
        reward = quest.reward if final else SocialReward()
        if error := self.grant_social_reward(reward, consumed):
            return error
        self.grant_social_reward(reward, consumed, apply=True)
        if final:
            progress["status"] = "completed"
        else:
            progress["stage"] += 1
            progress["counts"] = {}
        self.events.append(
            dict(
                kind="quest",
                message=quest.name + (": выполнено." if final else ": новый этап."),
            )
        )
        self.refresh_quests()
        return None

    def refresh_quests(self):
        if getattr(self, "_refreshing_quests", False):
            return
        self._refreshing_quests = True
        try:
            for ref, p in self.quests.items():
                while p["status"] == "active":
                    stage = self.quest_def(ref).stages[p["stage"]]
                    ready = all(
                        self.goal_count(o, p) >= o.quantity for o in stage.objectives
                    )
                    if stage.report_to or not ready or self.finish_quest_stage(ref):
                        break
        finally:
            self._refreshing_quests = False

    def quest_event(self, kind, *, target_id=None, recipe=None, quantity=1):
        if not self.state.level:
            return
        for ref, p in list(self.quests.items()):
            if p["status"] != "active":
                continue
            stage = self.quest_def(ref).stages[p["stage"]]
            for o in stage.objectives:
                if o.kind == kind and (
                    o.recipe == recipe
                    if kind == "craft"
                    else o.map_ref == self.state.level.ref and o.target_id == target_id
                ):
                    p["counts"][o.id] = min(
                        o.quantity, p["counts"].get(o.id, 0) + quantity
                    )
        self.refresh_quests()

    def quest_text(self, ref):
        q, p = self.quest_def(ref), self.quests[ref]
        if p["status"] == "completed":
            return q.name + "\nЗадание выполнено."
        stage = q.stages[p["stage"]]
        lines = [
            q.name,
            q.description,
            f"Этап {p['stage'] + 1}/{len(q.stages)}: {stage.description}",
        ]
        lines += [
            f"{'V' if self.goal_count(o, p) >= o.quantity else 'X'} {o.description}: {self.goal_count(o, p)}/{o.quantity}"
            for o in stage.objectives
        ]
        if stage.report_to:
            report_map = self.state.level.store.get("maps", stage.report_to.map_ref)
            placement = next(
                n for n in report_map.npcs if n.id == stage.report_to.npc_id
            )
            name = self.state.level.store.resolve("npcs", placement).name
            lines.append("Отчитаться: " + name + " — " + report_map.name)
        giver = self.state.level.store.get("maps", p["giver_map"])
        lines.append("Получено: " + giver.name)
        return "\n".join(lines)
