"""Exploration actions. Menus and key bindings are deliberately outside the engine."""

from dataclasses import dataclass
from enum import Enum
import random

from ..domain.actors import Character, Hero, Monster
from ..domain.actions import ActionContext, ActionOutcome, ActionRegistry
from ..domain.challenges import Challenge, ChallengeResult, TextChallenge
from ..domain.rules import Ability, Dice
from ..domain.equipment import Equipment
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement, ItemPlacement
from ..world.lighting import LightField
from ..domain.collections import EventLog
from ..world.graphics import glyph_cell


class Action(Enum):
    NORTH = (0, -1)
    SOUTH = (0, 1)
    WEST = (-1, 0)
    EAST = (1, 0)
    WAIT = "wait"
    REST = "rest"
    SHORT_REST = "short_rest"


@dataclass(frozen=True)
class ActionResult:
    performed: bool
    minutes: int
    message: str


def test_dungeon() -> DungeonMap:
    """A fixed, connected 60 x 28 dungeon with four rooms and winding passages."""
    cells = [["#"] * 60 for _ in range(28)]
    for left, top, right, bottom in (
        (2, 2, 16, 9),
        (25, 2, 44, 10),
        (6, 17, 23, 25),
        (37, 17, 56, 25),
    ):
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                cells[y][x] = "."
    for x in range(16, 26):
        cells[5][x] = "."
    for y in range(9, 18):
        cells[y][10] = "."
    for x in range(23, 39):
        cells[21][x] = "."
    for y in range(10, 18):
        cells[y][38] = "."
    return DungeonMap(tuple("".join(row) for row in cells))


class Engine:
    def __init__(
        self,
        state: GameState,
        rng: random.Random,
        *,
        actions: ActionRegistry | None = None,
    ):
        self.state = state
        self.dice = Dice(rng)
        self.catalog = state.hero.catalog
        self.actions = actions or ActionRegistry.default()
        self.challenges: dict[str, Challenge] = {}
        self.events: list[dict] = EventLog()
        level = getattr(state, "level", None)
        self.levels = {level.ref: state} if level else {}
        self.discard_consumed_lights()

    @classmethod
    def new_game(
        cls, hero: Hero, rng: random.Random, map_ref=None, store=None
    ) -> "Engine":
        if map_ref:
            from .factories import SessionFactory
            from ..content.packs import PackStore

            return cls(SessionFactory(store or PackStore()).state(map_ref, hero), rng)
        return cls(GameState(hero, test_dungeon(), Position(3, 3)), rng)

    def apply(self, action: Action) -> ActionResult:
        if not isinstance(action, Action):
            raise ValueError("Неизвестное игровое действие")
        if self.state.hero.hp <= 0:
            return ActionResult(False, 0, "Персонаж без сознания.")
        if action is Action.REST:
            self.state.hero.restore_after_rest()
            minutes = 8 * 60
            message = "Отдых завершён. Здоровье и магические ресурсы восстановлены."
        elif action is Action.SHORT_REST:
            # Simplified recovery: no hit-dice pool yet; spell resources stay spent.
            self.state.hero.heal(max(1, self.state.hero.max_hp // 2))
            self.state.hero.sneaking = False
            minutes = 60
            message = "Короткий отдых: восстановлено до половины максимального HP."
        elif action is Action.WAIT:
            minutes = 1
            message = "Вы ждёте одну минуту."
        else:
            dx, dy = action.value
            target = Position(self.state.position.x + dx, self.state.position.y + dy)
            if not self.state.dungeon.walkable(target):
                return ActionResult(False, 0, "Прохода нет.")
            if any(
                placement.position == target and placement.monster.hp > 0
                for placement in self.state.actor_index.at(target.x, target.y)
            ):
                return ActionResult(False, 0, "Путь преграждает существо.")
            self.state.position = target
            minutes = 2 if self.state.hero.sneaking else 1
            message = "Вы делаете шаг."
        expired = self._advance(minutes)
        if expired:
            message += " " + " ".join(expired)
        if isinstance(action.value, tuple):
            trap_messages = self._enter()
            if trap_messages:
                message += " " + " ".join(trap_messages)
        return ActionResult(True, minutes, message)

    def _advance(self, minutes: int, refreshed: set[str] | None = None) -> list[str]:
        preserved = {
            name: turns
            for name, turns in self.state.hero.conditions.items()
            if name in (refreshed or set())
        }
        self.state.hero.end_turn()
        self.state.hero.conditions.update(preserved)
        self.state.turns += 1
        self.state.clock.advance(minutes)
        states = list(self.levels.values()) if self.levels else [self.state]
        items = [
            item for state in states for _, item in state.light_sources(shining=False)
        ]
        seen = set()
        expired = []
        for item in items:
            if item.instance_id not in seen:
                seen.add(item.instance_id)
                if item.burn(minutes):
                    message = (
                        f"Сгорел: {item.name}."
                        if item.consumed
                        else f"Погас: {item.name}."
                    )
                    expired.append(message)
                    self.events.append({"kind": "light", "message": message})
        self.discard_consumed_lights()
        return expired

    def discard_consumed_lights(self) -> None:
        """Remove exhausted disposable sources from every session-owned container."""
        states = list(self.levels.values()) if self.levels else [self.state]
        inventories = [self.state.hero.inventory]
        for state in states:
            inventories.extend(
                p.monster.inventory
                for p in state.monsters
                if any(i.consumed for i in p.monster.light_items)
            )
            if any(i.consumed for _, i in state.item_index.lights):
                state.items[:] = [(p, i) for p, i in state.items if not i.consumed]
        for inventory in inventories:
            if not any(i.consumed for i in inventory):
                continue
            for item in inventory:
                if item.consumed:
                    item.equipped = item.lit = False
            inventory[:] = [item for item in inventory if not item.consumed]

    @property
    def lighting(self) -> LightField:
        state = self.state
        sources = state.light_sources()
        geometry = state.level.terrain if state.level else state.dungeon
        key = (
            id(state),
            id(geometry),
            state.position,
            tuple(
                (
                    p,
                    i.instance_id,
                    i.definition.light.radius,
                    i.definition.light.bright_radius,
                )
                for p, i in sources
            ),
        )
        if getattr(self, "_light_key", None) != key:
            physical_key = (id(geometry), key[-1])
            physical = (
                self._light.illumination
                if getattr(self, "_physical_key", None) == physical_key
                else None
            )
            self._light = LightField.calculate(
                state, sources=sources, illumination=physical
            )
            self._physical_key = physical_key
            self._light_key = key
        return self._light

    def render_cells(self, viewport=None):
        """One cached shaded frame shared by both clients; viewport is x/y/w/h."""
        state, light = self.state, self.lighting
        width, height = state.dungeon.width, state.dungeon.height
        x, y, w, h = viewport or (0, 0, width, height)
        if x < 0 or y < 0 or w < 1 or h < 1 or x >= width or y >= height:
            raise ValueError("Недопустимая область карты")
        region = (x, y, min(w, width - x), min(h, height - y))
        level = state.level
        key = (
            id(state),
            id(light),
            state.position,
            id(state.items),
            state.items.version,
            id(state.monsters),
            state.monsters.version,
            tuple(p.monster.hp > 0 for p in state.monsters),
            tuple(t.triggered for t in level.traps) if level else (),
            (id(level.points), level.points.version) if level else (),
        )
        if getattr(self, "_frame_key", None) != key:
            self._frames = {}
            self._frame_key = key
        if region in self._frames:
            return self._frames[region]
        x, y, w, h = region
        if level:
            cells = level.render_cells(state, region)
        else:
            cells = [
                [glyph_cell(c) for c in row[x : x + w]]
                for row in state.dungeon.rows[y : y + h]
            ]
            for p, item in state.item_index.region(*region):
                cells[p.y - y][p.x - x] = glyph_cell("!")
            for p in state.actor_index.region(*region):
                if p.monster.hp > 0:
                    cells[p.position.y - y][p.position.x - x] = glyph_cell("g", 2)
            p = state.position
            if x <= p.x < x + w and y <= p.y < y + h:
                cells[p.y - y][p.x - x] = glyph_cell("@", 15)
        frame = light.shade(cells, (x, y))
        # Keep at most the full map and a small number of camera regions.
        if len(self._frames) >= 4:
            self._frames.clear()
        self._frames[region] = frame
        return frame

    def add_monster(self, monster_id: str, position: Position) -> MonsterPlacement:
        if (
            not self.state.dungeon.walkable(position)
            or position == self.state.position
            or self.state.actor_index.at(position.x, position.y)
        ):
            raise ValueError("Для монстра нужна свободная клетка пола")
        placement = MonsterPlacement(
            Monster.create(monster_id.removeprefix("base:"), catalog=self.catalog), position
        )
        placement.monster.definition_ref = (
            monster_id if ":" in monster_id else "base:" + monster_id
        )
        self.state.monsters.append(placement)
        return placement

    def perform_character_action(
        self, action_id: str, context: ActionContext
    ) -> ActionOutcome:
        result = self.state.hero.perform(action_id, context, self.actions)
        if result.performed:
            self._advance(
                1,
                {
                    entry.condition
                    for entry in result.effects
                    if entry.kind == "condition" and entry.target is self.state.hero
                },
            )
        return result

    def use_item(
        self, item: Equipment, target: Character | None = None
    ) -> ActionOutcome:
        result = self.state.hero.use_item(item, self.dice, target, self.actions.effects)
        if result.performed:
            self._advance(
                1,
                {
                    entry.condition
                    for entry in result.effects
                    if entry.kind == "condition" and entry.target is self.state.hero
                },
            )
        return result

    @property
    def throw_range(self) -> int:
        return max(0, self.state.hero.stats.modifier(Ability.STRENGTH) + 1)

    def place_item(
        self, item: Equipment, target: Position, *, throwing=False
    ) -> ActionResult:
        """Move one owned instance onto the ground; throwing is not an attack."""
        state, hero = self.state, self.state.hero
        if hero.hp <= 0 or not any(owned is item for owned in hero.inventory):
            return ActionResult(False, 0, "Предмет недоступен.")
        distance = abs(target.x - state.position.x) + abs(target.y - state.position.y)
        if not throwing and target != state.position:
            return ActionResult(False, 0, "Положить предмет можно только под ноги.")
        if throwing and distance > self.throw_range:
            return ActionResult(False, 0, f"Дальность броска: {self.throw_range} кл.")
        if not state.dungeon.walkable(target) or any(
            p.monster.hp > 0 for p in state.actor_index.at(target.x, target.y)
        ):
            return ActionResult(False, 0, "Выберите клетку пола без существа.")
        if throwing and not self._clear_throw_path(target):
            return ActionResult(False, 0, "Бросок преграждает стена.")
        index = next(i for i, owned in enumerate(hero.inventory) if owned is item)
        hero.inventory.pop(index)
        item.equipped = False
        ref = item.id if ":" in item.id else "base:" + item.id
        state.items.append(
            (ItemPlacement(item.instance_id, ref, target.x, target.y), item)
        )
        self._advance(1)
        verb = "Брошено" if throwing else "Положено на землю"
        return ActionResult(True, 1, f"{verb}: {item.name}.")

    def _clear_throw_path(self, target):
        """Integer line trace, including corner walls to prevent diagonal clipping."""
        start = self.state.position
        x, y = start.x, start.y
        dx, dy = abs(target.x - x), abs(target.y - y)
        sx, sy = (1 if x < target.x else -1), (1 if y < target.y else -1)
        error = dx - dy
        while (x, y) != (target.x, target.y):
            twice = 2 * error
            nx, ny = x, y
            if twice > -dy:
                error -= dy
                nx += sx
            if twice < dx:
                error += dx
                ny += sy
            if (
                nx != x
                and ny != y
                and (
                    not self.state.dungeon.walkable(Position(nx, y))
                    or not self.state.dungeon.walkable(Position(x, ny))
                )
            ):
                return False
            x, y = nx, ny
            if not self.state.dungeon.walkable(Position(x, y)):
                return False
        return True

    def pickup_item(self) -> ActionResult:
        state = self.state
        if state.hero.hp <= 0:
            return ActionResult(False, 0, "Персонаж без сознания.")
        entries = state.item_index.at(state.position.x, state.position.y)
        if entries:
            placement, item = entries[0]
            state.items.remove(entries[0])
            item.lit = False
            state.hero.inventory.append(item)
            self._advance(1)
            return ActionResult(True, 1, f"Подобрано: {item.name}.")
        return ActionResult(False, 0, "Под ногами нет предметов.")

    def toggle_sneaking(self) -> ActionResult:
        if self.state.hero.hp <= 0:
            return ActionResult(False, 0, "Персонаж без сознания.")
        self.state.hero.sneaking = not self.state.hero.sneaking
        return ActionResult(
            True,
            0,
            "Скрытность включена: шаг за 2 минуты."
            if self.state.hero.sneaking
            else "Скрытность выключена.",
        )

    def manage_equipment(self, item, equipped) -> ActionResult:
        hero = self.state.hero
        if hero.hp <= 0:
            return ActionResult(False, 0, "Персонаж без сознания.")
        fuel = None
        light = item.definition.light
        if equipped:
            if not hero.can_equip(item):
                return ActionResult(
                    False,
                    0,
                    "Нельзя экипировать: освободите руку, сняв оружие или щит."
                    if item.hands
                    else "Предмет нельзя надеть.",
                )
            if light and item.fuel_minutes <= 0:
                if light.fuel_tag is None:
                    return ActionResult(False, 0, "Факел догорел. Нужен новый факел.")
                fuel = next(
                    (
                        i
                        for i in hero.inventory
                        if light.fuel_tag in i.tags
                        and i.charges is not None
                        and i.charges > 0
                    ),
                    None,
                )
                if fuel is None:
                    return ActionResult(
                        False, 0, "Для лампы нужно масло (одна порция на час)."
                    )
        changed = hero.equip(item) if equipped else hero.unequip(item)
        if not changed:
            return ActionResult(False, 0, "Предмет нельзя надеть или снять.")
        if equipped and light:
            if fuel:
                fuel.charges -= 1
                item.fuel_minutes = light.burn_minutes
            item.lit = True
        self._advance(1)
        if item.consumed:
            return ActionResult(True, 1, f"Сгорел: {item.name}.")
        return ActionResult(
            True,
            1,
            ("Надето: " + item.name if equipped else "Снято: " + item.name)
            + (
                f". Свет: осталось {item.fuel_minutes} мин."
                if equipped and light
                else ". Свет погашен."
                if light
                else ""
            ),
        )

    def cast_spell(self, spell_id, source, target=None) -> ActionOutcome:
        from ..domain.actions import SpellSource

        hero = self.state.hero
        if source not in (SpellSource.CLASS, SpellSource.RACIAL):
            return ActionOutcome(False, False, "Неизвестный источник магии.")
        if (
            target is not None
            and target is not hero
            and not any(
                p.monster is target and p.monster.hp > 0 for p in self.state.monsters
            )
        ):
            return ActionOutcome(False, False, "Цель отсутствует на карте.")
        if (
            target is not None
            and target is not hero
            and not any(
                p.monster is target and self.lighting.at(p.position)
                for p in self.state.monsters
            )
        ):
            return ActionOutcome(False, False, "Цель не видна: темно или обзор закрыт.")
        magic = next((a for a in hero.available_actions if a.kind == "magic"), None)
        if magic is None:
            return ActionOutcome(False, False, "Магия недоступна классу.")
        return self.perform_character_action(
            magic.id,
            ActionContext(self.dice, target, spell_id=spell_id, spell_source=source),
        )

    def inspect_cell(self, position: Position) -> list[str]:
        """Visible information only; inspection never reveals an untriggered hidden trap."""
        state = self.state
        if not (
            0 <= position.x < state.dungeon.width
            and 0 <= position.y < state.dungeon.height
        ):
            return ["За пределами карты."]
        light = self.lighting
        lines = [f"Клетка ({position.x}, {position.y})", *light.inspection(position)]
        if not light.at(position):
            return lines + ["Клетка не видна: темно или обзор закрыт."]
        details_start = len(lines)
        if position == state.position:
            lines += [state.hero.name, f"HP: {state.hero.hp}/{state.hero.max_hp}"]
        for p, item in state.items:
            if (p.x, p.y) == (position.x, position.y):
                lines += [
                    item.name,
                    item.definition.description,
                    f"Вес: {item.weight:g} кг",
                ]
        for p in state.monsters:
            if p.position == position:
                lines += [
                    p.monster.name,
                    p.monster.definition.description,
                    f"HP: {p.monster.hp}/{p.monster.max_hp} | КД: {p.monster.armor_class}",
                ]
        level = state.level
        if level:
            for p in level.points:
                if (p.placement.x, p.placement.y) == (position.x, position.y):
                    lines += [
                        p.definition.name,
                        p.challenge.text,
                        "Ситуация завершена."
                        if p.challenge.completed
                        else "Подойдите и нажмите Enter для взаимодействия.",
                    ]
            for trap in level.traps:
                if (trap.placement.x, trap.placement.y) == (
                    position.x,
                    position.y,
                ) and (not trap.definition.hidden or trap.triggered):
                    lines += [
                        trap.definition.name,
                        "Сработавшая ловушка." if trap.triggered else "Ловушка.",
                    ]
            tile_ref = level.terrain.tiles[position.y][position.x]
            if tile_ref:
                tile = level.store.get("tiles", tile_ref)
                hidden_brush_trap = any(
                    trap.definition.hidden
                    and not trap.triggered
                    and (trap.placement.x, trap.placement.y) == (position.x, position.y)
                    and tile.brush.trap == trap.placement.ref
                    for trap in level.traps
                )
                lines += (
                    ["Пол."] if hidden_brush_trap else [tile.name, tile.description]
                )
        if len(lines) == details_start:
            lines.append("Пол." if state.dungeon.walkable(position) else "Стена.")
        return [line for line in lines if line]

    def resolve_challenge(
        self, challenge: Challenge | str, choice_id: str
    ) -> ChallengeResult:
        if isinstance(challenge, str):
            if challenge not in self.challenges:
                self.challenges[challenge] = TextChallenge(
                    self.catalog.challenges[challenge], self.actions.effects
                )
            challenge = self.challenges[challenge]
        result = challenge.resolve(choice_id, self.state.hero, self.dice)
        if result.performed:
            self._advance(
                result.minutes,
                {
                    entry.condition
                    for entry in result.effects
                    if entry.kind == "condition"
                },
            )
        return result

    def _enter(self):
        level = getattr(self.state, "level", None)
        if level is None:
            return []
        from ..content.catalog import effect
        from ..domain.mechanics import mechanics
        from ..domain.rules import Ability

        messages = []
        for trap in level.index("traps").at(
            self.state.position.x, self.state.position.y
        ):
            if trap.triggered and not trap.definition.repeatable:
                continue
            definition = trap.definition
            check = self.dice.check(
                self.state.hero.stats.score(Ability[definition.ability.upper()]),
                definition.difficulty,
                advantage=self.state.hero.sneaking,
            )
            specs = tuple(
                effect(e.model_dump(), frozenset(mechanics.entries))
                for e in (definition.success if check.success else definition.failure)
            )
            outcomes = self.actions.effects.apply_all(specs, self.state.hero, self.dice)
            trap.triggered = True
            message = (
                f"{definition.name}: d20 {check.roll} + {check.modifier} = {check.total}, СЛ {check.difficulty}. "
                + ("Успех." if check.success else "Провал.")
            )
            messages.append(message)
            self.events.append(
                {
                    "kind": "trap",
                    "placement": trap.placement.id,
                    "message": message,
                    "roll": check.roll,
                    "rolls": list(check.rolls),
                    "advantage": check.advantage,
                    "total": check.total,
                    "success": check.success,
                    "effects": [
                        {"kind": e.kind, "amount": e.amount, "condition": e.condition}
                        for e in outcomes
                    ],
                }
            )
        if self.state.hero.hp > 0:
            for transition in level.definition.transitions:
                if (transition.x, transition.y) == (
                    self.state.position.x,
                    self.state.position.y,
                ):
                    from .factories import SessionFactory

                    target = transition.target
                    previous = self.state
                    if target not in self.levels:
                        self.levels[target] = SessionFactory(level.store).state(
                            target, previous.hero
                        )
                    self.state = self.levels[target]
                    self.state.position = Position(
                        self.state.level.definition.spawn.x,
                        self.state.level.definition.spawn.y,
                    )
                    self.state.clock = previous.clock
                    self.state.turns = previous.turns
                    message = f"Переход: {self.state.level.definition.name}."
                    messages.append(message)
                    self.events.append(
                        {"kind": "transition", "message": message, "target": target}
                    )
                    break
        return messages

    def nearby_points(self):
        level = getattr(self.state, "level", None)
        if not level:
            return []
        light = self.lighting
        return [
            p
            for p in level.nearby(self.state.position)
            if light.at(Position(p.placement.x, p.placement.y))
        ]

    def interact(self, placement_id, choice_id):
        for point in self.nearby_points():
            if point.placement.id == placement_id:
                result = self.resolve_challenge(point.challenge, choice_id)
                self.events.append(
                    {
                        "kind": "challenge",
                        "placement": placement_id,
                        "message": result.message,
                        "success": result.success,
                        "roll": result.check.roll if result.check else None,
                        "total": result.check.total if result.check else None,
                        "effects": [
                            {
                                "kind": e.kind,
                                "amount": e.amount,
                                "condition": e.condition,
                            }
                            for e in result.effects
                        ],
                    }
                )
                return result
        return ChallengeResult(False, False, 0, "Рядом нет этой точки интереса.")
