"""Key identity is independent of item tags and the player's current location."""

import re
from typing import Literal

KeyKind = Literal["door", "container", "unique"]


def key_code(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9]{4,16}", value.strip()
    ):
        raise ValueError("Код ключа: от 4 до 16 латинских букв или цифр")
    return value.strip().upper()


def key_matches(item, lock, kind, level_ref):
    if not item.usable:
        return False
    definition = item.definition
    if lock.key_code:
        return definition.key_kind == "unique" and definition.key_code == lock.key_code
    if definition.key_kind:
        return definition.key_kind == kind and bool(
            item.key_level and item.key_level == level_ref
        )
    return bool(lock.key_tag and lock.key_tag in item.tags)
