"""Resolve authored instance properties without changing shared templates."""

from copy import deepcopy

from .schemas import MODELS

PLACEMENT_CATEGORIES = {
    "doors": "objects",
    "objects": "objects",
    "decorations": "art",
    "traps": "traps",
    "points_of_interest": "points_of_interest",
    "monsters": "monsters",
    "equipment": "equipment",
}


def merge_properties(base, patch):
    """Objects merge recursively; lists, scalars and explicit null replace."""
    result = deepcopy(base)
    for key, value in patch.items():
        result[key] = (
            merge_properties(result[key], value)
            if isinstance(result.get(key), dict) and isinstance(value, dict)
            else deepcopy(value)
        )
    return result


def override_document(category, document, overrides):
    if not overrides:
        return document
    if {"id", "schema_version"} & overrides.keys():
        raise ValueError("Идентификатор и версия шаблона не переопределяются")
    merged = merge_properties(document.model_dump(mode="json"), overrides)
    # Old maps can override only the text sign on a migrated template.
    if "glyph" in overrides and "symbol" not in overrides:
        merged["symbol"] = None
    return MODELS[category].model_validate(merged)


def resolve_placement(documents, category, placement):
    if placement.challenge_overrides and category != "points_of_interest":
        raise ValueError("Настройки испытания допустимы только у точки интереса")
    return override_document(
        category, documents[category, placement.ref], placement.overrides
    )


def resolve_challenge(documents, point, placement):
    if point.challenge is None:
        if placement.challenge_overrides:
            raise ValueError("У этого объекта нет испытания для переопределения")
        return None
    return override_document(
        "challenges",
        documents["challenges", point.challenge],
        placement.challenge_overrides,
    )


def property_difference(base, effective):
    """A minimal equivalent patch; explicit null and changed lists remain changes."""
    result = {}
    for key, value in effective.items():
        if value == base.get(key):
            continue
        result[key] = (
            property_difference(base[key], value)
            if isinstance(base.get(key), dict) and isinstance(value, dict)
            else deepcopy(value)
        )
    return result


def normalized_map(document, documents):
    """Compare map semantics, ignoring redundant fields in old migrated patches."""
    raw = document.model_dump(mode="json")
    for layer, category in PLACEMENT_CATEGORIES.items():
        for placement, entry in zip(getattr(document, layer), raw[layer]):
            # Explicit legacy door placements can still point to custom tiles.
            resolved_category = (
                "tiles"
                if layer == "doors" and (category, placement.ref) not in documents
                else category
            )
            base = documents[resolved_category, placement.ref]
            effective = resolve_placement(documents, resolved_category, placement)
            entry["overrides"] = property_difference(
                base.model_dump(mode="json"), effective.model_dump(mode="json")
            )
    return MODELS["maps"].model_validate(raw)
