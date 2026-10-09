import { Doc, Entry, defaultFor, color } from "./model";
import { damageLabels } from "./damage";
const labels: Record<string, string> = {
  id: "Идентификатор",
  name: "Название",
  description: "Описание",
  glyph: "Символ на карте",
  underlay: "Тайл под предметом",
  door: "Дверь",
  material: "Материал двери",
  state: "Начальное состояние",
  locked: "Заперта",
  lock_quality: "Качество замка",
  lock_complexity: "Сложность замка",
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
  armor_class: "Класс доспеха",
  speed: "Скорость",
  initiative_bonus: "Бонус инициативы",
  actions: "Действия",
  special_actions: "Особые действия",
  inventory: "Инвентарь",
  storage: "Контейнер",
  capacity: "Вместимость, кг",
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
  skills: "Навыки (плейсхолдеры)",
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
export const fieldLabel = (key: string) => labels[key] ?? key;

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
  const title = label ? (labels[label] ?? original.title ?? label) : "";
  const category = refCategory ?? original.ref_category ?? s.ref_category;
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
      ([key]) => key !== "schema_version",
    );
    return (
      <fieldset
        className={
          label === "stats" || label === "ability_bonuses" ? "scores" : ""
        }
      >
        <legend>{title}</legend>
        {children.map(([key, child]) => (
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
        ))}
        {clear}
      </fieldset>
    );
  }
  if (s.type === "array") {
    const items = value ?? [];
    return (
      <fieldset>
        <legend>
          {title} <span className="count">{items.length}</span>
        </legend>
        {s.tag_labels && (
          <div className="toolbar">
            {Object.entries(s.tag_labels).map(([tag, name]) => (
              <label key={tag}>
                <input
                  type="checkbox"
                  aria-label={String(name)}
                  checked={items.includes(tag)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...items, tag]
                        : items.filter((v: string) => v !== tag),
                    )
                  }
                />
                {String(name)} <small>({tag})</small>
              </label>
            ))}
          </div>
        )}
        {s.description && <small>{s.description}</small>}
        {items.map((v: any, i: number) => (
          <div className="array-row" key={i}>
            <FieldForm
              schema={s.items}
              root={root}
              value={v}
              onChange={(n) =>
                onChange(items.map((x: any, j: number) => (j === i ? n : x)))
              }
              entries={entries}
              mechanics={mechanics}
              label={String(i + 1)}
              refCategory={category}
              path={`${path}[${i}]`}
            />
            <button
              className="mini"
              title="Удалить элемент"
              onClick={() =>
                onChange(items.filter((_: any, j: number) => i !== j))
              }
            >
              ×
            </button>
          </div>
        ))}
        <button
          className="subtle"
          onClick={() =>
            onChange([
              ...items,
              category
                ? (entries.find((e) => e.category === category)?.ref ?? "")
                : defaultFor(s.items, root),
            ])
          }
        >
          + Добавить
        </button>
      </fieldset>
    );
  }
  let input;
  if (category)
    input = (
      <select
        aria-label={title}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Выберите объект</option>
        {entries
          .filter((e) => e.category === category)
          .map((e) => (
            <option key={e.ref} value={e.ref}>
              {e.name} · {e.ref}
            </option>
          ))}
      </select>
    );
  else if (s.enum)
    input = (
      <select
        aria-label={title}
        value={value ?? s.enum[0]}
        onChange={(e) => onChange(e.target.value)}
      >
        {s.enum.map((v: string) => (
          <option key={v} value={v}>
            {(
              {
                ...damageLabels,
                wood: "Деревянная",
                bars: "Прутья",
                steel: "Стальная",
                stone: "Каменная плита",
                adamantine: "Адамантиевая",
                open: "Открыта",
                closed: "Закрыта",
                cheap: "Дешёвый — СЛ 10",
                normal: "Обычный — СЛ 15",
                expensive: "Дорогой — СЛ 20",
                legendary: "Легендарный — СЛ 25",
                simple: "Простой — 1 ход",
                complex: "Сложный — 10 ходов",
                strength: "Сила",
                weapons: "Вооружение",
                armor: "Доспехи",
                consumables: "Расходники",
                tools: "Инструменты",
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
                enter: "Вход на клетку",
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
  else if (["description", "text"].includes(label))
    input = (
      <textarea
        aria-label={title}
        rows={3}
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
    <div className="field">
      <label>{title}</label>
      <div className="field-input">
        {input}
        {clear}
      </div>
      {s.description && <small>{s.description}</small>}
    </div>
  );
}
