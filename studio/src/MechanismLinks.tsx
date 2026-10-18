import { Doc, Point, instanceDocument } from "./model";

export function signalTargets(doc: Doc, assets: Record<string, Doc>) {
  return ["doors", "traps", "lights", "objects"].flatMap((layer) =>
    (doc[layer] ?? []).flatMap((p: Doc) => {
      const definition =
        layer === "lights"
          ? {}
          : instanceDocument(
              assets[(layer === "doors" ? "objects" : layer) + "/" + p.ref] ??
                {},
              p,
            );
      const door = definition.brush?.door;
      const supported =
        layer === "doors"
          ? door &&
            door.access !== "unique_key" &&
            !door.travel &&
            door.openable !== false &&
            door.material !== "stone"
          : layer !== "objects" ||
            definition.illusion ||
            (definition.brush?.light && !definition.light_fixture);
      return supported
        ? [{ layer, placement: p, name: definition.name ?? "Источник света" }]
        : [];
    }),
  );
}

export function toggleSignalTarget(
  doc: Doc,
  assets: Record<string, Doc>,
  sourceId: string,
  targetId: string,
) {
  if (!signalTargets(doc, assets).some((t) => t.placement.id === targetId))
    return doc;
  return {
    ...doc,
    objects: doc.objects.map((p: Doc) => {
      if (p.id !== sourceId) return p;
      const d = instanceDocument(assets["objects/" + p.ref] ?? {}, p);
      const targets: string[] = d.mechanism_targets ?? [];
      return {
        ...p,
        overrides: {
          ...p.overrides,
          mechanism: d.mechanism ?? { trigger: "lever", initially_on: false },
          mechanism_targets: targets.includes(targetId)
            ? targets.filter((i) => i !== targetId)
            : [...targets, targetId],
        },
      };
    }),
  };
}

export function MechanismLinks({
  doc,
  assets,
  selected,
  linking,
  hover,
  onLink,
  onChange,
}: {
  doc: Doc;
  assets: Record<string, Doc>;
  selected: { category: string; id: string };
  linking: boolean;
  hover: Point;
  onLink: () => void;
  onChange: (d: Doc) => void;
}) {
  const p = (doc[selected.category] ?? []).find(
    (p: Doc) => p.id === selected.id,
  );
  if (!p) return null;
  const d = p.ref
    ? instanceDocument(
        assets[
          (selected.category === "doors" ? "objects" : selected.category) +
            "/" +
            p.ref
        ] ?? {},
        p,
      )
    : {};
  const source =
    selected.category === "objects" &&
    (d.mechanism || d.tags?.includes("mechanism"));
  const targets = signalTargets(doc, assets);
  const receiver = targets.some((t) => t.placement.id === p.id);
  if (!source && !receiver) return null;
  const update = (changes: Doc) =>
    onChange({
      ...doc,
      [selected.category]: doc[selected.category].map((e: Doc) =>
        e.id === p.id ? { ...e, ...changes } : e,
      ),
    });
  const codeField = (value: string, edit: (value: string | null) => void) => (
    <input
      aria-label={source ? "Код механизма" : "Код активации"}
      value={value ?? ""}
      placeholder="например: crypt_gate"
      maxLength={64}
      pattern="[a-z][a-z0-9_]*"
      onChange={(e) => edit(e.target.value || null)}
    />
  );
  const explicit: string[] = d.mechanism_targets ?? [];
  const connected = targets.filter(
    (t) =>
      explicit.includes(t.placement.id) ||
      (d.mechanism?.code && d.mechanism.code === t.placement.activation_code),
  );
  return (
    <section className="mechanism-links">
      <h3>{source ? "Связи механизма" : "Активация сигналом"}</h3>
      {source ? (
        <>
          <button className={linking ? "active" : ""} onClick={onLink}>
            {linking ? "Завершить связывание" : "Связать на карте"}
          </button>
          <p className="hint">
            Клик по цели добавляет связь, повторный — убирает. Зелёным выделены
            цели. Esc завершает выбор.
          </p>
          <label>
            Код механизма
            {codeField(d.mechanism?.code, (code) =>
              update({
                overrides: {
                  ...p.overrides,
                  mechanism: { ...(d.mechanism ?? { trigger: "lever" }), code },
                },
              }),
            )}
          </label>
          <p className="hint">
            Одинаковый код соединяет объекты в пределах этой карты. Несколько
            источников работают по правилу «ИЛИ».
          </p>
          <ul>
            {connected.map((t) => (
              <li key={t.placement.id}>
                {t.name} ({t.placement.x}, {t.placement.y})
                {explicit.includes(t.placement.id) ? (
                  <button
                    className="mini"
                    aria-label={"Убрать связь " + t.placement.id}
                    onClick={() =>
                      onChange(
                        toggleSignalTarget(doc, assets, p.id, t.placement.id),
                      )
                    }
                  >
                    ×
                  </button>
                ) : (
                  " · по коду"
                )}
              </li>
            ))}
          </ul>
          {!connected.length && <p className="hint">Цели ещё не выбраны.</p>}
          {linking &&
            targets.filter(
              (t) => t.placement.x === hover.x && t.placement.y === hover.y,
            ).length > 1 && (
              <div>
                <p>
                  Цели на клетке ({hover.x}, {hover.y}):
                </p>
                {targets
                  .filter(
                    (t) =>
                      t.placement.x === hover.x && t.placement.y === hover.y,
                  )
                  .map((t) => (
                    <button
                      key={t.placement.id}
                      onClick={() =>
                        onChange(
                          toggleSignalTarget(doc, assets, p.id, t.placement.id),
                        )
                      }
                    >
                      {explicit.includes(t.placement.id) ? "✓ " : "+ "}
                      {t.name} · {t.placement.id}
                    </button>
                  ))}
              </div>
            )}
        </>
      ) : (
        <label>
          Код активации
          {codeField(p.activation_code, (activation_code) =>
            update({ activation_code }),
          )}
        </label>
      )}
    </section>
  );
}

export function copiedSignalPlacement(
  p: Doc,
  assets: Record<string, Doc>,
  ids: Map<string, string>,
) {
  const d = instanceDocument(assets["objects/" + p.ref] ?? {}, p);
  return d.mechanism_targets?.length
    ? {
        ...p,
        overrides: {
          ...p.overrides,
          mechanism_targets: d.mechanism_targets.map(
            (id: string) => ids.get(id) ?? id,
          ),
        },
      }
    : p;
}

export function signalHighlights(
  doc: Doc,
  assets: Record<string, Doc>,
  sourceId: string,
): Point[] {
  const p = doc.objects?.find((p: Doc) => p.id === sourceId);
  if (!p) return [];
  const d = instanceDocument(assets["objects/" + p.ref] ?? {}, p);
  return signalTargets(doc, assets)
    .filter(
      (t) =>
        d.mechanism_targets?.includes(t.placement.id) ||
        (d.mechanism?.code && d.mechanism.code === t.placement.activation_code),
    )
    .map((t) => t.placement);
}
