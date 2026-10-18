import { sections } from "./catalog";
import { Doc, History, clone } from "./model";

export type Session = {
  key: string;
  category: string;
  ref: string;
  version: string | null;
  baseline: string;
  warnings: Doc[];
  usages: Doc[];
  history: History<Doc>;
  ui: Doc;
  saving?: boolean;
  error?: string;
};
export const documentKey = (category: string, ref: string) =>
  category + "/" + ref;
export const isDirty = (s: Session) =>
  JSON.stringify(s.history.present) !== s.baseline || !!s.ui.sourceDirty;

export class Workspace {
  tabs: Session[] = [];
  activeKey = "";
  route = "maps";
  libraries: Doc = {};
  packageState: Doc = {};
  get active() {
    return this.tabs.find((s) => s.key === this.activeKey);
  }
  open(category: string, ref: string, envelope: Doc) {
    const key = documentKey(category, ref);
    let session = this.tabs.find((s) => s.key === key);
    if (!session) {
      session = {
        key,
        category,
        ref,
        version: envelope.version,
        baseline: envelope.version ? JSON.stringify(envelope.document) : "",
        warnings: envelope.warnings ?? [],
        usages: envelope.usages ?? [],
        history: new History(clone(envelope.document)),
        ui: {},
      };
      this.tabs.push(session);
    }
    this.activeKey = key;
    return session;
  }
  close(key: string) {
    const index = this.tabs.findIndex((s) => s.key === key);
    this.tabs = this.tabs.filter((s) => s.key !== key);
    if (this.activeKey === key)
      this.activeKey = this.tabs[Math.max(0, index - 1)]?.key ?? "";
  }
  saved(session: Session, submitted: string, envelope: Doc) {
    if (JSON.stringify(session.history.present) === submitted)
      session.history.present = clone(envelope.document);
    session.version = envelope.version;
    session.baseline = JSON.stringify(envelope.document);
    session.warnings = envelope.warnings ?? [];
    session.usages = envelope.usages ?? [];
    session.error = "";
    session.ui.issues = [];
  }
  snapshot() {
    return clone({
      version: 1,
      activeKey: this.activeKey,
      route: this.route,
      libraries: this.libraries,
      packageState: this.packageState,
      tabs: this.tabs.map(({ history, saving, ...s }) => ({
        ...s,
        document: history.present,
      })),
    });
  }
  restore(raw: Doc) {
    if (raw.version !== 1 || !Array.isArray(raw.tabs))
      throw Error("Неизвестный формат рабочего места");
    const restored: Session[] = raw.tabs.map((s: Doc) => {
      if (
        !s.document ||
        typeof s.document.name !== "string" ||
        typeof s.baseline !== "string" ||
        !s.ref ||
        !sections[s.category] ||
        s.key !== documentKey(s.category, s.ref)
      )
        throw Error("Повреждённый черновик");
      const { document, ...metadata } = s;
      return {
        ...metadata,
        history: new History(document),
        ui: s.ui ?? {},
        saving: false,
      } as Session;
    });
    if (new Set(restored.map((s) => s.key)).size !== restored.length)
      throw Error("Повторные вкладки в черновике");
    this.tabs = restored;
    this.activeKey = restored.some((s) => s.key === raw.activeKey)
      ? raw.activeKey
      : (restored[0]?.key ?? "");
    this.route = raw.route ?? "maps";
    this.libraries = raw.libraries ?? {};
    this.packageState = raw.packageState ?? {};
  }
}

export function workspaceStorage() {
  const db = new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("tuidungeon-workspaces", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("projects");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  let writes: Promise<void> = Promise.resolve();
  return {
    async read(project: string): Promise<Doc | undefined> {
      const database = await db;
      return new Promise((resolve, reject) => {
        const request = database
          .transaction("projects")
          .objectStore("projects")
          .get(project);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    },
    write(project: string, value: Doc) {
      // Serialize snapshots so a slow earlier write cannot replace a newer draft.
      writes = writes
        .catch(() => {})
        .then(async () => {
          const database = await db;
          await new Promise<void>((resolve, reject) => {
            const transaction = database.transaction("projects", "readwrite");
            transaction.objectStore("projects").put(value, project);
            transaction.oncomplete = () => resolve();
            transaction.onerror = transaction.onabort = () =>
              reject(
                transaction.error ?? Error("Не удалось сохранить черновик"),
              );
          });
        });
      return writes;
    },
  };
}
