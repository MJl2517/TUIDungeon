"""Common lock rules, independent of door material and container capacity."""

from dataclasses import dataclass
from typing import Literal

LockQuality = Literal["cheap", "normal", "expensive", "legendary"]
LockComplexity = Literal["simple", "complex"]
LOCK_DC = {"cheap": 10, "normal": 15, "expensive": 20, "legendary": 25}
LOCK_NAMES = {
    "cheap": "лёгкий",
    "normal": "средний",
    "expensive": "сложный",
    "legendary": "легендарный",
}
LOCK_COLORS = {"cheap": 130, "normal": 110, "expensive": 220, "legendary": 135}


class LockRules:
    @property
    def lock_dc(self):
        return LOCK_DC[self.lock_quality]

    @property
    def lock_turns(self):
        return 10 if self.lock_complexity == "complex" else 1

    @property
    def lock_color(self):
        return LOCK_COLORS[self.lock_quality]


@dataclass
class Lock(LockRules):
    locked: bool = True
    lock_quality: LockQuality = "normal"
    lock_complexity: LockComplexity = "simple"
    key_tag: str | None = None
    key_code: str | None = None

    @classmethod
    def from_spec(cls, spec):
        return cls(**spec.model_dump())
