import { Doc, Entry } from "./model";

export const sections: Record<
  string,
  { icon: string; name: string; description: string; family: string }
> = {
  recipes: {
    icon: "⚒",
    name: "Рецепты",
    description:
      "Материалы, инструменты, владения, станции и пошаговое изготовление.",
    family: "Правила",
  },
  maps: {
    icon: "⌗",
    name: "Карты",
    description:
      "Рисуйте подземелья, размещайте объекты и проверяйте приключение.",
    family: "Мир",
  },
  tiles: {
    icon: "▦",
    name: "Поверхности",
    description:
      "Пол, стены, вода и природный рельеф; независимые маски карты.",
    family: "Мир",
  },
  objects: {
    icon: "+",
    name: "Окружение",
    description:
      "Двери, мебель, свет и переходы: рисунок и свойства в одном шаблоне.",
    family: "Объекты",
  },
  art: {
    icon: "░",
    name: "Рисунки",
    description:
      "Многоклеточные арты со слоями: портреты, декорации и иллюстрации.",
    family: "Мир",
  },
  monsters: {
    icon: "♜",
    name: "Существа",
    description: "Характеристики, хиты и действия; на карте блокируют проход.",
    family: "Объекты",
  },
  equipment: {
    icon: "◇",
    name: "Предметы",
    description: "Подбираемое снаряжение, расходники, оружие и инструменты.",
    family: "Объекты",
  },
  traps: {
    icon: "^",
    name: "Ловушки",
    description: "Триггер входа, проверка, последствия и повторяемость.",
    family: "Объекты",
  },
  points_of_interest: {
    icon: "$",
    name: "Взаимодействия",
    description:
      "Сундуки, алтари, записки и доски: испытания и тексты для чтения.",
    family: "Объекты",
  },
  challenges: {
    icon: "?",
    name: "Испытания",
    description:
      "Текст, варианты выбора, проверки и награды для взаимодействий.",
    family: "Правила",
  },
  spells: {
    icon: "✦",
    name: "Заклинания",
    description: "Уровни, цели и эффекты магии.",
    family: "Правила",
  },
  actions: {
    icon: "↯",
    name: "Действия",
    description: "Атаки и особые приёмы героев и существ.",
    family: "Правила",
  },
  classes: {
    icon: "♙",
    name: "Классы",
    description: "Стартовые хиты, снаряжение, магия и действия персонажа.",
    family: "Персонаж",
  },
  races: {
    icon: "♧",
    name: "Расы",
    description: "Бонусы характеристик и расовые особенности.",
    family: "Персонаж",
  },
  backgrounds: {
    icon: "≡",
    name: "Предыстории",
    description: "Навыки, стартовые предметы и теги для событий.",
    family: "Персонаж",
  },
};

// Palette sections describe purpose; paletteLayer still owns storage/painting.
export const paletteSections: Record<
  string,
  { name: string; description: string }
> = {
  floor: {
    name: "Пол",
    description:
      "Основание клетки: пол, земля, вода и рельеф. Не разбирается; строительство сможет заменить покрытие.",
  },
  wall: {
    name: "Стены",
    description:
      "Постоянные преграды движению. Прозрачность задаётся отдельно: решётки и ограды могут пропускать свет.",
  },
  destructible: {
    name: "Разрушаемые тайлы",
    description:
      "Специально отмеченные преграды и ресурсы: потресканные стены, баррикады, руда, завалы и растительность.",
  },
  doors: {
    name: "Двери",
    description:
      "Открываются, закрываются и выламываются. Разбор не предусмотрен; остатки после разрушения — будущий источник материалов.",
  },
  traps: {
    name: "Ловушки",
    description:
      "Настоящие ловушки с условиями обнаружения и срабатывания. Базовый разбор обнаруженной ловушки — следующий этап.",
  },
  furniture: {
    name: "Мебель",
    description:
      "Мебель и контейнеры. Назначение: разбор, подъём в пределах переносимого веса и перемещение на одну из 8 клеток вокруг героя.",
  },
  equipment: {
    name: "Предметы",
    description:
      "Подбираются в инвентарь и исчезают с карты; брошенные предметы снова появляются на земле.",
  },
  special: {
    name: "Особое",
    description:
      "Порталы, статуи, механизмы, записки и декорации. Защищены от уничтожения, пока автор явно не назначит другую возможность.",
  },
  monsters: {
    name: "Существа",
    description:
      "Монстры и другие существа. Полноценные NPC подключаются к этому же разделу.",
  },
  service: {
    name: "Служебные",
    description:
      "Источники света, старт героя, переходы между уровнями и независимые маски карты.",
  },
};
export const mapCategoryNames: Record<string, string> = {
  auto: "Автоматически",
  ...Object.fromEntries(
    Object.entries(paletteSections)
      .filter(([id]) =>
        ["floor", "wall", "destructible", "furniture", "special"].includes(id),
      )
      .map(([id, value]) => [id, value.name]),
  ),
};

export function paletteCategory(
  entry: Entry,
  assets: Record<string, Doc> = {},
): string | null {
  const doc: Doc = {
    ...entry,
    ...(entry.details ?? {}),
    ...(assets[entry.category + "/" + entry.ref] ?? {}),
  };
  const tags: string[] = doc.tags ?? [];
  if (doc.brush?.door) return "doors";
  if (
    entry.category === "equipment" ||
    entry.category === "monsters" ||
    entry.category === "traps"
  )
    return entry.category;
  if (entry.category === "art") return "special";
  if (!["tiles", "objects", "points_of_interest"].includes(entry.category))
    return null;
  if (doc.map_category && doc.map_category !== "auto") return doc.map_category;
  if (tags.includes("furniture") || doc.storage || entry.features?.storage)
    return "furniture";
  if (
    tags.some((t) =>
      ["portals", "teleports", "statues", "magic", "shrines", "runes"].includes(
        t,
      ),
    )
  )
    return "special";
  if (tags.includes("stairs") && doc.brush?.transition) return "service";
  if (
    tags.some((t) =>
      ["destructible", "plants", "fungi", "ruins", "webs"].includes(t),
    )
  )
    return "destructible";
  if (entry.category !== "tiles") return "special";
  if (tags.some((t) => ["walls", "fences"].includes(t))) return "wall";
  if (
    tags.some((t) =>
      ["floors", "water", "height", "ice", "blood", "tracks"].includes(t),
    )
  )
    return "floor";
  if (tags.some((t) => ["gas", "trap_decor", "keys"].includes(t)))
    return "special";
  return doc.walkable === false ? "wall" : "floor";
}

export function tileFamily(tile: Doc): string {
  const tags: string[] = tile.tags ?? [];
  if (!tags.length) {
    if (!tile.walkable && tile.blocks_sight) return "Архитектура";
    if (
      [".", "·"].includes(tile.glyph) ||
      (tile.group ?? "").toLowerCase().includes("пол")
    )
      return "Поверхности";
  }
  if (
    tags.includes("walls") ||
    tags.includes("doors") ||
    tags.includes("fences")
  )
    return "Архитектура";
  if (
    tags.some((t) => ["floors", "earth", "height", "ice", "water"].includes(t))
  )
    return "Поверхности";
  if (tags.some((t) => ["plants", "fungi", "gas", "webs"].includes(t)))
    return "Природа";
  if (tags.some((t) => ["fire", "acid", "trap_decor"].includes(t)))
    return "Опасности";
  if (
    tags.some((t) =>
      [
        "runes",
        "shrines",
        "magic",
        "portals",
        "teleports",
        "lighting_decor",
      ].includes(t),
    )
  )
    return "Магия и свет";
  if (
    tags.some((t) =>
      [
        "treasure",
        "weapon_decor",
        "armor_decor",
        "supplies_decor",
        "artifacts",
        "keys",
      ].includes(t),
    )
  )
    return "Вещи и сокровища";
  if (tags.includes("stairs") || tags.includes("markers"))
    return "Переходы и метки";
  return "Обстановка";
}

export function brushDescription(
  tile: Doc,
  assets: Record<string, Doc>,
): string[] {
  const rules = [
    tile.walkable ? "Проход разрешён" : "Движение запрещено",
    tile.blocks_sight ? "Закрывает обзор и свет" : "Пропускает обзор и свет",
  ];
  if ((tile.tags ?? []).includes("wooden"))
    rules.push("Материал: дерево / деревянные части.");
  if ((tile.tags ?? []).includes("flammable"))
    rules.push("Горючий материал (flammable).");
  const brush = tile.brush ?? {};
  if (brush.door) {
    const d = brush.door;
    const dc: Record<string, number> = {
      cheap: 10,
      normal: 15,
      expensive: 20,
      legendary: 25,
    };
    const force: Record<string, number> = {
      wood: 10,
      bars: 15,
      steel: 20,
      adamantine: 25,
    };
    if (d.material !== "stone")
      rules.push(
        `Enter: открыть / закрыть / вскрыть / выломать. Взлом: СЛ ${dc[d.lock_quality ?? "normal"]}, ${d.lock_complexity === "complex" ? 10 : 1} ход(ов). Нужны исправные воровские инструменты; провал: −1 прочность.`,
      );
    if (d.material !== "stone")
      rules.push(
        `Выломать: СИЛ, СЛ ${force[d.material ?? "wood"]}. Ломик в руке: преимущество, −1 прочность за попытку.`,
      );
    rules.push(
      d.material === "stone"
        ? "Обозначение: # каменная плита."
        : "Обозначения: + закрыта, X заперта, / открыта. Цвет задаёт материал.",
    );
    rules.push(
      d.material === "stone"
        ? "Выделение (V) → плита: HP конкретного экземпляра."
        : "Выделение (V) → дверь: состояние, замок и HP конкретного экземпляра.",
    );
    if (d.material === "bars")
      rules.push("Прутья пропускают свет; согнуть: СИЛ, СЛ 20.");
    if (d.material === "wood") rules.push("Можно атаковать и поджечь.");
    if (d.material === "steel")
      rules.push(
        "Физический урон не действует; кислота наносит двойной урон и вызывает коррозию.",
      );
    if (d.material === "stone")
      rules.push(
        "Каменная плита: нельзя открыть, вскрыть или выломать; только разрушение киркой или дробящими атаками.",
      );
    if (d.material === "adamantine")
      rules.push(
        "Неуничтожима; «Дневной свет» волшебника превращает её в каменную.",
      );
  }
  if (brush.trap) {
    const trap = assets["traps/" + brush.trap];
    rules.push(
      `Триггер: вход на клетку · ${trap?.name ?? brush.trap}${trap ? ` · СЛ ${trap.difficulty}${trap.hidden ? " · скрытая" : ""}` : ""}`,
    );
    if (trap?.failure?.length)
      rules.push(
        "При провале: " + trap.failure.map(effectDescription).join(", "),
      );
  }
  if (brush.interaction) {
    rules.push(
      "Enter: " +
        (assets["points_of_interest/" + brush.interaction]?.name ??
          brush.interaction),
    );
    const point = assets["points_of_interest/" + brush.interaction];
    const challenge = point ? assets["challenges/" + point.challenge] : null;
    if (challenge) {
      rules.push(
        "Выбор: " +
          challenge.choices.map((choice: Doc) => choice.text).join("; "),
      );
      const effects = [
        ...new Set<string>(
          challenge.choices.flatMap((choice: Doc) =>
            (choice.success ?? []).map(effectDescription),
          ),
        ),
      ];
      if (effects.length) rules.push("Награда: " + effects.join(", "));
    }
  }
  if (brush.item) {
    rules.push(
      "Можно подобрать: " +
        (assets["equipment/" + brush.item]?.name ?? brush.item),
    );
    const item = assets["equipment/" + brush.item];
    if (item)
      rules.push(
        `Вес ${item.weight} кг` +
          (item.weapon_damage ? ` · урон ${item.weapon_damage}` : "") +
          (item.properties?.length
            ? " · " + item.properties.map(effectDescription).join(", ")
            : ""),
      );
  }
  if (brush.light)
    rules.push(
      `Освещает: яркий ${brush.light.bright_radius}, тусклый ${brush.light.radius} кл.`,
    );
  if (brush.transition) rules.push("Переход на выбранную карту при входе");
  if (!Object.values(brush).some(Boolean))
    rules.push("Рисунок и маски, без дополнительных событий");
  return rules;
}

function effectDescription(effect: Doc): string {
  const amount =
    [effect.dice, effect.amount ? String(effect.amount) : ""]
      .filter(Boolean)
      .join("+") || "0";
  const labels: Record<string, string> = {
    damage: "урон",
    heal: "восстановление HP",
    gold: "золото",
    experience: "опыт",
    armor_class: "КД",
    armor_bonus: "бонус КД",
  };
  if (effect.kind === "condition")
    return `состояние ${effect.condition === "poisoned" ? "отравление" : effect.condition} (${effect.duration} ход.)`;
  return `${labels[effect.kind] ?? effect.kind}: ${amount}`;
}

export function paletteEntry(entry: Entry, assets: Record<string, Doc>): Doc {
  return assets[entry.category + "/" + entry.ref] ?? entry;
}

export function paletteLayer(
  entry: Entry,
  assets: Record<string, Doc>,
): string | null {
  if (entry.category === "art") return "decorations";
  if (entry.category === "objects")
    return paletteEntry(entry, assets).brush?.door ? "doors" : "objects";
  return [
    "tiles",
    "equipment",
    "traps",
    "points_of_interest",
    "monsters",
  ].includes(entry.category)
    ? entry.category
    : null;
}

export const craftNames: Record<string, string> = {
  basic: "Базовые",
  herbalist: "Травник",
  alchemist: "Алхимик",
  smith: "Кузнец",
  carpenter: "Плотник",
  tinker: "Жестянщик",
  leatherworker: "Кожевник",
  weaver: "Ткач",
  woodcarver: "Резчик",
  cook: "Повар",
  poisoner: "Отравитель",
  mason: "Каменщик",
  glassblower: "Стеклодув",
  potter: "Гончар",
  jeweler: "Ювелир",
  cobbler: "Сапожник",
  brewer: "Пивовар",
  cartographer: "Картограф",
  calligrapher: "Каллиграф",
  magic: "Магический крафт",
  experiment: "Эксперименты",
  other: "Прочее",
};
export const schoolNames: Record<string, string> = {
  abjuration: "Ограждение",
  conjuration: "Вызов",
  divination: "Прорицание",
  enchantment: "Очарование",
  evocation: "Воплощение",
  illusion: "Иллюзия",
  necromancy: "Некромантия",
  transmutation: "Преобразование",
};
export const itemNames: Record<string, string> = {
  weapons: "Оружие",
  armor: "Доспехи",
  consumables: "Расходники",
  tools: "Инструменты",
  materials: "Материалы",
};
export function contentGroup(
  entry: Entry,
  assets: Record<string, Doc> = {},
): string {
  const d = assets[entry.category + "/" + entry.ref] ?? entry.details ?? {};
  const tags = entry.tags ?? [];
  if (entry.category === "recipes")
    return craftNames[d.category] ?? d.category ?? "Прочее";
  if (entry.category === "spells") return schoolNames[d.school] ?? "Заклинания";
  if (entry.category === "monsters") {
    const hp = Number(d.hit_points);
    return !hp
      ? "Живучесть не указана"
      : hp <= 10
        ? "1–10 HP"
        : hp <= 30
          ? "11–30 HP"
          : hp <= 100
            ? "31–100 HP"
            : "101+ HP";
  }
  if (entry.category === "equipment")
    return itemNames[d.category] ?? entry.group ?? "Снаряжение";
  if (entry.category === "tiles") return tileFamily({ ...entry, ...d });
  if (entry.category === "maps")
    return (
      (
        {
          dark: "Тёмные локации",
          dim: "Тусклое освещение",
          bright: "Светлые локации",
        } as Doc
      )[d.ambient_light] ?? "Локации"
    );
  if (entry.category === "objects" || entry.category === "points_of_interest") {
    if (d.reading || entry.features?.reading || tags.includes("reading"))
      return "Тексты для чтения";
    if (d.brush?.door || tags.includes("doors") || tags.includes("door"))
      return "Двери";
    if (d.storage || entry.features?.storage || tags.includes("storage"))
      return "Контейнеры";
    if (d.map_light || entry.features?.map_light || tags.includes("light"))
      return "Освещение";
    if (tags.includes("furniture")) return "Мебель";
  }
  if (entry.category === "actions")
    return (
      (
        {
          attack: "Атаки",
          dodge: "Защита",
          magic: "Магия",
          stealth: "Скрытность",
          influence: "Влияние",
          special: "Особые действия",
        } as Doc
      )[d.kind] ?? "Действия"
    );
  return entry.group ?? sections[entry.category]?.name ?? "Прочее";
}
export function contentRank(entry: Entry): number {
  return Number(entry.details?.level ?? entry.details?.hit_points ?? 0);
}
export function contentBadges(entry: Entry): string[] {
  const d = entry.details ?? {};
  return [
    contentGroup(entry),
    ...(entry.category === "spells" && d.level != null
      ? [d.level === 0 ? "Заговор" : `${d.level} уровень`]
      : []),
    ...(entry.category === "monsters" && d.hit_points
      ? [`HP ${d.hit_points}`, `КД ${d.armor_class}`]
      : []),
    ...(entry.category === "recipes"
      ? [d.basic_known ? "Известен сразу" : "Нужно изучить"]
      : []),
  ];
}
