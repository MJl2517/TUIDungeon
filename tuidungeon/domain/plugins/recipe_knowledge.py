"""Recipe grants for class abilities, books, quests and future teachers."""

from pydantic import Field
from ..mechanics import Parameters, mechanics
from ..effects import EffectOutcome


class RecipeKnowledge(Parameters):
    learn_recipes: list[str] = Field(
        min_length=1, max_length=32, json_schema_extra={"ref_category": "recipes"}
    )


def learn(params, target, dice):
    if not hasattr(target, "learn_recipes"):
        raise ValueError("Рецепты изучает только персонаж игрока")
    return EffectOutcome(
        "learn_recipe", amount=len(target.learn_recipes(params.learn_recipes))
    )


mechanics.register(
    "learn_recipe",
    RecipeKnowledge,
    learn,
    name="Изучить рецепты",
    description="Добавляет знания персонажу один раз; подходит для классовых способностей и наград.",
)
