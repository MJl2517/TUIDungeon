"""A container belongs to one placed object in one visited level."""

from dataclasses import dataclass, field
from uuid import uuid4
from math import fsum

from ..domain.equipment import Equipment
from ..content.schemas import Placement, StorageSpec


@dataclass
class StorageInstance:
    placement: Placement
    definition: object
    spec: StorageSpec
    items: list[Equipment] = field(default_factory=list)
    instance_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def weight(self):
        return fsum(item.weight for item in self.items)

    def replace_loot(self, items):
        """Future restock jobs must never overwrite the player's personal stash."""
        if self.spec.personal:
            raise ValueError("Личный контейнер не обновляется")
        incoming = list(items)
        if sum(i.weight for i in incoming) > self.spec.capacity + 1e-9:
            raise ValueError("Лут превышает вместимость")
        if len({i.instance_id for i in incoming}) != len(incoming) or any(
            i.equipped or i.lit for i in incoming
        ):
            raise ValueError("Недопустимый лут контейнера")
        self.items[:] = incoming

    @property
    def challenge(self):
        # Same presentation contract as doors and points, without a text event.
        return self

    @property
    def text(self):
        return self.definition.description

    @property
    def completed(self):
        return False

    def available_choices(self, hero):
        return ()
