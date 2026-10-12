import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Doc, Entry } from "./model";

export function PackManager({
  packs,
  entries,
  initialPack,
  unsavedPack,
  onChanged,
  onClose,
}: {
  packs: Doc[];
  entries: Entry[];
  initialPack?: string;
  unsavedPack?: string;
  onChanged: (id: string, deleted: boolean) => Promise<void>;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(
    packs.some((p) => p.id === initialPack)
      ? initialPack!
      : (packs[0]?.id ?? null),
  );
  const [draft, setDraft] = useState<Doc | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [baseline, setBaseline] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const dirty = !!draft && JSON.stringify(draft) !== baseline;
  const dependents = packs.filter((p) => p.dependencies.includes(selected));
  const deleteReason =
    selected === "base"
      ? "Базовый пакет необходим для работы студии и игры."
      : selected === unsavedPack
        ? "Сначала сохраните или закройте черновик этого пакета."
        : dependents.length
          ? "От пакета зависят: " +
            dependents.map((p) => `${p.name} (${p.id})`).join(", ")
          : "";

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    dialog.current
      ?.querySelector<HTMLInputElement>('input[type="search"]')
      ?.focus();
    return () => {
      dialog.current?.close();
      previous?.focus();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError("");
    setDraft(null);
    setBusy(true);
    const load = selected
      ? api("/packs/" + selected)
      : Promise.resolve({
          document: {
            schema_version: 1,
            id: "",
            name: "",
            version: "1.0.0",
            dependencies: packs.some((p) => p.id === "base") ? ["base"] : [],
          },
          version: null,
        });
    void load
      .then((result) => {
        if (cancelled) return;
        setDraft(result.document);
        setVersion(result.version);
        setBaseline(JSON.stringify(result.document));
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  function discardChanges() {
    return (
      !dirty ||
      window.confirm(
        "В настройках пакета есть несохранённые изменения. Продолжить?",
      )
    );
  }
  function choose(id: string | null) {
    if (id === selected) return;
    if (busy || !discardChanges()) return;
    setMessage("");
    setDraft(null);
    setBusy(true);
    setSelected(id);
  }
  function close() {
    if (!busy && discardChanges()) onClose();
  }
  async function save() {
    if (!draft || busy) return;
    setBusy(true);
    setError("");
    try {
      if (selected)
        await api("/packs/" + selected, { document: draft, version }, "PUT");
      else await api("/packs", draft);
      const result = await api("/packs/" + draft.id);
      setDraft(result.document);
      setVersion(result.version);
      setBaseline(JSON.stringify(result.document));
      await onChanged(draft.id, false);
      setSelected(draft.id);
      setMessage(
        "Настройки пакета сохранены. Открытый документ можно сохранить без перезагрузки.",
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (
      !selected ||
      busy ||
      deleteReason ||
      !window.confirm(
        `Удалить пакет «${draft?.name}» (${selected}) со всем содержимым? Копия будет сохранена в архиве.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      const result = await api("/packs/" + selected, { version }, "DELETE");
      await onChanged(selected, true);
      setSelected(packs.find((p) => p.id !== selected)?.id ?? null);
      setMessage("Пакет удалён. Архив: " + result.archive);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="modal pack-manager"
      aria-label="Пакеты контента"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
          e.preventDefault();
          void save();
        }
      }}
    >
      <div className="dialog-heading">
        <div>
          <span className="eyebrow">БИБЛИОТЕКА ПРОЕКТА</span>
          <h2>Пакеты контента</h2>
        </div>
        <button disabled={busy} onClick={close}>
          Закрыть
        </button>
      </div>
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="hint" role="status">
          {message}
        </p>
      )}
      <div className="pack-manager-layout">
        <aside className="pack-manager-list" aria-label="Список пакетов">
          <input
            type="search"
            aria-label="Поиск пакетов"
            placeholder="Название или ID…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            disabled={busy}
            className="primary"
            onClick={() => choose(null)}
          >
            + Новый пакет
          </button>
          {packs
            .filter((p) =>
              `${p.name} ${p.id}`
                .toLocaleLowerCase("ru")
                .includes(query.trim().toLocaleLowerCase("ru")),
            )
            .sort((a, b) => a.name.localeCompare(b.name, "ru"))
            .map((p) => (
              <button
                key={p.id}
                disabled={busy}
                aria-pressed={selected === p.id}
                className={selected === p.id ? "selected" : ""}
                onClick={() => choose(p.id)}
              >
                <strong>{p.name}</strong>
                <small>
                  {p.id} ·{" "}
                  {entries.filter((e) => e.ref.startsWith(p.id + ":")).length}{" "}
                  документов
                </small>
              </button>
            ))}
        </aside>
        <form
          className="pack-manager-form"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
          aria-busy={busy}
        >
          {draft ? (
            <>
              <h3>
                {selected ? "Настройки пакета" : "Новый пакет контента"}
                {dirty ? " · есть изменения" : ""}
              </h3>
              <label>
                ID пакета
                <input
                  aria-label="ID пакета"
                  value={draft.id}
                  disabled={!!selected || busy}
                  required
                  pattern="[a-z][a-z0-9_]*"
                  onChange={(e) => setDraft({ ...draft, id: e.target.value })}
                />
              </label>
              <p className="hint">
                ID используется в ссылках и сохраняется постоянным. Отображаемое
                название можно менять.
              </p>
              <label>
                Название пакета
                <input
                  aria-label="Название пакета"
                  value={draft.name}
                  required
                  disabled={busy}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </label>
              <label>
                Версия пакета
                <input
                  aria-label="Версия пакета"
                  value={draft.version}
                  required
                  disabled={busy}
                  onChange={(e) =>
                    setDraft({ ...draft, version: e.target.value })
                  }
                />
              </label>
              <fieldset disabled={busy}>
                <legend>Зависимости пакета</legend>
                <p className="hint">
                  Отметьте пакеты, чьи элементы используются внутри этого
                  пакета. Для стандартных полов, света и предметов нужен base.
                </p>
                {packs
                  .filter((p) => p.id !== selected)
                  .map((p) => (
                    <label className="toggle" key={p.id}>
                      <input
                        type="checkbox"
                        checked={draft.dependencies.includes(p.id)}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            dependencies: e.target.checked
                              ? [...draft.dependencies, p.id]
                              : draft.dependencies.filter(
                                  (id: string) => id !== p.id,
                                ),
                          })
                        }
                      />
                      {p.name} · {p.id}
                    </label>
                  ))}
              </fieldset>
              {deleteReason && <p className="hint">{deleteReason}</p>}
              <div className="toolbar">
                {selected && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy || !!deleteReason}
                    onClick={() => void remove()}
                  >
                    Удалить пакет
                  </button>
                )}
                <button
                  className="primary"
                  type="submit"
                  disabled={busy || !dirty || !draft.name.trim()}
                >
                  {selected ? "Сохранить пакет" : "Создать пакет"}
                </button>
              </div>
            </>
          ) : (
            <p>{busy ? "Загружаем настройки…" : "Выберите пакет."}</p>
          )}
        </form>
      </div>
    </dialog>
  );
}
