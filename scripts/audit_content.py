"""Read-only content audit: python -m scripts.audit_content [--json]."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from tuidungeon.content.migrations import compatibility
from tuidungeon.content.packs import PackStore


def audit(store):
    errors, warnings = [], []
    names = defaultdict(list)
    for (category, ref), document in store.documents.items():
        if category in ("tiles", "objects", "equipment", "traps", "points_of_interest"):
            names[document.name.casefold()].append(f"{category}/{ref}")
        if category == "tiles" and any(
            (
                document.brush.item,
                document.brush.trap,
                document.brush.interaction,
                document.brush.door,
            )
        ):
            errors.append(f"{category}/{ref}: механический объект продублирован тайлом")
        if (
            category in compatibility()["aliases"]
            and ref in compatibility()["aliases"][category]
        ):
            errors.append(f"{category}/{ref}: удалённый дубль снова попал в библиотеку")
        if category == "equipment":
            if document.category is None:
                warnings.append(
                    f"{ref}: тип снаряжения определяется устаревшим способом"
                )
            if document.category == "weapons" and not document.weapon_damage:
                warnings.append(f"{ref}: оружию не задан урон")
            if "artifacts" in document.tags and not document.properties:
                warnings.append(f"{ref}: особые свойства артефакта пока не заданы")
    for name, references in names.items():
        if len(references) > 1:
            warnings.append(f"Одинаковое имя «{name}»: {', '.join(references)}")
    return {
        "counts": dict(sorted(Counter(c for c, _ in store.documents).items())),
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(PackStore(args.packs_dir) if args.packs_dir else PackStore())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Документы:", result["counts"])
        for level in ("errors", "warnings"):
            print(f"{level}: {len(result[level])}")
            for message in result[level]:
                print("  " + message)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
