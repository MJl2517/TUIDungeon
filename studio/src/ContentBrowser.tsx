import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SymbolPreview } from "./Symbols";
import { Doc, Entry, libraryResults } from "./model";
import { contentBadges, contentGroup, contentRank, sections } from "./catalog";

export function ContentBrowser({
  entries,
  assets = {},
  category = "all",
  selected,
  onChoose,
}: {
  entries: Entry[];
  assets?: Record<string, Doc>;
  category?: string;
  selected?: string;
  onChoose: (entry: Entry) => void;
}) {
  const [query, setQuery] = useState(""),
    [scope, setScope] = useState(category),
    [pack, setPack] = useState("all"),
    [group, setGroup] = useState(""),
    [rank, setRank] = useState(""),
    [sort, setSort] = useState("group"),
    [readiness, setReadiness] = useState("all"),
    [page, setPage] = useState(0);
  const categories = [...new Set(entries.map((e) => e.category))];
  const scoped = entries.filter((e) => scope === "all" || e.category === scope);
  const groups = [...new Set(scoped.map((e) => contentGroup(e, assets)))].sort(
    (a, b) => a.localeCompare(b, "ru"),
  );
  const ranks = [
    ...new Set(
      scoped
        .filter((e) => e.category === "spells")
        .map((e) => e.details?.level)
        .filter((v) => v != null),
    ),
  ].sort((a, b) => a - b);
  const searchable = entries.map((e) => ({
    ...e,
    search_text:
      (e.search_text ?? "") +
      " " +
      contentBadges(e).join(" ") +
      " " +
      (sections[e.category]?.name ?? ""),
  }));
  const results = libraryResults(searchable, query, scope, pack, assets).filter(
    (e) =>
      (!group || contentGroup(e, assets) === group) &&
      (readiness === "all" ||
        (readiness === "ready") === !!e.details?.reviewed) &&
      (!rank || (e.category === "spells" && String(e.details?.level) === rank)),
  );
  results.sort((a, b) => {
    const cmp =
      sort === "id"
        ? a.ref.localeCompare(b.ref)
        : sort === "rank"
          ? contentRank(a) - contentRank(b)
          : sort === "group"
            ? (
                sections[a.category]?.name + contentGroup(a, assets)
              ).localeCompare(
                sections[b.category]?.name + contentGroup(b, assets),
                "ru",
              )
            : 0;
    return (
      cmp ||
      (sort === "name_desc" ? -1 : 1) * a.name.localeCompare(b.name, "ru") ||
      a.ref.localeCompare(b.ref)
    );
  });
  const pages = Math.max(1, Math.ceil(results.length / 36)),
    current = Math.min(page, pages - 1);
  const change = (set: (value: string) => void, value: string) => {
    set(value);
    setPage(0);
  };
  const reset = () => {
    setQuery("");
    setScope(category);
    setPack("all");
    setGroup("");
    setRank("");
    setSort("group");
    setReadiness("all");
    setPage(0);
  };
  let previousGroup = "";
  return (
    <div className="content-browser">
      <div className="content-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          aria-label="Поиск контента"
          placeholder="Название, ID, описание, тег или свойство…"
          value={query}
          onChange={(e) => change(setQuery, e.target.value)}
        />
      </div>
      <div className="content-filters">
        {scope === "symbols" && (
          <label>
            Готовность
            <select
              aria-label="Готовность символов"
              value={readiness}
              onChange={(e) => change(setReadiness, e.target.value)}
            >
              <option value="all">Все символы</option>
              <option value="ready">Согласованные</option>
              <option value="unreviewed">Неразобранные</option>
            </select>
          </label>
        )}
        {categories.length > 1 && (
          <label>
            Раздел
            <select
              aria-label="Раздел контента"
              value={scope}
              onChange={(e) => {
                change(setScope, e.target.value);
                setGroup("");
                setRank("");
              }}
            >
              <option value="all">Все разделы</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {sections[c]?.name ?? c}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Пакет
          <select
            aria-label="Пакет контента"
            value={pack}
            onChange={(e) => change(setPack, e.target.value)}
          >
            <option value="all">Все пакеты</option>
            {[...new Set(entries.map((e) => e.ref.split(":")[0]))]
              .sort()
              .map((p) => (
                <option key={p}>{p}</option>
              ))}
          </select>
        </label>
        <label>
          Категория
          <select
            aria-label="Категория контента"
            value={group}
            onChange={(e) => change(setGroup, e.target.value)}
          >
            <option value="">Все категории</option>
            {groups.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        {ranks.length > 0 && (
          <label>
            Уровень заклинания
            <select
              aria-label="Уровень заклинания"
              value={rank}
              onChange={(e) => change(setRank, e.target.value)}
            >
              <option value="">Любой уровень</option>
              {ranks.map((n) => (
                <option key={n} value={n}>
                  {n === 0 ? "Заговоры" : `${n} уровень`}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Сортировка
          <select
            aria-label="Сортировка контента"
            value={sort}
            onChange={(e) => change(setSort, e.target.value)}
          >
            <option value="group">По категории</option>
            <option value="name">Название А–Я</option>
            <option value="name_desc">Название Я–А</option>
            <option value="id">По ID</option>
            <option value="rank">Уровень / HP по возрастанию</option>
          </select>
        </label>
        <button className="subtle" onClick={reset}>
          Сбросить
        </button>
      </div>
      <div className="content-count" role="status">
        Найдено {results.length} из {entries.length}
        <span>Поиск учитывает выбранные фильтры</span>
      </div>
      <div className="content-results">
        {results.slice(current * 36, (current + 1) * 36).map((e) => {
          const heading = `${sections[e.category]?.name ?? e.category} / ${contentGroup(e, assets)}`;
          const showHeading = sort === "group" && heading !== previousGroup;
          previousGroup = heading;
          return (
            <div className="content-result-wrap" key={e.category + "/" + e.ref}>
              {showHeading && (
                <h3 className="content-group-heading">{heading}</h3>
              )}
              <button
                className={
                  "content-entry " +
                  (selected === e.category + "/" + e.ref || selected === e.ref
                    ? "selected"
                    : "")
                }
                onClick={() => onChoose(e)}
              >
                <span className="content-glyph" aria-hidden="true">
                  {e.category === "symbols" ? (
                    <SymbolPreview
                      symbol={e.ref}
                      doc={assets["symbols/" + e.ref]}
                    />
                  ) : e.symbol ? (
                    <SymbolPreview
                      symbol={e.symbol}
                      mirror_x={!!assets[e.category + "/" + e.ref]?.mirror_x}
                    />
                  ) : (
                    (e.glyph ?? sections[e.category]?.icon)
                  )}
                </span>
                <span className="content-entry-body">
                  <strong>{e.name}</strong>
                  <small>
                    {e.ref} · {sections[e.category]?.name}
                  </small>
                  {e.category === "symbols" && (
                    <small>
                      {e.glyph} ·{" "}
                      {e.details?.reviewed ? "Согласован" : "Неразобранное"} ·{" "}
                      {e.usage_count ?? 0} использований
                      <br />
                      {e.source_name}
                    </small>
                  )}
                  <span className="content-badges">
                    {contentBadges(e).map((b) => (
                      <span key={b}>{b}</span>
                    ))}
                  </span>
                  {e.description && (
                    <span className="content-description">{e.description}</span>
                  )}
                </span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
          );
        })}
        {!results.length && (
          <div className="content-empty">
            <strong>Ничего не найдено</strong>
            <p>Измените запрос или сбросьте выбранные фильтры.</p>
            <button onClick={reset}>Сбросить поиск и фильтры</button>
          </div>
        )}
      </div>
      {pages > 1 && (
        <nav className="content-pagination" aria-label="Страницы контента">
          <button disabled={!current} onClick={() => setPage(current - 1)}>
            ← Назад
          </button>
          <span>
            {current + 1} / {pages}
          </span>
          <button
            disabled={current === pages - 1}
            onClick={() => setPage(current + 1)}
          >
            Далее →
          </button>
        </nav>
      )}
    </div>
  );
}

export function ContentPicker({
  entries,
  title = "Поиск по проекту",
  onChoose,
  onClose,
  selected,
}: {
  entries: Entry[];
  title?: string;
  selected?: string;
  onChoose: (entry: Entry) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    node?.showModal();
    node?.querySelector<HTMLInputElement>('input[type="search"]')?.focus();
    return () => {
      node?.close();
      previousFocus?.focus();
    };
  }, []);
  return createPortal(
    <dialog
      ref={dialog}
      className="content-picker"
      aria-label={title}
      onCancel={onClose}
      onClose={onClose}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <header>
        <div>
          <span className="eyebrow">БИБЛИОТЕКА ПРОЕКТА</span>
          <h2>{title}</h2>
        </div>
        <button onClick={onClose} aria-label="Закрыть поиск">
          Esc · Закрыть
        </button>
      </header>
      <ContentBrowser
        entries={entries}
        selected={selected}
        onChoose={(e) => {
          onChoose(e);
          onClose();
        }}
      />
    </dialog>,
    document.body,
  );
}
export function ContentSelect({
  entries,
  category,
  value,
  onChange,
  label,
  empty = "Выберите объект",
  disabled = false,
}: {
  entries: Entry[];
  category?: string;
  value: string;
  onChange: (ref: string) => void;
  label: string;
  empty?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const choices = entries.filter((e) => !category || e.category === category);
  const chosen = choices.find((e) => e.ref === value);
  return (
    <>
      <button
        type="button"
        disabled={disabled}
        className="content-select"
        aria-label={label}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <span>
          <strong>{chosen?.name ?? (value || empty)}</strong>
          {chosen && <small>{chosen.ref}</small>}
        </span>
        <span aria-hidden="true">⌕</span>
      </button>
      {open && (
        <ContentPicker
          title={label}
          entries={choices}
          selected={value}
          onChoose={(e) => onChange(e.ref)}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
