"""Install standard door presets without rewriting author maps."""

import json

from tuidungeon.content.packs import PackStore, PROJECT_ROOT
from tuidungeon.content.schemas import EquipmentDocument, SpellDocument


def main():
    from scripts.migrate_door_instances import migrate

    migrate()
    store = PackStore()
    crowbar = store.get("equipment", "base:crowbar").model_dump(mode="json")
    crowbar.update(
        durability=None,
        slot="hand",
        hands=1,
        description="В руке даёт преимущество на выламывание двери. Открывает ящики и снимает баррикады. Не изнашивается.",
    )
    thieves_tools = store.get("equipment", "base:thieves_tools").model_dump(mode="json")
    thieves_tools.update(
        durability=10,
        check_aids=[],
        description="Необходимы для взлома замков. Прочность 10; неудачная попытка взлома расходует 1 прочность.",
    )
    acid = dict(
        id="acid_flask",
        name="Флакон кислоты",
        category="consumables",
        glyph="!",
        foreground=10,
        weight=0.5,
        charges=1,
        tags=["acid", "consumable", "throwable"],
        weapon_damage="2d6",
        description="Кислота наносит 2d6 урона. Сталь и прутья получают двойной урон и затем 2 урона коррозией в минуту. Бросьте флакон в дверь; одна порция.",
    )
    pickaxe = dict(
        id="pickaxe",
        name="Кирка",
        category="tools",
        glyph="/",
        foreground=7,
        weight=3.0,
        durability=None,
        slot="hand",
        hands=1,
        tags=["pickaxe", "tool"],
        weapon_damage="1d6",
        description="Кирка в руке позволяет разрушать каменные плиты.",
    )
    daylight = dict(
        id="daylight",
        name="Дневной свет",
        level=3,
        target="other",
        effects=[],
        description="Волшебник может применить к адамантиевой двери через её меню: она станет каменной. Нужны известное заклинание и ячейка 3 уровня. На первом уровне не выдаётся.",
    )
    for raw, model, category in (
        (crowbar, EquipmentDocument, "equipment"),
        (thieves_tools, EquipmentDocument, "equipment"),
        (acid, EquipmentDocument, "equipment"),
        (pickaxe, EquipmentDocument, "equipment"),
        (daylight, SpellDocument, "spells"),
    ):
        doc = model.model_validate(raw)
        store.atomic_json(
            store.root / "base" / category / (doc.id + ".json"),
            doc.model_dump(mode="json"),
        )
        value = {
            k: v
            for k, v in raw.items()
            if k not in ("glyph", "foreground", "background", "art")
        }
        value["schema_version"] = 1
        store.atomic_json(
            PROJECT_ROOT / "tuidungeon/content/data" / category / (doc.id + ".json"),
            value,
        )
    for path in (
        store.root / "base/equipment/staff.json",
        PROJECT_ROOT / "tuidungeon/content/data/equipment/staff.json",
    ):
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["tags"] = list(dict.fromkeys([*raw["tags"], "bludgeoning"]))
        store.atomic_json(path, raw)
    PackStore()
    print(
        "Подготовлены пять материалов дверей с локальными настройками; ломик, кислота, кирка и Дневной свет."
    )


if __name__ == "__main__":
    main()
