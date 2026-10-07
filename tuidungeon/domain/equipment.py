"""A mutable item instance backed by an immutable JSON definition."""

from dataclasses import dataclass, field
from uuid import uuid4

from .definitions import EquipmentDefinition


@dataclass
class Equipment:
    definition: EquipmentDefinition
    durability: int | None
    charges: int | None
    equipped: bool = False
    instance_id: str = field(default_factory=lambda: str(uuid4()), compare=False)

    @classmethod
    def create(
        cls, definition: EquipmentDefinition, *, equipped: bool = False
    ) -> "Equipment":
        return cls(definition, definition.durability, definition.charges, equipped)

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def weight(self) -> float:
        return self.definition.weight

    @property
    def broken(self) -> bool:
        return self.durability is not None and self.durability <= 0

    @property
    def usable(self) -> bool:
        return not self.broken and (self.charges is None or self.charges > 0)

    @property
    def tags(self) -> frozenset[str]:
        return self.definition.tags if self.usable else frozenset()

    def wear(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Износ должен быть неотрицательным")
        if self.durability is not None:
            self.durability = max(0, self.durability - amount)

    def repair(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Ремонт должен быть неотрицательным")
        if self.durability is not None:
            self.durability = min(self.definition.durability, self.durability + amount)

    def check_support(self, check_tag: str) -> str | None:
        if not self.usable:
            return None
        modes = {
            aid.mode for aid in self.definition.check_aids if aid.check_tag == check_tag
        }
        return (
            "automatic"
            if "automatic" in modes
            else "advantage"
            if "advantage" in modes
            else None
        )
