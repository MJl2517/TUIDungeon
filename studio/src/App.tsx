import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Doc, Entry, History, clone, compose, color } from "./model";
import { FieldForm } from "./Form";
import { ArtEditor } from "./ArtEditor";
import { MapEditor } from "./MapEditor";
import { Playtest } from "./Playtest";
import { Grid } from "./Grid";
const icons: Record<string, string> = {
  art: "░",
  tiles: "▦",
  maps: "⌗",
  monsters: "♜",
  equipment: "◇",
  spells: "✦",
  actions: "↯",
  classes: "♙",
  races: "♧",
  backgrounds: "≡",
  challenges: "?",
  traps: "^",
  points_of_interest: "$",
};
export default function App() {
  const [library, setLibrary] = useState<Doc | null>(null),
    [meta, setMeta] = useState<Doc | null>(null),
    [category, setCategory] = useState("maps"),
    [pack, setPack] = useState("all"),
    [query, setQuery] = useState(""),
    [active, setActive] = useState<{
      category: string;
      ref: string;
      version: string | null;
      baseline: string;
      warnings: Doc[];
      usages: Doc[];
    } | null>(null),
    [revision, setRevision] = useState(0),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [assets, setAssets] = useState<Record<string, Doc>>({}),
    [creating, setCreating] = useState<Doc | null>(null),
    [packDialog, setPackDialog] = useState(false),
    [newPack, setNewPack] = useState({
      id: "",
      name: "",
      version: "1.0.0",
      dependencies: ["base"],
    }),
    [play, setPlay] = useState<string | null>(null),
    [source, setSource] = useState(false),
    [sourceText, setSourceText] = useState(""),
    [saving, setSaving] = useState(false),
    [sandbox, setSandbox] = useState<Doc | null>(null),
    [action, setAction] = useState(""),
    [seed, setSeed] = useState(42);
  const [sandboxDifficulty, setSandboxDifficulty] = useState(12),
    [sandboxTarget, setSandboxTarget] = useState("hero"),
    [sandboxSpell, setSandboxSpell] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false),
    [loadingAssets, setLoadingAssets] = useState(false);
  const assetVersions = useRef<Record<string, string>>({}),
    assetSequence = useRef(0);
  const activeRef = useRef(active),
    openSequence = useRef(0);
  activeRef.current = active;
  const history = useRef<History<Doc> | null>(null);
  const draft = history.current?.present;
  const entries: Entry[] = library?.documents ?? [];
  const dirty = active && draft && JSON.stringify(draft) !== active.baseline;
  const notify = (s: string) => {
    setMessage(s);
    setError("");
  };
  async function refresh() {
    const next = await api("/library");
    setLibrary(next);
    const assetEntries = next.documents.filter((e: Entry) =>
      [
        "art",
        "tiles",
        "traps",
        "points_of_interest",
        "monsters",
        "equipment",
        "actions",
      ].includes(e.category),
    );
    if (
      assetEntries.length !== Object.keys(assetVersions.current).length ||
      assetEntries.some(
        (e: Entry) =>
          assetVersions.current[e.category + "/" + e.ref] !== e.version,
      )
    )
      await loadAssets();
    return next;
  }
  async function loadAssets() {
    const sequence = ++assetSequence.current;
    setLoadingAssets(true);
    try {
      const result = await api("/assets");
      if (sequence !== assetSequence.current) return;
      setAssets(result.documents);
      assetVersions.current = result.versions;
    } finally {
      if (sequence === assetSequence.current) setLoadingAssets(false);
    }
  }
  async function open(c: string, ref: string) {
    if (
      dirty &&
      !window.confirm("Есть несохранённые изменения. Открыть другой документ?")
    )
      return;
    const sequence = ++openSequence.current;
    setLoadingDoc(true);
    try {
      const envelope = await api("/documents/" + c + "/" + ref);
      if (sequence !== openSequence.current) return;
      history.current = new History(envelope.document);
      setRevision((n) => n + 1);
      setActive({
        category: c,
        ref,
        version: envelope.version,
        baseline: JSON.stringify(envelope.document),
        warnings: envelope.warnings,
        usages: envelope.usages,
      });
      setCategory(c);
      setSource(false);
      setError("");
      setSandbox(null);
      notify("Документ открыт");
    } catch (e) {
      setError(String(e));
    } finally {
      if (sequence === openSequence.current) setLoadingDoc(false);
    }
  }
  useEffect(() => {
    Promise.all([api("/library"), api("/schemas")])
      .then(async ([lib, schemas]) => {
        setLibrary(lib);
        setMeta(schemas);
        await loadAssets();
        const initial =
          lib.documents.find(
            (e: Entry) => e.category === "maps" && e.ref === "base:crypt",
          ) ?? lib.documents[0];
        if (initial) await open(initial.category, initial.ref);
      })
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    const id = setInterval(() => {
      void refresh().catch((e) => setError(String(e)));
    }, 5000);
    return () => clearInterval(id);
  }, []);
  function change(next: Doc) {
    history.current!.commit(next);
    setRevision((n) => n + 1);
    setError("");
  }
  function undo() {
    history.current?.undo();
    setRevision((n) => n + 1);
  }
  function redo() {
    history.current?.redo();
    setRevision((n) => n + 1);
  }
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key === "s") {
        e.preventDefault();
        void save();
      } else if (
        e.key === "z" &&
        !(e.target as HTMLElement).matches("input,textarea")
      ) {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
      } else if (
        e.key === "y" &&
        !(e.target as HTMLElement).matches("input,textarea")
      ) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  });
  async function save() {
    if (!draft || !active) return;
    setSaving(true);
    const submitted = JSON.stringify(draft);
    try {
      const e = await api(
        "/documents/" + active.category + "/" + active.ref,
        { document: draft, version: active.version },
        "PUT",
      );
      if (
        activeRef.current?.ref === active.ref &&
        activeRef.current?.category === active.category
      ) {
        if (JSON.stringify(history.current!.present) === submitted)
          history.current!.present = e.document;
        setRevision((n) => n + 1);
        setActive((current) =>
          current?.ref === active.ref && current?.category === active.category
            ? {
                ...current,
                version: e.version,
                baseline: JSON.stringify(e.document),
                warnings: e.warnings,
                usages: e.usages,
              }
            : current,
        );
      }
      const lib = await refresh();
      await loadAssets();
      notify(
        "Сохранено в packs/" +
          active.ref.replace(":", "/" + active.category + "/") +
          ".json",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }
  async function validate() {
    if (!active || !draft) return;
    try {
      await api("/validate/" + active.category + "/" + active.ref, {
        document: draft,
      });
      notify("Структура, параметры и ссылки корректны");
    } catch (e) {
      setError(String(e));
    }
  }
  async function remove() {
    if (!active?.version) return;
    if (!window.confirm("Удалить " + active.ref + "?")) return;
    try {
      await api(
        "/documents/" + active.category + "/" + active.ref,
        { version: active.version },
        "DELETE",
      );
      setActive(null);
      history.current = null;
      setRevision((n) => n + 1);
      await refresh();
      notify("Объект удалён");
    } catch (e) {
      setError(String(e));
    }
  }
  function beginCreate(duplicate = false) {
    const c = duplicate ? active!.category : category;
    const raw = clone(duplicate ? draft! : meta!.templates[c]);
    raw.id = duplicate ? raw.id + "_copy" : "new_object";
    raw.name = duplicate ? raw.name + " — копия" : "Новый объект";
    setCreating({ category: c, pack: pack === "all" ? "base" : pack, raw });
  }
  function create() {
    if (!creating) return;
    if (!/^[a-z][a-z0-9_]*$/.test(creating.raw.id)) {
      setError("id: латинские строчные буквы, цифры и подчёркивание");
      return;
    }
    const ref = creating.pack + ":" + creating.raw.id;
    if (
      entries.some((e) => e.category === creating.category && e.ref === ref)
    ) {
      setError("Идентификатор уже занят");
      return;
    }
    ++openSequence.current;
    setLoadingDoc(false);
    history.current = new History(clone(creating.raw));
    setRevision((n) => n + 1);
    setActive({
      category: creating.category,
      ref,
      version: null,
      baseline: "",
      warnings: [],
      usages: [],
    });
    setCategory(creating.category);
    setCreating(null);
    setSource(false);
    notify("Новый документ. Сохраните, чтобы добавить в пакет.");
  }
  function download() {
    if (!draft) return;
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(draft, null, 2) + "\n"], {
          type: "application/json",
        }),
      ),
      a = document.createElement("a");
    a.href = url;
    a.download =
      draft.id + (active?.category === "art" ? ".art" : "") + ".json";
    a.click();
    URL.revokeObjectURL(url);
  }
  const external =
    active?.version &&
    entries.find((e) => e.category === active.category && e.ref === active.ref)
      ?.version !== active.version;
  const filtered = entries.filter(
    (e) =>
      e.category === category &&
      (pack === "all" || e.ref.startsWith(pack + ":")) &&
      `${e.name} ${e.ref}`.toLowerCase().includes(query.toLowerCase()),
  );
  const art = draft?.art ? assets["art/" + draft.art] : null;
  const availableActions =
    draft && active?.category === "monsters"
      ? [
          ...draft.actions.map((ref: string) => ({
            id: ref.replace(/^base:/, ""),
            name: assets["actions/" + ref]?.name ?? ref,
          })),
          ...draft.special_actions.map((a: Doc) => ({
            id: a.id,
            name: a.name,
          })),
        ]
      : [];
  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">▚</span>
          <div>
            <strong>
              DUNGEON<span>STUDIO</span>
            </strong>
            <small>Символы становятся мирами</small>
          </div>
        </div>
        <div className="header-meta">
          <span className="status-dot" />
          Локальный проект<span className="tag">v1.0</span>
        </div>
      </header>
      <aside className="navigation">
        <div className="nav-heading">МАСТЕРСКАЯ</div>
        {Object.entries(library?.categories ?? {}).map(([c, name]) => (
          <button
            key={c}
            className={category === c ? "selected" : ""}
            onClick={() => {
              setCategory(c);
              setQuery("");
            }}
          >
            <span>{icons[c]}</span>
            {name as string}
            <small>{entries.filter((e) => e.category === c).length}</small>
          </button>
        ))}
        <div className="nav-footer">
          <span>JSON + PYTHON</span>
          <p>
            Общие данные.
            <br />
            Один игровой движок.
          </p>
          <button className="subtle" onClick={() => setPackDialog(true)}>
            + Пакет контента
          </button>
        </div>
      </aside>
      <section className="library">
        <div className="library-heading">
          <span className="eyebrow">БИБЛИОТЕКА</span>
          <h2>{library?.categories[category] ?? "Загрузка…"}</h2>
          <button
            className="primary"
            disabled={!meta}
            onClick={() => beginCreate()}
          >
            + Создать
          </button>
        </div>
        <select
          aria-label="Пакет библиотеки"
          value={pack}
          onChange={(e) => setPack(e.target.value)}
        >
          <option value="all">Все пакеты</option>
          {library?.packs.map((p: Doc) => (
            <option key={p.id} value={p.id}>
              {p.name} · {p.id}
            </option>
          ))}
        </select>
        <input
          className="search"
          placeholder="Поиск по имени или ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="library-list">
          {filtered.map((e) => (
            <button
              className={
                "library-entry " +
                (active?.ref === e.ref && active.category === e.category
                  ? "selected"
                  : "")
              }
              key={e.ref}
              onClick={() => void open(e.category, e.ref)}
            >
              <span className="entry-glyph">
                {e.glyph ?? icons[e.category]}
              </span>
              <span>
                <strong>{e.name}</strong>
                <small>{e.ref}</small>
              </span>
            </button>
          ))}
          {!filtered.length && (
            <p className="hint">Пока нет объектов. Создайте первый шаблон.</p>
          )}
        </div>
        <footer>{filtered.length} объектов · файлы в packs/</footer>
      </section>
      <main className="main" aria-busy={loadingDoc || loadingAssets}>
        {(loadingDoc || loadingAssets) && (
          <div className="loading-overlay">
            <span className="status-dot" />
            {loadingDoc ? "Открытие документа…" : "Обновление библиотеки…"}
          </div>
        )}
        <div className="document-heading">
          <div>
            <span className="eyebrow">
              {active
                ? library?.categories[active.category]
                : "ВЫБЕРИТЕ ДОКУМЕНТ"}
            </span>
            <h1>
              {draft && active && ["art", "maps"].includes(active.category) ? (
                <input
                  aria-label="Название документа"
                  className="document-name"
                  size={Math.min(40, Math.max(12, draft.name.length))}
                  value={draft.name}
                  onChange={(e) => change({ ...draft, name: e.target.value })}
                />
              ) : (
                (draft?.name ?? "Мастерская подземелий")
              )}
              {dirty && (
                <span className="unsaved" title="Не сохранено">
                  ●
                </span>
              )}
            </h1>
            <span className="document-ref">
              {active?.ref ?? "Графика, механики и карты в одном проекте"}
            </span>
          </div>
          {active && (
            <div className="toolbar">
              <button
                disabled={!history.current?.past.length}
                onClick={undo}
                title="Ctrl+Z"
              >
                ↶
              </button>
              <button
                disabled={!history.current?.future.length}
                onClick={redo}
                title="Ctrl+Shift+Z"
              >
                ↷
              </button>
              <button onClick={() => void validate()}>Проверить</button>
              <button
                className="primary"
                disabled={saving}
                onClick={() => void save()}
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          )}
        </div>
        {error && (
          <div className="banner error" role="alert">
            {error}
            <button className="mini" onClick={() => setError("")}>
              ×
            </button>
          </div>
        )}
        {external && (
          <div className="banner warning">
            Файл изменён вне студии. Ваш черновик сохранён в редакторе.
            <button
              onClick={() => {
                if (active) void open(active.category, active.ref);
              }}
            >
              Перечитать
            </button>
          </div>
        )}
        {draft && active && meta ? (
          <>
            <div className="document-tabs">
              <button
                className={!source ? "selected" : ""}
                onClick={() => setSource(false)}
              >
                Редактор
              </button>
              <button
                className={source ? "selected" : ""}
                onClick={() => {
                  setSourceText(JSON.stringify(draft, null, 2));
                  setSource(true);
                }}
              >
                JSON
              </button>
              <span />
              <button onClick={() => beginCreate(true)}>Дублировать</button>
              <button onClick={download}>Экспорт JSON</button>
              <button
                disabled={!active.version || active.usages.length > 0}
                title={
                  active.usages.length
                    ? "Объект используется"
                    : "Удалить объект"
                }
                onClick={() => void remove()}
              >
                Удалить
              </button>
              {active.category === "maps" && (
                <button
                  className="test-button"
                  disabled={!active.version || !!dirty}
                  title={dirty ? "Сначала сохраните карту" : ""}
                  onClick={() => setPlay(active.ref)}
                >
                  ▶ Тестировать карту
                </button>
              )}
            </div>
            {source ? (
              <div className="source-editor">
                <textarea
                  aria-label="JSON документа"
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                />
                <button
                  onClick={async () => {
                    try {
                      const next = JSON.parse(sourceText);
                      if (next.id !== draft.id)
                        throw new Error("ID фиксируется после создания");
                      await api(
                        "/validate/" + active.category + "/" + active.ref,
                        { document: next },
                      );
                      change(next);
                      setSource(false);
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  Применить JSON
                </button>
              </div>
            ) : active.category === "art" ? (
              <ArtEditor
                key={active.ref}
                doc={draft}
                onChange={change}
                notify={notify}
              />
            ) : active.category === "maps" ? (
              <MapEditor
                key={active.ref}
                doc={draft}
                onChange={change}
                entries={entries}
                assets={assets}
                warnings={active.warnings}
                notify={notify}
              />
            ) : (
              <div className="mechanics-layout">
                <div className="mechanics-form">
                  <FieldForm
                    schema={meta.schemas[active.category]}
                    root={meta.schemas[active.category]}
                    value={draft}
                    onChange={change}
                    entries={entries}
                    mechanics={meta.mechanics}
                    lockedId={true}
                  />
                </div>
                <aside className="inspector">
                  <span className="eyebrow">ПРЕДПРОСМОТР</span>
                  <div className="portrait">
                    {art ? (
                      <Grid cells={compose(art)} zoom={1.5} grid={false} />
                    ) : (
                      <span style={{ color: color(draft.foreground ?? 7) }}>
                        {draft.glyph ?? icons[active.category]}
                      </span>
                    )}
                  </div>
                  <h3>{draft.name}</h3>
                  <p>{draft.description}</p>
                  {draft.hit_points && (
                    <div className="stat-grid">
                      <span>
                        Хиты<strong>{draft.hit_points}</strong>
                      </span>
                      <span>
                        КД<strong>{draft.armor_class ?? "—"}</strong>
                      </span>
                      <span>
                        Скорость<strong>{draft.speed ?? "—"}</strong>
                      </span>
                      <span>
                        Инициатива
                        <strong>{draft.initiative_bonus ?? "—"}</strong>
                      </span>
                    </div>
                  )}
                  {active.category === "monsters" && (
                    <section className="sandbox">
                      <h3>Песочница действий</h3>
                      <p className="hint">
                        Монстр действует против тестового воина. Для проверки
                        сначала сохраните шаблон.
                      </p>
                      <select
                        aria-label="Действие монстра"
                        value={
                          availableActions.some((a) => a.id === action)
                            ? action
                            : (availableActions[0]?.id ?? "")
                        }
                        onChange={(e) => setAction(e.target.value)}
                      >
                        {availableActions.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                      </select>
                      <label>
                        Seed{" "}
                        <input
                          type="number"
                          value={seed}
                          onChange={(e) => setSeed(Number(e.target.value))}
                        />
                      </label>
                      <label>
                        Сложность{" "}
                        <input
                          type="number"
                          min="0"
                          value={sandboxDifficulty}
                          onChange={(e) =>
                            setSandboxDifficulty(Number(e.target.value))
                          }
                        />
                      </label>
                      <select
                        aria-label="Цель песочницы"
                        value={sandboxTarget}
                        onChange={(e) => setSandboxTarget(e.target.value)}
                      >
                        <option value="hero">Тестовый герой</option>
                        <option value="self">Сам монстр</option>
                      </select>
                      {draft.spells.length > 0 && (
                        <select
                          aria-label="Заклинание песочницы"
                          value={sandboxSpell}
                          onChange={(e) => setSandboxSpell(e.target.value)}
                        >
                          <option value="">Выберите заклинание</option>
                          {draft.spells.map((ref: string) => (
                            <option key={ref} value={ref}>
                              {entries.find(
                                (e) => e.category === "spells" && e.ref === ref,
                              )?.name ?? ref}
                            </option>
                          ))}
                        </select>
                      )}
                      <button
                        disabled={
                          !!dirty || !active.version || !availableActions.length
                        }
                        onClick={async () => {
                          try {
                            setSandbox(
                              await api("/sandbox", {
                                monster: active.ref,
                                action: availableActions.some(
                                  (a) => a.id === action,
                                )
                                  ? action
                                  : availableActions[0].id,
                                seed,
                                difficulty: sandboxDifficulty,
                                target: sandboxTarget,
                                spell_id: sandboxSpell || null,
                              }),
                            );
                          } catch (e) {
                            setError(String(e));
                          }
                        }}
                      >
                        Выполнить действие
                      </button>
                      {sandbox && (
                        <div className="sandbox-result">
                          <p>{sandbox.message}</p>
                          {sandbox.roll != null && (
                            <p>
                              d20: {sandbox.roll} → {sandbox.total}
                            </p>
                          )}
                          <p>
                            HP цели: {sandbox.target.hp}/{sandbox.target.max_hp}
                          </p>
                          <p>
                            Состояния монстра:{" "}
                            {Object.keys(sandbox.actor.conditions).join(", ") ||
                              "нет"}
                          </p>
                          <p>
                            Ячейки:{" "}
                            {Object.entries(sandbox.actor.spell_slots)
                              .map(([level, count]) => `${level}: ${count}`)
                              .join(", ") || "нет"}
                          </p>
                          {sandbox.effects.map((e: Doc, i: number) => (
                            <p key={i}>
                              {e.kind}: {e.condition || e.amount}
                            </p>
                          ))}
                        </div>
                      )}
                    </section>
                  )}
                  <h3>Где используется</h3>
                  {active.usages.length ? (
                    active.usages.map((u, i) => (
                      <button
                        className="usage"
                        key={i}
                        onClick={() => void open(u.category, u.ref)}
                      >
                        {u.ref}
                        <small>{u.field}</small>
                      </button>
                    ))
                  ) : (
                    <p className="hint">
                      Другие объекты пока не ссылаются на этот шаблон.
                    </p>
                  )}
                </aside>
              </div>
            )}
          </>
        ) : (
          <div className="empty-state">
            <pre>
              {
                "   /\       /\   \n  /##\_____/##\  \n  |  DUNGEON  |  \n  |___[]______|  "
              }
            </pre>
            <h2>Создайте свой мир</h2>
            <p>
              Нарисуйте символы, задайте правила и соедините их в подземелье.
            </p>
          </div>
        )}
      </main>
      <div className="statusbar">
        <span className="status-dot" />
        {message || "Готово"}
        <span className="status-spacer" />
        <span>Ctrl+S сохранить · Ctrl+Z отменить</span>
      </div>
      {creating && (
        <div className="modal-backdrop">
          <div className="modal creation-modal">
            <span className="eyebrow">НОВЫЙ ДОКУМЕНТ</span>
            <h2>{library?.categories[creating.category]}</h2>
            <label>
              Пакет
              <select
                value={creating.pack}
                onChange={(e) =>
                  setCreating({ ...creating, pack: e.target.value })
                }
              >
                {library?.packs.map((p: Doc) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              ID
              <input
                aria-label="ID нового документа"
                value={creating.raw.id}
                onChange={(e) =>
                  setCreating({
                    ...creating,
                    raw: { ...creating.raw, id: e.target.value },
                  })
                }
              />
            </label>
            <label>
              Название
              <input
                aria-label="Название нового документа"
                value={creating.raw.name}
                onChange={(e) =>
                  setCreating({
                    ...creating,
                    raw: { ...creating.raw, name: e.target.value },
                  })
                }
              />
            </label>
            <p className="hint">
              ID остаётся постоянным. Новый вариант создаётся дублированием.
            </p>
            <div className="toolbar">
              <button onClick={() => setCreating(null)}>Отмена</button>
              <button className="primary" onClick={create}>
                Создать документ
              </button>
            </div>
          </div>
        </div>
      )}
      {packDialog && (
        <div className="modal-backdrop">
          <div className="modal creation-modal">
            <h2>Новый пакет контента</h2>
            {(["id", "name", "version"] as const).map((k) => (
              <label key={k}>
                {k}
                <input
                  value={newPack[k]}
                  onChange={(e) =>
                    setNewPack({ ...newPack, [k]: e.target.value })
                  }
                />
              </label>
            ))}
            <h3>Зависимости</h3>
            {library?.packs.map((p: Doc) => (
              <label className="toggle" key={p.id}>
                <input
                  type="checkbox"
                  checked={newPack.dependencies.includes(p.id)}
                  onChange={(e) =>
                    setNewPack({
                      ...newPack,
                      dependencies: e.target.checked
                        ? [...newPack.dependencies, p.id]
                        : newPack.dependencies.filter((d) => d !== p.id),
                    })
                  }
                />
                {p.name}
              </label>
            ))}
            <div className="toolbar">
              <button onClick={() => setPackDialog(false)}>Отмена</button>
              <button
                className="primary"
                onClick={async () => {
                  try {
                    await api("/packs", newPack);
                    await refresh();
                    setPackDialog(false);
                    setPack(newPack.id);
                    notify("Пакет создан");
                  } catch (e) {
                    setError(String(e));
                  }
                }}
              >
                Создать пакет
              </button>
            </div>
          </div>
        </div>
      )}
      {play && (
        <Playtest
          map={play}
          entries={entries}
          onClose={() => setPlay(null)}
          notify={(s) => setError(s)}
        />
      )}
      <span hidden>{revision}</span>
    </div>
  );
}
