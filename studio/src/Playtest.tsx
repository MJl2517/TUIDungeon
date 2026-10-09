import { useEffect, useState } from "react";
import { api } from "./api";
import { Grid } from "./Grid";
import { Doc, Entry } from "./model";
import { StorageDialog } from "./StorageDialog";
import { effectText } from "./damage";
export function Playtest({
  map,
  entries,
  onClose,
  notify,
}: {
  map: string;
  entries: Entry[];
  onClose: () => void;
  notify: (s: string) => void;
}) {
  const [background, setBackground] = useState("");
  const [classLoading, setClassLoading] = useState(true);
  const [cantripOptions, setCantripOptions] = useState<string[]>([]);
  const [cantripCount, setCantripCount] = useState(0);
  const [cantrips, setCantrips] = useState<string[]>([]);
  const [spellItems, setSpellItems] = useState<Record<string, string>>({});
  const [spellOption, setSpellOption] = useState("ignite");
  const [storageId, setStorageId] = useState<string | null>(null);
  const [targetAction, setTargetAction] = useState<{
    command: "throw" | "ignite" | "cast" | "hand";
    source?: string;
    option?: string;
    item: string;
    name: string;
  } | null>(null);
  const [seed, setSeed] = useState(42),
    [race, setRace] = useState(
      entries.find((e) => e.category === "races")?.ref ?? "",
    ),
    [cls, setCls] = useState(
      entries.find((e) => e.category === "classes")?.ref ?? "",
    ),
    [session, setSession] = useState<Doc | null>(null),
    [busy, setBusy] = useState(false),
    [scores, setScores] = useState([14, 12, 13, 10, 10, 8]);
  useEffect(() => {
    let active = true;
    setClassLoading(true);
    void api("/documents/classes/" + cls)
      .then(({ document }) => {
        if (!active) return;
        const options = document.cantrip_choices ?? [];
        setCantripOptions(options);
        setCantripCount(document.cantrips_known ?? 0);
        setCantrips(options.slice(0, document.cantrips_known ?? 0));
        setClassLoading(false);
      })
      .catch((e) => {
        if (active) {
          notify(String(e));
          setClassLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [cls]);
  async function start() {
    setStorageId(null);
    setTargetAction(null);
    setBusy(true);
    try {
      if (session) await api("/sessions/" + session.id, undefined, "DELETE");
      setSession(
        await api("/sessions", {
          map_ref: map,
          race,
          character_class: cls,
          seed,
          scores,
          background: background || null,
          cantrips,
          viewport_width: 48,
          viewport_height: 24,
        }),
      );
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function command(
    command: string,
    placement?: string,
    choice?: string,
    x?: number,
    y?: number,
    exchange?: {
      item?: string;
      quantity?: number;
      deposit?: boolean;
      spell_id?: string;
      source?: string;
      option?: string;
    },
  ) {
    if (!session || busy) return;
    setBusy(true);
    try {
      const result = await api("/sessions/" + session.id + "/commands", {
        command,
        placement,
        choice,
        x,
        y,
        ...exchange,
      });
      setSession(result);
      return result;
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (storageId) return;
      if ((e.target as HTMLElement).matches("input,textarea,select")) return;
      const key = e.key.toLowerCase();
      if (targetAction) {
        if (key === "escape" || key === "backspace") {
          e.preventDefault();
          setTargetAction(null);
        }
        return;
      }
      if (session?.lockpick) {
        e.preventDefault();
        if (e.repeat) return;
        if (key === " ") void command("lockpick_step");
        else if (key === "backspace" || key === "escape")
          void command("lockpick_cancel");
        return;
      }
      if (key === "g") {
        e.preventDefault();
        void command("pickup");
        return;
      }
      if ("wasd".includes(key) && key.length === 1) {
        e.preventDefault();
        void command(key);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
  useEffect(
    () => () => {
      if (session)
        void api("/sessions/" + session.id, undefined, "DELETE").catch(
          () => {},
        );
    },
    [session?.id],
  );
  return (
    <div className="modal-backdrop">
      <div className="playtest modal">
        <div className="dialog-heading">
          <div>
            <span className="eyebrow">PYTHON ENGINE / PLAYTEST</span>
            <h2>{map}</h2>
          </div>
          <button onClick={onClose}>Закрыть</button>
        </div>
        <div className="toolbar">
          <select
            aria-label="Тестовая раса"
            value={race}
            onChange={(e) => setRace(e.target.value)}
          >
            {entries
              .filter((e) => e.category === "races")
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Тестовый класс"
            value={cls}
            onChange={(e) => {
              const next = e.target.value;
              setCls(next);
              const selected = entries.find(
                (entry) =>
                  entry.ref === background && entry.category === "backgrounds",
              );
              if (selected?.classes?.length && !selected.classes.includes(next))
                setBackground("");
            }}
          >
            {entries
              .filter((e) => e.category === "classes")
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Тестовая предыстория"
            value={background}
            onChange={(e) => setBackground(e.target.value)}
          >
            <option value="">Без предыстории</option>
            {entries
              .filter(
                (e) =>
                  e.category === "backgrounds" &&
                  (!e.classes?.length || e.classes.includes(cls)),
              )
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <label>
            Seed{" "}
            <input
              className="short"
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </label>
          <button
            className="primary"
            disabled={busy || classLoading || cantrips.length !== cantripCount}
            onClick={() => void start()}
          >
            {session ? "Новая сессия" : "Начать тест"}
          </button>
          {session && (
            <button
              disabled={busy}
              onClick={async () => {
                setTargetAction(null);
                setStorageId(null);
                try {
                  setSession(
                    await api("/sessions/" + session.id + "/reset", {}),
                  );
                } catch (e) {
                  notify(String(e));
                }
              }}
            >
              Перезапустить
            </button>
          )}
        </div>
        <div className="toolbar">
          {["СИЛ", "ЛОВ", "ТЕЛ", "ИНТ", "МДР", "ХАР"].map((name, i) => (
            <label key={name}>
              {name}
              <input
                className="short"
                type="number"
                min="1"
                value={scores[i]}
                onChange={(e) =>
                  setScores(
                    scores.map((v, j) =>
                      i === j ? Number(e.target.value) : v,
                    ),
                  )
                }
              />
            </label>
          ))}
        </div>
        {!!cantripOptions.length && (
          <fieldset>
            <legend>
              Заговоры тестового героя: {cantrips.length}/{cantripCount}
            </legend>
            <div className="toolbar">
              {cantripOptions.map((ref) => (
                <label key={ref}>
                  <input
                    type="checkbox"
                    checked={cantrips.includes(ref)}
                    disabled={
                      !cantrips.includes(ref) && cantrips.length >= cantripCount
                    }
                    onChange={(e) =>
                      setCantrips(
                        e.target.checked
                          ? [...cantrips, ref]
                          : cantrips.filter((s) => s !== ref),
                      )
                    }
                  />
                  {entries.find((e) => e.category === "spells" && e.ref === ref)
                    ?.name ?? ref}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {session ? (
          <div className="play-layout">
            <div className="workspace">
              <div className="canvas-scroll">
                <Grid
                  cells={session.cells}
                  zoom={1.3}
                  onDown={
                    targetAction
                      ? (p) => {
                          if (busy) return;
                          void command(
                            targetAction.command,
                            targetAction.item,
                            undefined,
                            p.x + session.viewport.x,
                            p.y + session.viewport.y,
                            targetAction.command === "cast"
                              ? {
                                  spell_id: targetAction.item,
                                  source: targetAction.source,
                                  option: targetAction.option,
                                }
                              : undefined,
                          );
                          setTargetAction(null);
                        }
                      : undefined
                  }
                />
              </div>
              {targetAction && (
                <div className="toolbar">
                  <strong>
                    {targetAction.name}:{" "}
                    {targetAction.command === "ignite"
                      ? "поджечь одну из 8 соседних клеток"
                      : targetAction.command === "throw"
                        ? "выберите клетку броска"
                        : "выберите видимую клетку цели"}
                    . Нажмите на карту.
                  </strong>
                  <button onClick={() => setTargetAction(null)}>
                    Esc · Отменить
                  </button>
                </div>
              )}
              <p className="muted">
                Карта {session.width}×{session.height} · камера следует за
                героем
              </p>
              {session.lockpick && (
                <section className="lockpick-panel" aria-label="Взлом замка">
                  <strong>
                    Взлом замка: {session.lockpick.progress}/
                    {session.lockpick.total}
                  </strong>
                  <pre>
                    {Array.from({ length: session.lockpick.total }, (_, i) =>
                      i < session.lockpick.progress ? "[#]" : "[ ]",
                    ).join("")}
                  </pre>
                  <button
                    disabled={busy}
                    onClick={() => void command("lockpick_step")}
                  >
                    Space · Следующий ход
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void command("lockpick_cancel")}
                  >
                    Backspace · Отменить
                  </button>
                  <p>Каждое нажатие проводит ход и одну игровую минуту.</p>
                </section>
              )}
              <div className="toolbar">
                <button
                  disabled={
                    busy ||
                    !(session.ground ?? []).some(
                      (p: Doc) =>
                        p.x === session.position.x &&
                        p.y === session.position.y,
                    )
                  }
                  onClick={() => void command("pickup")}
                >
                  G · Подобрать
                </button>
                <button disabled={busy} onClick={() => void command("w")}>
                  W ↑
                </button>
                <button disabled={busy} onClick={() => void command("a")}>
                  A ←
                </button>
                <button disabled={busy} onClick={() => void command("s")}>
                  S ↓
                </button>
                <button disabled={busy} onClick={() => void command("d")}>
                  D →
                </button>
                <button disabled={busy} onClick={() => void command("wait")}>
                  Ждать
                </button>
                <button disabled={busy} onClick={() => void command("rest")}>
                  Отдых 8 часов
                </button>
              </div>
              <div className="event-log">
                {[...session.log].reverse().map((e: Doc, i: number) => (
                  <p key={i} className={e.performed ? "" : "muted"}>
                    {e.message}
                    <small> +{e.minutes} мин.</small>
                  </p>
                ))}
              </div>
            </div>
            <aside className="inspector">
              <h3>{session.hero.name}</h3>
              <div className="stat-grid">
                <span>
                  Хиты
                  <strong>
                    {session.hero.hp} / {session.hero.max_hp}
                  </strong>
                </span>
                <span>
                  КД<strong>{session.hero.armor_class}</strong>
                </span>
                <span>
                  Золото<strong>{session.hero.gold}</strong>
                </span>
                <span>
                  Опыт<strong>{session.hero.experience}</strong>
                </span>
              </div>
              <p>
                День {session.clock.day},{" "}
                {String(session.clock.hour).padStart(2, "0")}:
                {String(session.clock.minute).padStart(2, "0")} ·{" "}
                {session.clock.time_of_day}
              </p>
              <p className="hint">
                Ячейки:{" "}
                {Object.entries(session.hero.spell_slots)
                  .map(([lvl, count]) => `${lvl} ур. — ${count}`)
                  .join(", ") || "нет"}{" "}
                · Расовых применений: {session.hero.racial_uses}
              </p>
              <p className="hint">
                Ход {session.turns} · ({session.position.x},{" "}
                {session.position.y})
              </p>
              {(session.containers ?? []).map((c: Doc) => (
                <section key={"storage/" + c.id}>
                  <h3>{c.name}</h3>
                  <p>
                    {c.personal ? "Личный" : "Лутовый"} · {c.weight}/
                    {c.capacity} кг
                  </p>
                  <button
                    disabled={busy || !!session.lockpick}
                    onClick={() => {
                      setTargetAction(null);
                      setStorageId(c.id);
                    }}
                  >
                    Открыть контейнер
                  </button>
                </section>
              ))}
              {session.nearby
                .filter((p: Doc) => p.choices.length > 0)
                .map((p: Doc) => (
                  <section key={p.id}>
                    <h3>{p.name}</h3>
                    <p>{p.text}</p>
                    {p.completed && (
                      <p className="hint">Испытание уже завершено.</p>
                    )}
                    {p.choices.map((c: Doc) => (
                      <button
                        className="choice"
                        key={c.id}
                        disabled={busy}
                        onClick={() => void command("interact", p.id, c.id)}
                      >
                        {c.text}
                      </button>
                    ))}
                  </section>
                ))}
              <h3>Снаряжение и свет</h3>
              <p className="hint">
                Занято рук: {session.hero.hands_used}/2. Снимите оружие или щит,
                чтобы взять источник света. Одна порция масла — час; отдых
                расходует топливо.
              </p>
              {session.hero.inventory.map((item: Doc) => (
                <div
                  key={item.id}
                  className="playtest-item"
                  data-item-id={item.id}
                >
                  <span>
                    {item.equipped ? "[*] " : item.slot ? "[ ] " : ""}
                    {item.name}
                    {item.light &&
                      ` · ${item.lit ? "горит" : "погашен"}, ${item.fuel_minutes} мин.`}
                    {item.charges != null && ` · ${item.charges} примен.`}
                    {item.durability != null &&
                      ` · прочность ${item.durability}/${item.max_durability}`}
                    {item.glow &&
                      ` · Свечение [glowing]: ${item.glow.remaining_turns} ход., яркий радиус ${item.glow.bright_radius}, общий ${item.glow.radius} кл.`}
                  </span>
                  {item.slot && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void command(
                          item.equipped ? "unequip" : "equip",
                          item.id,
                        )
                      }
                    >
                      {item.equipped
                        ? "Снять"
                        : item.light
                          ? "Взять и зажечь"
                          : "Надеть"}
                    </button>
                  )}
                  {item.throwable && (
                    <button
                      disabled={busy || !!session.lockpick}
                      onClick={() =>
                        setTargetAction({
                          command: "throw",
                          item: item.id,
                          name: item.name,
                        })
                      }
                    >
                      Бросить на клетку
                    </button>
                  )}
                  {item.ignition_source && (
                    <button
                      disabled={busy || !!session.lockpick || !item.can_ignite}
                      title="Поджог: кремень и кресало, горящий факел или огненное оружие в руке; 8 соседних клеток"
                      onClick={() =>
                        setTargetAction({
                          command: "ignite",
                          item: item.id,
                          name: item.name,
                        })
                      }
                    >
                      Поджечь
                    </button>
                  )}
                </div>
              ))}
              {!!session.oil?.length && (
                <section>
                  <h3>Масло на клетках</h3>
                  {session.oil.map((p: Doc) => (
                    <p key={`${p.x},${p.y}`}>
                      ({p.x}, {p.y}): {p.turns} ход(ов); огонь +5 урона
                    </p>
                  ))}
                </section>
              )}
              <h3>Магия</h3>
              <p>
                Заговоры: {session.hero.cantrip_uses}/
                {session.hero.max_cantrip_uses} · Концентрация:{" "}
                {session.hero.concentrating ? "да" : "нет"}
              </p>
              <p className="hint">
                Каждое применение — 1 заряд и ход. Выбор цели бесплатный. Боевые
                заговоры проверяются в песочнице.
              </p>
              <label>
                Эффект фокусов{" "}
                <select
                  value={spellOption}
                  onChange={(e) => setSpellOption(e.target.value)}
                >
                  <option value="ignite">Поджечь</option>
                  <option value="extinguish">Погасить</option>
                  <option value="mark">Метка</option>
                  <option value="noise">Звук</option>
                </select>
              </label>
              {(session.hero.spells ?? []).map((s: Doc) => {
                const key = s.source + ":" + s.id;
                const items = session.hero.inventory.filter((item: Doc) =>
                  (s.item_targets ?? []).includes(item.id),
                );
                const selectedItem = items.some(
                  (item: Doc) => item.id === spellItems[key],
                )
                  ? spellItems[key]
                  : "";
                return (
                  <div key={key}>
                    {s.target === "item" && (
                      <label>
                        {s.name}: предмет
                        <select
                          aria-label={`Предмет для заговора ${s.name} (${s.source === "racial" ? "раса" : "класс"})`}
                          value={selectedItem}
                          disabled={busy || !items.length}
                          onChange={(e) =>
                            setSpellItems((previous) => ({
                              ...previous,
                              [key]: e.target.value,
                            }))
                          }
                        >
                          <option value="">
                            {items.length
                              ? "Выберите предмет"
                              : s.world_effect === "repair"
                                ? "Нет повреждённых предметов с прочностью"
                                : "Нет подходящих предметов"}
                          </option>
                          {items.map((item: Doc) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                              {item.durability != null
                                ? ` (${item.durability}/${item.max_durability})`
                                : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <button
                      disabled={
                        busy ||
                        !s.modes.includes("exploration") ||
                        (s.level === 0 && session.hero.cantrip_uses === 0) ||
                        (s.target === "item" && !selectedItem)
                      }
                      title={
                        s.description +
                        (s.pending_effects.length
                          ? " Позже: " + s.pending_effects.join("; ")
                          : "")
                      }
                      onClick={() => {
                        if (s.target === "item")
                          void command(
                            "cast",
                            undefined,
                            undefined,
                            undefined,
                            undefined,
                            {
                              spell_id: s.id,
                              source: s.source,
                              item: selectedItem,
                            },
                          );
                        else if (s.target === "cell")
                          setTargetAction({
                            command: "cast",
                            item: s.id,
                            name: s.name,
                            source: s.source,
                            option:
                              s.world_effect === "illusion" &&
                              !["mark", "noise"].includes(spellOption)
                                ? "mark"
                                : spellOption,
                          });
                        else
                          void command(
                            "cast",
                            undefined,
                            undefined,
                            undefined,
                            undefined,
                            { spell_id: s.id, source: s.source },
                          );
                      }}
                    >
                      {s.name} · {s.range} кл.{" "}
                      {s.modes.includes("exploration") ? "" : "[бой]"}
                    </button>
                  </div>
                );
              })}
              {session.hero.hand_active && (
                <button
                  disabled={busy}
                  onClick={() =>
                    setTargetAction({
                      command: "hand",
                      item: "",
                      name: "Волшебная рука",
                    })
                  }
                >
                  Волшебная рука: взаимодействовать
                </button>
              )}
              <button
                disabled={busy}
                onClick={() => void command("short_rest")}
              >
                Короткий отдых · заговоры +модификатор
              </button>
              <h3>Броски и эффекты</h3>
              <div className="event-log">
                {[...session.events].reverse().map((e: Doc, i: number) => (
                  <div key={i}>
                    <p>{e.message}</p>
                    {e.effects?.map((f: Doc, j: number) => (
                      <small key={j}>{effectText(f)} </small>
                    ))}
                  </div>
                ))}
              </div>
            </aside>
          </div>
        ) : (
          <div className="empty-state">
            <span>✦</span>
            <h3>Отдельная игровая сессия</h3>
            <p>
              Выберите героя и seed. Ловушки, испытания и ресурсы использует тот
              же движок, что и терминальная игра.
            </p>
          </div>
        )}
        {storageId &&
          session?.containers?.find((c: Doc) => c.id === storageId) && (
            <StorageDialog
              key={storageId}
              container={session.containers.find(
                (c: Doc) => c.id === storageId,
              )}
              hero={session.hero}
              busy={busy}
              message={session.log.at(-1)?.message ?? ""}
              onClose={() => setStorageId(null)}
              transfer={async (item, quantity, deposit) => {
                const result = await command(
                  "storage_transfer",
                  storageId,
                  undefined,
                  undefined,
                  undefined,
                  { item, quantity, deposit },
                );
                return !!result?.log.at(-1)?.performed;
              }}
            />
          )}
      </div>
    </div>
  );
}
