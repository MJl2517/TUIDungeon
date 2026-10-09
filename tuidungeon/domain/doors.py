"""Door rules and session state; no files, terminal or world coordinates."""

from dataclasses import dataclass
from typing import Literal
from .damage import DAMAGE_TYPES, DamageProfile, validate_damage

Material = Literal["wood", "bars", "steel", "stone", "adamantine"]
LockQuality = Literal["cheap", "normal", "expensive", "legendary"]
LockComplexity = Literal["simple", "complex"]

LOCK_DC = {"cheap": 10, "normal": 15, "expensive": 20, "legendary": 25}
LOCK_NAMES = {
    "cheap": "дешёвый",
    "normal": "обычный",
    "expensive": "дорогой",
    "legendary": "легендарный",
}


@dataclass(frozen=True)
class DoorMaterial:
    name: str
    force_dc: int | None
    hit_points: int
    color: int


MATERIALS = {
    "wood": DoorMaterial("Деревянная дверь", 10, 15, 130),
    "stone": DoorMaterial("Каменная плита", None, 30, 244),
    "bars": DoorMaterial("Дверь из прутьев", 15, 20, 250),
    "steel": DoorMaterial("Стальная дверь", 20, 40, 117),
    "adamantine": DoorMaterial("Адамантиевая дверь", 25, 60, 201),
}

DOOR_DAMAGE_PROFILES = {
    "wood": DamageProfile(),
    "bars": DamageProfile(vulnerabilities={"acid"}, immunities={"fire"}),
    "steel": DamageProfile(
        vulnerabilities={"acid"}, immunities=DAMAGE_TYPES - {"acid"}
    ),
    "stone": DamageProfile(immunities=DAMAGE_TYPES - {"bludgeoning"}),
    "adamantine": DamageProfile(immunities=DAMAGE_TYPES),
}


def door_glyph(opened, locked, *, destroyed=False, bent=False, material="wood"):
    return (
        "."
        if destroyed
        else "#"
        if material == "stone"
        else "%"
        if bent
        else "/"
        if opened
        else "X"
        if locked
        else "+"
    )


@dataclass
class Door:
    material: Material = "wood"
    opened: bool = False
    locked: bool = False
    lock_quality: LockQuality = "normal"
    lock_complexity: LockComplexity = "simple"
    max_hp: int = 15
    hp: int = 15
    bent: bool = False
    burning: bool = False
    corroding: bool = False
    burn_turns: int = 0

    @classmethod
    def from_spec(cls, spec):
        hp = spec.hit_points or MATERIALS[spec.material].hit_points
        return cls(
            spec.material,
            spec.state == "open" and spec.material != "stone",
            spec.locked and spec.material != "stone",
            spec.lock_quality,
            spec.lock_complexity,
            hp,
            hp,
        )

    @property
    def destroyed(self):
        return self.hp == 0

    @property
    def passable(self):
        return self.destroyed or (
            self.material != "stone" and (self.opened or self.bent)
        )

    @property
    def opaque(self):
        return not self.passable and self.material != "bars"

    @property
    def glyph(self):
        return door_glyph(
            self.opened,
            self.locked,
            destroyed=self.destroyed,
            bent=self.bent,
            material=self.material,
        )

    @property
    def color(self):
        return MATERIALS[self.material].color

    def display_color(self):
        """Turn-based flicker; the first completed burning turn is red."""
        return 9 if self.burning and self.burn_turns % 2 else self.color

    @property
    def lock_dc(self):
        return LOCK_DC[self.lock_quality]

    @property
    def lock_turns(self):
        return 10 if self.lock_complexity == "complex" else 1

    @property
    def force_dc(self):
        return MATERIALS[self.material].force_dc

    @property
    def geometry_key(self):
        return self.passable, self.opaque

    @property
    def visual_key(self):
        return self.glyph, self.display_color(), self.burning

    def force_open(self):
        if self.material == "stone":
            return False
        self.opened, self.locked = True, False
        return True

    @property
    def damage_profile(self):
        return DOOR_DAMAGE_PROFILES[self.material]

    def take_damage(self, amount: int, kind="physical", *, source_tags=()):
        # Legacy command aliases are not additional damage types.
        legacy_physical = kind == "physical"
        pickaxe = kind == "pickaxe" or (
            "pickaxe" in source_tags
            and kind in ("physical", "piercing", "bludgeoning", "slashing")
        )
        kind = "bludgeoning" if kind in ("physical", "pickaxe") else kind
        validate_damage(amount, kind, allow_untyped=False)
        if self.destroyed:
            return 0
        if self.material == "stone" and legacy_physical and not pickaxe:
            return 0
        profile = (
            DamageProfile()
            if self.material == "stone" and pickaxe
            else self.damage_profile
        )
        actual = min(self.hp, profile.resolve(amount, kind).resolved_amount)
        self.hp -= actual
        if self.destroyed:
            self.burning = self.corroding = self.locked = False
        return actual

    def ignite(self):
        if self.material != "wood" or self.destroyed or self.burning:
            return False
        self.burning = True
        self.burn_turns = 0
        return True

    def apply_acid(self, amount):
        actual = self.take_damage(amount, "acid")
        if self.material in ("steel", "bars") and not self.destroyed:
            self.corroding = True
        return actual

    def tick(self, minutes):
        if minutes < 0:
            raise ValueError("Время не может идти назад")
        damage = 0
        if self.burning:
            self.burn_turns += int(minutes > 0)
            damage += self.take_damage(5 * minutes, "fire")
        if self.corroding:
            damage += self.take_damage(minutes, "acid")
        return damage

    def daylight(self):
        if self.material != "adamantine" or self.destroyed:
            return False
        self.material = "stone"
        self.opened = self.locked = False
        self.max_hp = MATERIALS["stone"].hit_points
        self.hp = self.max_hp
        return True

    def inspection(self):
        if self.material == "stone":
            return [
                f"Каменная плита: {'уничтожена' if self.destroyed else 'перекрывает проход'}.",
                f"HP: {self.hp}/{self.max_hp}. Нельзя открыть, вскрыть или выломать.",
                "Разрушение: кирка или дробящий урон. Каждый удар: 1d4 износа оружия.",
            ]
        state = (
            "уничтожена"
            if self.destroyed
            else "прутья согнуты"
            if self.bent
            else "открыта"
            if self.opened
            else "закрыта"
        )
        return [
            f"{MATERIALS[self.material].name}: {state}.",
            "Заперта." if self.locked else "Не заперта.",
            f"Замок: {LOCK_NAMES[self.lock_quality]}, СЛ {self.lock_dc}; "
            f"{'сложный' if self.lock_turns == 10 else 'простой'}, {self.lock_turns} ход(ов).",
            f"Выломать: СИЛ, СЛ {self.force_dc}. HP: {self.hp}/{self.max_hp}.",
            *(
                ["Прутья пропускают свет. Согнуть: СИЛ, СЛ 20."]
                if self.material == "bars"
                else []
            ),
            "Каждый удар по двери: 1d4 износа оружия.",
            *(["Дверь горит: 5 урона за игровую минуту."] if self.burning else []),
            *(
                ["Кислота разъедает металл: 2 урона за игровую минуту."]
                if self.corroding
                else []
            ),
        ]


@dataclass
class LockpickAttempt:
    door_id: str
    progress: int = 0
    total: int = 10


@dataclass(frozen=True)
class DoorChoice:
    id: str
    text: str
