"""Build a spaced, playable showcase from installed interactive content."""

import argparse
from math import ceil
from pathlib import Path

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore, runtime_key
from tuidungeon.content.schemas import ArtDocument, Manifest, MapDocument
from tuidungeon.domain.equipment import Equipment

PACK_ID = "dev"
MAP_ID = "all_items"
COLUMNS = 12
SPACING = 4  # Three empty cells between adjacent objects, including diagonals.


def build_documents(store):
    catalog = store.runtime_catalog()
    groups = [
        ("weapons", "WEAPONS", "Вооружение"),
        ("armor", "ARMOR", "Доспехи"),
        ("consumables", "CONSUMABLES", "Расходники"),
        ("tools", "TOOLS", "Инструменты"),
    ]
    equipment = {key: [] for key, _, _ in groups}
    other = {"points_of_interest": [], "traps": []}
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
    ]
    width = 2 * 4 + (COLUMNS - 1) * SPACING + 1
    placements = {"equipment": [], "points_of_interest": [], "traps": []}
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
            placements[category].append(
                dict(id=f"sample_{number:03d}", ref=ref, x=x, y=y)
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
            description="Все предметы, точки взаимодействия и ловушки установленных пакетов. "
            "Номера и координаты: packs/dev/README.md. Между объектами три пустые клетки. "
            "Предметы подбираются с их клетки, взаимодействия доступны по Enter рядом; "
            "ловушки срабатывают при входе. Перезапуск восстанавливает экземпляры.",
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
        "Второй полигон: [все интерактивные тайлы](interactive_tiles.md).",
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
        "Предметы: встать на клетку и нажать G (в браузерном тесте — «Подобрать»), затем тестировать в инвентаре.",
        "Точки интереса: Enter с клетки или соседней клетки. Ловушки: вход на клетку.",
        "Скрытые ловушки сохраняют скрытость; найти их помогут номера ниже.",
        "Ловушки наносят настоящий урон. Долгий отдых восстанавливает HP; перезапуск теста возвращает все объекты.",
        "Декоративные тайлы без механики сюда не включены. Предметы лежат поверх пола и не оставляют рисунок после подбора.",
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
