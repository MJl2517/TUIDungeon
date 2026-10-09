"""Assign reviewed damage types, without guessing rules from arbitrary tags."""

import argparse
import json
from pathlib import Path

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore

WEAPONS = {
    "acid_flask": "acid",
    "dagger": "piercing",
    "pickaxe": "piercing",
    "staff": "bludgeoning",
    "sword": "slashing",
    "terrain_decor_axe": "slashing",
    "terrain_decor_bow": "piercing",
    "terrain_decor_greataxe": "slashing",
    "terrain_decor_greatsword": "slashing",
    "terrain_decor_halberd": "slashing",
    "terrain_decor_hammer": "bludgeoning",
    "terrain_decor_longbow": "piercing",
    "terrain_decor_mace": "bludgeoning",
    "terrain_decor_rapier": "piercing",
    "terrain_decor_sickle": "slashing",
    "terrain_decor_spear": "piercing",
}
SOURCES = {
    "magic_missile": "force",
    "spikes": "piercing",
    "terrain_acid": "acid",
    "terrain_acid_deep": "acid",
    "terrain_trap_acid": "acid",
    "terrain_arrow_slit": "piercing",
    "terrain_arrow_slit_barrage": "piercing",
    "terrain_cave_in": "bludgeoning",
    "terrain_wall_falling": "bludgeoning",
    "terrain_fire": "fire",
    "terrain_fire_large": "fire",
    "terrain_fire_small": "fire",
    "terrain_magic_fire": "fire",
    "terrain_rune_fire": "fire",
    "terrain_lava": "fire",
    "terrain_lava_bubbling": "fire",
    "terrain_lava_flow": "fire",
    "terrain_gas_toxic": "poison",
    "terrain_poison": "poison",
    "terrain_poison_surface": "poison",
    "terrain_toxic_spores": "poison",
    "terrain_spikes_hidden": "piercing",
    "terrain_spikes_large": "piercing",
    "terrain_magic_negative": "necrotic",
}


def assign_effects(value, damage_type):
    if isinstance(value, dict):
        if value.get("kind") == "damage" and value.get("damage_type") is None:
            value["damage_type"] = damage_type
        for child in value.values():
            assign_effects(child, damage_type)
    elif isinstance(value, list):
        for child in value:
            assign_effects(child, damage_type)


def run(write=False):
    changes = []
    legacy = Path(__file__).resolve().parents[1] / "tuidungeon/content/data"
    for root in (DEFAULT_PACKS / "base", legacy):
        for path in sorted(root.rglob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            before = json.dumps(raw, ensure_ascii=False)
            identifier = raw.get("id")
            category = path.relative_to(root).parts[0]
            if category == "equipment" and identifier in WEAPONS:
                raw.setdefault("damage_type", WEAPONS[identifier])
            if category in ("spells", "traps") and identifier in SOURCES:
                assign_effects(raw, SOURCES[identifier])
                if SOURCES[identifier] == "poison" and "acid" in raw.get("tags", []):
                    raw["tags"] = ["poison" if t == "acid" else t for t in raw["tags"]]
            if category == "monsters":
                for action in raw.get("special_actions", []):
                    if action["id"] == "bone_strike":
                        action.setdefault("damage_type", "bludgeoning")
                    elif action["id"] == "dirty_strike":
                        action.setdefault("damage_type", "piercing")
                if identifier == "skeleton":
                    raw.setdefault(
                        "damage_profile",
                        dict(
                            resistances=["piercing"],
                            vulnerabilities=["bludgeoning"],
                            immunities=["poison"],
                        ),
                    )
            if before != json.dumps(raw, ensure_ascii=False):
                changes.append(path)
                if write:
                    PackStore.atomic_json(path, raw)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="Записать проверенную разметку"
    )
    args = parser.parse_args()
    changes = run(args.write)
    for path in changes:
        print(path)
    print(f"{'Обновлено' if args.write else 'К обновлению'}: {len(changes)} файлов")


if __name__ == "__main__":
    main()
