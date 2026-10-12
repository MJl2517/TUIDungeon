"""Review/write bundled tags and regenerate the complete interaction inventory.

python -m scripts.tag_gameplay          # dry run; no files touched
python -m scripts.tag_gameplay --write  # validated, idempotent author traits + docs
"""

import argparse
from collections import Counter
import json

from tuidungeon.content.gameplay_tags import curated_gameplay_tags, classification
from tuidungeon.content.packs import PROJECT_ROOT, PackStore
from tuidungeon.content.catalog import ContentCatalog, ACTION_KINDS
from tuidungeon.content.schemas import MODELS
from tuidungeon.domain.tags import (
    TAG_CATALOG,
    TAG_GROUPS,
    interaction_tags,
    liquid_tags,
)
from tuidungeon.domain.liquids import LIQUID_NAMES
from tuidungeon.domain.mechanics import mechanics

CATEGORIES = (
    "equipment",
    "spells",
    "actions",
    "monsters",
    "tiles",
    "objects",
    "points_of_interest",
    "traps",
    "challenges",
    "races",
    "classes",
    "backgrounds",
    "recipes",
)


def sources():
    for root in (PROJECT_ROOT / "packs/base", PROJECT_ROOT / "tuidungeon/content/data"):
        for category in CATEGORIES:
            for path in sorted((root / category).rglob("*.json")):
                yield path, category, json.loads(path.read_text(encoding="utf-8"))


def collect_updates():
    updates = []
    for path, category, raw in sources():
        # Not every entity needs an authored tag field (race/class/recipe).
        if "tags" not in MODELS[category].model_fields:
            continue
        desired = curated_gameplay_tags(category, raw)
        previous = raw.get("tags", ())
        if desired != set(previous):
            updated = {
                **raw,
                "tags": [
                    *[tag for tag in previous if tag in desired],
                    *sorted(desired - set(previous)),
                ],
            }
            if "tuidungeon/content/data" in path.as_posix():
                ContentCatalog()._parse(
                    category,
                    {k: v for k, v in updated.items() if k != "schema_version"},
                    ACTION_KINDS,
                    frozenset(mechanics.entries),
                )
            else:
                MODELS[category].model_validate(updated)
            updates.append((path, category, updated))
    return updates


def effect_rows(value, path=""):
    if isinstance(value, dict):
        kind = value.get("kind")
        if kind in mechanics.entries:
            yield path or "effect", kind, sorted(interaction_tags(value))
        for key, child in value.items():
            yield from effect_rows(child, f"{path}.{key}".lstrip("."))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from effect_rows(child, f"{path}[{i}]")


def inventory():
    result = []
    for path, category, raw in sources():
        if "packs/base" not in path.as_posix():
            continue
        record = dict(
            category=category,
            ref="base:" + raw["id"],
            name=raw["name"],
            path=path.relative_to(PROJECT_ROOT).as_posix(),
            tags=sorted(classification(category, raw)),
            authored_tags=raw.get("tags", []),
            effects=list(effect_rows(raw)),
        )
        record["special_actions"] = [
            dict(id=a["id"], name=a["name"], tags=sorted(interaction_tags(a)))
            for a in raw.get("special_actions", [])
        ]
        # References describe abilities without assigning their material to the owner.
        record["abilities"] = {
            key: raw[key]
            for key in (
                "actions",
                "spells",
                "racial_spell",
                "cantrip_choices",
                "tool_proficiencies",
                "starting_recipes",
            )
            if raw.get(key)
        }
        result.append(record)
    return result


def write_docs(records):
    root = PROJECT_ROOT / "docs"
    counts = Counter(r["category"] for r in records)
    lines = [
        "# Полная классификация игрового контента",
        "",
        "Создано `python -m scripts.tag_gameplay --write` из проверенных документов `packs/base`. Пользовательские пакеты не изменяются. Теги не заменяют игровые поля и не включают новую механику.",
        "",
        "Каталог и правила: [gameplay-tags.md](gameplay-tags.md). Машиночитаемые данные: [gameplay-tags.json](gameplay-tags.json).",
        "",
        f"Проверено документов: **{len(records)}**. "
        + "; ".join(f"{k}: {v}" for k, v in counts.items())
        + ".",
        "",
    ]
    liquids = [
        dict(id=key, name=name, tags=sorted(liquid_tags(key)))
        for key, name in LIQUID_NAMES.items()
    ]
    lines += [
        "## Содержимое сосудов",
        "",
        "Это признаки жидкости отдельно от материала тары. Объём и вид хранятся в экземпляре; опасное питьё и лечение используют текущие правила движка.",
        "",
        "| Вид | Название | Признаки |",
        "| --- | --- | --- |",
    ]
    for liquid in liquids:
        lines.append(
            f"| `{liquid['id']}` | {liquid['name']} | "
            + ", ".join(f"`{t}`" for t in liquid["tags"])
            + " |"
        )
    lines.append("")
    for category in CATEGORIES:
        selected = [r for r in records if r["category"] == category]
        if not selected:
            continue
        lines += [
            f"## {category}",
            "",
            "| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |",
            "| --- | --- | --- |",
        ]
        for r in selected:
            semantic = [t for t in r["tags"] if t in TAG_CATALOG]
            legacy = [t for t in r["tags"] if t not in TAG_CATALOG]
            lines.append(
                f"| [{r['ref']}: {r['name']}](../{r['path']}) | "
                + (
                    ", ".join(f"`{t}`" for t in semantic)
                    or "Нет физических признаков; см. поля/ссылки ниже"
                )
                + " | "
                + (", ".join(f"`{t}`" for t in legacy) or "—")
                + " |"
            )
        for r in selected:
            if r["effects"] or r["special_actions"] or r["abilities"]:
                lines += ["", f"### {r['ref']} — {r['name']}", ""]
            for path, kind, tags in r["effects"]:
                lines.append(
                    f"- `{path}` / `{kind}` → "
                    + (
                        ", ".join(f"`{t}`" for t in tags)
                        or "Нет общего признака; параметры зарегистрированной механики"
                    )
                )
            for action in r["special_actions"]:
                lines.append(
                    f"- Особое действие `{action['id']}` ({action['name']}) → "
                    + ", ".join(f"`{t}`" for t in action["tags"])
                )
            for key, values in r["abilities"].items():
                refs = values if isinstance(values, list) else [values]
                lines.append(f"- `{key}`: " + ", ".join(f"`{v}`" for v in refs))
        lines.append("")
    (root / "content-tag-inventory.md").write_text("\n".join(lines), encoding="utf-8")
    (root / "gameplay-tags.json").write_text(
        json.dumps(
            dict(tags=TAG_CATALOG, liquids=liquids, content=records),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Keep definitions in one place; prose is maintained in the separate guide.
    table = [
        "# Справочник игровых тегов",
        "",
        f"**{len(TAG_CATALOG)}** общих признаков, включая состояния, инструменты и станции. Значения генерируются из `tuidungeon/domain/tags.py`.",
        "",
        "Правила использования: [gameplay-tags.md](gameplay-tags.md). Разметка всех документов и эффектов: [content-tag-inventory.md](content-tag-inventory.md).",
        "",
    ]
    for group, entries in TAG_GROUPS.items():
        table += [
            f"## {group}",
            "",
            "| Тег | Название | Точное значение |",
            "| --- | --- | --- |",
        ]
        table.extend(
            f"| `{key}` | {label} | {description} |"
            for key, (label, description) in entries.items()
        )
        table.append("")
    (root / "gameplay-tag-reference.md").write_text("\n".join(table), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    updates = collect_updates()
    if args.write:
        for path, _, raw in updates:
            PackStore.atomic_json(path, raw)
        PackStore().runtime_catalog()  # validate references and compilation, too.
        write_docs(inventory())
    print(
        "Изменено" if args.write else "Будет изменено",
        len(updates),
        "файлов:",
        dict(Counter(c for _, c, _ in updates)),
    )


if __name__ == "__main__":
    main()
