"""Generate one playable acceptance map for the implemented crafting roadmap."""

import argparse
from collections import Counter
from pathlib import Path

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import ArtDocument, ClassDocument, MapDocument
from tuidungeon.content.symbols import glyph_ref


ROOMS = [
    (
        1,
        1,
        "1. ОСНОВЫ И ЗАГОТОВКИ",
        "Материалы из мешка, с земли и из инвентаря. Изготовьте факел вручную: один ход →/Space, Esc — пауза. Переложите заготовку в пустой мешок, подберите, сохраните и загрузите, продолжите или разберите с возвратом вложений. Проверьте стопки одинаковых материалов и вес. Уберите лом и инструменты из инвентаря для сравнения длительности.",
    ),
    (
        27,
        1,
        "2. СВЕТ И КРЫША",
        "Крыша отключает дневной свет. В левой половине тусклый источник (33,9): только базовые рецепты. Справа (44,9) полная тьма: крафт недоступен. Проход между половинами снизу. Возьмите древесину и ткань заранее; зажгите факел или фонарь, повторите проверки. Истощение топлива приостанавливает работу. Факел горит 60 игровых минут; фонарь пополняется маслом.",
    ),
    (
        53,
        1,
        "3. ЗНАНИЯ И ЖУРНАЛ",
        "Два рунических рецепта неизвестны даже испытателю. Каменная табличка открывает кинжал, изучение мастерской — кожаную броню. J → Записи/Рецепты, чтение страниц ←/→, сохранение знаний. Эксперимент в зоне 9 также открывает оба рецепта; независимые способы проверяйте в свежих сессиях. Воин без тестового класса позволяет проверить нехватку владений.",
    ),
    (
        1,
        21,
        "4. ОБЪЕКТЫ И ПОЛ",
        "Соберите пять цветных растений в ряду y=35: каждый цвет даёт свой материал, повторный сбор через 3 минуты. Деревья (8/13,36) рубятся режущим инструментом и восстанавливаются через 5 минут; каменная жила (18,36) — через 4 минуты. Длительный отдых возможен только у кровати, лежанки (4,30) или разложенного спального мешка (4,31). Закрытый ящик (20,30) открывается ломиком либо разбирается; поиска ценностей по умолчанию нет. Крупный завал (12,30): 30 ходов вручную, 10 с киркой, без износа кирки. Баррикада снимается ломиком за ход без износа. Разберите стол и кровать, поднимите стул, передвиньте мебель на соседнюю клетку. Каменный пол остаётся. Шкаф содержит вещи: разбор выбрасывает их однократно. Треснувшая преграда разбирается; обычные стены не разбираются. Разрушьте дверь тараном или атакой: остаётся древесина. Сожгите деревянную баррикаду; проверьте изменение прохода, обзора и света. Повреждённые объекты ремонтируются в крафте.",
    ),
    (
        27,
        21,
        "5. ОГОНЬ И ЖИДКОСТИ",
        "Шесть подписанных источников: чистая, грязная, болотная, солёная, отравленная и святая вода. Подберите котелки/фляги и загрязнённый кинжал. Лужа (30,35) содержит две порции грязной воды и исчезает после исчерпания. Факелы в подставках (34/37,35) можно забрать и вернуть; топливо сохраняется. Фонарь (40,35) и свечу (40,33) можно подобрать. Инструменты не ломаются. Золото в мешках — обычный материал: проверьте перенос, бросок и вариант золотой оправы рунного фокуса. Набор, переливание, опустошение, очистка кинжала одной порцией чистой воды. Пополните и зажгите костёр: тепло и свет расходуют топливо. Вскипятите грязную воду, сварите припарку. Кипячение не опресняет солёную воду. Облейте землю (48,35) — появится грязь; потушите костёр/горящую мебель. Постройте второй костёр на свободном месте.",
    ),
    (
        53,
        21,
        "6. СТАНЦИИ И РЕМОНТ",
        "Горн и наковальня доступны одновременно из (61,26), мешок рядом. Верстак — работа из (67,25), алхимический стол — (67,31), печь — (72,25). Возле каждого лежат припасы. Изготовьте оружие/щит, таран, кислоту, зелье, флакон и горшок. Повреждённые кинжал, посох и сапоги лежат у входа. Ремонт резервирует цель; Esc возвращает доступ без бесплатного восстановления. Повредите станцию, проверьте ремонт и отказ сломанной станции.",
    ),
    (
        1,
        41,
        "7. ПОСТРОЙКИ И ЛОВУШКИ",
        "Свободное поле для баррикады и установки ловушки. Готовый набор, кол, каменный клин, шест и таран — в мешке. Подоприте дверь колом/клином; уберите подпорку. Ветки (20,52) достигаются шестом из (18,52). Видимая ловушка (9,51); скрытая (13,51) сначала требует обнаружения. Обезвредьте, разберите инструментами, изготовьте и установите новую, войдите на неё. Риск обезвреживания явный. Механизм разбирается и ремонтируется. Ловушки наносят настоящий урон.",
    ),
    (
        27,
        41,
        "8. ОСТАНКИ И РЕМЁСЛА",
        "Волк, змея и паук: разделка 5 ходов вручную или 2 с клинком; извлечение яда требует набора и владения отравителя. Добыча однократная. Из материалов изготовьте ткань, верёвку, посох, кожаные вещи, каменный блок, сапоги; оцените самоцвет. Нанесите яд на кинжал. Манекен-гоблин в зоне 9 нужен для проверки успешного попадания и расхода покрытия. Готовка и пивоварение — у тепла зоны 5/6. Полного боя, голода и торговли пока нет.",
    ),
    (
        53,
        41,
        "9. ЧЕРНИЛА И МАГИЯ",
        "Из чистой воды, пигмента и смолы сделайте чернила, затем надпись и свитки. Вода уже в котелке; фляги и припасы рядом. Читайте надпись, проверьте журнал. Свитки Света, Починки и Огненного снаряда работают через меню магии, расходуя свиток. Фокус даёт бонус только экипированным. Эксперимент открывает рунические рецепты; рунический кинжал требует горн+наковальню зоны 6. Железное дерево, мифрил и драконья кожа имеют готовые рецепты. Вариант дубинки из одного дерева — рискованная импровизация. Картография отложена. AI/патрули, полноценный бой, голод/жажда, NPC/торговля и альпинизм — этап 12, ещё не реализованы.",
    ),
]
UNKNOWN = {"base:craft_rune_dagger", "base:craft_rune_leather"}


def build_documents(store):
    # A fixture can reference its dependencies, not every installed optional pack.
    accessible = set()

    def include(identifier):
        for dependency in store.manifests[identifier].dependencies:
            if dependency not in accessible:
                accessible.add(dependency)
                include(dependency)

    include("dev")
    recipes = sorted(
        (ref, d)
        for (cat, ref), d in store.documents.items()
        if cat == "recipes" and ref.split(":")[0] in accessible
    )
    materials = Counter()
    required_tools = {"lockpicks", "blade", "poisoner_kit", "lever", "pickaxe"}
    proficiencies = set()
    for _, recipe in recipes:
        for variant in recipe.variants:
            required_tools.update(variant.tools)
            proficiencies.update(variant.proficiencies)
            for ingredient in variant.ingredients:
                for ref in ingredient.items:
                    materials[ref] = max(materials[ref], ingredient.quantity * 4)
    equipment = {
        ref: d
        for (cat, ref), d in store.documents.items()
        if cat == "equipment" and ref != "base:cartographer_tools"
    }
    tools = sorted(
        {
            min(
                (ref for ref, d in equipment.items() if tag in d.tags),
                key=lambda ref: (equipment[ref].weight, ref),
            )
            for tag in required_tools
        }
    )
    # Ordinary carrying limits remain in force; bulk inputs stay beside stations.
    tester = store.get("classes", "base:wizard").model_dump(mode="json")
    tester.update(
        id="roadmap_tester",
        name="Испытатель ремёсел",
        description="Dev: владения, инструменты и заклинания для этапов 1–11. Два рунических рецепта открываются на полигоне.",
        hit_points=50,
        tool_proficiencies=sorted(proficiencies),
        starting_recipes=[ref for ref, _ in recipes if ref not in UNKNOWN],
        starting_items=sorted(
            set(
                tools
                + [
                    "base:flint_and_steel",
                    "base:torch",
                    "base:lamp",
                    "base:oil",
                    "base:cooking_pot",
                ]
            )
        ),
        spells=sorted(
            ref
            for cat, ref in store.documents
            if cat == "spells" and ref.startswith("base:")
        ),
        spell_slots={"1": 10},
        cantrip_choices=[],
        cantrips_known=0,
        order=99,
    )
    own_symbol = "base:visual_classes_roadmap_tester"
    if ("symbols", own_symbol) in store.documents:
        tester["symbol"] = own_symbol
    tester = ClassDocument.model_validate(tester)
    width, height = 79, 61
    tiles = [["base:floor"] * width for _ in range(height)]
    walk = [[True] * width for _ in range(height)]
    sight = [[False] * width for _ in range(height)]
    roof = [[False] * width for _ in range(height)]

    def wall(x, y, enabled=True):
        tiles[y][x] = "base:wall" if enabled else "base:floor"
        walk[y][x], sight[y][x] = not enabled, enabled

    for x in range(width):
        wall(x, 0)
        wall(x, height - 1)
    for y in range(height):
        wall(0, y)
        wall(width - 1, y)
    cells = [[None] * width for _ in range(height)]
    layers = {
        k: []
        for k in (
            "objects",
            "doors",
            "points_of_interest",
            "equipment",
            "traps",
            "monsters",
        )
    }
    entries = []

    def put(layer, identifier, ref, x, y, **overrides):
        p = dict(id=identifier, ref="base:" + ref, x=x, y=y, overrides=overrides)
        layers[layer].append(p)
        entries.append((identifier, layer, x, y))
        return p

    def supply(identifier, x, y, extras=None, empty=False):
        names = {
            "basics": "Базовые материалы",
            "workpiece_storage": "Хранилище заготовок",
            "dim_materials": "Материалы в полутьме",
            "dark_materials": "Материалы в темноте",
            "environment_tools": "Разбор и ремонт",
            "camp_supplies": "Костёр и варка",
            "forge_supplies": "Кузнечные припасы",
            "wood_supplies": "Столярные припасы",
            "oven_supplies": "Обжиг и стекло",
            "alchemy_supplies": "Алхимические припасы",
            "construction_supplies": "Постройки и ловушки",
            "harvest_supplies": "Разделка и ремёсла",
            "arcane_supplies": "Чернила и магия",
        }
        contents = {} if empty else dict(materials)
        for ref, n in (extras or {}).items():
            contents["base:" + ref] = max(contents.get("base:" + ref, 0), n)
        return put(
            "points_of_interest",
            identifier,
            "terrain_sack",
            x,
            y,
            name=names[identifier],
            description=(
                "Личный пустой контейнер: хранение и перенос заготовок."
                if empty
                else "Материалы для проверок. Крафт берёт их из соседнего мешка; не нужно переносить весь запас."
            ),
            challenge=None,
            storage=dict(
                capacity=100000,
                personal=empty,
                contents=[
                    dict(item=ref, quantity=n) for ref, n in sorted(contents.items())
                ],
            ),
        )

    for index, (x, y, title, instruction) in enumerate(ROOMS, 1):
        for xx in range(x, x + 24):
            wall(xx, y)
            wall(xx, y + 17)
        for yy in range(y, y + 18):
            wall(x, yy)
            wall(x + 23, yy)
        for xx, yy in ((x + 11, y), (x + 11, y + 17), (x, y + 8), (x + 23, y + 8)):
            wall(xx, yy, False)
        for offset, char in enumerate(title[:22]):
            cells[y + 1][x + 1 + offset] = dict(
                char=char,
                symbol=glyph_ref(char)
                if ("symbols", glyph_ref(char)) in store.documents
                else None,
                foreground=14,
                background=None,
            )
        put(
            "points_of_interest",
            f"guide_{index}",
            "stone_tablet",
            x + 2,
            y + 3,
            name=title,
            reading=dict(
                title=title,
                pages=[
                    instruction,
                    "Общие клавиши: Esc — меню, M — заклинания, B — строительство, J — журнал, L — история логов, I — инвентарь, Enter — окружение; →/Space — рабочий ход, Esc — пауза. Сохранение из меню; свежий тест возвращает исходные образцы. Координаты в памятках начинаются с нуля.",
                ],
            ),
        )

    # 1: neighboring inventory/ground/container inputs, portable workpiece storage.
    supply("basics", 5, 7, {"crowbar": 1})
    supply("workpiece_storage", 8, 7, empty=True)
    for i, ref in enumerate(("wood", "cloth", "plant_fiber", "wood", "cloth")):
        put("equipment", f"ground_input_{i}", ref, 4 + i, 10)
    put("objects", "route_table", "table", 11, 7)
    put(
        "points_of_interest",
        "blocked_storage",
        "terrain_sack",
        17,
        7,
        challenge=None,
        name="Мешок за стеной: не источник",
        storage=dict(
            capacity=1000,
            personal=False,
            contents=[dict(item="base:wood", quantity=10)],
        ),
    )
    for y in range(6, 9):
        wall(16, y)

    # 2: no ambient light under a roof, dark and dim halves separated by stone.
    for y in range(1, 19):
        for x in range(27, 51):
            roof[y][x] = True
    for y in range(2, 16):
        wall(39, y)
    # Put this instruction board outside the roof so it can always be read.
    board = next(p for p in layers["points_of_interest"] if p["id"] == "guide_2")
    board.update(x=28, y=20)
    entries = [
        (i, k, 28, 20) if i == "guide_2" else (i, k, x, y) for i, k, x, y in entries
    ]
    supply("dim_materials", 33, 8)
    supply("dark_materials", 44, 8)

    # 3: two initially unknown recipes, independent book and workshop routes.
    put(
        "points_of_interest",
        "recipe_book",
        "stone_tablet",
        59,
        7,
        name="Рунный кинжал: учебная табличка",
        reading=dict(
            title="Секрет рунного кинжала",
            pages=[
                "Прочтение открывает рецепт рунного кинжала.",
                "Кинжал, магическая пыль и фокусная обработка у горна и наковальни.",
            ],
            learn_recipes=["base:craft_rune_dagger"],
        ),
    )
    put(
        "points_of_interest",
        "recipe_workshop",
        "crafting_workshop",
        65,
        7,
        name="Мастерская рунной брони",
        learn_recipes=["base:craft_rune_leather"],
    )

    # 4: destructible overlays never replace their stone floor.
    for identifier, ref, x, y in (
        ("table", "table", 7, 27),
        ("bed", "bed", 12, 27),
        ("chair", "chair", 17, 27),
        ("cabinet", "cabinet", 7, 32),
        ("cracked_wall", "cracked_barrier", 12, 32),
        ("burnable", "barricade", 17, 32),
    ):
        put("objects", identifier, ref, x, y)
    next(p for p in layers["objects"] if p["id"] == "cabinet")["overrides"][
        "storage"
    ] = dict(
        capacity=1000,
        personal=False,
        contents=[
            dict(item="base:cloth", quantity=3),
            dict(item="base:wood", quantity=2),
        ],
    )
    put("doors", "breakable_door", "door_wood", 20, 27)
    put("objects", "large_rubble", "rubble_large", 12, 30)
    put("objects", "sleeping_place", "bedroll", 4, 30)
    put("equipment", "sleeping_bag", "bedroll", 4, 31)
    put(
        "points_of_interest",
        "closed_crate",
        "terrain_crate_closed",
        20,
        30,
        storage={"contents": [{"item": "base:wood", "quantity": 2}]},
    )
    for index, ref in enumerate(
        (
            "medicinal_flower",
            "poison_flower",
            "bitter_flower",
            "alchemy_flower",
            "fiber_flower",
        )
    ):
        put(
            "objects",
            "gather_" + ref,
            ref,
            6 + index * 3,
            35,
            destruction={"regrow_minutes": 3},
        )
    put("objects", "regrowing_tree", "tree", 8, 36, destruction={"regrow_minutes": 5})
    put(
        "objects",
        "regrowing_young_tree",
        "tree_young",
        13,
        36,
        destruction={"regrow_minutes": 5},
    )
    put(
        "objects",
        "regrowing_mine",
        "cracked_barrier",
        18,
        36,
        name="Восстанавливаемая каменная жила",
        destruction={"regrow_minutes": 4},
    )
    supply(
        "environment_tools",
        4,
        34,
        {"battering_ram": 1, "stake": 2, "stone_wedge": 2, "wooden_pole": 1},
    )

    # 5: six explicitly typed sources; an empty campfire and nearby working supplies.
    for index, (kind, label) in enumerate(
        (
            ("clean_water", "Чистая"),
            ("dirty_water", "Грязная"),
            ("swamp_water", "Болотная"),
            ("salt_water", "Солёная"),
            ("poisoned_water", "Отравленная"),
            ("holy_water", "Святая"),
        )
    ):
        put(
            "objects",
            "water_" + kind,
            "water_well",
            39 + index % 3 * 4,
            26 + index // 3 * 5,
            name=label + " вода",
            water_source=dict(kind=kind),
        )
    put("objects", "campfire", "campfire", 34, 26)
    supply(
        "camp_supplies",
        34,
        24,
        {"wood": 40, "tinder": 10, "oil": 6, "cooking_pot": 2, "water_flask": 3},
    )
    for index, ref in enumerate(("cooking_pot", "water_flask", "waterskin")):
        put("equipment", "vessel_" + ref, ref, 30 + index * 2, 31)
    put("equipment", "dirty_dagger", "dagger", 30, 33)["item_state"] = dict(
        contaminated=True
    )
    soil = next(
        ref
        for (cat, ref), d in sorted(store.documents.items())
        if cat == "tiles" and "soil" in d.tags and d.walkable and not d.brush.door
    )
    tiles[35][48] = soil
    put("objects", "fire_test_chair", "chair", 44, 35)
    put("objects", "finite_puddle", "puddle", 30, 35)
    put("objects", "wall_torch", "torch_wall", 34, 35)
    put("objects", "standing_torch", "torch_decor", 37, 35)
    put("objects", "placed_lamp", "lantern", 40, 35)
    put("objects", "placed_candle", "candle", 40, 33)

    # 6: each work cell shares a cardinal neighbor with its supply bag.
    for identifier, ref, x, y in (
        ("forge", "forge", 60, 26),
        ("anvil", "anvil", 61, 27),
        ("workbench", "workbench", 67, 26),
        ("oven", "oven", 72, 26),
        ("alchemy", "alchemy_table", 67, 32),
    ):
        put("objects", identifier, ref, x, y)
    for identifier, x, y in (
        ("forge_supplies", 61, 25),
        ("wood_supplies", 67, 24),
        ("oven_supplies", 72, 24),
        ("alchemy_supplies", 67, 30),
    ):
        supply(identifier, x, y)
    for index, ref in enumerate(("dagger", "staff", "leather_boots")):
        definition = store.get("equipment", "base:" + ref)
        put("equipment", "damaged_" + ref, ref, 56 + index * 2, 34)["item_state"] = (
            dict(durability=max(0, definition.durability // 3))
        )

    # 7: avoid traps on circulation routes; leave free space for player construction.
    supply(
        "construction_supplies",
        5,
        47,
        {
            "battering_ram": 1,
            "stake": 2,
            "stone_wedge": 2,
            "wooden_pole": 1,
            "trap_kit": 3,
        },
    )
    put("doors", "brace_door", "door_wood", 9, 47)
    put("doors", "locked_door", "door_wood", 13, 47, brush=dict(door=dict(locked=True)))
    put("objects", "mechanism", "craft_mechanism", 17, 47)
    put("objects", "pole_branches", "tangled_branches", 20, 52)
    put("traps", "visible_trap", "improvised_trap", 9, 51)
    put("traps", "hidden_trap", "improvised_trap", 13, 51, hidden=True)

    # 8: one-shot harvest targets, extended crafts and a pre-made poison.
    supply(
        "harvest_supplies", 33, 47, {"simple_poison": 3, "uncut_gem": 3, "raw_meat": 6}
    )
    for identifier, ref, x in (
        ("wolf", "wolf_remains", 33),
        ("snake", "snake_remains", 39),
        ("spider", "spider_remains", 45),
    ):
        put("objects", identifier, ref, x, 52)
    put(
        "objects",
        "loot_corpse",
        "corpse",
        33,
        55,
        storage={"contents": [{"item": "base:bandage", "quantity": 2}]},
    )
    put(
        "objects",
        "loot_skeleton",
        "skeleton_remains",
        39,
        55,
        storage={"contents": [{"item": "base:dagger", "quantity": 1}]},
    )
    put(
        "objects",
        "loot_carcass",
        "carcass",
        45,
        55,
        storage={"contents": [{"item": "base:raw_meat", "quantity": 1}]},
    )

    # 9: ink, authored reading, scrolls, focus, rare ingredients and experiment.
    supply(
        "arcane_supplies",
        59,
        47,
        {
            "arcane_focus": 1,
            "scroll_light": 2,
            "scroll_mending": 2,
            "scroll_fire_bolt": 3,
            "uncut_gem": 4,
            "cooking_pot": 2,
        },
    )
    put(
        "equipment",
        "ink_water",
        "cooking_pot",
        61,
        47,
        name="Вода для чернил",
        vessel=dict(initial_kind="clean_water", initial_portions=1),
    )
    put("equipment", "inscription_sample", "inscribed_page", 59, 50)
    put("equipment", "focus_sample", "arcane_focus", 63, 50)
    put(
        "monsters",
        "spell_target",
        "goblin",
        70,
        53,
        name="Гоблин: цель для магии и яда",
        hit_points=30,
    )

    art = ArtDocument.model_validate(
        dict(
            id="roadmap_lab_labels",
            name="Подписи единого полигона",
            width=width,
            height=height,
            layers=[dict(id="labels", name="Зоны", cells=cells)],
        )
    )
    level = MapDocument.model_validate(
        dict(
            id="roadmap_lab",
            name="Единый полигон: roadmap 1–11",
            description="Девять зон крафта, окружения, жидкостей и магии. Выберите класс dev:roadmap_tester. Этап 12 и картография отложены.",
            width=width,
            height=height,
            tiles=tiles,
            walkability=walk,
            blocks_sight=sight,
            roof=roof,
            ambient_light="bright",
            spawn=dict(x=4, y=6),
            lights=[dict(id="dim_only", x=33, y=9, radius=5, bright_radius=0)],
            decorations=[dict(id="labels", ref="dev:roadmap_lab_labels", x=0, y=0)],
            **layers,
        )
    )
    return level, art, tester, entries


def guide(level, entries):
    lines = [
        "# Единый полигон roadmap",
        "",
        f"`dev:roadmap_lab`, {level.width}×{level.height}. Один основной полигон для реализованного базового объёма этапов 1–11; не заменяет галерею всех образцов `dev:all_items`.",
        "",
        "## Запуск",
        "",
        "```powershell",
        r".\run.bat --test-map dev:roadmap_lab --test-class dev:roadmap_tester --seed 42",
        "```",
        "",
        "```bash",
        "./run.sh --test-map dev:roadmap_lab --test-class dev:roadmap_tester --seed 42",
        "# Тот же сценарий в терминале:",
        "./run.sh --terminal --test-map dev:roadmap_lab --test-class dev:roadmap_tester --seed 42",
        "```",
        "",
        "В студии: пакет dev → карта «Единый полигон: roadmap 1–11» → тестовый класс «Испытатель ремёсел» → запуск в игровом окне. Готовый герой получает необходимые владения, рабочие инструменты и существующие заклинания. Не получает два рунических рецепта. Ограничение переносимого веса обычное; припасы остаются в мешках у рабочих мест. Для отрицательной проверки владений запустите ту же карту с `--test-class base:warrior`.",
        "",
        "На каждой зоне двухстраничная инструкция. Координаты с нуля. Esc — меню, M — заклинания, B — строительство, I — инвентарь, J — журнал, L — логи, Enter — окружение. Во время работы карта видна: →/Space — один ход, Esc — пауза. Все образцы настоящие, ловушки причиняют урон; перезапуск теста создаёт свежую карту. Сохранение/загрузка — через меню игры.",
        "",
        "## Зоны и маршрут",
        "",
        "| Зона | Этапы | Инструкция |",
        "| --- | --- | --- |",
    ]
    stages = (
        "1–3",
        "1–3: ограничения света",
        "4",
        "5",
        "6–7",
        "7–8, 10",
        "9",
        "8, 10",
        "11 без картографии",
    )
    for index, ((x, y, title, instruction), stage) in enumerate(zip(ROOMS, stages), 1):
        bx, by = (28, 20) if index == 2 else (x + 2, y + 3)
        lines.append(f"| {title} | {stage} | ({bx}, {by}) |")
    for _, _, title, instruction in ROOMS:
        lines.extend(["", "### " + title, "", instruction])
    lines.extend(
        [
            "",
            "## Основной приёмочный маршрут",
            "",
            "1. Стол (11,7) → древесина → ручной факел у мешка (5,7).",
            "2. Взять ткань и древесину; начать ручной факел на два хода, выполнить один ход, Esc. Перенести заготовку в пустой мешок (8,7), затем на землю и обратно. Сохранить/загрузить; завершить или разобрать и сверить материалы/вес.",
            "3. Перейти к крыше: базовый рецепт доступен в (33,9), профессиональный нет; в (44,9) недоступны оба. Зажечь факел — ограничения снимаются в освещённых клетках. Погасший источник останавливает работу.",
            "4. Костёр (34,26): взять топливо у (34,24), пополнить и зажечь. Пустой котелок → грязная вода (43,26) → работа у костра из (34,25) → чистая вода → припарка. Можно построить свой костёр на свободном полу.",
            "5. Изготовить предмет у горна+наковальни из (61,26), отремонтировать повреждённый кинжал. Разобрать шкаф (7,32), сверить выпавшее содержимое и неизменный пол; сохранить и загрузить.",
            "6. Ловушка (9,51) → обезвреживание → разбор → изготовление набора у (5,47) → установка в свободном поле → срабатывание. Скрытая ловушка (13,51) проверяет обнаружение. Для неудачи/успеха проверок используйте разные seed.",
            "7. Останки → разделка/яд → изделия. Эксперимент у (59,47) → открытые рунические рецепты → чернила из котелка (61,47) → надпись/свиток → чтение/применение. Чтобы отдельно проверить обучение книгой и мастерской, начните свежую сессию и сначала посетите зону 3.",
            "",
            "## Границы полигона",
            "",
            "Проверяется существующая базовая реализация, а не весь будущий массовый контент ремёсел. Полный доспех, сети/стрелы и другие ещё не добавленные рецепты не изображаются работающими. Картография и инструменты картографа исключены из этапа 11 по решению пользователя. Этап 12 (AI/патрули, полноценный бой, голод/жажда, NPC/торговля, альпинизм) остаётся зависимостью. Гоблин — статичная цель существующего расчёта атак и заклинаний. Межлокационное сохранение проверяется автоматическими тестами окружения; этот полигон не требует переходов на другие карты.",
            "",
            "## Пересборка",
            "",
            "```powershell",
            r".venv\Scripts\python.exe -m scripts.build_roadmap_lab --force",
            "```",
            "",
            "```bash",
            ".venv/bin/python -m scripts.build_roadmap_lab --force",
            "```",
            "",
            "Генератор обновляет только эту карту, её подписи, тестовый класс и памятку. Новые рецепты и их ингредиенты/инструменты подхватываются при пересборке; новые виды операций требуют явного сценария в зоне. Файлы исходных пакетов игры не меняются при прохождении. Начальную прочность и загрязнение образца можно изменить в студии: слой «Предметы» → выделение V → свойства экземпляра → «Начальное состояние предмета».",
            "",
            "## Образцы",
            "",
            "| ID | Слой | X | Y |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| `{identifier}` | {layer} | {x} | {y} |"
        for identifier, layer, x, y in entries
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    store = PackStore(args.packs_dir)
    level, art, tester, entries = build_documents(store)
    root = store.root / "dev"
    writes = {
        root / "maps/roadmap_lab.json": level,
        root / "art/roadmap_lab_labels.art.json": art,
        root / "classes/roadmap_tester.json": tester,
    }
    if not args.force and any(p.exists() for p in (*writes, root / "roadmap_lab.md")):
        parser.error("Полигон уже существует; для пересборки укажите --force")
    candidate = dict(store.documents)
    for category, document in (("maps", level), ("art", art), ("classes", tester)):
        candidate[category, "dev:" + document.id] = document
    store.validate_references(candidate, store.manifests)
    for path, document in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        store.atomic_json(path, document.model_dump(mode="json"))
    (root / "roadmap_lab.md").write_text(guide(level, entries), encoding="utf-8")
    print(f"dev:roadmap_lab: {level.width}×{level.height}, {len(entries)} образцов")


if __name__ == "__main__":
    main()
