"""A mutable item instance backed by an immutable JSON definition."""

from dataclasses import dataclass, field
from uuid import uuid4

from .definitions import EquipmentDefinition
from .materials import FLAMMABLE, WOODEN


def find_lockpicks(inventory):
    """Find working thieves' tools; custom packs share the lockpicks tag."""
    return next((item for item in inventory if "lockpicks" in item.tags), None)


@dataclass(frozen=True)
class ItemGlow:
    """Read-only view of a session-owned light enchantment."""

    remaining_turns: int
    radius: int
    bright_radius: int

    @property
    def description(self):
        return (
            f"Свечение (Свет): осталось {self.remaining_turns} ход.; "
            f"яркий радиус {self.bright_radius}, общий {self.radius} кл. "
            "Без топлива и свободной руки."
        )


@dataclass
class Equipment:
    definition: EquipmentDefinition
    durability: int | None
    charges: int | None
    equipped: bool = False
    instance_id: str = field(default_factory=lambda: str(uuid4()), compare=False)
    fuel_minutes: int = 0
    lit: bool = False
    template: dict | None = field(default=None, repr=False, compare=False)
    glow: ItemGlow | None = field(default=None, repr=False, compare=False)

    @classmethod
    def create(
        cls, definition: EquipmentDefinition, *, equipped: bool = False
    ) -> "Equipment":
        item = cls(definition, definition.durability, definition.charges, equipped)
        if definition.light and definition.light.fuel_tag is None:
            item.fuel_minutes = definition.light.burn_minutes
        return item

    @property
    def hands(self) -> int:
        if self.definition.hands:
            return self.definition.hands
        if "two_handed" in self.definition.tags:
            return 2
        return int(self.definition.slot in {"weapon", "main_hand", "off_hand", "hand"})

    @property
    def shining(self) -> bool:
        return bool(
            self.definition.light
            and self.lit
            and self.fuel_minutes > 0
            and not self.broken
        )

    @property
    def consumed(self) -> bool:
        return bool(
            self.definition.light
            and self.definition.light.fuel_tag is None
            and self.fuel_minutes == 0
        )

    def burn(self, minutes: int) -> bool:
        """Consume game minutes, reporting the moment a flame expires."""
        if minutes < 0:
            raise ValueError("Время не может идти назад")
        if not self.lit:
            return False
        self.fuel_minutes = max(0, self.fuel_minutes - minutes)
        if not self.fuel_minutes or self.broken:
            self.lit = False
            return True
        return False

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
    def category(self) -> str:
        """Explicit author category, with a fallback for older content packs."""
        definition = self.definition
        if definition.category:
            return definition.category
        if definition.weapon_damage or "weapon" in definition.tags:
            return "weapons"
        if definition.slot in ("armor", "shield") or any(
            effect.kind in ("armor_class", "armor_bonus")
            for effect in definition.properties
        ):
            return "armor"
        if definition.charges is not None or definition.tags & {"consumable", "potion"}:
            return "consumables"
        return "tools"

    @property
    def damage_type(self):
        # Compatibility for weapons authored before the typed field existed.
        return (
            "fire"
            if "fire_damage" in self.definition.tags
            else self.definition.damage_type
        )

    @property
    def broken(self) -> bool:
        return self.durability is not None and self.durability <= 0

    @property
    def usable(self) -> bool:
        return not self.broken and (self.charges is None or self.charges > 0)

    @property
    def tags(self) -> frozenset[str]:
        return (self.definition.tags if self.usable else frozenset()) | self.effect_tags

    @property
    def effect_tags(self) -> frozenset[str]:
        return frozenset({"glowing"}) if self.glow else frozenset()

    @property
    def ignition_source(self) -> bool:
        return bool(self.tags & {"поджог", "ignite", "fire_damage"})

    @property
    def flammable(self) -> bool:
        return FLAMMABLE in self.definition.tags

    @property
    def wooden(self) -> bool:
        return WOODEN in self.definition.tags

    @property
    def can_ignite(self) -> bool:
        if not self.ignition_source:
            return False
        if self.definition.light:
            return self.equipped and self.shining
        if self.definition.weapon_damage:
            return self.equipped
        return True

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
