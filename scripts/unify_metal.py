"""Merge bundled metal components, preserving copies and legacy references.

python -m scripts.unify_metal --write
Without --write, report pending changes. Repeating is safe.
"""

import argparse
from copy import deepcopy
from datetime import datetime
import json
import shutil

from tuidungeon.content.packs import PROJECT_ROOT
from tuidungeon.domain.definitions import EquipmentDefinition

ALIASES = {f"base:{name}": "base:metal" for name in ("iron", "steel", "metal_scrap")}


def rewrite(value):
    if isinstance(value, str):
        return ALIASES.get(value, value)
    if isinstance(value, list):
        return [rewrite(v) for v in value]
    if isinstance(value, dict):
        result = {k: (v if k == "params" else rewrite(v)) for k, v in value.items()}
        if isinstance(result.get("items"), list) and all(
            isinstance(v, str) for v in result["items"]
        ):
            result["items"] = list(dict.fromkeys(result["items"]))
        return result
    return value


def changes():
    root = PROJECT_ROOT
    source = root / "packs/base/equipment/crafting/metal.json"
    metal = json.loads(
        (source if source.exists() else source.with_name("iron.json")).read_text()
    )
    metal.update(
        id="metal",
        name="Металл",
        description="Универсальный металлический компонент для ремёсел, строительства и разбора. Заменяет железо, сталь и металлический лом.",
        weight=0.3,
        tags=["metal"],
    )
    pending = {}
    removed = []
    for base in (root / "packs", root / "tuidungeon/content/data"):
        for path in base.rglob("*.json"):
            if path.parent.name == "symbols":
                continue
            raw = json.loads(path.read_text())
            if (
                (base.name != "packs" or path.is_relative_to(root / "packs/base"))
                and path.stem in {"iron", "metal_scrap", "steel"}
                and "equipment" in path.parts
            ):
                removed.append(path)
                continue
            updated = rewrite(raw)
            if updated != raw:
                pending[path] = updated
    for path in (source, root / "tuidungeon/content/data/equipment/metal.json"):
        document = (
            metal
            if path == source
            else {
                key: value
                for key, value in metal.items()
                if key == "schema_version"
                or key in EquipmentDefinition.__dataclass_fields__
            }
        )
        if not path.exists() or json.loads(path.read_text()) != document:
            pending[path] = document
    path = root / "tuidungeon/content/compatibility.json"
    compatibility = json.loads(path.read_text())
    updated = deepcopy(compatibility)
    for ref in ALIASES:
        updated["aliases"]["equipment"][ref] = {
            "ref": "base:metal",
            "legacy": metal,
            "overrides": {},
        }
    if updated != compatibility:
        pending[path] = updated
    return pending, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    pending, removed = changes()
    print(f"Изменений: {len(pending)}; удаляемых дублей: {len(removed)}")
    if not args.write or not (pending or removed):
        return
    backup = (
        PROJECT_ROOT
        / "backups"
        / ("metal-merge-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    )
    for path in [*pending, *removed]:
        if path.exists():
            target = backup / path.relative_to(PROJECT_ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for path, raw in pending.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temp.replace(path)
    for path in removed:
        path.unlink()
    print("Резервная копия:", backup.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
