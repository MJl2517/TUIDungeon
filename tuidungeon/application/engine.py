"""Exploration actions. Menus and key bindings are deliberately outside the engine."""

from dataclasses import dataclass
from enum import Enum
import random

from ..domain.actors import Character, Hero, Monster
from ..domain.actions import ActionContext, ActionOutcome, ActionRegistry
from ..domain.challenges import Challenge, ChallengeResult, TextChallenge
from ..domain.rules import Dice
from ..domain.equipment import Equipment
from ..world.maps import DungeonMap, Position
from ..world.state import GameState, MonsterPlacement


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
        self.events: list[dict] = []
        level = getattr(state, "level", None)
        self.levels = {level.ref: state} if level else {}

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
                for placement in self.state.monsters
            ):
                return ActionResult(False, 0, "Путь преграждает существо.")
            self.state.position = target
            minutes = 2 if self.state.hero.sneaking else 1
            message = "Вы делаете шаг."
        self._advance(minutes)
        if isinstance(action.value, tuple):
            trap_messages = self._enter()
            if trap_messages:
                message += " " + " ".join(trap_messages)
        return ActionResult(True, minutes, message)

    def _advance(self, minutes: int, refreshed: set[str] | None = None) -> None:
        preserved = {
            name: turns
            for name, turns in self.state.hero.conditions.items()
            if name in (refreshed or set())
        }
        self.state.hero.end_turn()
        self.state.hero.conditions.update(preserved)
        self.state.turns += 1
        self.state.clock.advance(minutes)

    def add_monster(self, monster_id: str, position: Position) -> MonsterPlacement:
        if (
            not self.state.dungeon.walkable(position)
            or position == self.state.position
            or any(entry.position == position for entry in self.state.monsters)
        ):
            raise ValueError("Для монстра нужна свободная клетка пола")
        placement = MonsterPlacement(
            Monster.create(monster_id, catalog=self.catalog), position
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
        changed = hero.equip(item) if equipped else hero.unequip(item)
        if not changed:
            return ActionResult(False, 0, "Предмет нельзя надеть или снять.")
        self._advance(1)
        return ActionResult(
            True, 1, "Надето: " + item.name if equipped else "Снято: " + item.name
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
        lines = [f"Клетка ({position.x}, {position.y})"]
        if position == state.position:
            lines += [state.hero.name, f"HP: {state.hero.hp}/{state.hero.max_hp}"]
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
            for p, item in level.items:
                if (p.x, p.y) == (position.x, position.y):
                    lines += [
                        item.name,
                        item.definition.description,
                        f"Вес: {item.weight:g} кг",
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
            tile_ref = level.definition.tiles[position.y][position.x]
            if tile_ref:
                tile = level.store.get("tiles", tile_ref)
                lines += [tile.name, tile.description]
        if len(lines) == 1:
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
        for trap in level.traps:
            if (trap.placement.x, trap.placement.y) != (
                self.state.position.x,
                self.state.position.y,
            ):
                continue
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
        return level.nearby(self.state.position) if level else []

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
