import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "./api";
import { Doc, Entry, clone, compose, color, assetVersionsMatch } from "./model";
import { DocumentForm } from "./Form";
import { ContentBrowser, ContentPicker, ContentSelect } from "./ContentBrowser";
import { ArtEditor } from "./ArtEditor";
import { MapEditor } from "./MapEditor";
import { PackManager } from "./PackManager";
import { Grid } from "./Grid";
import { SymbolContext, SymbolEditor, SymbolPreview } from "./Symbols";
import {
  Workspace,
  workspaceStorage,
  isDirty,
  documentKey,
  Session,
} from "./workspace";
import { sections } from "./catalog";
import { effectText } from "./damage";
const icons = Object.fromEntries(
  Object.entries(sections).map(([key, value]) => [key, value.icon]),
);
export default function App() {
  const workspace = useRef(new Workspace()).current;
  const storage = useRef<ReturnType<typeof workspaceStorage> | null>(null);
  const [project, setProject] = useState("");
  const [observedVersions, setObservedVersions] = useState<
    Record<string, string | null>
  >({});
  const [recovery, setRecovery] = useState<Doc | null>(null);
  const [storageError, setStorageError] = useState("");
  const [persisting, setPersisting] = useState(false);
  const persistSequence = useRef(0);
  const [section, setSection] = useState("maps");
  const [screen, setScreen] = useState<"library" | "editor" | "packs">(
    "library",
  );
  const [closing, setClosing] = useState<string | null>(null);
  const [documentPage, setDocumentPage] = useState("properties");
  const [diagnostics, setDiagnostics] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [library, setLibrary] = useState<Doc | null>(null),
    [meta, setMeta] = useState<Doc | null>(null),
    [category, setCategory] = useState("maps"),
    [pack, setPack] = useState("all"),
    [revision, setRevision] = useState(0),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [assets, setAssets] = useState<Record<string, Doc>>({}),
    [creating, setCreating] = useState<Doc | null>(null),
    [launchingGame, setLaunchingGame] = useState(false);
  const [loadingDoc, setLoadingDoc] = useState(false),
    [loadingAssets, setLoadingAssets] = useState(false);
  const assetVersions = useRef<Record<string, string>>({}),
    assetSequence = useRef(0);
  const active = workspace.active ?? null;
  const history = { current: active?.history ?? null };
  const draft = active?.history.present;
  function editorValue(key: string, value: unknown) {
    if (active) {
      active.ui[key] = value;
      redraw();
    }
  }
  const gameClass = active?.ui.gameClass ?? "base:warrior",
    setGameClass = (v: string) => editorValue("gameClass", v);
  const seed = active?.ui.seed ?? 42,
    setSeed = (v: number) => editorValue("seed", v);
  const action = active?.ui.action ?? "",
    setAction = (v: string) => editorValue("action", v);
  const sandbox = active?.ui.sandbox ?? null,
    setSandbox = (v: Doc) => editorValue("sandbox", v);
  const sandboxDifficulty = active?.ui.sandboxDifficulty ?? 12,
    setSandboxDifficulty = (v: number) => editorValue("sandboxDifficulty", v);
  const sandboxTarget = active?.ui.sandboxTarget ?? "hero",
    setSandboxTarget = (v: string) => editorValue("sandboxTarget", v);
  const sandboxSpell = active?.ui.sandboxSpell ?? "",
    setSandboxSpell = (v: string) => editorValue("sandboxSpell", v);
  const source = !!active?.ui.source;
  const sourceText = active?.ui.sourceText ?? "";
  const openSequence = useRef(0);
  const jsonArea = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const node = jsonArea.current;
    if (node && active) {
      node.scrollTop = active.ui.jsonScrollTop ?? 0;
      node.setSelectionRange(
        active.ui.jsonSelectionStart ?? 0,
        active.ui.jsonSelectionEnd ?? 0,
      );
    }
  }, [active?.key, source]);
  const dirty = active ? isDirty(active) : false;
  function redraw() {
    setRevision((n) => n + 1);
  }
  function setSource(value: boolean) {
    if (active) {
      active.ui.source = value;
      redraw();
    }
  }
  function setSourceText(value: string) {
    if (active) {
      active.ui.sourceText = value;
      active.ui.sourceDirty = value !== active.ui.sourceBase;
      redraw();
    }
  }
  function openJson() {
    if (!active) return;
    if (!active.ui.sourceDirty) {
      active.ui.sourceText = JSON.stringify(draft, null, 2);
      active.ui.sourceBase = active.ui.sourceText;
    }
    setSource(true);
  }
  function navigate(route: string, replace = false) {
    ++openSequence.current;
    setLoadingDoc(false);
    workspace.route = route;
    const hash = "#/" + route;
    if (location.hash !== hash)
      window.history[replace ? "replaceState" : "pushState"](null, "", hash);
  }
  function activate(key: string, push = true) {
    const tab = workspace.tabs.find((s) => s.key === key);
    if (!tab) return;
    ++openSequence.current;
    setLoadingDoc(false);
    workspace.activeKey = key;
    setCategory(tab.category);
    setSection(
      tab.category === "maps"
        ? "maps"
        : ["symbols", "art"].includes(tab.category)
          ? "graphics"
          : "content",
    );
    setScreen("editor");
    setDocumentPage(tab.ui.documentPage ?? "properties");
    setError(tab.error ?? "");
    setRecent((old) => [key, ...old.filter((k) => k !== key)].slice(0, 12));
    if (push) navigate("edit/" + key);
    requestAnimationFrame(() =>
      document
        .querySelector<HTMLElement>(`[data-document-key="${CSS.escape(key)}"]`)
        ?.scrollIntoView({ block: "nearest", inline: "nearest" }),
    );
    redraw();
  }
  async function persist() {
    if (!project || recovery || !storage.current) return;
    const sequence = ++persistSequence.current;
    setPersisting(true);
    try {
      await storage.current.write(project, workspace.snapshot());
      if (sequence === persistSequence.current) setStorageError("");
    } catch (e) {
      setStorageError("Не удалось сохранить локальный черновик: " + String(e));
    } finally {
      if (sequence === persistSequence.current) setPersisting(false);
    }
  }
  function updateUi(session: Session, key: string, value: Doc) {
    session.ui[key] = value;
    void persist();
  }
  function page(value: string) {
    setDocumentPage(value);
    if (active) {
      active.ui.documentPage = value;
      redraw();
    }
  }
  function closeTab(key: string, discard = false) {
    const tab = workspace.tabs.find((s) => s.key === key);
    if (!tab || tab.saving) return;
    if (isDirty(tab) && !discard) {
      setClosing(key);
      return;
    }
    workspace.close(key);
    setClosing(null);
    if (workspace.active) activate(workspace.activeKey);
    else browse("maps");
    redraw();
  }
  const entries: Entry[] = library?.documents ?? [];
  const gameClasses = entries.filter((entry) => entry.category === "classes");
  const selectedGameClass = gameClasses.some((entry) => entry.ref === gameClass)
    ? gameClass
    : (gameClasses[0]?.ref ?? "");
  const notify = (s: string) => {
    setMessage(s);
    setError("");
  };
  async function refresh() {
    let next: Doc;
    try {
      next = await api("/library");
      setObservedVersions({});
    } catch (e) {
      const results = await Promise.allSettled(
        workspace.tabs
          .filter((s) => s.version)
          .map(
            async (s) =>
              [
                s.key,
                (
                  await api(
                    "/documents/" + s.category + "/" + s.ref + "/version",
                  )
                ).version,
              ] as const,
          ),
      );
      setObservedVersions(
        Object.fromEntries(
          results.flatMap((r) => (r.status === "fulfilled" ? [r.value] : [])),
        ),
      );
      throw e;
    }
    setLibrary((previous) =>
      JSON.stringify(previous) === JSON.stringify(next) ? previous : next,
    );
    if (!assetVersionsMatch(next.documents, assetVersions.current))
      await loadAssets();
    return next;
  }
  async function loadAssets() {
    const sequence = ++assetSequence.current;
    const initial = !Object.keys(assetVersions.current).length;
    if (initial) setLoadingAssets(true);
    try {
      const result = await api("/assets");
      if (sequence !== assetSequence.current) return;
      const previousVersions = assetVersions.current;
      setAssets((previous) =>
        Object.fromEntries(
          Object.entries(result.documents as Record<string, Doc>).map(
            ([key, doc]) => [
              key,
              previousVersions[key] === result.versions[key] && previous[key]
                ? previous[key]
                : doc,
            ],
          ),
        ),
      );
      assetVersions.current = result.versions;
    } finally {
      if (initial && sequence === assetSequence.current)
        setLoadingAssets(false);
    }
  }
  async function open(c: string, ref: string, reload = false) {
    const key = documentKey(c, ref);
    if (!reload && workspace.tabs.some((s) => s.key === key)) {
      ++openSequence.current;
      activate(key);
      return;
    }
    const sequence = ++openSequence.current;
    setLoadingDoc(true);
    try {
      const envelope = await api("/documents/" + c + "/" + ref);
      if (reload) {
        const old = workspace.tabs.find((s) => s.key === key);
        if (
          old &&
          isDirty(old) &&
          !window.confirm("Заменить локальный черновик версией с диска?")
        )
          return;
        workspace.close(key);
      }
      const previousKey = workspace.activeKey;
      workspace.open(c, ref, envelope);
      if (sequence === openSequence.current) activate(key);
      else workspace.activeKey = previousKey;
      notify("Документ открыт");
      redraw();
    } catch (e) {
      setError(String(e));
    } finally {
      if (sequence === openSequence.current) setLoadingDoc(false);
    }
  }
  useEffect(() => {
    if (!project || recovery) return;
    void persist();
  }, [revision, project, recovery, screen]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (
        (persisting || storageError) &&
        (workspace.tabs.some(isDirty) || workspace.packageState.dirty)
      ) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [persisting, storageError]);
  useEffect(() => {
    if (!closing && !recovery) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>(
      '.modal-backdrop [role="dialog"]',
    );
    dialog?.querySelector<HTMLButtonElement>("button")?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closing) {
        e.preventDefault();
        setClosing(null);
      }
      if (e.key !== "Tab" || !dialog) return;
      const controls = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),[tabindex="0"]',
        ),
      );
      if (!controls.length) return;
      const i = controls.indexOf(document.activeElement as HTMLElement);
      if (
        i < 0 ||
        (!e.shiftKey && i === controls.length - 1) ||
        (e.shiftKey && i === 0)
      ) {
        e.preventDefault();
        controls[e.shiftKey ? controls.length - 1 : 0].focus();
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("keydown", handle);
      if (previous?.isConnected) previous.focus();
    };
  }, [closing, !!recovery]);
  function followRoute(force = false) {
    const route = location.hash.slice(2);
    if (route === workspace.route) return;
    workspace.route = route;
    if (route.startsWith("edit/")) {
      const key = decodeURIComponent(route.slice(5));
      if (workspace.tabs.some((s) => s.key === key)) activate(key, false);
      else {
        const at = key.indexOf("/");
        if (at > 0) void open(key.slice(0, at), key.slice(at + 1));
      }
    } else {
      const [area, cat] = route.split("/");
      if (area === "packs") {
        setSection("packs");
        setScreen("packs");
      } else {
        setSection(
          area === "graphics"
            ? "graphics"
            : area === "content"
              ? "content"
              : "maps",
        );
        setCategory(
          cat ||
            (area === "graphics"
              ? "symbols"
              : area === "content"
                ? "equipment"
                : "maps"),
        );
        setScreen("library");
      }
      workspace.route = route || "maps";
      redraw();
    }
  }
  useEffect(() => {
    const follow = () => followRoute();
    window.addEventListener("popstate", follow);
    window.addEventListener("hashchange", follow);
    return () => {
      window.removeEventListener("popstate", follow);
      window.removeEventListener("hashchange", follow);
    };
  }, []);
  useEffect(() => {
    void (async () => {
      const [lib, schemas, status] = await Promise.allSettled([
        api("/library"),
        api("/schemas"),
        api("/status"),
      ]);
      if (schemas.status === "fulfilled") setMeta(schemas.value);
      if (lib.status === "fulfilled") setLibrary(lib.value);
      else setError(String(lib.reason));
      try {
        await loadAssets();
      } catch (e) {
        setError(String(e));
      }
      if (status.status !== "fulfilled") {
        setError(String(status.reason));
        return;
      }
      let saved: Doc | undefined;
      try {
        storage.current = workspaceStorage();
        saved = await storage.current.read(status.value.packs_dir);
      } catch (e) {
        setStorageError("Локальное восстановление недоступно: " + String(e));
      }
      const hasRecovery = !!(
        saved &&
        (saved.tabs?.length || saved.packageState?.dirty)
      );
      if (hasRecovery) setRecovery(saved!);
      if (lib.status !== "fulfilled") {
        // Keep saved documents accessible while an external edit breaks pack references.
        setLibrary({
          packs: [],
          categories: Object.fromEntries(
            Object.entries(sections).map(([key, value]) => [key, value.name]),
          ),
          documents: (saved?.tabs ?? []).map((s: Doc) => ({
            category: s.category,
            ref: s.ref,
            name: s.document.name,
            version: s.version,
          })),
        });
      }
      setProject(status.value.packs_dir);
      if (!hasRecovery) followRoute(true);
    })().catch((e) => setError(String(e)));
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
    if (active) {
      active.error = "";
      active.ui.issues = [];
    }
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
      if (e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      } else if (
        screen !== "editor" ||
        closing ||
        recovery ||
        creating ||
        searchOpen
      ) {
        return;
      } else if (e.key.toLowerCase() === "s") {
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
  async function save(session = workspace.active): Promise<boolean> {
    if (!session || session.saving) return false;
    if (session.ui.sourceDirty) {
      session.error = "Сначала примените изменения JSON.";
      if (workspace.active === session) setError(session.error);
      redraw();
      return false;
    }
    session.saving = true;
    redraw();
    const submitted = JSON.stringify(session.history.present);
    try {
      const envelope = await api(
        "/documents/" + session.category + "/" + session.ref,
        { document: JSON.parse(submitted), version: session.version },
        "PUT",
      );
      workspace.saved(session, submitted, envelope);
      await refresh();
      if (workspace.active === session) notify("Сохранено: " + session.ref);
      else setMessage("Сохранено: " + session.ref);
      return true;
    } catch (e) {
      recordError(session, e);
      return false;
    } finally {
      session.saving = false;
      redraw();
    }
  }
  async function launchGame() {
    if (
      !active ||
      active.category !== "maps" ||
      !active.version ||
      dirty ||
      launchingGame ||
      !selectedGameClass
    )
      return;
    setLaunchingGame(true);
    try {
      await api("/game", {
        map_ref: active.ref,
        character_class: selectedGameClass,
        seed,
      });
      notify("Карта запущена в игровом окне: " + active.ref);
    } catch (e) {
      setError(String(e));
    } finally {
      setLaunchingGame(false);
    }
  }
  async function validate() {
    const target = workspace.active;
    if (!target) return;
    try {
      await api("/validate/" + target.category + "/" + target.ref, {
        document: target.history.present,
      });
      target.error = "";
      target.ui.issues = [];
      if (workspace.active === target)
        notify("Структура, параметры и ссылки корректны");
    } catch (e) {
      recordError(target, e);
    } finally {
      redraw();
    }
  }
  function recordError(target: Session, e: unknown) {
    target.error = String(e);
    try {
      const detail = JSON.parse(String(e).replace(/^Error: /, ""));
      target.ui.issues = Array.isArray(detail)
        ? detail.map((v) => ({
            message: v.msg ?? v.message,
            field:
              v.path ??
              (v.loc ?? []).filter((k: string) => k !== "document").join("."),
          }))
        : [];
    } catch {
      target.ui.issues = [];
    }
    if (workspace.active === target) setError(target.error);
  }
  function showIssue(issue: Doc) {
    if (!active) return;
    activate(active.key);
    active.ui.diagnostic = { ...issue, token: Date.now() };
    setSource(false);
    page("properties");
    setDiagnostics(false);
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
      workspace.close(active.key);
      if (workspace.active) activate(workspace.activeKey);
      else browse(category);
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
      entries.some((e) => e.category === creating.category && e.ref === ref) ||
      workspace.tabs.some((s) => s.key === documentKey(creating.category, ref))
    ) {
      setError("Идентификатор уже занят");
      return;
    }
    ++openSequence.current;
    setLoadingDoc(false);
    workspace.open(creating.category, ref, {
      document: clone(creating.raw),
      version: null,
      warnings: [],
      usages: [],
    });
    activate(documentKey(creating.category, ref));
    setCreating(null);
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
  const diskVersion =
    active && active.key in observedVersions
      ? observedVersions[active.key]
      : entries.find(
          (e) => e.category === active?.category && e.ref === active?.ref,
        )?.version;
  const external = active?.version && diskVersion !== active.version;
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
  function browse(c: string) {
    const area =
      c === "maps"
        ? "maps"
        : ["symbols", "art"].includes(c)
          ? "graphics"
          : "content";
    setCategory(c);
    setSection(area);
    setScreen("library");
    navigate(area + "/" + c);
    redraw();
  }
  return (
    <SymbolContext.Provider
      value={{
        assets,
        entries,
        packs: (library?.packs ?? []).map((p: Doc) => p.id),
        refresh,
        open: (c, r) => void open(c, r),
      }}
    >
      <div className="app studio-shell workspace-shell">
        <header className="app-header">
          <div className="brand">
            <span className="brand-mark">▚</span>
            <strong>DUNGEON STUDIO</strong>
          </div>
          <nav className="primary-navigation" aria-label="Мастерская">
            {[
              ["maps", "Карты"],
              ["content", "Контент"],
              ["graphics", "Графика"],
              ["packs", "Пакеты"],
            ].map(([id, label]) => (
              <button
                key={id}
                aria-current={section === id ? "page" : undefined}
                className={section === id ? "selected" : ""}
                onClick={() => {
                  if (id === "packs") {
                    setSection(id);
                    setScreen("packs");
                    navigate("packs");
                    redraw();
                  } else
                    browse(
                      id === "maps"
                        ? "maps"
                        : id === "graphics"
                          ? "symbols"
                          : "equipment",
                    );
                }}
              >
                {label}
              </button>
            ))}
          </nav>
          <button
            className="global-search-button"
            onClick={() => setSearchOpen(true)}
          >
            ⌕ Поиск по проекту <kbd>Ctrl K</kbd>
          </button>
        </header>
        <div
          className="document-tabs workspace-tabs"
          role="tablist"
          aria-label="Открытые документы"
          onKeyDown={(e) => {
            if (e.key === "Delete") {
              const key = (e.target as HTMLElement).closest<HTMLElement>(
                "[data-document-key]",
              )?.dataset.documentKey;
              if (key) {
                e.preventDefault();
                closeTab(key);
              }
              return;
            }
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key))
              return;
            const tabs = Array.from(
              e.currentTarget.querySelectorAll<HTMLButtonElement>(
                '[role="tab"]',
              ),
            );
            const i = tabs.indexOf(document.activeElement as HTMLButtonElement);
            const next =
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? tabs.length - 1
                  : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) %
                    tabs.length;
            tabs[next]?.focus();
            tabs[next]?.click();
            e.preventDefault();
          }}
        >
          {workspace.tabs.length ? (
            workspace.tabs.map((tab) => (
              <div
                className={
                  "document-tab " +
                  (screen === "editor" && active?.key === tab.key
                    ? "selected"
                    : "")
                }
                key={tab.key}
              >
                <button
                  tabIndex={active?.key === tab.key ? 0 : -1}
                  aria-controls="document-panel"
                  data-document-key={tab.key}
                  role="tab"
                  aria-selected={screen === "editor" && active?.key === tab.key}
                  title={tab.ref + " · " + sections[tab.category]?.name}
                  onClick={() => activate(tab.key)}
                >
                  {icons[tab.category]} {tab.history.present.name}{" "}
                  {isDirty(tab) ? "●" : ""}
                  {tab.saving ? " …" : ""}
                </button>
                <button
                  disabled={!!tab.saving}
                  tabIndex={-1}
                  aria-label={"Закрыть вкладку: " + tab.history.present.name}
                  onClick={() => closeTab(tab.key)}
                >
                  ×
                </button>
              </div>
            ))
          ) : (
            <span className="hint">
              Откройте карту или объект — документы появятся здесь
            </span>
          )}
        </div>
        <main
          id="document-panel"
          className="main"
          aria-busy={loadingDoc || loadingAssets}
        >
          {!active && (loadingDoc || loadingAssets) && (
            <div className="loading-overlay">
              <span className="status-dot" />
              {loadingDoc ? "Открытие документа…" : "Обновление библиотеки…"}
            </div>
          )}
          {error && (
            <div className="banner error" role="alert">
              {error}
              <button className="mini" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          {storageError && (
            <div className="banner warning" role="alert">
              {storageError}. Сохраните изменения в пакеты перед закрытием
              студии.
            </div>
          )}
          {screen === "packs" && library ? (
            <PackManager
              inline
              packs={library.packs}
              entries={entries}
              initialPack={pack === "all" ? undefined : pack}
              unsavedPacks={workspace.tabs
                .filter(isDirty)
                .flatMap((t) => [
                  t.ref.split(":")[0],
                  ...Array.from(
                    (
                      JSON.stringify(t.history.present) +
                      " " +
                      (t.ui.sourceText ?? "")
                    ).matchAll(/"([a-z][a-z0-9_]*):[a-z0-9_]+/g),
                    (m) => m[1],
                  ),
                ])}
              state={workspace.packageState}
              onStateChange={(value) => {
                workspace.packageState = value;
                void persist();
              }}
              onClose={() => browse("maps")}
              onChanged={async (id, deleted) => {
                if (deleted) {
                  for (const tab of [...workspace.tabs])
                    if (tab.ref.startsWith(id + ":")) workspace.close(tab.key);
                  redraw();
                }
                await refresh();
                notify(deleted ? "Пакет перемещён в архив" : "Пакет сохранён");
              }}
            />
          ) : screen === "library" ? (
            <section className="library library-page">
              <div className="library-heading">
                <span className="eyebrow">БИБЛИОТЕКА</span>
                <h1>{sections[category]?.name ?? "Загрузка…"}</h1>
                <p className="category-description">
                  {sections[category]?.description}
                </p>
                <button
                  className="primary"
                  disabled={!meta}
                  onClick={() => beginCreate()}
                >
                  + Создать
                </button>
              </div>
              {section !== "maps" && (
                <nav
                  className="content-categories"
                  aria-label="Категории контента"
                >
                  {["Мир", "Объекты", "Правила", "Персонаж"].map((family) => (
                    <div key={family}>
                      {Object.entries(sections)
                        .filter(
                          ([id, v]) =>
                            v.family === family &&
                            (section === "graphics"
                              ? ["symbols", "art"].includes(id)
                              : !["symbols", "art", "maps"].includes(id)),
                        )
                        .map(([id, v]) => (
                          <button
                            key={id}
                            className={category === id ? "selected" : ""}
                            onClick={() => browse(id)}
                          >
                            {v.icon} {v.name}
                          </button>
                        ))}
                    </div>
                  ))}
                </nav>
              )}
              {section === "maps" && recent.length > 0 && (
                <div className="recent-documents">
                  <strong>Недавние</strong>
                  {recent.map((key) => {
                    const entry = entries.find(
                      (e) => documentKey(e.category, e.ref) === key,
                    );
                    return entry?.category === "maps" ? (
                      <button
                        key={key}
                        onClick={() => void open(entry.category, entry.ref)}
                      >
                        {entry.name}
                      </button>
                    ) : null;
                  })}
                </div>
              )}
              <ContentBrowser
                key={category}
                state={workspace.libraries[category]}
                onStateChange={(value) => {
                  workspace.libraries[category] = value;
                  void persist();
                }}
                entries={entries.filter((e) =>
                  section === "maps"
                    ? e.category === "maps"
                    : section === "graphics"
                      ? ["symbols", "art"].includes(e.category)
                      : !["maps", "symbols", "art"].includes(e.category),
                )}
                assets={assets}
                category={category}
                selected={
                  active ? active.category + "/" + active.ref : undefined
                }
                onChoose={(e) => void open(e.category, e.ref)}
              />
            </section>
          ) : (
            <>
              <div className="document-heading">
                <div>
                  <span className="eyebrow">
                    {active
                      ? sections[active.category]?.name
                      : "ВЫБЕРИТЕ ДОКУМЕНТ"}
                  </span>
                  <h1>
                    {draft &&
                    active &&
                    ["art", "maps"].includes(active.category) ? (
                      <input
                        aria-label="Название документа"
                        className="document-name"
                        size={Math.min(40, Math.max(12, draft.name.length))}
                        value={draft.name}
                        onChange={(e) =>
                          change({ ...draft, name: e.target.value })
                        }
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
                      disabled={!!active.saving}
                      onClick={() => void save()}
                    >
                      {active.saving ? "Сохранение…" : "Сохранить"}
                    </button>
                  </div>
                )}
              </div>
              {external && (
                <div className="banner warning">
                  {diskVersion == null
                    ? "Файл удалён вне студии."
                    : "Файл изменён вне студии."}{" "}
                  Ваш черновик сохранён в редакторе.
                  <button
                    onClick={() => {
                      if (active) void open(active.category, active.ref, true);
                    }}
                  >
                    Перечитать
                  </button>
                </div>
              )}
              {draft && active && meta ? (
                <>
                  <div className="editor-tabs">
                    <button
                      className={
                        !source && documentPage === "properties"
                          ? "selected"
                          : ""
                      }
                      onClick={() => {
                        setSource(false);
                        page("properties");
                      }}
                    >
                      Редактор
                    </button>
                    {!["maps", "symbols", "art"].includes(active.category) && (
                      <>
                        <button
                          className={
                            !source && documentPage === "preview"
                              ? "selected"
                              : ""
                          }
                          onClick={() => {
                            setSource(false);
                            page("preview");
                          }}
                        >
                          Предпросмотр
                        </button>
                        <button
                          className={
                            !source && documentPage === "links"
                              ? "selected"
                              : ""
                          }
                          onClick={() => {
                            setSource(false);
                            page("links");
                          }}
                        >
                          Связи
                        </button>
                        {active.category === "monsters" && (
                          <button
                            className={
                              !source && documentPage === "test"
                                ? "selected"
                                : ""
                            }
                            onClick={() => {
                              setSource(false);
                              page("test");
                            }}
                          >
                            Проверка
                          </button>
                        )}
                      </>
                    )}
                    <details className="more-menu">
                      <summary>Дополнительно</summary>
                      <div>
                        <button onClick={openJson}>JSON</button>
                        <button onClick={() => beginCreate(true)}>
                          Дублировать
                        </button>
                        <button onClick={download}>Экспорт JSON</button>
                        <button
                          disabled={!active.version || active.usages.length > 0}
                          onClick={() => void remove()}
                        >
                          Удалить
                        </button>
                      </div>
                    </details>
                    {active.category === "maps" && (
                      <>
                        <details className="launch-options">
                          <summary>Параметры теста</summary>
                          <ContentSelect
                            entries={gameClasses}
                            value={selectedGameClass}
                            onChange={setGameClass}
                            label="Класс для запуска игры"
                          />
                          <label>
                            Seed{" "}
                            <input
                              type="number"
                              value={seed}
                              onChange={(e) => setSeed(Number(e.target.value))}
                            />
                          </label>
                        </details>
                        <button
                          className="test-button"
                          disabled={
                            !active.version ||
                            !!dirty ||
                            !!active.saving ||
                            launchingGame ||
                            !selectedGameClass
                          }
                          onClick={() => void launchGame()}
                        >
                          ▶ Запустить
                        </button>
                      </>
                    )}
                  </div>
                  {source ? (
                    <div className="source-editor">
                      <textarea
                        ref={jsonArea}
                        onScroll={(e) => {
                          active.ui.jsonScrollTop = e.currentTarget.scrollTop;
                          void persist();
                        }}
                        onSelect={(e) => {
                          active.ui.jsonSelectionStart =
                            e.currentTarget.selectionStart;
                          active.ui.jsonSelectionEnd =
                            e.currentTarget.selectionEnd;
                        }}
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
                            active.ui.sourceDirty = false;
                            active.ui.sourceBase = sourceText;
                            setSource(false);
                          } catch (e) {
                            setError(String(e));
                          }
                        }}
                      >
                        Применить JSON
                      </button>
                    </div>
                  ) : active.category === "symbols" ? (
                    <SymbolEditor
                      key={active.key}
                      viewState={active.ui.symbol ?? {}}
                      onViewState={(value) => updateUi(active, "symbol", value)}
                      usages={active.usages}
                      doc={draft}
                      onChange={change}
                      onUndo={undo}
                      onRedo={redo}
                      notify={notify}
                    />
                  ) : active.category === "art" ? (
                    <ArtEditor
                      packId={active.ref.split(":")[0]}
                      key={active.key}
                      doc={draft}
                      onChange={change}
                      notify={notify}
                    />
                  ) : active.category === "maps" ? (
                    <MapEditor
                      key={active.key}
                      doc={draft}
                      onChange={change}
                      entries={entries}
                      assets={assets}
                      schemas={meta.schemas}
                      mechanics={meta.mechanics}
                      warnings={active.warnings}
                      notify={notify}
                      shortcutsEnabled={
                        !creating &&
                        !closing &&
                        !recovery &&
                        !source &&
                        !searchOpen
                      }
                      documentRef={active.ref}
                      diagnostic={active.ui.diagnostic}
                      viewState={active.ui.map ?? {}}
                      onViewState={(value) => updateUi(active, "map", value)}
                      onOpenDocument={(c, r) => void open(c, r)}
                    />
                  ) : (
                    <div className="mechanics-layout">
                      {documentPage === "properties" && (
                        <div className="mechanics-form">
                          <DocumentForm
                            key={active.key}
                            category={active.category}
                            schema={meta.schemas[active.category]}
                            root={meta.schemas[active.category]}
                            value={draft}
                            onChange={change}
                            entries={entries}
                            mechanics={meta.mechanics}
                            lockedId={true}
                            diagnostic={active.ui.diagnostic}
                            viewState={active.ui.form ?? {}}
                            onViewState={(value) =>
                              updateUi(active, "form", value)
                            }
                          />
                        </div>
                      )}
                      {documentPage !== "properties" && (
                        <aside className="inspector document-detail-page">
                          {documentPage === "preview" && (
                            <>
                              <span className="eyebrow">ПРЕДПРОСМОТР</span>
                              <div className="portrait">
                                {art ? (
                                  <Grid
                                    cells={compose(art)}
                                    zoom={1.5}
                                    grid={false}
                                  />
                                ) : draft.symbol ? (
                                  <SymbolPreview
                                    mirror_x={!!draft.mirror_x}
                                    symbol={draft.symbol}
                                    size={64}
                                    tint={color(draft.foreground ?? 7)}
                                  />
                                ) : (
                                  <span
                                    style={{
                                      color: color(draft.foreground ?? 7),
                                    }}
                                  >
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
                                    КД
                                    <strong>{draft.armor_class ?? "—"}</strong>
                                  </span>
                                  <span>
                                    Скорость
                                    <strong>{draft.speed ?? "—"}</strong>
                                  </span>
                                  <span>
                                    Инициатива
                                    <strong>
                                      {draft.initiative_bonus ?? "—"}
                                    </strong>
                                  </span>
                                </div>
                              )}
                            </>
                          )}
                          {documentPage === "test" &&
                            active.category === "monsters" && (
                              <section className="sandbox">
                                <h3>Песочница действий</h3>
                                <p className="hint">
                                  Монстр действует против тестового воина. Для
                                  проверки сначала сохраните шаблон.
                                </p>
                                <select
                                  aria-label="Действие монстра"
                                  value={
                                    availableActions.some(
                                      (a) => a.id === action,
                                    )
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
                                    onChange={(e) =>
                                      setSeed(Number(e.target.value))
                                    }
                                  />
                                </label>
                                <label>
                                  Сложность{" "}
                                  <input
                                    type="number"
                                    min="0"
                                    value={sandboxDifficulty}
                                    onChange={(e) =>
                                      setSandboxDifficulty(
                                        Number(e.target.value),
                                      )
                                    }
                                  />
                                </label>
                                <select
                                  aria-label="Цель песочницы"
                                  value={sandboxTarget}
                                  onChange={(e) =>
                                    setSandboxTarget(e.target.value)
                                  }
                                >
                                  <option value="hero">Тестовый герой</option>
                                  <option value="self">Сам монстр</option>
                                </select>
                                {draft.spells.length > 0 && (
                                  <ContentSelect
                                    entries={entries.filter(
                                      (e) =>
                                        e.category === "spells" &&
                                        draft.spells.includes(e.ref),
                                    )}
                                    value={sandboxSpell}
                                    onChange={setSandboxSpell}
                                    label="Заклинание песочницы"
                                    empty="Выберите заклинание"
                                  />
                                )}
                                <button
                                  disabled={
                                    !!dirty ||
                                    !active.version ||
                                    !availableActions.length
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
                                      recordError(active, e);
                                      redraw();
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
                                      HP цели: {sandbox.target.hp}/
                                      {sandbox.target.max_hp}
                                    </p>
                                    <p>
                                      Состояния монстра:{" "}
                                      {Object.keys(
                                        sandbox.actor.conditions,
                                      ).join(", ") || "нет"}
                                    </p>
                                    <p>
                                      Ячейки:{" "}
                                      {Object.entries(sandbox.actor.spell_slots)
                                        .map(
                                          ([level, count]) =>
                                            `${level}: ${count}`,
                                        )
                                        .join(", ") || "нет"}
                                    </p>
                                    {sandbox.effects.map(
                                      (e: Doc, i: number) => (
                                        <p key={i}>{effectText(e)}</p>
                                      ),
                                    )}
                                  </div>
                                )}
                              </section>
                            )}
                          {documentPage === "links" && (
                            <>
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
                                  Другие объекты пока не ссылаются на этот
                                  шаблон.
                                </p>
                              )}
                            </>
                          )}
                        </aside>
                      )}
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
                    Нарисуйте символы, задайте правила и соедините их в
                    подземелье.
                  </p>
                </div>
              )}
            </>
          )}
        </main>
        <div className="statusbar">
          <span className="status-dot" />
          {message || "Готово"}
          <button
            aria-expanded={diagnostics}
            onClick={() => setDiagnostics(!diagnostics)}
          >
            Ошибки и предупреждения:{" "}
            {(active?.ui.issues?.length || (error ? 1 : 0)) +
              (active?.warnings.length ?? 0)}
          </button>
          <span role="status">
            {storageError ||
              (persisting
                ? "Сохраняем локальный черновик…"
                : "Черновик сохранён локально")}
          </span>
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
        {diagnostics && (
          <section
            className="diagnostics-panel"
            aria-label="Ошибки и предупреждения"
          >
            <button onClick={() => setDiagnostics(false)}>Закрыть</button>
            {error && <p role="alert">{error}</p>}
            {[...(active?.ui.issues ?? []), ...(active?.warnings ?? [])].map(
              (w, i) => (
                <button key={i} onClick={() => showIssue(w)}>
                  {w.message} {w.field ?? w.path}
                </button>
              ),
            )}
          </section>
        )}
        {closing && (
          <div className="modal-backdrop">
            <div
              className="modal"
              aria-modal="true"
              role="dialog"
              aria-label="Закрыть изменённый документ"
            >
              <h2>Сохранить изменения?</h2>
              <p>
                {
                  workspace.tabs.find((t) => t.key === closing)?.history.present
                    .name
                }
              </p>
              {workspace.tabs.find((t) => t.key === closing)?.ui
                .sourceDirty && (
                <p className="warning">
                  В JSON есть неприменённый текст. Отмените закрытие и примените
                  JSON перед сохранением.
                </p>
              )}
              {workspace.tabs.find((t) => t.key === closing)?.error && (
                <p role="alert">
                  {workspace.tabs.find((t) => t.key === closing)?.error}
                </p>
              )}
              <div className="toolbar">
                <button onClick={() => setClosing(null)}>Отмена</button>
                <button onClick={() => closeTab(closing, true)}>
                  Закрыть без сохранения
                </button>
                <button
                  className="primary"
                  onClick={async () => {
                    const tab = workspace.tabs.find((t) => t.key === closing);
                    if (tab && (await save(tab))) {
                      if (!isDirty(tab)) closeTab(tab.key, true);
                      else setError("В документе появились новые изменения.");
                    }
                  }}
                >
                  Сохранить
                </button>
              </div>
            </div>
          </div>
        )}
        {recovery && (
          <div className="modal-backdrop">
            <div
              className="modal"
              aria-modal="true"
              role="dialog"
              aria-label="Восстановление рабочего места"
            >
              <h2>Восстановить рабочее место?</h2>
              <p>
                Открытых документов: {recovery.tabs?.length ?? 0}. Файлы пакетов
                не будут изменены.
              </p>
              <ul>
                {recovery.tabs?.map((t: Doc) => (
                  <li key={t.key}>
                    {t.document?.name}{" "}
                    {JSON.stringify(t.document) !== t.baseline ||
                    t.ui?.sourceDirty
                      ? "●"
                      : ""}
                  </li>
                ))}
              </ul>
              <div className="toolbar">
                <button
                  onClick={() => {
                    setRecovery(null);
                    followRoute(true);
                    redraw();
                  }}
                >
                  Не восстанавливать
                </button>
                <button
                  className="primary"
                  onClick={() => {
                    try {
                      workspace.restore(recovery);
                      setRecent(workspace.tabs.map((t) => t.key));
                      setRecovery(null);
                      if (
                        workspace.route.startsWith("edit/") &&
                        workspace.active
                      )
                        activate(workspace.activeKey);
                      else if (workspace.route === "packs") {
                        setScreen("packs");
                        setSection("packs");
                      } else browse(workspace.route.split("/")[1] || "maps");
                      redraw();
                    } catch (e) {
                      setStorageError(String(e));
                    }
                  }}
                >
                  Восстановить
                </button>
              </div>
            </div>
          </div>
        )}
        {searchOpen && (
          <ContentPicker
            entries={entries}
            onChoose={(e) => void open(e.category, e.ref)}
            onClose={() => setSearchOpen(false)}
          />
        )}
        <span hidden>{revision}</span>
      </div>
    </SymbolContext.Provider>
  );
}
