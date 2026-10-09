"""Create a spaced showcase that expands every interactive tile's brush recipe."""

import argparse
from math import ceil
from pathlib import Path

from scripts.build_developer_map import COLUMNS, PACK_ID, SPACING
from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import ArtDocument, Manifest, MapDocument, TileDocument

MAP_ID = "all_interactive_tiles"
SECTIONS = (
    ("door", "ДВЕРИ"),
    ("item", "ПРЕДМЕТЫ"),
    ("interaction", "ВЗАИМОДЕЙСТВИЯ"),
    ("trap", "ЛОВУШКИ"),
    ("light", "ИСТОЧНИКИ СВЕТА"),
    ("transition", "ПЕРЕХОДЫ"),
)


def primary_mechanic(tile):
    # A mixed tile appears once, but retains all its mechanics.
    return next(
        (
            key
            for key in ("door", "trap", "interaction", "item", "light", "transition")
            if getattr(tile.brush, key)
        ),
        None,
    )


def build_documents(store):
    groups = {key: [] for key, _ in SECTIONS}
    for (category, ref), tile in store.documents.items():
        if ref.startswith("dev:"):
            continue
        if category in ("equipment", "points_of_interest", "traps"):
            source = tile
            tile = TileDocument(
                id=source.id,
                name=source.name,
                description=source.description,
                glyph=source.glyph,
                foreground=source.foreground,
                background=source.background,
                group=source.group,
                tags=[tag for tag in source.tags if tag != "поджог"],
                brush={
                    {
                        "equipment": "item",
                        "points_of_interest": "interaction",
                        "traps": "trap",
                    }[category]: ref,
                    "underlay": "base:floor",
                    "light": getattr(source, "map_light", None),
                },
            )
        elif category not in ("tiles", "objects"):
            continue
        mechanic = primary_mechanic(tile)
        if mechanic:
            groups[mechanic].append((ref, tile))
    width = 2 * 4 + (COLUMNS - 1) * SPACING + 1
    placements = {
        key: []
        for key in (
            "equipment",
            "points_of_interest",
            "traps",
            "lights",
            "transitions",
            "doors",
            "objects",
        )
    }
    samples, labels = [], []
    heading_y = 2
    for key, title in SECTIONS:
        tiles = sorted(groups[key], key=lambda pair: (pair[1].group, pair[0]))
        if not tiles:
            continue
        labels.append((2, heading_y, f"{title} ({len(tiles)})", 14))
        for index, (ref, tile) in enumerate(tiles):
            x = 4 + index % COLUMNS * SPACING
            y = heading_y + 4 + index // COLUMNS * SPACING
            number = len(samples) + 1
            samples.append((number, ref, tile, x, y))
            labels.append((x - 1, y - 1, f"{number:03d}", 8))
            brush = tile.brush
            for category, reference in (
                ("equipment", brush.item),
                ("points_of_interest", brush.interaction),
                ("traps", brush.trap),
            ):
                if reference:
                    placements[category].append(
                        dict(id=f"tile_{category}_{x}_{y}", ref=reference, x=x, y=y)
                    )
            if not (brush.item or brush.interaction or brush.trap or brush.door):
                placements["objects"].append(
                    dict(id=f"tile_objects_{x}_{y}", ref=ref, x=x, y=y)
                )
            if brush.door:
                placements["doors"].append(
                    dict(id=f"tile_doors_{x}_{y}", ref=ref, x=x, y=y)
                )
            if brush.light:
                placements["lights"].append(
                    dict(
                        id=f"tile_lights_{x}_{y}",
                        x=x,
                        y=y,
                        **brush.light.model_dump(),
                        enabled=True,
                    )
                )
            if brush.transition:
                placements["transitions"].append(
                    dict(
                        id=f"tile_transitions_{x}_{y}",
                        x=x,
                        y=y,
                        target="dev:" + MAP_ID,
                    )
                )
        heading_y += 6 + ceil(len(tiles) / COLUMNS) * SPACING
    height = heading_y + 2
    if height > 256:
        raise ValueError("Тайлы не помещаются на одну карту; разделите полигон")
    tiles, walkability, blocks_sight = [], [], []
    for y in range(height):
        border = [x in (0, width - 1) or y in (0, height - 1) for x in range(width)]
        tiles.append(["base:wall" if wall else "base:floor" for wall in border])
        walkability.append([not wall for wall in border])
        blocks_sight.append(border)
    for _, ref, tile, x, y in samples:
        # Same as painting into an empty floor cell in Studio: item graphics
        # belong to the instance, all other tiles keep their authored image.
        tiles[y][x] = tile.brush.underlay or "base:floor"
        walkability[y][x] = True if tile.brush.door else tile.walkable
        blocks_sight[y][x] = False if tile.brush.door else tile.blocks_sight
    cells = [[None] * width for _ in range(height)]
    for x, y, text, color in labels:
        for offset, char in enumerate(text):
            cells[y][x + offset] = dict(char=char, foreground=color)
    art = ArtDocument.model_validate(
        dict(
            id=MAP_ID + "_labels",
            name="Подписи интерактивных тайлов",
            width=width,
            height=height,
            layers=[dict(id="labels", name="Разделы и номера", cells=cells)],
        )
    )
    level = MapDocument.model_validate(
        dict(
            id=MAP_ID,
            name="Полигон разработчика: интерактивные тайлы",
            description="Каждый тайл с игровой механикой размещён один раз, со всеми свойствами кисти. "
            "Между образцами три пустые клетки; номера и координаты: packs/dev/interactive_tiles.md. "
            "G: подобрать; Enter: взаимодействовать; вход: ловушка или переход. "
            "Переходы возвращают к старту этой карты. Тусклый фон позволяет видеть работу источников света.",
            width=width,
            height=height,
            tiles=tiles,
            walkability=walkability,
            blocks_sight=blocks_sight,
            spawn=dict(x=2, y=4),
            ambient_light="dim",
            decorations=[dict(id="tile_labels", ref="dev:" + art.id, x=0, y=0)],
            **placements,
        )
    )
    dependencies = (
        set(store.manifests[PACK_ID].dependencies)
        if PACK_ID in store.manifests
        else {"base"}
    )
    dependencies.update(ref.split(":", 1)[0] for _, ref, _, _, _ in samples)
    manifest = Manifest.model_validate(
        dict(
            id=PACK_ID,
            name="Полигон разработчика",
            version="1.0.0",
            dependencies=sorted(dependencies),
        )
    )
    return manifest, level, art, samples


def guide(level, samples):
    lines = [
        "# Полигон интерактивных тайлов",
        "",
        f"Карта `dev:{MAP_ID}`, {level.width}×{level.height}; {len(samples)} образцов.",
        "Между тайлами три пустые клетки. Номер расположен над образцом.",
        "Образцы сгруппированы по основной механике, внутри — по группе и ID.",
        "Если тайл совмещает несколько механик, включены все: например, огонь одновременно светит и наносит урон.",
        "",
        "```bash",
        f"./run.sh --test-map dev:{MAP_ID}",
        f"./run.sh --terminal --test-map dev:{MAP_ID}",
        "# Windows:",
        rf".\run.bat --test-map dev:{MAP_ID}",
        "```",
        "",
        "В студии: пакет `dev` → карты → «Полигон разработчика: интерактивные тайлы».",
        "G на клетке предмета: подобрать. Enter рядом с точкой интереса: взаимодействовать.",
        "Двери: Enter рядом. + закрыта, X заперта, / открыта; материал обозначен цветом. Долгий взлом: Space — ход, Backspace — отмена.",
        "Ловушки срабатывают при входе и наносят настоящий урон; скрытые сохраняют скрытость.",
        "Порталы, лестницы и телепорты возвращают к старту этого же полигона, сохраняя состояние образцов.",
        "Общий свет тусклый: источники создают яркие области. Для проверки тьмы можно переключить общий свет карты в студии.",
        "У предметных кистей рисунок принадлежит подбираемому предмету; после подбора остаётся пол.",
        "Перезапуск теста восстанавливает размещения. Все эффекты используют обычные правила движка.",
        "",
        "Пересборка после добавления новых тайлов (заменяет только файлы этого полигона):",
        "",
        "```bash",
        ".venv/bin/python -m scripts.build_developer_tiles --force",
        "# Windows:",
        r".venv\Scripts\python.exe -m scripts.build_developer_tiles --force",
        "```",
        "",
        "Для переноса скопируйте `packs/dev/` и пакеты из его `manifest.json`.",
        "Координаты начинаются с нуля и совпадают с инспектором.",
        "",
        "| № | Группа | Тайл | Ссылка | Механики | X | Y |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for number, ref, tile, x, y in samples:
        mechanics = []
        if tile.brush.door:
            spec = tile.brush.door
            mechanics.append(
                f"Дверь: {spec.material}, {spec.state}, {'заперта' if spec.locked else 'не заперта'}, {spec.lock_quality}/{spec.lock_complexity}"
            )
        for key, name in (
            ("item", "Предмет"),
            ("interaction", "Взаимодействие"),
            ("trap", "Ловушка"),
        ):
            if getattr(tile.brush, key):
                mechanics.append(name + ": `" + getattr(tile.brush, key) + "`")
        if tile.brush.light:
            mechanics.append(
                f"Свет: {tile.brush.light.bright_radius}/{tile.brush.light.radius}"
            )
        if tile.brush.transition:
            mechanics.append("Переход к старту")
        group, name = (
            text.replace("|", "\\|").replace("\n", " ")
            for text in (tile.group, tile.name)
        )
        lines.append(
            f"| {number:03d} | {group} | {name} | `{ref}` | {'; '.join(mechanics)} | {x} | {y} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument(
        "--force", action="store_true", help="Пересобрать полигон тайлов"
    )
    args = parser.parse_args()
    store = PackStore(args.packs_dir)
    manifest, level, art, samples = build_documents(store)
    root = store.root / PACK_ID
    writes = {
        root / "maps" / f"{MAP_ID}.json": level,
        root / "art" / f"{art.id}.art.json": art,
    }
    if not args.force and any(
        p.exists() for p in (*writes, root / "interactive_tiles.md")
    ):
        parser.error("Полигон уже существует; для пересборки укажите --force")
    candidate = dict(store.documents)
    candidate["maps", "dev:" + MAP_ID] = level
    candidate["art", "dev:" + art.id] = art
    manifests = dict(store.manifests)
    manifests[PACK_ID] = manifest
    store.validate_references(candidate, manifests)
    for path, document in {root / "manifest.json": manifest, **writes}.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        store.atomic_json(path, document.model_dump(mode="json"))
    (root / "interactive_tiles.md").write_text(guide(level, samples), encoding="utf-8")
    print(
        f"Создана карта dev:{MAP_ID}: {len(samples)} тайлов, {level.width}×{level.height}"
    )


if __name__ == "__main__":
    main()
