"""Tag actual containers, leaving sleeping bags, keys and pictures alone."""

import argparse
from pathlib import Path

from tuidungeon.content.packs import PackStore, DEFAULT_PACKS

CONTAINERS = {
    "objects": {"bookcase", "shelf", "cabinet"},
    "points_of_interest": {
        "chest",
        "terrain_barrel",
        "terrain_barrel_large",
        "terrain_barrel_small",
        "terrain_chest",
        "terrain_chest_open",
        "terrain_chest_treasure",
        "terrain_crate",
        "terrain_crate_closed",
        "terrain_crate_reinforced",
        "terrain_jug",
        "terrain_pot",
        "terrain_sack",
        "terrain_sack_large",
        "terrain_urn",
        "terrain_vessel_large",
    },
}


def run(root=DEFAULT_PACKS, write=False):
    store = PackStore(root)
    changed = 0
    for category, identifiers in CONTAINERS.items():
        for identifier in sorted(identifiers):
            key = category, "base:" + identifier
            if key not in store.documents:
                continue
            doc = store.get(*key)
            if doc.storage is not None and "storage" in doc.tags:
                continue
            raw = doc.model_dump(mode="json")
            raw["tags"] = sorted(set(raw["tags"]) | {"storage"})
            small = identifier in {"bookcase", "shelf"}
            chest = identifier in {
                "chest",
                "terrain_chest",
                "terrain_chest_open",
                "terrain_chest_treasure",
            }
            raw["storage"] = dict(
                capacity=30 if small else 300 if chest else 1000,
                max_item_size="small" if small else "medium" if chest else "large",
                personal=False,
                contents=[],
            )
            changed += 1
            if write:
                store.save(*key, raw, store.versions[key])
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(
        f"Контейнеров {'размечено' if args.write else 'для разметки'}: {run(args.packs_dir, args.write)}"
    )
