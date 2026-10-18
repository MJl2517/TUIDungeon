"""Spell metadata, world-effect parameter schemas and reusable cast rules."""

from pydantic import Field, model_validator, field_validator
from .mechanics import Parameters


class LightParameters(Parameters):
    duration: int = Field(default=10, ge=1, le=1000)
    radius: int = Field(default=6, ge=1, le=32)
    bright_radius: int = Field(default=3, ge=0, le=32)

    @model_validator(mode="after")
    def radii(self):
        if self.bright_radius > self.radius:
            raise ValueError("Яркий радиус не может превышать общий")
        return self


class RepairParameters(Parameters):
    tool_amount: int = Field(default=1, ge=1)
    equipment_dice: str = "1d4"

    @field_validator("equipment_dice")
    @classmethod
    def dice_valid(cls, value):
        from .definitions import DiceExpression

        DiceExpression.parse(value)
        return value


class EmptyParameters(Parameters):
    pass


class HandParameters(Parameters):
    duration: int = Field(default=5, ge=1, le=100)
    max_weight: float = Field(default=2.0, gt=0, le=100)


class MarkerParameters(Parameters):
    duration: int = Field(default=5, ge=1, le=100)


class WorldSpellParameters:
    def __init__(self):
        self.models = {}

    def register(self, kind, model):
        if kind in self.models:
            raise ValueError(f"Механика исследования уже зарегистрирована: {kind}")
        self.models[kind] = model

    def validate(self, kind, params):
        if kind is None:
            if params:
                raise ValueError("world_parameters требует world_effect")
            return None
        if kind not in self.models:
            raise ValueError(f"Неизвестная механика исследования: {kind}")
        return self.models[kind].model_validate(params)

    def schemas(self):
        return {kind: model.model_json_schema() for kind, model in self.models.items()}


world_spell_parameters = WorldSpellParameters()
for kind, model in (
    ("light", LightParameters),
    ("repair", RepairParameters),
    ("projectile", EmptyParameters),
    ("hand", HandParameters),
    ("illusion", MarkerParameters),
    ("tricks", MarkerParameters),
    ("dancing_lights", LightParameters),
    ("elementalism", MarkerParameters),
    ("noise", EmptyParameters),
    ("dispel", EmptyParameters),
):
    world_spell_parameters.register(kind, model)


def scaling_multiplier(level):
    return 1 + sum(level >= threshold for threshold in (5, 11, 17))
