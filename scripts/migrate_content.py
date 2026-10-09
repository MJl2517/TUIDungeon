"""Migrate old maps with validated references, backups and unchanged-file checks."""

import argparse
from datetime import datetime
from pathlib import Path
import shutil

from tuidungeon.content.migrations import migrate_map
from tuidungeon.content.packs import DEFAULT_PACKS, PROJECT_ROOT, PackStore, Conflict
from tuidungeon.content.schemas import MapDocument


def plan_migration(store):
    writes, candidate = [], dict(store.documents)
    for key, path in store.paths.items():
        if key[0] != "maps":
            continue
        raw = store.read_json(path)
        migrated = migrate_map(raw)
        if raw == migrated:
            continue
        document = MapDocument.model_validate(migrated)
        candidate[key] = document
        writes.append((path, migrated, store.version(path)))
    store.validate_references(candidate, store.manifests)
    return writes


def migrate(root=DEFAULT_PACKS, backup_root=None, *, write=False):
    store = PackStore(root)
    writes = plan_migration(store)
    if not write or not writes:
        return len(writes), None
    backup_root = (
        Path(backup_root)
        if backup_root
        else PROJECT_ROOT
        / "backups"
        / ("content-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    )
    backups = {}
    for path, _, version in writes:
        if store.version(path) != version:
            raise Conflict(f"Файл изменён во время ревизии: {path}")
        destination = backup_root / path.relative_to(store.root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        backups[path] = destination
    completed = []
    try:
        for path, raw, version in writes:
            if store.version(path) != version:
                raise Conflict(f"Файл изменён во время миграции: {path}")
            store.atomic_json(path, raw)
            completed.append((path, store.version(path)))
        PackStore(root)
    except Exception:
        for path, version in completed:
            # Do not undo an external edit that raced with the migration.
            if store.version(path) == version:
                shutil.copy2(backups[path], path)
        raise
    return len(writes), backup_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    count, backup = migrate(args.packs_dir, write=args.write)
    print("Обновлено карт:" if args.write else "Требуют миграции:", count)
    if backup:
        print("Резервная копия:", backup)


if __name__ == "__main__":
    main()
