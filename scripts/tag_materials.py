"""Review/apply bundled material tags without changing maps or instance settings.

python -m scripts.tag_materials          # report
python -m scripts.tag_materials --write  # idempotent, validated updates
"""

import argparse
from collections import Counter
import json

from tuidungeon.content.materials import curated_material_tags
from tuidungeon.content.packs import PROJECT_ROOT, PackStore
from tuidungeon.content.schemas import MODELS


def collect_updates():
    updates = []
    for root in (PROJECT_ROOT / "packs/base", PROJECT_ROOT / "tuidungeon/content/data"):
        for category in ("tiles", "objects", "equipment", "points_of_interest", "traps"):
            for path in sorted((root / category).rglob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                tags = raw.get("tags", [])
                additions = curated_material_tags(raw["id"], tags) - set(tags)
                if additions:
                    raw["tags"] = tags + sorted(additions)
                    # Validate before touching any files, retaining author fields.
                    MODELS[category].model_validate(raw)
                    updates.append((path, category, raw))
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    updates = collect_updates()
    for path, category, raw in updates:
        if args.write:
            PackStore.atomic_json(path, raw)
    print(
        "Изменено" if args.write else "Будет изменено",
        len(updates),
        "файлов:",
        dict(Counter(c for _, c, _ in updates)),
    )


if __name__ == "__main__":
    main()
