"""Inventory stacks are a view over distinct items, never copies of their state."""

from dataclasses import dataclass
import json
from math import fsum

from .equipment import Equipment


def stack_key(item):
    return (
        item.instance_id if item.work or item.furniture else None,
        item.definition,
        item.key_level,
        item.durability,
        item.charges,
        item.equipped,
        item.fuel_minutes,
        item.lit,
        json.dumps(item.template, sort_keys=True, ensure_ascii=False),
        item.glow,
        item.liquid_kind,
        item.liquid_portions,
        item.contaminated,
        item.poison_damage,
        item.appraised,
        repr(item.liquid_effects),
    )


@dataclass
class ItemStack:
    items: list[Equipment]

    @property
    def first(self):
        return self.items[0]

    @property
    def quantity(self):
        return len(self.items)

    @property
    def weight(self):
        return fsum(item.weight for item in self.items)

    @property
    def label(self):
        item = self.first
        state = "[*] " if item.equipped else "[ ] " if item.definition.slot else ""
        durability = (
            f" ({item.durability}/{item.definition.durability})"
            if item.durability is not None
            else ""
        )
        glow = f" [свет:{item.glow.remaining_turns}]" if item.glow else ""
        return f"{state}{item.name}{durability}{glow} x{self.quantity}"


def item_stacks(items):
    stacks, keys = [], {}
    for item in items:
        # Definitions contain nested fields: equality is sufficient; hash the
        # serialized mutable signature plus the definition ID for bucketing.
        key = stack_key(item)
        bucket = (item.id, key[0], *key[2:])
        candidates = keys.setdefault(bucket, [])
        stack = next(
            (s for s in candidates if s.first.definition == item.definition), None
        )
        if stack is None:
            stack = ItemStack([])
            candidates.append(stack)
            stacks.append(stack)
        stack.items.append(item)
    return stacks
