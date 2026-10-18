import { describe, it, expect } from "vitest";
import { Workspace, isDirty } from "./workspace";
const envelope = (name: string, version = "v1") => ({
  document: { id: "one", name },
  version,
});
describe("document sessions", () => {
  it("reuses tabs and keeps independent history and unapplied JSON", () => {
    const w = new Workspace(),
      a = w.open("maps", "demo:one", envelope("Map"));
    a.history.commit({ id: "one", name: "Draft" });
    a.ui = { map: { zoom: 4 }, sourceText: "{invalid", sourceDirty: true };
    const b = w.open("npcs", "demo:one", envelope("NPC"));
    b.history.commit({ id: "one", name: "Other" });
    b.history.undo();
    expect(b.history.present.name).toBe("NPC");
    expect(w.open("maps", "demo:one", envelope("external"))).toBe(a);
    expect(a.history.present.name).toBe("Draft");
    expect(isDirty(a)).toBe(true);
    const snapshot = w.snapshot();
    a.ui.map.zoom = 6;
    expect(snapshot.tabs[0].ui.map.zoom).toBe(4);
    const restored = new Workspace();
    restored.restore(snapshot);
    expect(restored.active?.ui.sourceText).toBe("{invalid");
    expect(restored.active?.history.past).toEqual([]);
    a.history.undo();
    expect(a.history.present.name).toBe("Map");
    expect(isDirty(b)).toBe(false);
  });
  it("saves the originating tab without overwriting subsequent edits", () => {
    const w = new Workspace(),
      a = w.open("maps", "demo:one", envelope("Map"));
    a.history.commit({ id: "one", name: "Submitted" });
    const submitted = JSON.stringify(a.history.present);
    const b = w.open("recipes", "demo:one", envelope("Recipe"));
    a.history.commit({ id: "one", name: "Newer" });
    w.saved(a, submitted, envelope("Submitted", "v2"));
    expect(w.active).toBe(b);
    expect(b.version).toBe("v1");
    expect(a.history.present.name).toBe("Newer");
    expect(isDirty(a)).toBe(true);
    a.history.undo();
    expect(isDirty(a)).toBe(false);
  });
  it("rejects corrupt restore data without discarding existing sessions", () => {
    const w = new Workspace(),
      a = w.open("maps", "demo:one", envelope("Map"));
    const saved = w.snapshot();
    saved.tabs.push(saved.tabs[0]);
    expect(() => w.restore(saved)).toThrow();
    expect(w.active).toBe(a);
  });
});
