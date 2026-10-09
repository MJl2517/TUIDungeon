"""Build a reproducible showcase from all installed storage templates."""

import argparse
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import ArtDocument, Manifest, MapDocument

PACK_ID = "dev"
MAP_ID = "all_containers"
COLUMNS = 6
SPACING = 6
CONTENTS = (
    ("base:rations", 3),
    ("base:oil", 2),
    ("base:healing_potion", 1),
)


@dataclass(frozen=True)
class Sample:
    number: int
    category: str
    ref: str
    name: str
    personal: bool
    capacity: float
    x: int
    y: int


def build_documents(store: PackStore):
    templates = sorted(
        (
            (category, ref, document)
            for (category, ref), document in store.documents.items()
            if category in ("objects", "points_of_interest")
            and document.storage is not None
        ),
        key=lambda entry: (entry[2].name.casefold(), entry[1], entry[0]),
    )
    if not templates:
        raise ValueError("Не найдены шаблоны контейнеров с storage")
    width = 9 + (COLUMNS - 1) * SPACING
    placements = {"objects": [], "points_of_interest": []}
    samples, labels = [], []
    heading_y = 2
    for personal, title in (
        (False, "ЛУТОВЫЕ: ТОЛЬКО ЗАБИРАТЬ"),
        (True, "ЛИЧНЫЕ: КЛАСТЬ И ЗАБИРАТЬ"),
    ):
        labels.append((2, heading_y, title, 14))
        for index, (category, ref, document) in enumerate(templates):
            x = 4 + index % COLUMNS * SPACING
            y = heading_y + 4 + index // COLUMNS * SPACING
            number = len(samples) + 1
            # Capacity and contents are local test settings, not template edits.
            storage = dict(
                personal=personal,
                capacity=max(1000, document.storage.capacity),
                contents=[
                    dict(item=item, quantity=quantity) for item, quantity in CONTENTS
                ],
            )
            placements[category].append(
                dict(
                    id=f"container_{number:03d}",
                    ref=ref,
                    x=x,
                    y=y,
                    overrides=dict(storage=storage),
                )
            )
            samples.append(
                Sample(
                    number,
                    category,
                    ref,
                    document.name,
                    personal,
                    storage["capacity"],
                    x,
                    y,
                )
            )
            labels.append((x - 1, y - 1, f"{number:03d}", 8))
        heading_y += 6 + ceil(len(templates) / COLUMNS) * SPACING
    height = heading_y + 2
    if height > 256:
        raise ValueError("Контейнеры не помещаются на одну карту; разделите полигон")
    walls = [
        [x in (0, width - 1) or y in (0, height - 1) for x in range(width)]
        for y in range(height)
    ]
    cells = [[None] * width for _ in range(height)]
    for x, y, text, color in labels:
        for offset, char in enumerate(text):
            cells[y][x + offset] = dict(char=char, foreground=color)
    art = ArtDocument.model_validate(
        dict(
            id=MAP_ID + "_labels",
            name="Подписи полигона контейнеров",
            width=width,
            height=height,
            layers=[dict(id="labels", name="Разделы и номера", cells=cells)],
        )
    )
    level = MapDocument.model_validate(
        dict(
            id=MAP_ID,
            name="Полигон разработчика: все контейнеры",
            description=(
                "Все шаблоны storage: сверху лутовые, снизу личные. "
                "В каждом 3 пайка, 2 масла и 1 зелье лечения. Enter рядом: открыть; "
                "Tab: колонка; Enter/F5: перенести; Backspace: закрыть. "
                "Номера и координаты: packs/dev/containers.md."
            ),
            width=width,
            height=height,
            tiles=[
                ["base:wall" if wall else "base:floor" for wall in row] for row in walls
            ],
            # Object geometry is compiled separately from these floor masks.
            walkability=[[not wall for wall in row] for row in walls],
            blocks_sight=walls,
            spawn=dict(x=2, y=4),
            ambient_light="bright",
            decorations=[dict(id="labels", ref=f"dev:{art.id}", x=0, y=0)],
            **placements,
        )
    )
    existing = store.manifests.get(PACK_ID) or Manifest(
        id=PACK_ID, name="Полигон разработчика", version="1.0.0"
    )
    dependencies = set(existing.dependencies) | {"base"}
    dependencies.update(sample.ref.split(":", 1)[0] for sample in samples)
    dependencies.discard(PACK_ID)
    manifest = existing.model_copy(update={"dependencies": sorted(dependencies)})
    return manifest, level, art, samples


def guide(level, samples):
    lines = [
        "# Полигон всех контейнеров",
        "",
        f"Карта `dev:{MAP_ID}`, {level.width}×{level.height}: "
        f"{len(samples) // 2} шаблонов, {len(samples)} размещений.",
        "Каждый шаблон представлен дважды: верхний раздел — лутовый, нижний — личный.",
        "Между соседними образцами пять пустых клеток. Номер расположен сверху.",
        "",
        "```bash",
        f"./run.sh --test-map dev:{MAP_ID}",
        f"./run.sh --terminal --test-map dev:{MAP_ID}",
        "# Windows:",
        rf".\run.bat --test-map dev:{MAP_ID}",
        "```",
        "",
        "В студии: пакет `dev` → карты → «Полигон разработчика: все контейнеры» → тестировать.",
        "Карта полностью освещена; врагов, ловушек и автоматических переходов нет.",
        "",
        "## Что проверить",
        "",
        "1. Подойти по WASD к контейнеру по одной из четырёх сторон и нажать Enter.",
        "2. Tab или ←/→ переключают колонки, ↑/↓ выбирают вещь, Enter/F5 переносят.",
        "3. Для пайков (3) и масла (2) появляется выбор количества; зелье (1) переносится сразу.",
        "4. Лутовые контейнеры разрешают только забирать; личные — также класть обратно.",
        "5. Проверить вес в обеих колонках. Вместимость каждого образца не меньше 1000 кг; нагрузка героя обычная.",
        "6. Закрыть окно Backspace, уйти и вернуться: содержимое должно сохраниться.",
        "7. Перезапустить тест: во всех контейнерах снова исходные предметы.",
        "",
        "Все образцы содержат 3 пайка, 2 масла и 1 зелье лечения. "
        "Содержимое, вместимость и режим заданы в свойствах размещений; исходные шаблоны не меняются.",
        "Графика и механики принадлежат исходным объектам и точкам интереса, копий тайлов нет.",
        "",
        "## Обновление после добавления контейнеров",
        "",
        "Генератор автоматически находит все установленные `objects` и `points_of_interest` с `storage`.",
        "Пересборка заменяет карту этого полигона, её подписи и этот справочник:",
        "",
        "```bash",
        "python -m scripts.build_developer_containers --force",
        "```",
        "",
        "Без `--force` существующий полигон защищён от перезаписи. "
        "Для переноса нужны `packs/dev/` и пакеты из его `manifest.json`.",
        "",
        "## Образцы",
        "",
        "Координаты начинаются с нуля, как в инспекторе студии.",
        "",
        "| № | Контейнер | Режим | Ссылка | X | Y |",
        "| ---: | --- | --- | --- | ---: | ---: |",
    ]
    for sample in samples:
        mode = "Личный" if sample.personal else "Лутовый"
        lines.append(
            f"| {sample.number:03d} | {sample.name} | {mode} | "
            f"`{sample.ref}` | {sample.x} | {sample.y} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--force", action="store_true", help="Пересобрать полигон")
    args = parser.parse_args()
    store = PackStore(args.packs_dir)
    manifest, level, art, samples = build_documents(store)
    root = store.root / PACK_ID
    writes = {
        root / "maps" / f"{MAP_ID}.json": level,
        root / "art" / f"{art.id}.art.json": art,
    }
    guide_path = root / "containers.md"
    if not args.force and any(path.exists() for path in (*writes, guide_path)):
        parser.error("Полигон уже существует; для пересборки укажите --force")
    candidate, manifests = dict(store.documents), dict(store.manifests)
    candidate["maps", f"dev:{MAP_ID}"] = level
    candidate["art", f"dev:{art.id}"] = art
    manifests[PACK_ID] = manifest
    store.validate_references(candidate, manifests)
    if manifest != store.manifests.get(PACK_ID):
        writes[root / "manifest.json"] = manifest
    for path, document in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        store.atomic_json(path, document.model_dump(mode="json"))
    guide_path.write_text(guide(level, samples), encoding="utf-8")
    print(
        f"Создана карта dev:{MAP_ID}: {len(samples)} контейнеров, {level.width}×{level.height}"
    )


if __name__ == "__main__":
    main()
