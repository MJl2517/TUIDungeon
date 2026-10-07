"""Extension point: register a parameter model and an effect handler once."""

from dataclasses import dataclass
import re
from pydantic import BaseModel, ConfigDict, Field


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class AmountParameters(Parameters):
    amount: int = Field(default=0, ge=0)
    dice: str | None = None


class ConditionParameters(Parameters):
    condition: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    duration: int = Field(default=1, ge=1)


@dataclass(frozen=True)
class Mechanic:
    id: str
    name: str
    parameters: type[BaseModel]
    handler: object = None
    description: str = ""
    builtin: bool = False


class MechanicsRegistry:
    def __init__(self):
        self.entries = {}

    def register(self, identifier, parameters, handler, *, name=None, description=""):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", identifier):
            raise ValueError("Некорректный id механики")
        if not isinstance(parameters, type) or not issubclass(parameters, BaseModel):
            raise TypeError("Параметры механики должны быть Pydantic-моделью")
        if not callable(handler):
            raise TypeError("Нужен вызываемый обработчик")
        if identifier in self.entries:
            raise ValueError(f"Механика {identifier} уже зарегистрирована")
        self.entries[identifier] = Mechanic(
            identifier, name or identifier, parameters, handler, description
        )

    def validate_effect(self, effect):
        if effect.kind not in self.entries:
            raise ValueError(f"Неизвестная механика {effect.kind}")
        entry = self.entries[effect.kind]
        if entry.builtin:
            data = (
                {"condition": effect.condition, "duration": effect.duration}
                if effect.kind == "condition"
                else {"amount": effect.amount, "dice": effect.dice}
            )
            entry.parameters.model_validate(data)
            if effect.params:
                raise ValueError(
                    "Встроенная механика использует именованные поля, а не params"
                )
            if effect.kind != "condition" and effect.condition:
                raise ValueError("condition допустимо только для condition")
            if (
                effect.kind in ("condition", "armor_class", "armor_bonus")
                and effect.dice
            ):
                raise ValueError(f"{effect.kind} не поддерживает dice")
        else:
            if effect.amount or effect.dice or effect.condition or effect.duration != 1:
                raise ValueError("Новая механика использует только params")
            entry.parameters.model_validate(effect.params)

    def schemas(self):
        return [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "builtin": m.builtin,
                "schema": m.parameters.model_json_schema(),
            }
            for m in self.entries.values()
        ]

    def extend(self, registry):
        from .effects import EffectHandler

        for entry in self.entries.values():
            if entry.builtin:
                continue

            class Adapter(EffectHandler):
                def __init__(self, descriptor):
                    self.descriptor = descriptor

                def apply(self, spec, target, dice):
                    params = self.descriptor.parameters.model_validate(spec.params)
                    return self.descriptor.handler(params, target, dice)

            registry.register(entry.id, Adapter(entry))
        return registry


mechanics = MechanicsRegistry()
for identifier, name in [
    ("damage", "Урон"),
    ("heal", "Лечение"),
    ("gold", "Деньги"),
    ("experience", "Опыт"),
    ("condition", "Состояние"),
    ("armor_class", "Базовая КД"),
    ("armor_bonus", "Бонус КД"),
]:
    model = ConditionParameters if identifier == "condition" else AmountParameters
    mechanics.entries[identifier] = Mechanic(identifier, name, model, builtin=True)

# Agent-written extensions belong here; imports perform registration.
from . import plugins  # noqa: E402,F401
