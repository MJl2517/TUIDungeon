"""A container belongs to one placed object in one visited level."""

from dataclasses import dataclass, field
from uuid import uuid4
from math import fsum

from ..domain.equipment import Equipment, lockpicks_hint
from ..content.schemas import Placement, StorageSpec
from ..domain.item_sizes import fits_size
from ..domain.locks import Lock
from ..domain.doors import DoorChoice


@dataclass
class StorageInstance:
    placement: Placement
    definition: object
    spec: StorageSpec
    items: list[Equipment] = field(default_factory=list)
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    lock: Lock | None = None
    opened: bool = False

    def __post_init__(self):
        self.opened = self.spec.state == "open"
        if self.lock is None and self.spec.lock:
            self.lock = Lock.from_spec(self.spec.lock)

    @property
    def locked(self):
        return bool(self.lock and self.lock.locked)

    def snapshot_spec(self):
        return self.spec.model_copy(
            update={
                "state": "open" if self.opened else "closed",
                "lock": self.spec.lock.model_copy(update={"locked": self.lock.locked})
                if self.lock
                else None,
            }
        )

    @property
    def weight(self):
        return fsum(item.weight for item in self.items)

    def replace_loot(self, items):
        """Future restock jobs must never overwrite the player's personal stash."""
        if self.spec.personal:
            raise ValueError("Личный контейнер не обновляется")
        incoming = list(items)
        if any(not fits_size(item.size, self.spec.max_item_size) for item in incoming):
            raise ValueError(
                "Размер лута превышает допустимый размер вещей в контейнере"
            )
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
        if not self.locked:
            return ()
        choices = [
            DoorChoice(
                "pick_container_lock",
                f"Вскрыть замок: ЛОВ, СЛ {self.lock.lock_dc}, {self.lock.lock_turns} ход(ов); {lockpicks_hint(hero.inventory)}",
            )
        ]
        choices.append(DoorChoice("unlock_container_key", "Открыть подходящим ключом"))
        return tuple(choices)
