import { SymbolSelect } from "./Symbols";
import { useState, useEffect, useRef } from "react";
import { ContentSelect } from "./ContentBrowser";
import { craftNames, mapCategoryNames } from "./catalog";
import { Doc, Entry, defaultFor, color } from "./model";
import { damageLabels } from "./damage";
const skillLabels: Record<string, string> = {
  acrobatics: "Акробатика",
  animal_handling: "Уход за животными",
  arcana: "Магия",
  athletics: "Атлетика",
  deception: "Обман",
  history: "История",
  insight: "Проницательность",
  intimidation: "Запугивание",
  investigation: "Расследование",
  medicine: "Медицина",
  nature: "Природа",
  perception: "Внимательность",
  performance: "Выступление",
  persuasion: "Убеждение",
  religion: "Религия",
  sleight_of_hand: "Ловкость рук",
  stealth: "Скрытность",
  survival: "Выживание",
};
const labels: Record<string, string> = {
  greeting: "Приветствие",
  topics: "Вопросы",
  question: "Вопрос",
  answer: "Ответ",
  failure_answer: "Ответ при провале",
  once: "Скрыть после получения ответа",
  conditions: "Условия видимости",
  reward: "Награда",
  failure_reward: "Последствия провала",
  trade: "Магазин",
  stock: "Начальный ассортимент",
  rules: "Правила цен (первое совпадение)",
  buy: "Выкуп у игрока, зол.",
  sell: "Продажа игроку, зол.",
  percent: "Поправка Убеждения, %",
  quests: "Задания NPC",
  quest: "Квест",
  stages: "Этапы",
  objectives: "Цели",
  report_to: "Отчёт NPC (пусто — автоматически)",
  map_ref: "Карта",
  npc_id: "ID размещения NPC",
  target_id: "ID размещения цели",
  consume: "Передать предметы при сдаче",
  offer: "Предложить задание",
  accept_answer: "Ответ при принятии",
  discuss: "Обсудить задание",
  discuss_answer: "Ответ о ходе задания",
  report: "Доложить",
  report_answer: "Ответ при отчёте",
  stage: "ID этапа",
  topic: "ID вопроса",
  outcome: "Результат вопроса",
  status: "Статус задания",
  furniture: "Шаблон мебели",
  tag: "Группа по тегу",
  recipe: "Рецепт",
  gold: "Золото",
  experience: "Опыт",
  cast_spell: "Заклинание свитка",
  spell_bonus: "Бонус фокуса к магической атаке и СЛ",
  operation: "Операция с предметом или миром",
  target_tags: "Материал или назначение цели",
  liquids: "Подходящие виды жидкости",
  portions: "Количество порций",
  liquid_result: "Жидкость после обработки (пусто — расход)",
  repair_amount: "Восстановить прочности",
  place_object: "Создаваемый объект",
  place_trap: "Устанавливаемая ловушка",
  poison_damage: "Ядовитый урон следующего попадания",
  value_gold: "Стоимость, раскрываемая оценкой (золото)",
  disarm: "Обезвреживание: провал вызывает срабатывание",
  verb: "Вид работы",
  ignition: "Требуется источник зажигания",
  vessel: "Сосуд и начальное содержимое",
  capacity_portions: "Вместимость, порции",
  heat_safe: "Допускается нагревание",
  fragile: "Разбивается при броске",
  initial_kind: "Начальная жидкость",
  initial_portions: "Начальное количество порций",
  water_source: "Источник жидкости",
  campfire: "Костёр",
  fuel_minutes: "Минут горения на единицу топлива",
  destruction: "Разрушение и разбор",
  regrow_minutes: "Восстановление через (игровые минуты)",
  regrow_as: "Молодое растение после сбора",
  poisonous: "Ядовитое растение",
  dismantle: "Разбор",
  loot: "Материалы после разбора",
  bonus_tools: "Инструменты или типы урона для дополнительной добычи",
  bonus_loot: "Дополнительная добыча с инструментом",
  on_enter: "Воздействие при входе на клетку",
  rarity: "Редкость",
  remains: "Остатки после разрушения",
  door_remains: "Остатки сломанной двери",
  max_hp: "Максимальная прочность",
  movable: "Можно поднять и передвинуть",
  fast_tool: "Инструмент для ускорения",
  fast_turns: "Ходы с инструментом",
  open_tool: "Тег инструмента для открытия (пусто — открыто)",
  search_contents: "Разрешить поиск ценностей",
  light_fixture: "Подставка для источника света",
  stays_when_empty: "Оставлять подставку после снятия",
  id: "Идентификатор",
  ingredients: "Ингредиенты",
  items: "Подходящие материалы (один из вариантов)",
  result: "Результат изготовления",
  tools: "Теги нужных инструментов",
  proficiencies: "Нужные владения инструментами",
  tool_proficiencies: "Владения инструментами",
  tool_expertise: "Экспертиза инструментов",
  tool: "Инструмент проверки (вместо навыка)",
  starting_recipes: "Начальные рецепты",
  stations: "Станции: все группы, один вариант внутри группы",
  turns: "Ходы изготовления",
  basic_known: "Рецепт известен с начала игры",
  check: "Проверка рискованной работы",
  name: "Название",
  description: "Описание",
  glyph: "Текстовый знак (совместимость)",
  symbol: "Символ из библиотеки",
  state_symbols: "Символы состояний",
  mirror_x: "Отразить по горизонтали",
  rotation: "Направление (поворот по часовой стрелке)",
  loot_tier: "Цветовая категория добычи",
  underlay: "Тайл под предметом",
  door: "Дверь",
  material: "Материал двери",
  access: "Правило открытия двери",
  travel: "Переход при подтверждённом открытии",
  destination: "Локация назначения двери",
  mechanism_targets: "ID связанных целей на карте",
  mechanism: "Активирующий механизм",
  initially_on: "Рычаг включён изначально",
  code: "Код сигнала",
  activation_code: "Код активации",
  illusion: "Иллюзорная стена: исчезает при сигнале",
  growth: "Рост растения",
  grown_object: "Взрослое растение",
  chance: "Шанс добычи, %",
  state: "Начальное состояние",
  locked: "Заперта",
  lock_quality: "Качество замка (СЛ)",
  lock_complexity: "Механизм замка (длительность)",
  foreground: "Цвет символа",
  background: "Цвет фона",
  art: "Рисунок",
  stats: "Характеристики",
  strength: "Сила",
  dexterity: "Ловкость",
  constitution: "Телосложение",
  intelligence: "Интеллект",
  wisdom: "Мудрость",
  charisma: "Харизма",
  hit_points: "Хиты",
  attackable: "Можно атаковать",
  transmits_light: "Пропускает свет в закрытом состоянии",
  openable: "Есть открываемая створка",
  force_allowed: "Можно выломать",
  bend_difficulty: "СЛ сгибания прутьев",
  bent: "Прутья погнуты (проход свободен)",
  armor_class: "Класс доспеха",
  speed: "Скорость",
  initiative_bonus: "Бонус инициативы",
  actions: "Действия",
  special_actions: "Особые действия",
  inventory: "Инвентарь",
  storage: "Контейнер",
  reading: "Текст для чтения",
  learn_recipes: "Изучаемые рецепты",
  learn_on_proficiency: "Изучается с владением инструментами",
  title: "Заголовок текста",
  pages: "Страницы",
  capacity: "Вместимость, кг",
  lock: "Замок",
  key_tag: "Тег подходящего ключа",
  key_kind: "Вид ключа",
  key_code: "Код уникального замка / ключа",
  size: "Размер предмета",
  max_item_size: "Максимальный размер предмета",
  personal: "Личный (можно класть вещи; не обновляется)",
  contents: "Начальное содержимое",
  quantity: "Количество предметов",
  spells: "Заклинания",
  spell_slots: "Ячейки заклинаний",
  tags: "Теги",
  kind: "Механика",
  ability: "Характеристика",
  bonus: "Бонус",
  damage: "Кубики урона",
  damage_type: "Тип урона",
  damage_profile: "Защита от урона",
  resistances: "Сопротивления (½ урона)",
  vulnerabilities: "Уязвимости (двойной урон)",
  immunities: "Иммунитеты (нет урона)",
  effects: "Эффекты",
  difficulty: "Сложность",
  weight: "Вес, кг",
  category: "Тип снаряжения",
  map_category: "Категория на карте",
  durability: "Стойкость",
  slot: "Слот снаряжения",
  hands: "Занимает рук (0–2)",
  light: "Источник света",
  radius: "Общий радиус света, клеток",
  bright_radius: "Яркий радиус света, клеток",
  burn_minutes: "Запас горения, минут",
  fuel_tag: "Тег топлива (пусто — одноразовый)",
  ambient_light: "Освещение карты",
  properties: "Свойства",
  check_aids: "Помощь в проверках",
  weapon_damage: "Кубики оружия",
  weapon_ability: "Характеристика оружия",
  charges: "Применения",
  level: "Уровень (0 — заговор)",
  school: "Школа магии",
  modes: "Режимы применения",
  range: "Дальность, клеток",
  resolution: "Бросок",
  save_ability: "Характеристика спасброска",
  cantrip_scaling: "Масштабирование урона на уровнях 5/11/17",
  wounded_dice: "Кубики против раненой цели",
  max_targets: "Максимум целей",
  world_effect: "Механика исследования",
  world_parameters: "Параметры исследования",
  concentration: "Требует концентрации",
  pending_effects: "Отложенные эффекты (подсказки)",
  spellcasting_ability: "Заклинательская характеристика",
  cantrip_choices: "Доступные заговоры",
  cantrips_known: "Количество заговоров на выбор",
  tool_amount: "Починка инструментов",
  equipment_dice: "Починка оружия и доспехов",
  max_weight: "Предел веса руки, кг",
  target: "Цель",
  ability_bonuses: "Бонусы характеристик",
  hp_per_level: "Хиты за уровень",
  racial_spell: "Расовое заклинание",
  racial_uses: "Расовые применения",
  order: "Порядок",
  starting_items: "Стартовые предметы",
  classes: "Доступно классам",
  skills: "Владения навыками",
  skill: "Навык проверки",
  skill_choices: "Доступные навыки класса",
  skills_known: "Количество выбираемых навыков",
  expertise_count: "Количество навыков с экспертизой на старте",
  carry_per_strength: "Нагрузка на единицу силы",
  text: "Текст",
  choices: "Варианты выбора",
  repeatable: "Повторяемое",
  check_tag: "Тег проверки",
  required_tags: "Обязательные теги",
  visible_tags: "Теги для показа варианта",
  advantage_tags: "Теги преимущества",
  automatic_tags: "Теги автоматического успеха",
  success: "Последствия успеха",
  failure: "Последствия провала",
  minutes: "Минуты",
  hidden: "Скрытая",
  trigger: "Условие активации",
  challenge: "Испытание",
  walkable: "Проходимый",
  blocks_sight: "Преграждает обзор",
  group: "Группа",
  variants: "Варианты внешнего вида",
  map_light: "Свет объекта на карте",
  brush: "Размещения при рисовании",
  trap: "Ловушка при входе",
  interaction: "Взаимодействие по Enter",
  item: "Подбираемый предмет",
  transition: "Переход (цель выбирается на карте)",
  amount: "Количество",
  dice: "Кубики",
  condition: "Состояние",
  duration: "Длительность",
  mode: "Режим",
  params: "Параметры",
};
function resolve(s: Doc, root: Doc): Doc {
  return s.$ref ? resolve(root.$defs[s.$ref.split("/").pop()!], root) : s;
}
export const fieldLabel = (key: string, root?: Doc) =>
  root?.title === "RecipeDocument" && key === "variants"
    ? "Способы изготовления"
    : root?.title === "RecipeDocument" && key === "category"
      ? "Ремесло"
      : (labels[key] ?? key);

type Props = {
  schema: Doc;
  root: Doc;
  value: any;
  onChange: (v: any) => void;
  entries: Entry[];
  mechanics: Doc[];
  label?: string;
  refCategory?: string;
  lockedId?: boolean;
  path?: string;
};
function TagPicker({
  labels,
  groups,
  items,
  onChange,
}: {
  labels: Record<string, string>;
  groups?: Record<string, string[]>;
  items: string[];
  onChange: (value: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase();
  const quick = Object.keys(labels).filter(
    (tag) =>
      items.includes(tag) || ["flammable", "wooden", "storage"].includes(tag),
  );
  const choice = (tag: string) => (
    <label key={tag}>
      <input
        type="checkbox"
        aria-label={labels[tag]}
        checked={items.includes(tag)}
        onChange={(e) =>
          onChange(
            e.target.checked
              ? [...items, tag]
              : items.filter((value) => value !== tag),
          )
        }
      />
      {labels[tag]} <small>({tag})</small>
    </label>
  );
  const sections = Object.entries(
    groups ?? { Признаки: Object.keys(labels) },
  ).map(([group, tags]) => {
    const visible = tags.filter(
      (tag) =>
        labels[tag] &&
        (needle
          ? `${labels[tag]} ${tag}`.toLocaleLowerCase().includes(needle)
          : !quick.includes(tag)),
    );
    return visible.length ? (
      <fieldset key={group}>
        <legend>{group}</legend>
        <div className="toolbar">{visible.map(choice)}</div>
      </fieldset>
    ) : null;
  });
  return (
    <div className="tag-picker">
      <input
        type="search"
        aria-label="Поиск игровых тегов"
        placeholder="Найти тег: камень, poison, магия…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {needle ? (
        <div className="tag-options">
          {sections.some(Boolean) ? sections : <p>Теги не найдены</p>}
        </div>
      ) : (
        <>
          <div className="toolbar">{quick.map(choice)}</div>
          <details>
            <summary>Все игровые признаки по группам</summary>
            <div className="tag-options">{sections}</div>
          </details>
        </>
      )}
      <small>
        Теги описывают свойства. Прочность, перемещение, содержимое и эффекты
        настраиваются в своих разделах.
      </small>
    </div>
  );
}

export function FieldForm({
  schema,
  root,
  value,
  onChange,
  entries,
  mechanics,
  label = "",
  refCategory,
  lockedId = false,
  path = "",
}: Props) {
  const original = resolve(schema, root);
  let s = original;
  const nullable = s.anyOf?.some((x: Doc) => x.type === "null");
  if (s.anyOf)
    s = resolve(
      s.anyOf.find((x: Doc) => x.type !== "null"),
      root,
    );
  const title = label ? fieldLabel(label, root) : "";
  const category = refCategory ?? original.ref_category ?? s.ref_category;
  if (label === "key_code")
    return (
      <div className="field">
        <label>{title}</label>
        {original.generate_key_code && (
          <label className="check">
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? crypto
                        .randomUUID()
                        .replaceAll("-", "")
                        .slice(0, 8)
                        .toUpperCase()
                    : null,
                )
              }
            />
            Уникальный замок
          </label>
        )}
        {(!original.generate_key_code || value) && (
          <input
            aria-label={title}
            type="text"
            maxLength={16}
            value={value ?? ""}
            placeholder="Вставьте код замка"
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) =>
              onChange(e.target.value.trim().toUpperCase() || null)
            }
          />
        )}
        <small>{original.description}</small>
      </div>
    );
  if (label === "symbol")
    return (
      <div className="field">
        <label>{title}</label>
        <SymbolSelect value={value} onChange={onChange} label={title} />
      </div>
    );
  if (nullable && value == null)
    return (
      <div className="field">
        <label>{title}</label>
        <button
          className="subtle"
          onClick={() => onChange(defaultFor(s, root))}
        >
          + Задать
        </button>
      </div>
    );
  const clear = nullable ? (
    <button
      className="mini"
      title="Сбросить значение"
      onClick={() => onChange(null)}
    >
      ×
    </button>
  ) : null;
  if (label === "state_symbols")
    return (
      <fieldset>
        <legend>{title}</legend>
        {[
          ...new Set([
            ...(schema.state_options ?? ["closed", "locked", "open", "bent"]),
            ...Object.keys(value ?? {}),
          ]),
        ]
          .map((key) => [key, value?.[key]])
          .map(([key, ref]) => (
            <div className="field" key={key}>
              <label>
                {(
                  {
                    closed: "Закрыта",
                    on: "Включён / нажата",
                    off: "Выключен / отпущена",
                    locked: "Заперта",
                    open: "Открыта",
                    bent: "Прутья погнуты",
                  } as Doc
                )[key] ?? key}
              </label>
              <SymbolSelect
                value={ref as string}
                onChange={(r) => onChange({ ...value, [key]: r })}
                label={"Символ состояния " + key}
              />
            </div>
          ))}
      </fieldset>
    );
  if (s.type === "object") {
    if (
      value?.kind &&
      mechanics.some((m) => m.id === value.kind) &&
      s.properties?.params
    ) {
      const m = mechanics.find((m) => m.id === value.kind)!;
      const params = m.builtin ? value : value.params;
      return (
        <fieldset>
          <legend>{title || "Эффект"}</legend>
          <div className="field">
            <label>Механика</label>
            <select
              value={value.kind}
              onChange={(e) => {
                const next = mechanics.find((m) => m.id === e.target.value)!;
                onChange({
                  kind: next.id,
                  amount: 0,
                  dice: null,
                  condition: "",
                  duration: 1,
                  params: next.builtin
                    ? {}
                    : defaultFor(next.schema, next.schema),
                });
              }}
            >
              {mechanics.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
          <p className="hint">{m.description}</p>
          <FieldForm
            schema={m.schema}
            root={m.schema}
            value={params}
            onChange={(v) =>
              onChange(m.builtin ? { ...value, ...v } : { ...value, params: v })
            }
            entries={entries}
            mechanics={[]}
            path={path}
          />
        </fieldset>
      );
    }
    if (!s.properties) {
      const obj = value ?? {};
      return (
        <fieldset>
          <legend>{title}</legend>
          {Object.entries(obj).map(([k, v]) => (
            <div className="slot-row" key={k}>
              <span>Уровень {k}</span>
              <input
                aria-label={`Ячейки уровня ${k}`}
                type="number"
                min="0"
                value={v as number}
                onChange={(e) =>
                  onChange({ ...obj, [k]: Number(e.target.value) })
                }
              />
              <button
                className="mini"
                onClick={() => {
                  const n = { ...obj };
                  delete n[k];
                  onChange(n);
                }}
              >
                ×
              </button>
            </div>
          ))}
          <button
            className="subtle"
            onClick={() => {
              const k = Array.from({ length: 9 }, (_, i) => String(i + 1)).find(
                (k) => !(k in obj),
              );
              if (k) onChange({ ...obj, [k]: 1 });
            }}
          >
            + Уровень
          </button>
        </fieldset>
      );
    }
    const children = Object.entries(s.properties).filter(
      ([key]) =>
        (key !== "key_code" ||
          !s.properties.key_kind ||
          value?.key_kind === "unique") &&
        key !== "schema_version" &&
        key !== "glyph" &&
        key !== "char" &&
        (s.title !== "QuestObjective" ||
          [
            "id",
            "description",
            "kind",
            "quantity",
            ...(value?.kind === "bring"
              ? ["item", "consume"]
              : value?.kind === "craft"
                ? ["recipe"]
                : value?.kind === "visit"
                  ? ["map_ref", "x", "y", "width", "height"]
                  : ["map_ref", "target_id"]),
          ].includes(key)) &&
        (s.title !== "RecipeOperation" ||
          (
            {
              liquid: [
                "kind",
                "liquids",
                "portions",
                "liquid_result",
                "heat_safe",
              ],
              repair_item: ["kind", "target_tags", "repair_amount"],
              repair_object: ["kind", "target_tags", "repair_amount"],
              place_object: ["kind", "place_object", "ignition"],
              place_trap: ["kind", "place_trap"],
              coat_weapon: ["kind", "target_tags", "poison_damage"],
              appraise_item: ["kind", "target_tags"],
            } as Record<string, string[]>
          )[value?.kind ?? "liquid"]?.includes(key)),
    );
    const renderChild = ([key, child]: [string, unknown]) => (
      <FieldForm
        key={key}
        schema={
          key === "world_parameters"
            ? ((s.properties.world_effect?.world_schemas ?? {})[
                value?.world_effect
              ] ?? { type: "object", properties: {} })
            : (child as Doc)
        }
        root={
          key === "world_parameters"
            ? ((s.properties.world_effect?.world_schemas ?? {})[
                value?.world_effect
              ] ?? root)
            : root
        }
        value={value?.[key]}
        onChange={(v) =>
          onChange(
            key === "world_effect"
              ? {
                  ...value,
                  [key]: v,
                  world_parameters: v
                    ? defaultFor(
                        s.properties.world_effect.world_schemas[v],
                        s.properties.world_effect.world_schemas[v],
                      )
                    : {},
                }
              : key === "kind" && s.title === "RecipeOperation"
                ? {
                    kind: v,
                    ...(v === "liquid"
                      ? { liquids: [], portions: 3, heat_safe: false }
                      : v === "place_object"
                        ? { place_object: null, ignition: false }
                        : v === "place_trap"
                          ? { place_trap: null }
                          : v === "coat_weapon"
                            ? { target_tags: [], poison_damage: 2 }
                            : { target_tags: [], repair_amount: 10 }),
                  }
                : { ...value, [key]: v },
          )
        }
        entries={entries}
        mechanics={mechanics}
        label={key}
        refCategory={category}
        lockedId={lockedId && key === "id" && path === ""}
        path={path ? `${path}.${key}` : key}
      />
    );
    const recipeVariant = s.title === "RecipeVariant";
    const requirements = children.filter(([key]) =>
      ["tools", "proficiencies", "stations"].includes(key),
    );
    const hasRequirements = requirements.some(([key]) => value?.[key]?.length);
    return (
      <fieldset
        className={
          "form-object " +
          (!label ? "anonymous-object " : "") +
          (label === "stats" || label === "ability_bonuses" ? "scores " : "") +
          (s.title === "RecipeIngredient" ? "recipe-ingredient" : "")
        }
      >
        {title && <legend>{title}</legend>}
        {recipeVariant ? (
          <div className="recipe-variant-fields">
            {children
              .filter(([key]) => ["name", "turns"].includes(key))
              .map(renderChild)}
            <div className="wide">
              {children
                .filter(([key]) => key === "ingredients")
                .map(renderChild)}
            </div>
            <details
              className="recipe-requirements wide"
              open={hasRequirements}
            >
              <summary>
                Условия работы{" "}
                <small>
                  {hasRequirements
                    ? "Инструменты, владения и станции"
                    : "Без специальных требований"}
                </small>
              </summary>
              <div>{requirements.map(renderChild)}</div>
            </details>
          </div>
        ) : (
          children.map(renderChild)
        )}
        {clear}
      </fieldset>
    );
  }

  if (s.type === "array") {
    const items = value ?? [];
    return (
      <fieldset className="form-array">
        <legend>
          {title} <span className="count">{items.length}</span>
        </legend>
        {s.tag_labels && (
          <TagPicker
            labels={s.tag_labels}
            groups={s.tag_groups}
            items={items}
            onChange={onChange}
          />
        )}
        {s.description && <small>{s.description}</small>}
        {items.map((v: any, i: number) => {
          const complex = resolve(s.items, root).type === "object";
          const itemName =
            (
              {
                variants: root.title === "RecipeDocument" ? "Способ" : "Вид",
                ingredients: "Ингредиент",
                items: "Материал",
                tools: "Инструмент",
                proficiencies: "Владение",
                result: "Результат",
                choices: "Вариант",
                effects: "Эффект",
                contents: "Предмет",
                pages: "Страница",
              } as Record<string, string>
            )[label] ?? "Элемент";
          const materials = v?.items
            ?.map(
              (ref: string) =>
                entries.find((e) => e.category === "equipment" && e.ref === ref)
                  ?.name ?? ref,
            )
            .join(" / ");
          const output = v?.item
            ? (entries.find(
                (e) => e.category === "equipment" && e.ref === v.item,
              )?.name ?? v.item)
            : "";
          const detail =
            v?.name || v?.question || v?.description || materials || output;
          const caption = `${itemName} ${i + 1}${detail ? " · " + detail : ""}${v?.quantity ? " ×" + v.quantity : ""}`;
          const control = (
            <FieldForm
              schema={s.items}
              root={root}
              value={v}
              onChange={(n) =>
                onChange(items.map((x: any, j: number) => (j === i ? n : x)))
              }
              entries={entries}
              mechanics={mechanics}
              label={complex ? "" : `${itemName} ${i + 1}`}
              refCategory={category}
              path={`${path}[${i}]`}
            />
          );
          const remove = (
            <button
              className="mini array-remove"
              aria-label={`Удалить: ${caption}`}
              title={`Удалить: ${caption}`}
              onClick={() =>
                onChange(items.filter((_: any, j: number) => i !== j))
              }
            >
              ×
            </button>
          );
          return complex ? (
            <div className="array-card-wrap" key={i}>
              <details className="array-card" open>
                <summary>{caption}</summary>
                <div className="array-card-body">{control}</div>
              </details>
              {remove}
              {["topics", "stages", "objectives", "rules"].includes(label) && (
                <div className="array-order">
                  <button
                    type="button"
                    disabled={i === 0}
                    aria-label={`Выше: ${caption}`}
                    onClick={() => {
                      const next = [...items];
                      [next[i - 1], next[i]] = [next[i], next[i - 1]];
                      onChange(next);
                    }}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    disabled={i === items.length - 1}
                    aria-label={`Ниже: ${caption}`}
                    onClick={() => {
                      const next = [...items];
                      [next[i + 1], next[i]] = [next[i], next[i + 1]];
                      onChange(next);
                    }}
                  >
                    ↓
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="array-row" key={i}>
              {control}
              {remove}
            </div>
          );
        })}
        <button
          className="subtle"
          onClick={() =>
            onChange([
              ...items,
              category
                ? (entries.find((e) => e.category === category)?.ref ?? "")
                : (() => {
                    const fresh = defaultFor(s.items, root);
                    if (["topics", "stages", "objectives"].includes(label)) {
                      let n = 1;
                      const prefix = fresh.id || "entry";
                      while (
                        items.some(
                          (entry: Doc) => entry.id === `${prefix}_${n}`,
                        )
                      )
                        n++;
                      fresh.id = `${prefix}_${n}`;
                    }
                    return fresh;
                  })(),
            ])
          }
        >
          + Добавить:{" "}
          {(
            {
              variants: root.title === "RecipeDocument" ? "способ" : "вид",
              ingredients: "ингредиент",
              items: "альтернативный материал",
              result: "результат",
              stations: "группу станций",
            } as Record<string, string>
          )[label] ?? fieldLabel(label, root).toLowerCase()}
        </button>
      </fieldset>
    );
  }
  let input;
  if (category)
    input = (
      <ContentSelect
        entries={entries}
        category={category}
        label={title || "Выбор объекта"}
        value={value ?? ""}
        onChange={onChange}
      />
    );
  else if (root.title === "RecipeDocument" && label === "category")
    input = (
      <input
        aria-label={title}
        list="craft-categories"
        value={value ?? "basic"}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  else if (s.enum)
    input = (
      <select
        aria-label={title}
        value={value ?? s.enum[0]}
        onChange={(e) =>
          onChange(
            s.type === "integer" || s.type === "number"
              ? Number(e.target.value)
              : e.target.value,
          )
        }
      >
        {s.enum.map((v: string) => (
          <option key={v} value={v}>
            {(
              {
                ...damageLabels,
                ...skillLabels,
                door: "Ключ для дверей уровня",
                container: "Ключ для контейнеров уровня",
                unique: "Уникальный ключ",
                liquid: "Обработка жидкости",
                repair_item: "Ремонт предмета",
                repair_object: "Ремонт объекта",
                place_object: "Создание объекта",
                place_trap: "Установка ловушки",
                coat_weapon: "Нанесение яда",
                appraise_item: "Оценка предмета",
                dismantle: "Разбор",
                butcher: "Разделка",
                harvest: "Сбор растений",
                chop: "Рубка дерева",
                remove_barricade: "Снятие баррикады",
                clean_water: "Чистая вода",
                dirty_water: "Грязная вода",
                swamp_water: "Болотная вода",
                salt_water: "Солёная вода",
                poisoned_water: "Отравленная вода",
                holy_water: "Святая вода",
                healing_broth: "Лечебный отвар",
                healing_potion: "Лечебное зелье",
                antidote: "Противоядный отвар",
                cactus_juice: "Сок кактуса",
                common: "Обычная",
                uncommon: "Необычная",
                rare: "Редкая",
                wood: "Деревянная",
                bars: "Прутья",
                steel: "Стальная",
                stone: "Каменная плита",
                adamantine: "Адамантиевая",
                glass: "Стеклянная",
                unique_key: "Только уникальный ключ",
                open: "Открыта",
                closed: "Закрыта",
                cheap: "Лёгкий, бронзовый — СЛ 10",
                normal: "Средний, синевато-железный — СЛ 15",
                expensive: "Сложный, золотой — СЛ 20",
                legendary: "Легендарный, фиолетовый — СЛ 25",
                white: "Белый",
                bronze: "Бронзовый",
                iron: "Металлический",
                gold: "Золотой",
                simple: "Простой — 1 ход",
                complex: "Сложный — 10 ходов",
                strength: "Сила",
                weapons: "Вооружение",
                armor: "Доспехи",
                consumables: "Расходники",
                tools: "Инструменты",
                materials: "Материалы",
                small: "Маленький",
                medium: "Средний",
                large: "Большой",
                dexterity: "Ловкость",
                constitution: "Телосложение",
                intelligence: "Интеллект",
                wisdom: "Мудрость",
                charisma: "Харизма",
                attack: "Атака",
                dodge: "Уклонение",
                stealth: "Скрытность",
                magic: "Магия",
                influence: "Влияние",
                special: "Особое действие",
                available: "Не принято",
                active: "Активно",
                completed: "Выполнено",
                seen: "Прочитано",
                success: "Успех",
                failure: "Провал",
                bring: "Принести предметы",
                visit: "Посетить область",
                talk: "Поговорить с NPC",
                read: "Прочитать записку",
                craft: "Изготовить по рецепту",
                break_object: "Разрушить",
                disarm: "Обезвредить",
                activate_mechanism: "Активировать механизм",
                lever: "Рычаг: переключение",
                pressure_plate: "Плита: пока герой стоит на ней",
                self: "На себя",
                other: "На другого",
                any: "Любая цель",
                advantage: "Преимущество",
                automatic: "Без броска",
                save: "Спасбросок цели",
                combat: "Бой",
                exploration: "Исследование",
                cell: "Клетка карты",
                item: "Предмет",
                abjuration: "Ограждение",
                conjuration: "Вызов",
                divination: "Прорицание",
                enchantment: "Очарование",
                evocation: "Воплощение",
                illusion: "Иллюзия",
                necromancy: "Некромантия",
                transmutation: "Преобразование",
                light: "Свет на предмете",
                repair: "Починка",
                projectile: "Снаряд / касание",
                hand: "Волшебная рука",
                tricks: "Фокусы",
                dancing_lights: "Пляшущие огоньки",
                elementalism: "Элементализм",
                noise: "Шум",
                dispel: "Развеивание магического поля",
                enter: "Вход на клетку",
                ...(label === "map_category" ? mapCategoryNames : {}),
                ...(label === "access"
                  ? {
                      normal: "Обычные взаимодействия",
                      magic: "Механизм / развеивание магии",
                    }
                  : {}),
              } as Record<string, string>
            )[v] ?? v}
          </option>
        ))}
      </select>
    );
  else if (s.type === "boolean")
    input = (
      <input
        aria-label={title}
        type="checkbox"
        checked={value ?? false}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  else if (s.type === "integer" || s.type === "number")
    input = (
      <div className="number-field">
        {(label === "foreground" || label === "background") && (
          <i style={{ background: color(value) }} />
        )}
        <input
          aria-label={title}
          type="number"
          min={s.minimum}
          max={s.maximum}
          step={s.type === "number" ? "0.1" : "1"}
          value={value ?? 0}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {path.startsWith("stats.") && (
          <span className="hint">
            {Math.floor((value - 10) / 2) >= 0 ? "+" : ""}
            {Math.floor((value - 10) / 2)}
          </span>
        )}
      </div>
    );
  else if (
    ["description", "text"].includes(label) ||
    /(?:^|\.)pages\[\d+\]$/.test(path)
  )
    input = (
      <textarea
        aria-label={title}
        rows={path.includes("pages[") ? 8 : 3}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  else
    input = (
      <input
        aria-label={title}
        disabled={lockedId}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  return (
    <div className={"field " + (s.type === "boolean" ? "boolean-field" : "")}>
      <label>{title}</label>
      <div className="field-input">
        {input}
        {clear}
      </div>
      {s.description && <small>{s.description}</small>}
    </div>
  );
}

type Section = {
  id: string;
  title: string;
  description: string;
  fields: string[];
};
export function propertySections(category: string, keys: string[]): Section[] {
  const layout: [string, string, string[]][] = [
    [
      "Основное",
      "Название, назначение и поиск в библиотеке",
      ["id", "name", "description", "category", "group", "tags", "basic_known"],
    ],
    ...(category === "npcs"
      ? ([
          [
            "Разговор",
            "Плоский список вопросов и ответов; условия выполняются совместно",
            ["greeting", "topics"],
          ],
          [
            "Магазин",
            "Конечный запас, правила цен и один бросок Убеждения раз в 1440 минут",
            ["trade"],
          ],
          ["Задания", "Предложения и тексты отчётов", ["quests"]],
        ] as [string, string, string[]][])
      : []),
    ...(category === "quests"
      ? ([
          [
            "Этапы задания",
            "Выполняются по порядку; последний сдаётся NPC",
            ["stages"],
          ],
          ["Награда", "Выдаётся однократно при финальной сдаче", ["reward"]],
        ] as [string, string, string[]][])
      : []),
    ...(category === "recipes"
      ? ([
          [
            "Способы изготовления",
            "У каждого способа свои ингредиенты, условия и длительность",
            ["variants"],
          ],
          [
            "Результат",
            "Что получит персонаж после завершения работы",
            ["result", "operation", "learn_recipes"],
          ],
          [
            "Рискованная работа",
            "Необязательная проверка; обычное изготовление проходит без броска",
            ["check"],
          ],
        ] as [string, string, string[]][])
      : []),
    [
      "Графика",
      "Отображение на карте и варианты оформления",
      [
        "symbol",
        "mirror_x",
        "rotation",
        "state_symbols",
        "foreground",
        "background",
        "art",
        "variants",
        "underlay",
      ],
    ],
    [
      "Характеристики",
      "Числовые параметры, нагрузка и защита",
      [
        "stats",
        "ability_bonuses",
        "hit_points",
        "armor_class",
        "speed",
        "initiative_bonus",
        "damage_profile",
        "weight",
        "size",
        "rarity",
        "durability",
        "slot",
        "hands",
        "charges",
        "vessel",
        "carry_per_strength",
        "hp_per_level",
        "order",
      ],
    ],
    [
      "Применение и эффекты",
      "Правила использования и последствия",
      [
        "level",
        "school",
        "modes",
        "range",
        "target",
        "resolution",
        "save_ability",
        "concentration",
        "cantrip_scaling",
        "wounded_dice",
        "max_targets",
        "weapon_damage",
        "weapon_ability",
        "damage_type",
        "kind",
        "ability",
        "skill",
        "tool",
        "bonus",
        "damage",
        "difficulty",
        "properties",
        "effects",
        "on_enter",
        "check_aids",
        "world_effect",
        "world_parameters",
        "pending_effects",
      ],
    ],
    [
      "Снаряжение и знания",
      "Предметы, действия, заклинания и владения",
      [
        "inventory",
        "starting_items",
        "actions",
        "special_actions",
        "spells",
        "spell_slots",
        "spellcasting_ability",
        "cantrip_choices",
        "cantrips_known",
        "racial_spell",
        "racial_uses",
        "tool_proficiencies",
        "tool_expertise",
        "starting_recipes",
        "learn_recipes",
        "learn_on_proficiency",
        "classes",
        "skills",
        "skill_choices",
        "skills_known",
        "expertise_count",
      ],
    ],
    [
      "Окружение и взаимодействия",
      "Свет, движение, контейнеры и доступные действия",
      [
        "map_category",
        "walkable",
        "blocks_sight",
        "light",
        "map_light",
        "brush",
        "storage",
        "light_fixture",
        "destruction",
        "poisonous",
        "water_source",
        "campfire",
        "growth",
        "mechanism_targets",
        "mechanism",
        "illusion",
        "dismantle",
        "door_remains",
        "movable",
        "reading",
        "challenge",
        "text",
        "choices",
        "hidden",
        "trigger",
        "repeatable",
      ],
    ],
  ];
  const remaining = new Set(keys.filter((k) => k !== "schema_version"));
  const result = layout
    .map(([title, description, fields], i) => {
      const chosen = fields.filter((k) => remaining.delete(k));
      return { id: `section-${i}`, title, description, fields: chosen };
    })
    .filter((section) => section.fields.length);
  if (remaining.size)
    result.push({
      id: "section-extra",
      title: "Дополнительные свойства",
      description: "Параметры этого типа контента",
      fields: [...remaining],
    });
  return result;
}
export function propertySearchText(
  key: string,
  schema: Doc,
  root: Doc,
  seen = new Set<string>(),
): string {
  let text = fieldLabel(key, root) + " " + key;
  if (schema.$ref) {
    if (seen.has(schema.$ref)) return text;
    seen = new Set(seen).add(schema.$ref);
  }
  const resolved = resolve(schema, root);
  if (resolved.properties)
    text +=
      " " +
      Object.entries(resolved.properties)
        .map(([k, s]) => propertySearchText(k, s as Doc, root, seen))
        .join(" ");
  if (resolved.items)
    text += " " + propertySearchText("", resolved.items, root, seen);
  if (resolved.anyOf)
    text +=
      " " +
      resolved.anyOf
        .map((s: Doc) => propertySearchText("", s, root, seen))
        .join(" ");
  return text;
}
export function DocumentForm({
  category,
  viewState = {},
  onViewState,
  diagnostic,
  ...props
}: Props & {
  category: string;
  diagnostic?: Doc;
  viewState?: Doc;
  onViewState?: (state: Doc) => void;
}) {
  const [query, setQuery] = useState(viewState.query ?? "");
  const [selectedSection, setSelectedSection] = useState(
    viewState.section ?? "section-0",
  );
  const [focusedField, setFocusedField] = useState("");
  const [conditionPercent, setConditionPercent] = useState(
    viewState.conditionPercent ?? 100,
  );
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = viewState.scrollTop ?? 0;
  }, []);
  useEffect(() => {
    onViewState?.({
      query,
      section: selectedSection,
      conditionPercent,
      scrollTop: scrollRef.current?.scrollTop ?? 0,
    });
  }, [query, selectedSection, conditionPercent]);
  const groups = propertySections(
    category,
    Object.keys(props.schema.properties).filter(
      (k) =>
        !["glyph", "char"].includes(k) &&
        (k !== "state_symbols" ||
          !!props.value.mechanism ||
          !!props.value.brush?.door ||
          !!props.value.storage),
    ),
  );
  const matches = (key: string) => {
    const params =
      key === "world_parameters"
        ? props.schema.properties.world_effect?.world_schemas?.[
            props.value.world_effect
          ]
        : null;
    return (
      !query.trim() ||
      propertySearchText(
        key,
        params ?? props.schema.properties[key],
        params ?? props.root,
      )
        .toLocaleLowerCase("ru")
        .includes(query.trim().toLocaleLowerCase("ru"))
    );
  };
  const current = groups.find((g) => g.id === selectedSection) ?? groups[0];
  const shown = current ? [current] : [];
  function focusField(groupId: string, key: string) {
    setSelectedSection(groupId);
    setFocusedField(key);
    requestAnimationFrame(() =>
      scrollRef.current
        ?.querySelector<HTMLElement>(`[data-field="${key}"]`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" }),
    );
  }
  useEffect(() => {
    if (!diagnostic) return;
    const key = String(diagnostic.field ?? diagnostic.path ?? "symbol").split(
      /[.[]/,
    )[0];
    const g = groups.find((g) => g.fields.includes(key));
    if (g) focusField(g.id, key);
  }, [diagnostic]);
  return (
    <div
      className="document-form"
      ref={scrollRef}
      onScroll={(e) =>
        onViewState?.({
          query,
          section: selectedSection,
          conditionPercent,
          scrollTop: e.currentTarget.scrollTop,
        })
      }
    >
      <div className="property-toolbar">
        <label>
          Найти свойство
          <input
            type="search"
            aria-label="Поиск свойств"
            placeholder="Например: ингредиенты, свет, урон…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <span>
          {groups.reduce((n, g) => n + g.fields.length, 0)} свойств ·{" "}
          {groups.length} разделов
        </span>
      </div>
      {query.trim() && (
        <div
          className="property-search-results"
          aria-label="Результаты поиска свойств"
        >
          {groups.flatMap((g) =>
            g.fields.filter(matches).map((key) => (
              <button key={g.id + key} onClick={() => focusField(g.id, key)}>
                {g.title} → {fieldLabel(key, props.root)}
              </button>
            )),
          )}
        </div>
      )}
      <nav className="property-nav" aria-label="Разделы свойств">
        {groups.map((g) => (
          <button
            type="button"
            key={g.id}
            className={current?.id === g.id ? "selected" : ""}
            onClick={() => setSelectedSection(g.id)}
          >
            {g.title}
          </button>
        ))}
      </nav>
      {shown.map((g) => (
        <section
          id={g.id}
          className="property-section"
          key={g.id}
          aria-label={g.title}
        >
          <header>
            <h2>{g.title}</h2>
            <p>{g.description}</p>
          </header>
          <div className="property-fields">
            {g.fields.map((key) => {
              const params =
                key === "world_parameters"
                  ? props.schema.properties.world_effect?.world_schemas?.[
                      props.value.world_effect
                    ]
                  : null;
              const field =
                params ??
                (key === "world_parameters"
                  ? { type: "object", properties: {} }
                  : props.schema.properties[key]);
              const fieldRoot = params ?? props.root;
              const expanded = resolve(field, fieldRoot);
              const type =
                expanded.type ??
                resolve(
                  expanded.anyOf?.find((x: Doc) => x.type !== "null") ?? {},
                  fieldRoot,
                ).type;
              return (
                <div
                  key={key}
                  data-field={key}
                  className={
                    "property-control " +
                    (focusedField === key ? "field-highlight " : "") +
                    (["array", "object"].includes(type) ||
                    ["description", "text"].includes(key)
                      ? "wide"
                      : "")
                  }
                >
                  <FieldForm
                    {...props}
                    schema={
                      key === "state_symbols"
                        ? {
                            ...field,
                            state_options: props.value.mechanism
                              ? ["off", "on"]
                              : props.value.storage && !props.value.brush?.door
                                ? ["closed", "open"]
                                : props.value.brush?.door?.material === "stone"
                                  ? ["closed"]
                                  : props.value.brush?.door?.material === "bars"
                                    ? ["closed", "locked", "open", "bent"]
                                    : ["closed", "locked", "open"],
                          }
                        : field
                    }
                    root={fieldRoot}
                    label={key}
                    lockedId={props.lockedId && key === "id"}
                    value={props.value[key]}
                    path={key}
                    onChange={(value) => {
                      const next = { ...props.value, [key]: value };
                      if (key === "world_effect")
                        next.world_parameters = value
                          ? defaultFor(
                              props.schema.properties.world_effect
                                .world_schemas[value],
                              props.schema.properties.world_effect
                                .world_schemas[value],
                            )
                          : {};
                      props.onChange(next);
                    }}
                  />
                </div>
              );
            })}
          </div>
          {category === "npcs" &&
            g.fields.includes("trade") &&
            props.value.trade && (
              <div className="trade-preview">
                <h3>Предпросмотр цен</h3>
                <label>
                  Состояние, %{" "}
                  <input
                    aria-label="Состояние для предпросмотра цен"
                    type="number"
                    min={0}
                    max={100}
                    value={conditionPercent}
                    onChange={(e) =>
                      setConditionPercent(
                        Math.max(0, Math.min(100, Number(e.target.value))),
                      )
                    }
                  />
                </label>
                <p>
                  Покупка / продажа игроком, золото. Реальная цена зависит от
                  состояния экземпляра.
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>Товар / группа</th>
                      <th>Без торга</th>
                      <th>Успех</th>
                      <th>Провал</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(props.value.trade.rules ?? []).map(
                      (r: Doc, i: number) => (
                        <tr key={i}>
                          <td>
                            {r.item || r.furniture || r.tag || "Выберите товар"}
                          </td>
                          {[
                            0,
                            props.value.trade.percent ?? 10,
                            -(props.value.trade.percent ?? 10),
                          ].map((p) => (
                            <td key={p}>
                              {tradePreview(r, conditionPercent, p).join(" / ")}
                            </td>
                          ))}
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )}
        </section>
      ))}
      {!shown.length && (
        <p className="content-empty">
          Нет свойств с таким названием.{" "}
          <button onClick={() => setQuery("")}>Сбросить</button>
        </p>
      )}
      <datalist id="craft-categories">
        {Object.entries(craftNames).map(([id, name]) => (
          <option value={id} key={id}>
            {name}
          </option>
        ))}
      </datalist>
    </div>
  );
}

export function tradePreview(
  rule: Doc,
  condition: number,
  percent: number,
): number[] {
  const buy = Math.max(
    1,
    Math.ceil((rule.sell * condition * (100 - percent)) / 10000),
  );
  return [
    buy,
    Math.min(buy, Math.floor((rule.buy * condition * (100 + percent)) / 10000)),
  ];
}
