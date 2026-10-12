"""A portable workpiece owns its inputs until completion or full refund."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..content.schemas import RecipeDocument
    from .equipment import Equipment


@dataclass
class CraftWork:
    recipe_ref: str
    recipe: "RecipeDocument"
    variant: int
    ingredients: list["Equipment"]
    progress: int = 0
    target: "Equipment | None" = None
    target_id: str | None = None
    target_object: str | None = None
    map_ref: str | None = None
    destination: tuple[int, int] | None = None

    @property
    def total(self):
        return self.recipe.variants[self.variant].turns


def ingredient_choices(requirements, available):
    """Choose one material per requirement, including overlapping alternatives."""
    from functools import lru_cache

    refs = tuple(sorted({r for req in requirements for r in req.items}))

    @lru_cache(maxsize=None)
    def choose(index, counts):
        if index == len(requirements):
            return ()
        req = requirements[index]
        for ref in req.items:
            slot = refs.index(ref)
            if counts[slot] >= req.quantity:
                rest = list(counts)
                rest[slot] -= req.quantity
                tail = choose(index + 1, tuple(rest))
                if tail is not None:
                    return (ref, *tail)
        return None

    return choose(0, tuple(available.get(ref, 0) for ref in refs))


def operation_target_matches(op, item):
    if item.work or item.furniture or item.equipped or item.lit:
        return False
    if op.target_tags and not set(op.target_tags).intersection(item.definition.tags):
        return False
    if op.kind == "liquid":
        return bool(
            item.usable
            and item.definition.vessel
            and item.liquid_kind in op.liquids
            and item.liquid_portions == op.portions
            and (not op.heat_safe or item.definition.vessel.heat_safe)
        )
    if op.kind == "appraise_item":
        return bool(
            item.usable
            and item.definition.value_gold is not None
            and not item.appraised
        )
    if op.kind == "coat_weapon":
        return bool(
            item.usable
            and item.definition.weapon_damage
            and item.damage_type in ("piercing", "slashing")
            and not item.poison_damage
        )
    return bool(
        op.kind == "repair_item"
        and item.durability is not None
        and item.durability < item.definition.durability
    )
