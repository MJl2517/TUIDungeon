"""Session state for placed objects; furniture retains its identity when carried."""

from dataclasses import dataclass, field
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from ..content.schemas import Placement, Transition
from ..domain.definitions import ChallengeChoice

WORK_NAMES = {
    "dismantle": "Разбор",
    "butcher": "Разделка",
    "harvest": "Сбор",
    "chop": "Рубка",
    "remove_barricade": "Снятие баррикады",
}
WORK_ACTIONS = {
    "dismantle": "Разобрать",
    "butcher": "Разделать",
    "harvest": "Собрать",
    "chop": "Срубить",
    "remove_barricade": "Снять баррикаду",
}
WORK_RESULTS = {
    "dismantle": "Разобрано",
    "butcher": "Разделано",
    "harvest": "Собрано",
    "chop": "Срублено",
    "remove_barricade": "Снято",
}


class RegrowingObject(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Literal["objects", "points_of_interest"]
    placement: Placement
    ready_at: int = Field(ge=1)
    sprout_id: str | None = Field(default=None, min_length=1)
    completed: bool = False
    transitions: list[Transition] = Field(default_factory=list)


class ObjectState(BaseModel):
    water_portions: int | None = Field(default=None, ge=0, le=1000)
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)
    instance_id: str = Field(default_factory=lambda: str(uuid4()))
    hp: int | None = Field(default=None, ge=0)
    progress: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0, le=1000)
    fast_tool: str | None = None
    fuel_minutes: int = Field(default=0, ge=0, le=100000)
    lit: bool = False
    burning: bool = False


@dataclass
class WorldObject:
    category: str
    placement: object
    definition: object
    state: ObjectState
    original: object = None

    @property
    def text(self):
        text = (
            self.original.text
            if self.original and hasattr(self.original, "text")
            else self.definition.description
        )
        if self.state.hp is not None:
            text += f" Прочность: {self.state.hp}/{self.definition.destruction.max_hp}."
        if getattr(self.definition, "campfire", None):
            text += f" Костёр: {'горит' if self.state.lit else 'потушен'}, топливо {self.state.fuel_minutes} мин."
        if self.state.burning:
            text += " Горит: 5 урона огнём за минуту."
        if self.state.progress:
            text += f" {WORK_NAMES[self.dismantle.verb]}: {self.state.progress}/{self.state.total}."
        return text

    @property
    def completed(self):
        return bool(self.original and getattr(self.original, "completed", False))

    @property
    def challenge(self):
        return (
            self.original.challenge
            if self.original and hasattr(self.original, "challenge")
            else None
        )

    @property
    def is_furniture(self):
        return self.category != "traps" and (
            "furniture" in self.definition.tags or self.definition.movable
        )

    @property
    def dismantle(self):
        if self.category == "traps":
            return self.definition.dismantle
        return (
            self.definition.destruction.dismantle
            if self.definition.destruction
            else None
        )

    def available_choices(self, hero):
        choices = (
            list(self.original.available_choices(hero))
            if self.original and hasattr(self.original, "available_choices")
            else []
        )
        fixture = getattr(self.definition, "light_fixture", None)
        if fixture:
            choices.extend(
                [
                    ChallengeChoice("take_light", "Забрать источник света", minutes=1),
                    ChallengeChoice(
                        "mount_light", "Установить источник света", minutes=1
                    ),
                ]
                if fixture.stays_when_empty
                else [
                    ChallengeChoice(
                        "take_light", "Подобрать: " + self.definition.name, minutes=1
                    )
                ]
            )
        elif self.category != "traps" and self.definition.storage:
            choices.append(
                ChallengeChoice("open_storage", "Открыть контейнер", minutes=0)
            )
        if getattr(self.definition, "water_source", None):
            from ..domain.liquids import LIQUID_NAMES

            choices.append(
                ChallengeChoice(
                    "fill_water",
                    "Набрать: " + LIQUID_NAMES[self.definition.water_source.kind],
                    minutes=1,
                )
            )
        if getattr(self.definition, "campfire", None):
            choices += [
                ChallengeChoice("fire_refuel", "Добавить топливо", minutes=1),
                ChallengeChoice(
                    "fire_extinguish" if self.state.lit else "fire_ignite",
                    "Потушить" if self.state.lit else "Зажечь",
                    minutes=1,
                ),
            ]
        if (
            self.category == "traps"
            and self.definition.disarm
            and not self.original.disabled
        ):
            check = self.definition.disarm
            choices.append(
                ChallengeChoice(
                    "disarm",
                    f"Обезвредить: {check.ability}, СЛ {check.difficulty}; провал — срабатывание",
                    minutes=1,
                )
            )
            return tuple(choices)
        if (
            self.category != "traps"
            and self.definition.destruction
            and not getattr(self.definition, "campfire", None)
            and "flammable" in self.definition.tags
            and not self.state.burning
            and any(i.can_ignite for i in hero.inventory)
        ):
            choices.append(
                ChallengeChoice(
                    "ignite_object", "Поджечь: 5 урона огнём за минуту", minutes=1
                )
            )
        if self.dismantle and not self.state.burning:
            verb = WORK_NAMES[self.dismantle.verb]
            label = (
                f"Продолжить: {verb}"
                if self.state.progress
                else WORK_ACTIONS[self.dismantle.verb]
            )
            fast = self.dismantle.fast_tool and any(
                i.usable and self.dismantle.fast_tool in i.tags for i in hero.inventory
            )
            turns = self.state.total or (
                self.dismantle.fast_turns if fast else self.dismantle.turns
            )
            choices.append(
                ChallengeChoice(
                    "dismantle",
                    f"{label} ({self.state.progress}/{turns})"
                    + (" — яркий свет, больше материалов" if self.is_furniture else ""),
                    minutes=0,
                )
            )
        if self.category != "traps":
            if self.definition.destruction:
                choices.append(
                    ChallengeChoice(
                        "break_object",
                        "Разрушить"
                        + (" — меньше материалов" if self.is_furniture else ""),
                        minutes=1,
                    )
                )
            if self.definition.movable:
                choices += [
                    ChallengeChoice("lift", "Поднять мебель", minutes=1),
                    ChallengeChoice("move", "Передвинуть мебель", minutes=1),
                ]
        return tuple(choices)


@dataclass
class FurnitureCargo:
    category: str
    placement: object
    definition: object
    state: ObjectState
    items: list = field(default_factory=list)
    completed: bool = False
    container_spec: object = None

    @property
    def weight(self):
        return self.definition.weight + sum(i.weight for i in self.items)


def validate_object_state(state, definition, category):
    source = getattr(definition, "water_source", None)
    if state.water_portions is not None and (
        not source
        or source.portions is None
        or not 0 < state.water_portions <= source.portions
    ):
        raise ValueError("Недопустимый запас источника жидкости")
    maximum = (
        definition.destruction.max_hp
        if category != "traps" and definition.destruction
        else None
    )
    if (maximum is None) != (state.hp is None) or (
        maximum is not None and not 0 < state.hp <= maximum
    ):
        raise ValueError("Недопустимая прочность объекта")
    spec = (
        definition.dismantle
        if category == "traps"
        else definition.destruction.dismantle
        if definition.destruction
        else None
    )
    if state.burning and (
        maximum is None
        or "flammable" not in definition.tags
        or getattr(definition, "campfire", None)
    ):
        raise ValueError("Гореть может только разрушаемый горючий объект")
    if state.lit and not state.fuel_minutes:
        raise ValueError("Костёр без топлива не может гореть")
    if (state.fuel_minutes or state.lit) and not getattr(definition, "campfire", None):
        raise ValueError("Топливо допустимо только для костра")
    if not state.total:
        if state.progress or state.fast_tool:
            raise ValueError("Недопустимый прогресс разбора")
    elif (
        not spec
        or state.progress >= state.total
        or state.total != (spec.fast_turns if state.fast_tool else spec.turns)
        or (state.fast_tool and state.fast_tool != spec.fast_tool)
    ):
        raise ValueError("Недопустимая работа над объектом")
