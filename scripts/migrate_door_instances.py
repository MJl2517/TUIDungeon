"""Consolidate old presets into five doors; back up every affected source file."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from tuidungeon.content.packs import PackStore, DEFAULT_PACKS, PROJECT_ROOT
from tuidungeon.content.schemas import TileDocument
from tuidungeon.content.migrations import door_alias
from tuidungeon.domain.doors import MATERIALS


def migrate(root=DEFAULT_PACKS, backup_root=None):
    root = Path(root).resolve()
    backup_root = backup_root or PROJECT_ROOT / "backups" / (
        "doors-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    )

    def backup(path):
        target = backup_root / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)

    for material, info in MATERIALS.items():
        identifier = f"door_{material}"
        path = next(
            (
                p
                for p in (root / "base/objects").rglob("*.json")
                if json.loads(p.read_text(encoding="utf-8")).get("id") == identifier
            ),
            root / "base/objects/doors" / f"{identifier}.json",
        )
        if path.exists():
            continue  # Preserve authored base templates on repeat runs.
        doc = TileDocument(
            id=f"door_{material}",
            name=info.name,
            group="Двери",
            tags=["doors", "transparent" if material == "bars" else "opaque"]
            + (["flammable", "wooden"] if material == "wood" else []),
            description="Поставьте дверь, нажмите V и выберите её: состояние, замок и хиты настраиваются для каждого экземпляра.",
            brush={"door": {"material": material}},
        )
        PackStore.atomic_json(path, doc.model_dump(mode="json"))
    store = PackStore(root)
    originals = dict(store.paths)
    changed = 0
    for (category, ref), path in originals.items():
        if category == "maps":
            raw = json.loads(path.read_text(encoding="utf-8"))
            migrated = store.get(category, ref).model_dump(mode="json")
            # Only write maps whose references or placements needed conversion.
            from tuidungeon.content.migrations import migrate_map

            if migrate_map(raw) != raw:
                backup(path)
                store.atomic_json(path, migrated)
                changed += 1
        elif category == "tiles" and door_alias(ref):
            backup(path)
            path.unlink()
    PackStore(root)  # Validate the completed transaction before reporting success.
    return changed, backup_root


def main():
    count, backup = migrate()
    print(f"Оставлено пять материалов дверей. Обновлено карт: {count}. Копии: {backup}")


if __name__ == "__main__":
    main()
