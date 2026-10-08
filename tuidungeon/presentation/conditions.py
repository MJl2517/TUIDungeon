"""Display placeholders for planned conditions; no rules or actor state changes."""

CONDITION_LABELS = {
    "blinded": "Ослепление",
    "exhaustion": "Истощение",
    "thirst": "Жажда",
    "hunger": "Голод",
    "poisoned": "Отравление",
    "blessed": "Благословление",
    "stunned": "Оглушение",
    "frightened": "Испуг",
}


def condition_lines() -> list[str]:
    return [f"{label}: --" for label in CONDITION_LABELS.values()]
