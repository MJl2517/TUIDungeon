"""Interaction vocabulary. Traits never grant actions or replace typed rules."""

from collections.abc import Mapping

from .damage import DAMAGE_TYPES, DAMAGE_LABELS

# id, Russian label, meaning. Only the first three groups are authored flags.
TAG_GROUPS = {
    "Материалы и вещества": {
        "wooden": (
            "Деревянный",
            "Существенные деревянные части; не обязательно чистое дерево.",
        ),
        "stone": ("Каменный", "Камень, кладка или каменные части."),
        "metal": (
            "Металлический",
            "Существенные металлические части; не означает проводимость или защиту от огня.",
        ),
        "glass": (
            "Стеклянный",
            "Стекло или стекольное сырьё; хрупкость задаётся отдельно.",
        ),
        "ceramic": ("Керамический", "Обожжённая керамика; отличается от сырой глины."),
        "clay": ("Глиняный", "Необожжённая глина."),
        "cloth": ("Тканевый", "Ткань или существенные тканевые части."),
        "leather": ("Кожаный", "Кожа или кожаные части."),
        "paper": ("Бумажный / пергамент", "Бумага, пергамент и страницы книг."),
        "bone": ("Костяной", "Кости, рога или костяные части."),
        "organic": (
            "Органический",
            "Биологическое сырьё; не гарантирует съедобность, горючесть или живое существо.",
        ),
        "fiber": ("Волокнистый", "Растительное волокно и волокнистые изделия."),
        "soil": (
            "Земляной",
            "Грунт, который может обрабатываться отдельно от каменного пола.",
        ),
        "sand": ("Песчаный", "Песок; не любое стекольное сырьё."),
        "ice": ("Лёд / снег", "Замёрзшая вода; не жидкость и не атака холодом."),
        "liquid": (
            "Жидкость",
            "Жидкая среда или содержимое; пустая тара этого признака не имеет.",
        ),
        "gas": (
            "Газ / аэрозоль",
            "Газовая среда, дым, туман или взвесь; не обязательно ядовита.",
        ),
        "water": (
            "Вода",
            "Водная среда; качество определяется видом воды, а не внешним видом.",
        ),
        "oil": ("Масло", "Масляная среда; пригодность для лампы задаёт lamp_oil."),
        "blood": ("Кровь", "Кровь или её следы; след не обязательно жидкая лужа."),
        "iron": ("Железо / сталь", "Явно железный или стальной материал."),
        "silver": ("Серебро", "Явно серебряный материал; не любая светлая вещь."),
        "gold": (
            "Золото",
            "Явно золотой материал; отличается от эффекта выдачи денег.",
        ),
        "copper": ("Медь", "Явно медный материал."),
        "adamantine": (
            "Адамант",
            "Особый материал существующей двери; не синоним неуничтожимости.",
        ),
    },
    "Природа и реакции": {
        "flammable": (
            "Горючий",
            "Может участвовать в горении; тег не задаёт механику разрушения.",
        ),
        "magic": (
            "Магический",
            "Магическая природа источника; книга о магии сама по себе не зачарована.",
        ),
        "holy": (
            "Святой",
            "Явно освящённый источник, вода или символ; не всякий алтарь святой.",
        ),
        "cursed": (
            "Проклятый",
            "Только явно заданное автором проклятие; никогда не выводится из неизвестности артефакта.",
        ),
        "sticky": ("Липкий", "Паутина, вязкая слизь и явно липкие поверхности."),
        "edible": (
            "Съедобный",
            "Явно предназначено в пищу; не любая органика или гриб.",
        ),
        "medicinal": (
            "Лекарственное сырьё",
            "Ингредиент для лечения; не обещает лечение при употреблении.",
        ),
        "fuel": (
            "Топливо",
            "Явно топливный ресурс; конкретная станция всё равно проверяет свой fuel_tag.",
        ),
        "plants": (
            "Растительность",
            "Растения и растительное сырьё, не деревянная мебель.",
        ),
        "fungi": ("Грибы", "Гриб или грибное сырьё; съедобность задаётся отдельно."),
        "remains": (
            "Останки",
            "Останки существа; состав и однократная добыча задаются отдельно.",
        ),
        "rest_spot": (
            "Место для сна",
            "Разложенная лежанка, кровать или спальный мешок для длительного отдыха.",
        ),
        "living": (
            "Живое существо",
            "Биологическое существо по природе; текущие HP и смерть проверяются отдельно.",
        ),
        "humanoid": ("Гуманоид", "Тип существа; не материал его оружия."),
        "undead": ("Нежить", "Тип существа; не накладывает иммунитеты автоматически."),
    },
    "Назначение и источники": {
        "weapon": ("Оружие", "Предназначено для атаки; урон берётся из weapon_damage."),
        "armor": ("Броня", "Доспех; защита берётся из свойств и профиля."),
        "shield": ("Щит", "Щит; не всякий предмет в левой руке."),
        "clothing": (
            "Одежда",
            "Одежда, обувь или носимая ткань; не обязательно броня.",
        ),
        "tool": (
            "Инструмент",
            "Инструмент; отдельные теги набора уточняют назначение, владение отдельно.",
        ),
        "ammunition": (
            "Боеприпас",
            "Стрела или болт; тип урона зависит от фактической атаки.",
        ),
        "food": ("Пища", "Пищевой предмет; последствия употребления задаёт механика."),
        "potion": (
            "Зелье",
            "Авторское назначение средства; содержимое сосуда проверяется отдельно.",
        ),
        "book": ("Книга", "Физическая книга; читаемость требует текста или действия."),
        "rope": (
            "Верёвка",
            "Верёвка или канат; прочность и длина не кодируются тегами.",
        ),
        "key": ("Ключ", "Ключ; совместимость задаёт конкретная ссылка/тег замка."),
        "focus": (
            "Магический фокус",
            "Назначение для колдовства; не обязательно зачарованный предмет.",
        ),
        "mechanism": (
            "Механизм",
            "Механическое устройство; не гарантирует доступный разбор.",
        ),
        "furniture": (
            "Мебель",
            "Мебель; подвижность и разбор задаются собственными полями.",
        ),
        "door": ("Дверь", "Дверь или плита с DoorSpec; не просто рисунок прохода."),
        "portal": (
            "Портал",
            "Портал или телепорт; активность и переход определяются настройками.",
        ),
        "trap": (
            "Ловушка / опасность",
            "Проверяемая опасность; обнаружение и разбор проверяются отдельно.",
        ),
        "ignite": (
            "Поджигающий",
            "Явное назначение источника зажигания; для предмета проверяется can_ignite.",
        ),
        "repair": (
            "Восстанавливающий",
            "Действие ремонта; не свойство ремонтируемости цели.",
        ),
        "illusion": (
            "Иллюзия",
            "Иллюзорный источник/воздействие; реакции AI не включаются автоматически.",
        ),
        "noise": (
            "Шумный",
            "Явно шумное воздействие; дальность слышимости задаётся отдельно.",
        ),
        "aoe": (
            "Область",
            "Явно площадное действие; форма и цели задаются параметрами.",
        ),
        "utility": (
            "Вспомогательный",
            "Вспомогательное действие; не обещает все возможные операции.",
        ),
        "interaction": (
            "Манипуляция",
            "Действие взаимодействия с миром, например волшебная рука.",
        ),
    },
    "Типы воздействия (из damage_type)": {
        key: (
            DAMAGE_LABELS[key],
            "Тип воздействия; для урона источник истины — damage_type. Не задаёт побочные реакции.",
        )
        for key in sorted(DAMAGE_TYPES)
    },
    "Вычисляемые возможности и эффекты": {
        "destructible": (
            "Разрушаемый",
            "Есть DestructionSpec или разрушаемая дверь, либо изнашиваемый предмет.",
        ),
        "dismantlable": (
            "Разбираемый",
            "Есть конкретный рецепт разбора; не всякий разрушаемый объект.",
        ),
        "movable": (
            "Передвигаемый",
            "Объект разрешает перенос/сдвиг; вес и свободная клетка проверяются действием.",
        ),
        "repairable": (
            "Ремонтируемый",
            "Есть исправляемая прочность; фактический ремонт требует повреждения и рецепта.",
        ),
        "storage": ("Контейнер", "Есть StorageSpec; не любой сосуд для жидкости."),
        "vessel": ("Сосуд", "Есть VesselSpec, ёмкость для жидкости."),
        "heat_safe": (
            "Нагреваемый сосуд",
            "VesselSpec явно допускает нагревание; не выводится из металла.",
        ),
        "fragile": ("Хрупкий сосуд", "VesselSpec явно разрешает разбить при броске."),
        "readable": (
            "Читаемый",
            "Есть ReadingText; изображение свитка само по себе не даёт текст.",
        ),
        "recipe_source": ("Источник рецептов", "Явно выдаёт знания рецептов."),
        "water_source": (
            "Источник воды",
            "Есть WaterSourceSpec; количество и качество определяются им.",
        ),
        "station": (
            "Рабочая станция",
            "Есть известный тег станции; исправность проверяется рецептом.",
        ),
        "light_source": (
            "Источник света",
            "Есть источник света; горение и оставшееся время проверяются отдельно.",
        ),
        "heat": (
            "Источник тепла",
            "Действующий источник тепла; для костра зависит от горения и топлива.",
        ),
        "attack": ("Атака", "Атакующее действие или оружие с уроном."),
        "damage": (
            "Наносит урон",
            "Есть явно заданный урон; величина не кодируется тегом.",
        ),
        "healing": (
            "Лечит",
            "Есть эффект лечения; величина и доступность определяются эффектом.",
        ),
        "protection": ("Защита", "Есть свойство базовой КД или бонуса КД."),
        "condition": (
            "Накладывает состояние",
            "Есть эффект condition; конкретное состояние отдельным признаком.",
        ),
        "applies_poison": (
            "Накладывает отравление",
            "Есть condition poisoned; ядовитый урон сам по себе не накладывает отравление.",
        ),
        "applies_fear": ("Вызывает страх", "Есть condition frightened."),
        "applies_persuasion": ("Убеждает", "Есть condition persuaded."),
        "detect_magic": (
            "Обнаруживает магию",
            "Есть condition detect_magic; радиус и длительность в эффекте.",
        ),
        "antidote": ("Противоядие", "Средство явно снимает отравление."),
        "knowledge": ("Даёт знание", "Есть зарегистрированный эффект learn_recipe."),
        "reward": (
            "Выдаёт награду",
            "Есть эффект gold или experience; не материал цели.",
        ),
        "dodge": ("Уклонение", "Действие dodge; не обещает неуязвимость."),
        "stealth": ("Скрытность", "Действие stealth; успех определяет проверка."),
        "influence": (
            "Социальное воздействие",
            "Действие influence; не психический урон.",
        ),
    },
    "Текущее состояние (только экземпляр)": {
        "state_burning": (
            "Горит",
            "Источник реально горит; отличается от типа огненного урона.",
        ),
        "state_glowing": (
            "Светится",
            "Активное горение, свечение или зачарование Свет.",
        ),
        "state_broken": ("Сломан", "Прочность предмета равна нулю."),
        "state_damaged": ("Повреждён", "Текущая прочность ниже максимальной."),
        "state_contaminated": ("Загрязнён", "У экземпляра установлен contaminated."),
        "state_empty": ("Пустой сосуд", "В сосуде нет жидкости."),
        "state_filled": (
            "Есть жидкость",
            "Объём жидкости больше нуля, сосуд не обязательно полон.",
        ),
        "state_equipped": ("Экипирован", "Предмет экипирован."),
        "state_work_in_progress": (
            "Незавершённая работа",
            "Есть заготовка или прогресс разбора.",
        ),
        "state_locked": ("Заперт", "Дверь действительно заперта."),
        "state_open": ("Открыт", "Дверь открыта/проходима после разрушения."),
        "state_closed": ("Закрыт", "Дверь закрыта; не обязательно заперта."),
        "state_poisoned": (
            "Отравлен",
            "У существа действует poisoned; не означает ядовитое тело или атаку.",
        ),
        "state_frightened": ("Испуган", "У существа действует frightened."),
        "state_persuaded": ("Убеждён", "У существа действует persuaded."),
        "state_detect_magic": (
            "Обнаружение магии активно",
            "У существа действует detect_magic.",
        ),
    },
}

TAG_GROUPS["Инструменты и специальные назначения"] = {
    "lever": (
        "Рычаг / лом",
        "Инструмент рычага; существующие ускорения разбора и проверки.",
    ),
    "pickaxe": ("Кирка", "Инструмент для поддерживаемых каменных целей."),
    "lockpicks": (
        "Отмычки",
        "Инструмент взлома; работоспособность проверяется отдельно.",
    ),
    "lamp_oil": (
        "Топливо лампы",
        "Совместимо с текущей масляной лампой; не любое масло.",
    ),
    "tinder": ("Растопка", "Стартовый ингредиент костра; не любое топливо."),
    "stake": ("Кол", "Назначение кола; подпорка требует отдельного действия."),
    "blade": ("Клинок", "Явно клинковый инструмент; не всякий колющий предмет."),
    "writing": ("Для письма", "Принадлежности для письма; не всякая бумага."),
    "arcane": (
        "Магические знания",
        "Книга/принадлежность магических знаний, не обязательно зачарована.",
    ),
    "camping": ("Для лагеря", "Походная принадлежность; текущий спальный мешок."),
    "two_handed": (
        "Двуручный",
        "Совместимый старый тег; предпочтительно числовое поле hands.",
    ),
    **{
        key: (
            label,
            "Наличие набора. Владение с тем же ключом хранится отдельно в tool_proficiencies.",
        )
        for key, label in {
            "alchemist_tools": "Алхимические принадлежности",
            "brewer_tools": "Принадлежности пивовара",
            "calligrapher_tools": "Принадлежности каллиграфа",
            "carpenter_tools": "Инструменты плотника",
            "cartographer_tools": "Инструменты картографа",
            "cobbler_tools": "Инструменты сапожника",
            "cook_tools": "Кухонные принадлежности",
            "glassblower_tools": "Инструменты стеклодува",
            "herbalism_kit": "Набор травника",
            "jeweler_tools": "Инструменты ювелира",
            "leatherworker_tools": "Инструменты кожевника",
            "mason_tools": "Инструменты каменщика",
            "painter_tools": "Принадлежности художника",
            "poisoner_kit": "Набор отравителя",
            "potter_tools": "Инструменты гончара",
            "smith_tools": "Инструменты кузнеца",
            "tinker_tools": "Инструменты жестянщика",
            "weaver_tools": "Инструменты ткача",
            "woodcarver_tools": "Инструменты резчика",
        }.items()
    },
}
TAG_GROUPS["Станции"] = {
    key: (
        label,
        "Существующий ключ подходящей станции; состояние и соседство проверяет движок.",
    )
    for key, label in {
        "campfire": "Костёр",
        "forge": "Горн",
        "anvil": "Наковальня",
        "workbench": "Верстак",
        "alchemy_table": "Алхимический стол",
        "oven": "Печь",
    }.items()
}

TAG_GROUPS["Применение инструментов"] = {
    "door_brace": (
        "Подпорка",
        "Кол или клин, которым можно зафиксировать открытую или закрытую дверь.",
    ),
    "battering_ram": (
        "Таран",
        "Даёт преимущество при силовом выламывании двери, если экипирован.",
    ),
    "pole": (
        "Шест",
        "Позволяет работать с поддерживаемым объектом через одну свободную клетку.",
    ),
    "pole_reachable": (
        "Доступен шесту",
        "Допускает работу шестом на расстоянии двух клеток по прямой.",
    ),
}

TAG_CATALOG = {
    key: {"label": label, "description": description, "group": group}
    for group, entries in TAG_GROUPS.items()
    for key, (label, description) in entries.items()
}
AUTHORED_GROUPS = (
    *tuple(TAG_GROUPS)[:4],
    "Инструменты и специальные назначения",
    "Станции",
)
TAG_LABELS = {
    key: value[0]
    for group in AUTHORED_GROUPS
    for key, value in TAG_GROUPS[group].items()
}
TAG_LABELS["storage"] = "Контейнер"
TAG_SCHEMA = {
    "tag_labels": TAG_LABELS,
    "tag_groups": {group: list(TAG_GROUPS[group]) for group in AUTHORED_GROUPS}
    | {"Контейнер": ["storage"]},
}
TAGS_DESCRIPTION = "Игровые признаки; материалы и природа независимы. Возможности и состояния вычисляются из настроек. Каталог: docs/gameplay-tags.md. Старые и пользовательские теги сохраняются."
STATIONS = frozenset(
    {"campfire", "forge", "anvil", "workbench", "alchemy_table", "oven"}
)
ALIASES = {
    "поджог": "ignite",
    "fire_damage": "ignite",
    "light": "light_source",
    "cool": "cold",
    "glowing": "state_glowing",
}


def _get(value, key, default=None):
    return (
        value.get(key, default)
        if isinstance(value, Mapping)
        else getattr(value, key, default)
    )


def liquid_tags(kind):
    """Contents alone, never the glass/leather vessel around them."""
    if not kind:
        return frozenset()
    tags = {"liquid"}
    if kind.endswith("water"):
        tags.add("water")
    if kind == "holy_water":
        tags.add("holy")
    if kind == "poisoned_water":
        tags.add("poison")
    if kind in {"dirty_water", "swamp_water", "poisoned_water"}:
        tags.add("applies_poison")
    if kind in {"healing_potion", "healing_broth"}:
        tags.add("healing")
    if kind == "antidote":
        tags.add("antidote")
    if kind == "cactus_juice":
        tags.update({"plants", "organic", "food"})
    return frozenset(tags)


def interaction_tags(value, *, category=None, include_contents=True):
    """Semantic view for raw JSON, author definitions and live instances.

    Does not change Equipment.tags/Character.tags (tool permissions), grant actions,
    or expose hidden traits in player descriptions. Pass category for raw documents.
    """
    # Character.tags contains its inventory; body traits come only from race/innate tags.
    actor = _get(value, "innate_tags")
    if actor is not None:
        tags = set(actor)
        tags.update(_get(_get(value, "race"), "tags", ()))
        for condition, turns in _get(value, "conditions", {}).items():
            if turns > 0:
                tags.add("state_" + condition)
        return frozenset(tags)

    definition = _get(value, "definition")
    if definition is not None:
        vessel = _get(definition, "vessel")
        tags = set(
            interaction_tags(
                definition,
                category=_get(value, "category", category),
                include_contents=False if vessel else include_contents,
            )
        )
        cargo = _get(value, "furniture")
        if cargo:
            tags.update(interaction_tags(cargo, include_contents=include_contents))
        if vessel:
            if include_contents and _get(value, "liquid_portions", 0):
                tags.update(liquid_tags(_get(value, "liquid_kind")))
                for effect in _get(value, "liquid_effects", ()):
                    tags.update(interaction_tags(effect))
            tags.add(
                "state_filled" if _get(value, "liquid_portions", 0) else "state_empty"
            )
        state = _get(value, "state", value)
        if (
            _get(state, "lit", False)
            and _get(state, "fuel_minutes", 0) > 0
            and not _get(value, "broken", False)
        ):
            tags.update({"state_burning", "state_glowing"})
        elif _get(definition, "campfire"):
            tags.discard("heat")
        if _get(definition, "map_light") and not _get(definition, "campfire"):
            tags.add("state_glowing")
        if _get(state, "burning", False):
            tags.update({"state_burning", "state_glowing", "heat", "light_source"})
        if _get(value, "poison_damage", 0):
            tags.update({"poison", "damage"})
        if _get(value, "glow"):
            tags.update({"magic", "state_glowing", "light_source"})
        for field, tag in [
            ("equipped", "state_equipped"),
            ("contaminated", "state_contaminated"),
            ("work", "state_work_in_progress"),
            ("progress", "state_work_in_progress"),
        ]:
            if _get(state, field):
                tags.add(tag)
        current = _get(state, "durability", _get(state, "hp"))
        destruction = _get(definition, "destruction")
        maximum = _get(definition, "durability", _get(destruction, "max_hp"))
        if current is not None and maximum is not None and current < maximum:
            tags.add("state_broken" if current == 0 else "state_damaged")
        return frozenset(tags)

    tags = set(_get(value, "tags", ()))
    if _get(value, "poisonous", False):
        tags.add("poison")
    tags.update(ALIASES[t] for t in tuple(tags) if t in ALIASES)

    kind = _get(value, "kind")
    if kind in {"attack", "dodge", "stealth", "influence"}:
        tags.add(kind)
    if (
        kind == "magic"
        or category == "spells"
        or _get(value, "level") is not None
        or _get(value, "cast_spell")
        or _get(value, "spell_bonus", 0)
    ):
        tags.add("magic")
    if kind == "damage" or _get(value, "weapon_damage") or _get(value, "damage"):
        tags.add("damage")
        damage_type = "fire" if "fire_damage" in tags else _get(value, "damage_type")
        if damage_type:
            tags.add(damage_type)
        if _get(value, "weapon_damage"):
            tags.update({"weapon", "attack"})
    if kind == "heal":
        tags.add("healing")
    if kind in {"armor_class", "armor_bonus"}:
        tags.add("protection")
    if kind in {"gold", "experience"}:
        tags.add("reward")
    if kind == "learn_recipe":
        tags.add("knowledge")
    if kind == "condition":
        tags.add("condition")
        condition = _get(value, "condition")
        tags.update(
            {
                "poisoned": {"poison", "applies_poison"},
                "frightened": {"applies_fear"},
                "persuaded": {"applies_persuasion"},
                "detect_magic": {"detect_magic"},
            }.get(condition, ())
        )
    vessel = _get(value, "vessel")
    for effect in (*_get(value, "effects", ()), *_get(value, "on_enter", ())):
        tags.update(interaction_tags(effect))
    if not vessel:
        for effect in _get(value, "properties", ()):
            tags.update(interaction_tags(effect))
    else:
        tags.add("vessel")
        for field in ("fragile", "heat_safe"):
            if _get(vessel, field):
                tags.add(field)
        if include_contents and _get(vessel, "initial_portions", 0):
            tags.update(liquid_tags(_get(vessel, "initial_kind")))
            for effect in _get(value, "properties", ()):
                tags.update(interaction_tags(effect))
    destruction = _get(value, "destruction")
    if destruction or _get(value, "durability") is not None:
        tags.update({"destructible", "repairable"})
    if _get(value, "dismantle") or _get(destruction, "dismantle"):
        tags.add("dismantlable")
    for field, tag in [
        ("movable", "movable"),
        ("storage", "storage"),
        ("reading", "readable"),
        ("learn_recipes", "recipe_source"),
        ("water_source", "water_source"),
        ("light", "light_source"),
        ("map_light", "light_source"),
    ]:
        if _get(value, field):
            tags.add(tag)
    if _get(_get(value, "reading"), "learn_recipes"):
        tags.add("recipe_source")
    if _get(value, "campfire"):
        tags.add("light_source")
    if tags & STATIONS:
        tags.add("station")
    if category == "traps" or _get(value, "trigger") == "enter":
        tags.add("trap")
        for effect in (*_get(value, "success", ()), *_get(value, "failure", ())):
            tags.update(interaction_tags(effect))
    brush = _get(value, "brush")
    door = _get(brush, "door")
    # Live Door has material/opened/hp directly, unlike author DoorSpec.
    if (
        door is None
        and _get(value, "material") is not None
        and _get(value, "max_hp") is not None
    ):
        door = value
    if door:
        material = _get(door, "material")
        tags.update({"door", "destructible"})
        tags.update(
            {
                "wood": {"wooden", "flammable"},
                "stone": {"stone"},
                "steel": {"metal", "iron"},
                "bars": {"metal", "iron"},
                "adamantine": {"metal", "adamantine"},
            }.get(material, ())
        )
        if door is value:
            tags.add("state_open" if _get(value, "passable", False) else "state_closed")
            if _get(value, "locked") and not _get(value, "destroyed"):
                tags.add("state_locked")
            if _get(value, "burning"):
                tags.add("state_burning")
            if _get(value, "hp") < _get(value, "max_hp"):
                tags.add(
                    "state_broken" if _get(value, "destroyed") else "state_damaged"
                )
    return frozenset(tags)
