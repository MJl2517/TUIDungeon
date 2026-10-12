"""Build a spaced, playable showcase from all installed map elements."""

import argparse
from math import ceil
from pathlib import Path

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore, runtime_key
from tuidungeon.content.schemas import ArtDocument, Manifest, MapDocument
from tuidungeon.domain.equipment import Equipment

PACK_ID = "dev"
MAP_ID = "all_items"
COLUMNS = 16
SPACING = 4  # Three empty cells between adjacent objects, including diagonals.


def build_documents(store):
    catalog = store.runtime_catalog()
    groups = [
        ("weapons", "WEAPONS", "Вооружение"),
        ("armor", "ARMOR", "Доспехи"),
        ("consumables", "CONSUMABLES", "Расходники"),
        ("tools", "TOOLS", "Инструменты"),
        ("materials", "MATERIALS", "Материалы"),
    ]
    equipment = {key: [] for key, _, _ in groups}
    other = {
        key: []
        for key in ("points_of_interest", "traps", "objects", "monsters", "tiles")
    }
    for (category, ref), document in sorted(store.documents.items()):
        if ref.startswith(PACK_ID + ":"):
            continue
        if category == "equipment":
            kind = Equipment.create(catalog.equipment[runtime_key(ref)]).category
            equipment[kind].append((ref, document))
        elif category in other:
            other[category].append((ref, document))
    sections = [
        ("equipment", title, name, equipment[key]) for key, title, name in groups
    ] + [
        (
            "points_of_interest",
            "INTERACTIONS",
            "Точки взаимодействия",
            other["points_of_interest"],
        ),
        ("traps", "TRAPS - ENTER TO TRIGGER", "Ловушки", other["traps"]),
        (
            "objects",
            "WORLD OBJECTS AND STATIONS",
            "Объекты и станции",
            other["objects"],
        ),
        ("monsters", "CREATURES", "Существа", other["monsters"]),
        ("tiles", "SURFACES AND WALLS", "Поверхности и стены", other["tiles"]),
    ]
    width = 2 * 4 + (COLUMNS - 1) * SPACING + 1
    placements = {
        key: []
        for key in (
            "equipment",
            "points_of_interest",
            "traps",
            "objects",
            "monsters",
            "doors",
            "lights",
            "transitions",
        )
    }
    surfaces = []
    labels, entries, dependencies = [], [], {"base"}
    heading_y = 2
    for category, title, name, documents in sections:
        if not documents:
            continue
        labels.append((2, heading_y, f"{title} ({len(documents)})", 14))
        for index, (ref, document) in enumerate(documents):
            x = 4 + index % COLUMNS * SPACING
            y = heading_y + 4 + index // COLUMNS * SPACING
            number = len(entries) + 1
            placement = dict(id=f"sample_{number:03d}", ref=ref, x=x, y=y)
            if category == "tiles":
                surfaces.append((ref, document, x, y))
            else:
                layer = (
                    "doors"
                    if category == "objects" and document.brush.door
                    else category
                )
                placements[layer].append(placement)
            if category == "objects":
                if document.brush.light and not document.light_fixture:
                    placements["lights"].append(
                        dict(
                            id=f"sample_light_{number:03d}",
                            x=x,
                            y=y,
                            **document.brush.light.model_dump(),
                            enabled=True,
                        )
                    )
                if document.brush.transition:
                    placements["transitions"].append(
                        dict(
                            id=f"sample_transition_{number:03d}",
                            x=x,
                            y=y,
                            target=f"{PACK_ID}:{MAP_ID}",
                        )
                    )
            labels.append((x - 1, y - 1, f"{number:03d}", 8))
            entries.append((number, name, document.name, ref, x, y))
            dependencies.add(ref.split(":", 1)[0])
        heading_y += 6 + ceil(len(documents) / COLUMNS) * SPACING
    height = heading_y + 2
    if height > 256:
        raise ValueError(
            "Контент не помещается в одну карту; разделите каталог на несколько карт"
        )
    tiles, walkability, blocks_sight = [], [], []
    for y in range(height):
        border = [x in (0, width - 1) or y in (0, height - 1) for x in range(width)]
        tiles.append(["base:wall" if wall else "base:floor" for wall in border])
        walkability.append([not wall for wall in border])
        blocks_sight.append(border)
    for ref, document, x, y in surfaces:
        tiles[y][x] = ref
        walkability[y][x] = document.walkable
        blocks_sight[y][x] = document.blocks_sight
    cells = [[None] * width for _ in range(height)]
    for x, y, text, color in labels:
        for offset, char in enumerate(text):
            cells[y][x + offset] = dict(char=char, foreground=color)
    art = ArtDocument.model_validate(
        dict(
            id="all_items_labels",
            name="Подписи полигона",
            width=width,
            height=height,
            layers=[dict(id="labels", name="Разделы и номера", cells=cells)],
        )
    )
    level = MapDocument.model_validate(
        dict(
            id=MAP_ID,
            name="Полигон разработчика: все предметы",
            description="Все размещаемые элементы установленных пакетов: предметы, точки взаимодействия, "
            "ловушки, объекты, станции, двери, существа, поверхности и стены. "
            "Номера и координаты: packs/dev/README.md. Между объектами три пустые клетки. "
            "Предметы подбираются с их клетки, взаимодействия доступны по Enter рядом; "
            "ловушки срабатывают при входе. Переходы возвращают к старту. Перезапуск восстанавливает экземпляры.",
            width=width,
            height=height,
            tiles=tiles,
            walkability=walkability,
            blocks_sight=blocks_sight,
            spawn=dict(x=2, y=4),
            ambient_light="bright",
            decorations=[dict(id="labels", ref="dev:all_items_labels", x=0, y=0)],
            **placements,
        )
    )
    manifest = Manifest.model_validate(
        dict(
            id=PACK_ID,
            name="Полигон разработчика",
            version="1.0.0",
            dependencies=sorted(
                dependencies
                | (
                    set(store.manifests[PACK_ID].dependencies)
                    if PACK_ID in store.manifests
                    else set()
                )
            ),
        )
    )
    return manifest, level, art, entries


def guide(entries, level):
    lines = [
        "# Полигон разработчика",
        "",
        "Другие полигоны: [интерактивные тайлы и свет](interactive_tiles.md), [контейнеры](containers.md).",
        "Единый сценарий roadmap: [dev:roadmap_lab](roadmap_lab.md). Старый полигон: `dev:crafting_lab`.",
        "",
        f"Карта `dev:all_items`, {level.width}×{level.height}. Яркий общий свет, внешние стены, открытые проходы.",
        "Между любыми размещёнными объектами не менее трёх пустых клеток.",
        "",
        "```bash",
        "./run.sh --test-map dev:all_items",
        "# Терминал вместо окна:",
        "./run.sh --terminal --test-map dev:all_items",
        "# Windows:",
        r".\run.bat --test-map dev:all_items",
        "```",
        "",
        "В студии выберите пакет `dev`, раздел карт и «Полигон разработчика: все предметы».",
        "Предметы: встать на клетку и нажать G, затем тестировать в инвентаре.",
        "Точки интереса: Enter с клетки или соседней клетки. Ловушки: вход на клетку.",
        "Скрытые ловушки сохраняют скрытость; найти их помогут номера ниже.",
        "Ловушки наносят настоящий урон. Долгий отдых требует кровати, лежанки или разложенного спального мешка; перезапуск теста возвращает все объекты.",
        f"Всего {len(entries)} образцов: все предметы, точки интереса, ловушки, объекты, станции, двери, существа и поверхности установленных пакетов (кроме `dev`).",
        "Мебель, станции и двери стоят поверх отдельного пола. После подбора или разборки пол сохраняется.",
        "Двери открываются через Enter рядом. Источники воды, станции и разбираемая мебель используют обычные действия окружения.",
        "Порталы и лестницы возвращают к старту этой же карты, сохраняя состояние образцов.",
        "Для проверки динамического света используйте второй полигон с тусклым фоном: здесь общий свет яркий.",
        "Рецепты, заклинания и способности не являются размещаемыми объектами: они доступны через соответствующие игровые меню.",
        "",
        "Добавили контент? Сохраните его в студии, остановите тест и пересоберите полигон:",
        "",
        "```bash",
        ".venv/bin/python -m scripts.build_developer_map --force",
        "# Windows:",
        r".venv\Scripts\python.exe -m scripts.build_developer_map --force",
        "```",
        "",
        "Пересборка заменяет только сгенерированные файлы этого полигона и таблицу ниже.",
        "Для переноса скопируйте весь `packs/dev/` вместе с пакетами из `manifest.json`.",
        "",
        "Координаты начинаются с нуля и совпадают с инспектором карты.",
        "",
        "| № | Раздел | Название | Ссылка | X | Y |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for number, category, name, ref, x, y in entries:
        name = name.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {number:03d} | {category} | {name} | `{ref}` | {x} | {y} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument(
        "--force", action="store_true", help="Пересобрать существующий полигон"
    )
    args = parser.parse_args()
    store = PackStore(args.packs_dir)
    manifest, level, art, entries = build_documents(store)
    root = store.root / PACK_ID
    writes = {
        root / "manifest.json": manifest,
        root / "maps" / "all_items.json": level,
        root / "art" / "all_items_labels.art.json": art,
    }
    if not args.force and any(path.exists() for path in (*writes, root / "README.md")):
        parser.error("Полигон уже существует. Для пересборки укажите --force")
    candidate = dict(store.documents)
    candidate[("maps", "dev:all_items")] = level
    candidate[("art", "dev:all_items_labels")] = art
    manifests = dict(store.manifests)
    manifests[PACK_ID] = manifest
    store.validate_references(candidate, manifests)
    for path, document in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        store.atomic_json(path, document.model_dump(mode="json"))
    (root / "README.md").write_text(guide(entries, level), encoding="utf-8")
    print(
        f"Создана карта dev:all_items: {len(entries)} объектов, {level.width}×{level.height}"
    )


if __name__ == "__main__":
    main()
