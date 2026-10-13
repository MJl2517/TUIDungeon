"""Non-destructive compatibility for earlier door-preset maps."""

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from .placements import merge_properties


LEGACY_DOORS = {
    "door_closed": ("wood", False, False),
    "door_wooden": ("wood", False, False),
    "door_vertical": ("wood", False, False),
    "door_horizontal": ("wood", False, False),
    "door_unlocked": ("wood", False, False),
    "door_locked": ("wood", False, True),
    "door_open": ("wood", True, False),
    "door_open_wooden": ("wood", True, False),
    "door_grate": ("bars", False, False),
    "iron_portcullis": ("bars", False, True),
    "door_massive": ("steel", False, True),
}


def door_alias(ref):
    if not isinstance(ref, str) or not ref.startswith("base:"):
        return None
    identifier = ref.removeprefix("base:")
    if identifier in LEGACY_DOORS:
        material, opened, locked = LEGACY_DOORS[identifier]
        return f"base:door_{material}", dict(
            material=material,
            state="open" if opened else "closed",
            locked=locked,
            lock_quality="normal",
            lock_complexity="simple",
            hit_points=None,
        )
    for material in ("wood", "bars", "steel", "stone", "adamantine"):
        prefix = f"door_{material}_"
        if not identifier.startswith(prefix):
            continue
        suffix = identifier[len(prefix) :]
        spec = dict(
            material=material,
            state="closed",
            locked=False,
            lock_quality="normal",
            lock_complexity="simple",
            hit_points=None,
        )
        if suffix == "open":
            spec["state"] = "open"
        elif suffix != "closed":
            parts = suffix.split("_")
            if (
                len(parts) != 3
                or parts[0] != "locked"
                or parts[1] not in ("cheap", "normal", "expensive", "legendary")
                or parts[2] not in ("simple", "complex")
            ):
                return None
            spec.update(locked=True, lock_quality=parts[1], lock_complexity=parts[2])
        return f"base:door_{material}", spec
    return None


def _migrate_door_map(raw):
    """Old assets become a base material plus local properties; safe to repeat."""
    result = deepcopy(raw)
    doors = result.setdefault("doors", [])
    occupied = {(p["x"], p["y"]) for p in doors}
    identifiers = {
        p["id"]
        for key in (
            "doors",
            "traps",
            "equipment",
            "monsters",
            "points_of_interest",
            "decorations",
            "lights",
            "transitions",
        )
        for p in result.get(key, [])
    }
    for p in doors:
        alias = door_alias(p["ref"])
        if alias:
            p["ref"], spec = alias
            p["overrides"] = merge_properties(
                {"brush": {"door": spec}}, p.get("overrides", {})
            )
    for y, row in enumerate(result.get("tiles", [])):
        for x, ref in enumerate(row):
            alias = door_alias(ref)
            if not alias:
                continue
            if (x, y) not in occupied:
                target, spec = alias
                identifier = f"tile_doors_{x}_{y}"
                while identifier in identifiers:
                    identifier += "_migrated"
                identifiers.add(identifier)
                doors.append(
                    dict(
                        id=identifier,
                        ref=target,
                        x=x,
                        y=y,
                        overrides={"brush": {"door": spec}},
                    )
                )
                occupied.add((x, y))
            row[x] = "base:floor"
            result["walkability"][y][x] = True
            result["blocks_sight"][y][x] = False
    return result


# Removed definitions live only in this compatibility table, outside pack libraries.
# It lets external maps and saves migrate without resurrecting duplicate documents.
@lru_cache(maxsize=1)
def compatibility():
    return json.loads(
        Path(__file__).with_name("compatibility.json").read_text(encoding="utf-8")
    )


def content_alias(category, ref):
    return compatibility()["aliases"].get(category, {}).get(ref)


def canonical_ref(category, ref):
    qualified = ref if ":" in ref else "base:" + ref
    record = content_alias(category, qualified)
    target = record["ref"] if record else qualified
    return target if ":" in ref else target.removeprefix("base:")


def equipment_alias(ref):
    return canonical_ref("equipment", ref)


def legacy_item_template(ref, template=None):
    record = content_alias("equipment", ref if ":" in ref else "base:" + ref)
    if not record:
        return template
    result = deepcopy(template if template is not None else record["legacy"])
    result["id"] = record["ref"].split(":")[-1]
    return result


def _placement_alias(category, placement):
    record = content_alias(category, placement["ref"])
    if not record:
        return
    target = record["ref"]
    old_template = record["overrides"]
    placement["ref"] = target
    placement["overrides"] = merge_properties(
        old_template, placement.get("overrides", {})
    )


def migrate_document(raw, category):
    """Rewrite typed reference fields only: never modify narrative or plugin params."""
    references = {
        "starting_items": "equipment",
        "inventory": "equipment",
        "item": "equipment",
        "items": "equipment",
    }

    def visit(value):
        if isinstance(value, list):
            return [visit(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, val in value.items():
            if key in references:
                result[key] = (
                    [canonical_ref(references[key], r) for r in val]
                    if isinstance(val, list) and all(isinstance(r, str) for r in val)
                    else canonical_ref(references[key], val)
                    if isinstance(val, str)
                    else visit(val)
                )
            else:
                result[key] = val if key == "params" else visit(val)
        return result

    return visit(deepcopy(raw))


def migrate_map(raw):
    result = _migrate_door_map(raw)
    table = compatibility()["tiles"]
    used = {
        p["id"]
        for layer in (
            "objects",
            "doors",
            "traps",
            "equipment",
            "monsters",
            "points_of_interest",
            "lights",
            "decorations",
            "transitions",
        )
        for p in result.get(layer, [])
    }

    def identifier(layer, x, y):
        candidate = f"tile_{layer}_{x}_{y}"
        while candidate in used:
            candidate += "_migrated"
        used.add(candidate)
        return candidate

    for y, row in enumerate(result.get("tiles", [])):
        for x, ref in enumerate(row):
            recipe = table.get(ref)
            if not recipe:
                continue
            category, target, source = (
                recipe["category"],
                recipe["ref"],
                recipe["legacy"],
            )
            brush = source.get("brush", {})
            layer = "doors" if brush.get("door") else category
            placements = result.setdefault(layer, [])
            # Prefer an existing authored placement, including any local properties.
            matching = next(
                (
                    p
                    for p in placements
                    if p["x"] == x
                    and p["y"] == y
                    and (
                        p["ref"] == target
                        or canonical_ref(category, p["ref"]) == target
                    )
                ),
                None,
            )
            if matching is None:
                original_ref = next(
                    (
                        r
                        for r in (
                            brush.get("item"),
                            brush.get("interaction"),
                            brush.get("trap"),
                        )
                        if r
                    ),
                    target,
                )
                matching = dict(id=identifier(layer, x, y), ref=original_ref, x=x, y=y)
                placements.append(matching)
            row[x] = brush.get("underlay") or "base:floor"
            # Static objects now provide their own geometry, so the old default
            # masks belong to the removed picture. Preserve manually changed masks.
            if category == "objects":
                if result["walkability"][y][x] == source["walkable"]:
                    result["walkability"][y][x] = True
                if result["blocks_sight"][y][x] == source["blocks_sight"]:
                    result["blocks_sight"][y][x] = False
    for category in ("equipment", "traps", "points_of_interest", "objects"):
        for placement in result.get(category, []):
            _placement_alias(category, placement)
    # Old brushes generated a second, permanent light on top of these fixtures.
    # Keep separately authored service lights, remove only generated duplicates.
    fixtures = {
        (p["x"], p["y"])
        for p in result.get("objects", [])
        if p["ref"]
        in {"base:torch_wall", "base:torch_decor", "base:lantern", "base:candle"}
    }
    if fixtures and "lights" in result:
        result["lights"] = [
            p
            for p in result["lights"]
            if (p["x"], p["y"]) not in fixtures
            or not p["id"].startswith(("tile_lights_", "sample_light_"))
        ]
    return migrate_document(result, "maps")
