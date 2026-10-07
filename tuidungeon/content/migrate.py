"""Non-destructive migration: originals are retained; validate before publishing base."""

import json
from pathlib import Path
import shutil
import tempfile
from .catalog import DEFAULT_ROOT
from .packs import DEFAULT_PACKS, PackStore, REF_FIELDS
from .schemas import MODELS
from ..presentation.art import import_txt
from ..application.engine import test_dungeon


def migrate(root=DEFAULT_PACKS):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "base").exists():
        raise ValueError("base уже существует; миграция не перезаписывает файлы")
    with tempfile.TemporaryDirectory(dir=root, prefix=".migration-") as temporary:
        staging = Path(temporary)
        base = staging / "base"
        for category in MODELS:
            (base / category).mkdir(parents=True)

        def write(category, raw):
            document = MODELS[category].model_validate(raw)
            PackStore.atomic_json(
                base
                / category
                / f"{document.id}{'.art' if category == 'art' else ''}.json",
                document.model_dump(mode="json"),
            )

        PackStore.atomic_json(
            base / "manifest.json",
            {
                "id": "base",
                "name": "Базовое подземелье",
                "version": "1.0.0",
                "dependencies": [],
            },
        )

        def qualify(raw):
            for key, value in list(raw.items()):
                if key in REF_FIELDS and key not in ("target", "tiles") and value:
                    raw[key] = (
                        [f"base:{v}" for v in value]
                        if isinstance(value, list)
                        else f"base:{value}"
                    )

        for category in (
            "equipment",
            "spells",
            "actions",
            "races",
            "classes",
            "backgrounds",
            "monsters",
            "challenges",
        ):
            for path in sorted((DEFAULT_ROOT / category).glob("*.json")):
                raw = json.loads(path.read_text())
                qualify(raw)
                if category == "monsters":
                    raw.update(
                        glyph="g" if raw["id"] == "goblin" else "s",
                        foreground=10 if raw["id"] == "goblin" else 7,
                    )
                write(category, raw)
        arts = Path(__file__).resolve().parents[1] / "assets/art"
        for identifier in ("goblin", "skeleton"):
            art = import_txt(
                (arts / f"{identifier}.ascii.txt").read_text(),
                identifier,
                identifier.title(),
            )
            write("art", art.model_dump(mode="json"))
        write(
            "tiles",
            {
                "id": "floor",
                "name": "Каменный пол",
                "glyph": ".",
                "foreground": 8,
                "walkable": True,
            },
        )
        write(
            "tiles",
            {
                "id": "wall",
                "name": "Каменная стена",
                "glyph": "#",
                "foreground": 7,
                "walkable": False,
                "blocks_sight": True,
            },
        )
        write(
            "traps",
            {
                "id": "spikes",
                "name": "Шипы",
                "glyph": "^",
                "foreground": 9,
                "difficulty": 12,
                "failure": [{"kind": "damage", "dice": "1d4", "amount": 1}],
                "success": [],
            },
        )
        write(
            "points_of_interest",
            {
                "id": "chest",
                "name": "Запертый сундук",
                "glyph": "$",
                "foreground": 11,
                "challenge": "base:locked_chest",
                "description": "Старый сундук. Возможно, внутри осталось золото.",
            },
        )
        write(
            "points_of_interest",
            {
                "id": "shrine",
                "name": "Забытый алтарь",
                "glyph": "&",
                "foreground": 14,
                "challenge": "base:ruined_shrine",
                "description": "На камне вырезаны древние руны.",
            },
        )

        def map_raw(identifier, name, rows, spawn):
            return {
                "id": identifier,
                "name": name,
                "width": len(rows[0]),
                "height": len(rows),
                "tiles": [
                    [f"base:{'wall' if c == '#' else 'floor'}" for c in row]
                    for row in rows
                ],
                "walkability": [[c != "#" for c in row] for row in rows],
                "blocks_sight": [[c == "#" for c in row] for row in rows],
                "spawn": spawn,
            }

        write(
            "maps",
            map_raw(
                "dungeon", "Учебное подземелье", test_dungeon().rows, {"x": 3, "y": 3}
            ),
        )
        rows = ["#" * 24] + ["#" + "." * 22 + "#" for _ in range(12)] + ["#" * 24]
        crypt = map_raw("crypt", "Склеп забытых", rows, {"x": 3, "y": 3})
        for y in range(1, 13):
            if y == 7:
                continue
            crypt["tiles"][y][12] = "base:wall"
            crypt["walkability"][y][12] = False
            crypt["blocks_sight"][y][12] = True
        crypt.update(
            traps=[{"id": "spikes_1", "ref": "base:spikes", "x": 5, "y": 3}],
            points_of_interest=[
                {"id": "chest_1", "ref": "base:chest", "x": 7, "y": 3},
                {"id": "shrine_1", "ref": "base:shrine", "x": 4, "y": 6},
            ],
            monsters=[{"id": "goblin_1", "ref": "base:goblin", "x": 16, "y": 7}],
            equipment=[
                {"id": "potion_1", "ref": "base:healing_potion", "x": 4, "y": 9}
            ],
        )
        write("maps", crypt)
        PackStore(staging).runtime_catalog()
        shutil.move(str(base), str(root / "base"))
    return PackStore(root)


if __name__ == "__main__":
    store = migrate()
    print(
        f"Миграция проверена: {len(store.documents)} документов. Исходники сохранены."
    )
