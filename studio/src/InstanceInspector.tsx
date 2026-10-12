import { useState } from "react";
import {
  Doc,
  Entry,
  clone,
  diffProperties,
  instanceDocument,
  mergeProperties,
} from "./model";
import { FieldForm, fieldLabel } from "./Form";

type Props = {
  placement: Doc;
  layer: string;
  assets: Record<string, Doc>;
  schemas: Record<string, Doc>;
  entries: Entry[];
  mechanics: Doc[];
  onChange: (changes: Doc) => void;
};

function Properties({
  base,
  patch,
  schema,
  entries,
  mechanics,
  onChange,
  door = false,
}: {
  base: Doc;
  patch: Doc;
  schema: Doc;
  entries: Entry[];
  mechanics: Doc[];
  onChange: (patch: Doc) => void;
  door?: boolean;
}) {
  const [query, setQuery] = useState("");
  const effective = mergeProperties(base, patch);
  const fields = door ? schema.$defs.DoorSpec.properties : schema.properties;
  const values = door ? effective.brush.door : effective;
  return (
    <div className="instance-properties">
      <input
        type="search"
        aria-label="Поиск свойств экземпляра"
        placeholder="Найти свойство…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {Object.entries(fields)
        .filter(([key]) => !["id", "schema_version"].includes(key))
        .filter(([key]) =>
          (fieldLabel(key) + " " + key)
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
        )
        .filter(
          ([key]) =>
            !(
              door &&
              values.material === "stone" &&
              ["state", "locked", "lock_quality", "lock_complexity"].includes(
                key,
              )
            ),
        )
        .map(([key, field]) => {
          const changed = door
            ? key in (patch.brush?.door ?? {})
            : key in patch;
          const edit = (value: any) => {
            const next = clone(effective);
            if (door) next.brush.door[key] = value;
            else next[key] = value;
            onChange(diffProperties(base, next));
          };
          const reset = () => {
            const next = clone(patch);
            if (door) {
              delete next.brush.door[key];
              if (!Object.keys(next.brush.door).length) delete next.brush.door;
              if (!Object.keys(next.brush).length) delete next.brush;
            } else delete next[key];
            onChange(next);
          };
          const control = (
            <>
              <FieldForm
                schema={field as Doc}
                root={schema}
                value={values[key]}
                onChange={edit}
                entries={entries}
                mechanics={mechanics}
                label={key}
              />
              {changed && (
                <button className="subtle mini" onClick={reset}>
                  Вернуть из шаблона
                </button>
              )}
            </>
          );
          return door ? (
            <div key={key}>{control}</div>
          ) : (
            <details key={key} className="instance-field">
              <summary>
                {fieldLabel(key)}
                {changed && <small> · изменено</small>}
              </summary>
              {control}
            </details>
          );
        })}
    </div>
  );
}

export function InstanceInspector({
  placement,
  layer,
  assets,
  schemas,
  entries,
  mechanics,
  onChange,
}: Props) {
  const category =
    layer === "doors" ? "objects" : layer === "decorations" ? "art" : layer;
  const base = assets[category + "/" + placement.ref];
  const schema = schemas[category];
  if (!base || !schema) return null;
  const effective = instanceDocument(base, placement);
  const challenge =
    layer === "points_of_interest"
      ? assets["challenges/" + effective.challenge]
      : null;
  return (
    <section className="instance-inspector" aria-label="Свойства экземпляра">
      <h3>Свойства экземпляра</h3>
      <strong>{effective.name}</strong>
      <p className="hint">
        {placement.ref} · ({placement.x}, {placement.y})
      </p>
      <p className="hint">
        Изменения действуют только на этот объект. Остальные свойства
        наследуются из шаблона. Выделение: V, отмена/повтор: Ctrl+Z / Ctrl+Y.
      </p>
      {base.variants?.length > 0 && (
        <label>
          Внешний вид
          <select
            aria-label="Вариант внешнего вида"
            value=""
            onChange={(event) => {
              const next = clone(placement.overrides ?? {});
              if (event.target.value === "default") {
                for (const key of ["glyph", "foreground", "background"])
                  delete next[key];
              } else {
                const variant = base.variants[Number(event.target.value)];
                for (const key of ["glyph", "foreground", "background"])
                  next[key] = variant[key];
              }
              onChange({ overrides: next });
            }}
          >
            <option value="" disabled>
              Выберите вариант…
            </option>
            <option value="default">Основной · {base.glyph}</option>
            {base.variants.map((v: Doc, i: number) => (
              <option key={i} value={i}>
                {v.name} · {v.glyph}
              </option>
            ))}
          </select>
        </label>
      )}
      {layer === "equipment" && (
        <details className="instance-field">
          <summary>Начальное состояние предмета</summary>
          <p className="hint">
            Применяется при первом запуске карты. Сохранение хранит текущее
            состояние.
          </p>
          {effective.durability != null && (
            <label>
              Начальная прочность
              <input
                type="number"
                min={0}
                max={effective.durability}
                placeholder={String(effective.durability)}
                value={placement.item_state?.durability ?? ""}
                onChange={(event) =>
                  onChange({
                    item_state: {
                      ...placement.item_state,
                      durability:
                        event.target.value === ""
                          ? null
                          : Number(event.target.value),
                    },
                  })
                }
              />
            </label>
          )}
          <label>
            <input
              type="checkbox"
              checked={placement.item_state?.contaminated ?? false}
              onChange={(event) =>
                onChange({
                  item_state: {
                    ...placement.item_state,
                    contaminated: event.target.checked,
                  },
                })
              }
            />
            Загрязнён
          </label>
          <button
            className="subtle"
            onClick={() => onChange({ item_state: null })}
          >
            Сбросить начальное состояние
          </button>
        </details>
      )}
      <Properties
        base={base}
        patch={placement.overrides ?? {}}
        schema={schema}
        entries={entries}
        mechanics={mechanics}
        door={layer === "doors"}
        onChange={(overrides) => onChange({ overrides })}
      />
      {challenge && schemas.challenges && (
        <details className="instance-challenge">
          <summary>Испытание: текст, варианты и последствия</summary>
          <Properties
            base={challenge}
            patch={placement.challenge_overrides ?? {}}
            schema={schemas.challenges}
            entries={entries}
            mechanics={mechanics}
            onChange={(challenge_overrides) =>
              onChange({ challenge_overrides })
            }
          />
        </details>
      )}
      <button
        className="subtle"
        onClick={() =>
          onChange({ overrides: {}, challenge_overrides: {}, item_state: null })
        }
      >
        Сбросить настройки экземпляра
      </button>
    </section>
  );
}
