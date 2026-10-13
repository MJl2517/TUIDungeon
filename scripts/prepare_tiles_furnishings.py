"""Create the reviewed rails, furniture and service-symbol atlas batch.

Only the current batch's content is described here; archived task prompts are
not read. Existing authored files are never overwritten.
"""

import argparse
from copy import deepcopy
import json

from tuidungeon.content.packs import PackStore, PROJECT_ROOT
from tuidungeon.content.schemas import MODELS

NUMBERS = [
    *range(246, 254),
    *range(295, 307),
    347,
    348,
    350,
    352,
    353,
    354,
    394,
    395,
    456,
    457,
    491,
    540,
]
TABLES = {
    350: ("Прямоугольный стол", 15),
    352: ("Низкий стол", 10),
    394: ("Овальный стол", 10),
    395: ("Квадратный стол", 15),
    456: ("Длинный овальный стол", 25),
    457: ("Длинный прямоугольный стол", 25),
}
TIERS = [
    ("white", "Белый", 15),
    ("bronze", "Бронзовый", 130),
    ("iron", "Металлический", 153),
    ("gold", "Золотой", 220),
]


def documents(store):
    docs = {}
    labels = {}

    def add(category, identifier, name, number=None, **values):
        raw = dict(schema_version=1, id=identifier, name=name, **values)
        if number is not None:
            raw["symbol"] = f"tiles:cell_{number:04d}"
            labels.setdefault(
                number, (name, raw.get("glyph", "?"), raw.get("group", "Tiles"))
            )
        MODELS[category].model_validate(raw)
        docs[category, identifier] = raw
        return raw

    def furniture(
        identifier,
        name,
        number,
        *,
        material="wooden",
        weight=15,
        storage=None,
        blocks_sight=False,
        quantity=3,
    ):
        wood = material == "wooden"
        stone = material == "stone"
        loot = [
            dict(
                item="base:" + ("wood" if wood else "stone" if stone else "metal"),
                quantity=quantity,
            )
        ]
        dismantle = (
            None
            if stone
            else dict(
                tools=["carpenter_tools" if wood else "tinker_tools"],
                turns=3 if wood else 5,
                fast_tool=None,
                loot=loot
                + ([dict(item="base:furniture_hardware", quantity=1)] if wood else []),
            )
        )
        return add(
            "objects",
            identifier,
            name,
            number,
            glyph="T",
            foreground=130 if wood else 244 if stone else 153,
            description="Переносимая мебель. "
            + (
                "Можно только разрушить; разбор недоступен."
                if stone
                else "Для разбора нужен инструмент в инвентаре, владение не требуется."
            ),
            map_category="furniture",
            group="Мебель: " + ("дерево" if wood else "камень" if stone else "металл"),
            tags=["furniture", material, *(["flammable"] if wood else [])],
            walkable=False,
            blocks_sight=blocks_sight,
            movable=True,
            size="large",
            weight=weight,
            destruction=dict(
                max_hp=20 if wood else 40, dismantle=dismantle, remains=loot
            ),
            storage=storage,
        )

    for n in range(246, 251):
        add(
            "objects",
            f"rails_{n}",
            f"Рельсы {n}",
            n,
            glyph="=",
            foreground=153,
            description="Декорация. Разбирается инструментами жестянщика на металл и дерево.",
            group="Декорации: рельсы",
            map_category="destructible",
            tags=["rails", "metal", "wooden", "flammable"],
            walkable=True,
            blocks_sight=False,
            attackable=False,
            destruction=dict(
                max_hp=20,
                dismantle=dict(
                    tools=["tinker_tools"],
                    turns=3,
                    fast_tool=None,
                    loot=[
                        dict(item="base:metal", quantity=2),
                        dict(item="base:wood", quantity=1),
                    ],
                ),
                remains=[dict(item="base:metal", quantity=1)],
            ),
        )
    fence = deepcopy(store.get("objects", "tiles:metal_fence").model_dump(mode="json"))
    for k in ("schema_version", "id", "name", "symbol"):
        fence.pop(k, None)
    add(
        "objects",
        "metal_fence_251",
        "Металлический забор с верхними прутьями",
        251,
        **fence,
    )
    recipe = deepcopy(
        store.get("recipes", "tiles:build_metal_fence").model_dump(mode="json")
    )
    recipe.update(
        id="build_metal_fence_251", name="Построить: забор с верхними прутьями"
    )
    recipe["operation"]["place_object"] = "tiles:metal_fence_251"
    docs["recipes", recipe["id"]] = recipe
    for n, kind, title in [(252, "suspended", "навесной"), (253, "flat", "плоский")]:
        for material, color, word in [
            ("wood", 130, "Деревянный"),
            ("stone", 244, "Каменный"),
        ]:
            add(
                "tiles",
                f"{material}_bridge_{kind}_{n}",
                f"{word} {title} мост {n}",
                n,
                glyph="=",
                foreground=color,
                description="Проходимая поверхность моста. Не разбирается.",
                group="Поверхности: мосты",
                map_category="floor",
                walkable=True,
                blocks_sight=False,
                tags=["bridge", "wooden" if material == "wood" else "stone"],
            )
    for n, title, glyph in [
        (295, "Лестница наверх", "<"),
        (296, "Лестница вниз", ">"),
        (297, "Ступени наверх", "<"),
        (298, "Ступени вниз", ">"),
        (299, "Ступени вперёд", "="),
    ]:
        add(
            "objects",
            f"stairs_{n}",
            title,
            n,
            glyph=glyph,
            foreground=7,
            tags=["stairs", "transition"],
            group="Лестницы и переходы",
            map_category="service",
            walkable=True,
            blocks_sight=False,
            brush=dict(transition=True),
            description="Переход между картами. Выберите карту назначения при размещении в студии.",
        )
    for n, title, capacity, weight, opaque in [
        (300, "Книжная полка", 30, 15, True),
        (347, "Большая книжная полка", 30, 25, True),
        (348, "Маленькая книжная полка", 15, 8, False),
    ]:
        doc = furniture(
            f"bookshelf_{n}",
            title,
            n,
            weight=weight,
            blocks_sight=opaque,
            storage=dict(capacity=capacity, max_item_size="small"),
        )
        doc["glyph"] = "K"
        labels[n] = (title, "K", "Tiles: книжные полки")
    add(
        "tiles",
        "wood_support_301",
        "Деревянные подпорки",
        301,
        glyph="H",
        foreground=130,
        description="Непроходимая декорация. Пропускает свет и обзор, не разбирается.",
        group="Декорации: подпорки",
        map_category="special",
        tags=["wooden", "flammable", "support"],
        walkable=False,
        blocks_sight=False,
    )
    add(
        "tiles",
        "pit_302",
        "Яма",
        302,
        glyph="O",
        foreground=8,
        description="Непроходимая яма. Заготовка для будущей ловушки: падение и урон пока не заданы.",
        group="Пропасти и рельеф",
        map_category="special",
        tags=["pit", "height"],
        walkable=False,
        blocks_sight=False,
    )
    for n, (title, weight) in TABLES.items():
        for material, adjective, factor in [
            ("wooden", "Деревянный", 1),
            ("metal", "Стальной", 2),
            ("stone", "Каменный", 4),
        ]:
            furniture(
                f"table_{material}_{n}",
                f"{adjective} {title.lower()}",
                n,
                material=material,
                weight=weight * factor,
                quantity=5 if weight == 25 else 3,
            )
    for closed, opened, identifier, title, capacity, size in [
        (353, 354, "wall_chest_353", "Настенный сундук", 100, "medium"),
        (303, 304, "chest_303", "Сундук с накладкой", 300, "large"),
        (305, 306, "chest_305", "Сундук с решётчатой крышкой", 300, "large"),
    ]:
        doc = furniture(
            identifier,
            title,
            closed,
            weight=12,
            storage=dict(capacity=capacity, max_item_size=size),
        )
        doc.update(
            glyph="C",
            state_symbols={
                "closed": f"tiles:cell_{closed:04d}",
                "open": f"tiles:cell_{opened:04d}",
            },
            group="Мебель: сундуки",
        )
        labels[closed] = (title + ": закрытый", "C", "Tiles: сундуки")
        labels[opened] = (title + ": открытый", "U", "Tiles: сундуки")
        if identifier != "wall_chest_353":
            doc["foreground"] = 15
            doc["loot_tier"] = "white"
            doc["variants"] = [
                dict(
                    name=word,
                    glyph="C",
                    symbol=doc["symbol"],
                    foreground=color,
                    loot_tier=tier,
                )
                for tier, word, color in TIERS
            ]
    for n, kind, title, glyph in [
        (491, "simple", "Простой замок", "l"),
        (540, "complex", "Сложный замок", "L"),
    ]:
        add(
            "tiles",
            f"service_lock_{kind}",
            title,
            n,
            glyph=glyph,
            foreground=110,
            description="Служебный индикатор рядом с запертым объектом. Цвет задаёт качество замка.",
            map_category="service",
            group="Служебные: замки",
            tags=["lock_indicator", "lock_" + kind],
            walkable=True,
            blocks_sight=False,
        )

    for n in NUMBERS:
        original = store.get("symbols", f"base:kenney_{(n - 1) % 49}_{(n - 1) // 49}")
        title, glyph, group = labels[n]
        add(
            "symbols",
            f"cell_{n:04d}",
            title,
            glyph=glyph,
            pixels=list(original.pixels),
            group=group,
            reviewed=True,
            tags=[],
            source=original.source.model_dump(mode="json"),
        )

    width, height = 51, 41
    tiles = [
        [
            "base:wall" if x in (0, width - 1) or y in (0, height - 1) else "base:floor"
            for x in range(width)
        ]
        for y in range(height)
    ]
    objects, transitions, equipment = [], [], []
    for i, (category, identifier) in enumerate(k for k in docs if k[0] == "objects"):
        x, y = 5 + i % 9 * 5, 5 + i // 9 * 5
        objects.append(dict(id=identifier, ref="tiles:" + identifier, x=x, y=y))
        if docs[category, identifier].get("brush", {}).get("transition"):
            transitions.append(
                dict(
                    id=identifier + "_transition",
                    x=x,
                    y=y,
                    target="tiles:furnishings_annex",
                )
            )
    for i, (tier, _, color) in enumerate(TIERS):
        for j, chest in enumerate(("chest_303", "chest_305")):
            objects.append(
                dict(
                    id=f"{chest}_{tier}",
                    ref="tiles:" + chest,
                    x=5 + (i * 2 + j) * 5,
                    y=25,
                    overrides=dict(
                        foreground=color,
                        loot_tier=tier,
                        storage=dict(
                            personal=True,
                            contents=[dict(item="base:spellbook", quantity=1)],
                        ),
                    ),
                )
            )
    objects.append(
        dict(
            id="wall_chest_open",
            ref="tiles:wall_chest_353",
            x=45,
            y=25,
            overrides=dict(storage=dict(state="open")),
        )
    )
    for i, quality in enumerate(("cheap", "normal", "expensive", "legendary")):
        for j, complexity in enumerate(("simple", "complex")):
            objects.append(
                dict(
                    id=f"lock_{quality}_{complexity}",
                    ref="tiles:chest_303",
                    x=5 + (i * 2 + j) * 5,
                    y=30,
                    overrides=dict(
                        storage=dict(
                            lock=dict(
                                locked=True,
                                lock_quality=quality,
                                lock_complexity=complexity,
                            )
                        )
                    ),
                )
            )
    surfaces = [k for k in docs if k[0] == "tiles" and "lock" not in k[1]]
    for i, (_, identifier) in enumerate(surfaces):
        tiles[35][5 + i * 5] = "tiles:" + identifier
    for i, ref in enumerate(
        (
            "carpenter_tools",
            "tinker_tools",
            "thieves_tools",
            "flint_and_steel",
            "acid_flask",
            "spellbook",
            "staff",
            "metal",
            "wood",
            "stone",
        )
    ):
        equipment.append(dict(id="test_" + ref, ref="base:" + ref, x=2 + i, y=2))
    add(
        "maps",
        "furnishings_lab",
        "Tiles: рельсы, мебель и контейнеры",
        width=width,
        height=height,
        tiles=tiles,
        walkability=[
            [
                store.get("tiles", ref).walkable
                if ref.startswith("base:")
                else docs["tiles", ref.split(":")[1]]["walkable"]
                for ref in row
            ]
            for row in tiles
        ],
        blocks_sight=[[ref == "base:wall" for ref in row] for row in tiles],
        spawn=dict(x=2, y=3),
        objects=objects,
        equipment=equipment,
        transitions=transitions,
        ambient_light="bright",
    )
    add(
        "maps",
        "furnishings_annex",
        "Tiles: проверка переходов",
        width=9,
        height=7,
        tiles=[["base:floor"] * 9 for _ in range(7)],
        walkability=[[True] * 9 for _ in range(7)],
        blocks_sight=[[False] * 9 for _ in range(7)],
        spawn=dict(x=2, y=2),
        objects=[dict(id="return_stairs", ref="tiles:stairs_295", x=4, y=2)],
        transitions=[
            dict(
                id="return_stairs_transition", x=4, y=2, target="tiles:furnishings_lab"
            )
        ],
    )
    return docs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    docs = documents(PackStore())
    missing = []
    for (category, identifier), raw in docs.items():
        MODELS[category].model_validate(raw)
        path = PROJECT_ROOT / "packs/tiles" / category / (identifier + ".json")
        if path.exists():
            if MODELS[category].model_validate(json.loads(path.read_text())) != MODELS[
                category
            ].model_validate(raw):
                raise SystemExit(
                    f"Файл уже изменён автором, перезапись запрещена: {path}"
                )
        else:
            missing.append((path, raw))
    print(f"Документов в партии: {len(docs)}; новых: {len(missing)}")
    if args.write:
        for path, raw in missing:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".json.tmp")
            temp.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temp.replace(path)
        PackStore()


if __name__ == "__main__":
    main()
