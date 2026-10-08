import { Doc, Entry } from "./model";

export const sections: Record<
  string,
  { icon: string; name: string; description: string; family: string }
> = {
  maps: {
    icon: "⌗",
    name: "Карты",
    description:
      "Рисуйте подземелья, размещайте объекты и проверяйте приключение.",
    family: "Мир",
  },
  tiles: {
    icon: "▦",
    name: "Тайлы и кисти",
    description:
      "Одна клетка: рисунок, проходимость и готовые размещения механики.",
    family: "Мир",
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
      "Сундуки, алтари и события: объект карты с текстовым испытанием.",
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
  const brush = tile.brush ?? {};
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
