import { describe, it, expect } from "vitest";
import {
  History,
  compose,
  flood,
  line,
  rectangle,
  resizeArt,
  resizeMap,
  mapGrid,
  matchesEntry,
  clone,
  mergeProperties,
  diffProperties,
  instanceDocument,
} from "./model";
describe("instance properties", () => {
  const door = {
    glyph: "+",
    foreground: 130,
    background: null,
    brush: {
      door: {
        material: "wood",
        state: "closed",
        locked: false,
        lock_quality: "normal",
        lock_complexity: "simple",
      },
    },
  };
  it("stores only local changes, inherits nested defaults and supports undo/redo", () => {
    const changed = mergeProperties(door, {
      brush: { door: { locked: true } },
    });
    const overrides = diffProperties(door, changed);
    expect(overrides).toEqual({ brush: { door: { locked: true } } });
    const h = new History({ id: "door", overrides: {} });
    h.commit({ id: "door", overrides });
    expect(instanceDocument(door, h.present).glyph).toBe("X");
    h.undo();
    expect(instanceDocument(door, h.present).glyph).toBe("+");
    h.redo();
    expect(instanceDocument(door, h.present).glyph).toBe("X");
    expect(door.brush.door.locked).toBe(false);
    expect(diffProperties(door, clone(door))).toEqual({});
  });
  it("replaces arrays and explicit null while retaining unrelated properties", () => {
    const base = {
      name: "Шипы",
      failure: [{ kind: "damage", amount: 2 }],
      art: "base:spikes",
    };
    const patch = { failure: [], art: null };
    expect(mergeProperties(base, patch)).toEqual({ name: "Шипы", ...patch });
    expect(diffProperties(base, mergeProperties(base, patch))).toEqual(patch);
  });
  it("renders local glyphs and canonical door state rather than shared templates", () => {
    const doc = {
      width: 4,
      height: 2,
      tiles: [
        [null, null, null, null],
        [null, null, null, null],
      ],
      spawn: { x: 0, y: 0 },
      doors: [
        {
          id: "d",
          ref: "base:door_wood",
          x: 1,
          y: 0,
          overrides: { brush: { door: { state: "open" } } },
        },
      ],
      equipment: [
        { id: "i", ref: "base:tool", x: 2, y: 0, overrides: { glyph: "!" } },
      ],
    };
    const result = mapGrid(doc, {
      "objects/base:door_wood": door,
      "equipment/base:tool": { glyph: "?", foreground: 7, background: null },
    });
    expect(result[0][1]?.char).toBe("/");
    expect(result[0][2]?.char).toBe("!");
  });
});
const cell = (char: string, bg: number | null = null) => ({
  char,
  foreground: 7,
  background: bg,
});
describe("content search", () => {
  const tile = {
    category: "tiles",
    ref: "base:door_grate",
    id: "door_grate",
    name: "Решётчатая дверь",
    version: "v1",
    glyph: "╫",
    group: "Двери и проходы",
    tags: ["doors", "obstacle", "transparent"],
  };
  it("combines words across Russian names, groups and technical tags", () => {
    expect(matchesEntry(tile, "  ДВЕРИ transparent  ")).toBe(true);
    expect(matchesEntry(tile, "╫ base:door_grate")).toBe(true);
    expect(matchesEntry(tile, "дверь opaque")).toBe(false);
    expect(matchesEntry(tile, "")).toBe(true);
  });
  it("searches material traits by Russian labels and stable tag IDs", () => {
    const wood = { ...tile, tags: ["wooden", "flammable"] };
    for (const query of ["горючий", "деревянный", "flammable", "wooden"])
      expect(matchesEntry(wood, query)).toBe(true);
    expect(matchesEntry(tile, "горючий")).toBe(false);
  });
  it("keeps old documents searchable without tile metadata", () => {
    expect(
      matchesEntry(
        {
          category: "tiles",
          ref: "base:wall",
          id: "wall",
          name: "Каменная стена",
          version: "v1",
        },
        "СТЕНА",
      ),
    ).toBe(true);
  });
});
describe("document editing", () => {
  it("renders stone as an immovable slab regardless of stale lock settings", () => {
    const base = {
      glyph: "+",
      brush: { door: { material: "stone", state: "open", locked: true } },
    };
    const slab = instanceDocument(base, { overrides: {} });
    expect(slab.glyph).toBe("#");
    expect(slab.walkable).toBe(false);
    expect(slab.blocks_sight).toBe(true);
    expect(slab.brush.door.locked).toBe(false);
    expect(slab.brush.door.state).toBe("closed");
    expect(base.brush.door.state).toBe("open");
  });
  it("undo/redo returns entire layered documents and clears redo on a branch", () => {
    const h = new History({ layers: [{ cells: [[null]] }] });
    h.commit({ layers: [{ cells: [[cell("█")]] }] } as any);
    h.undo();
    expect(h.present.layers[0].cells[0][0]).toBeNull();
    h.redo();
    expect((h.present.layers[0].cells[0][0] as any).char).toBe("█");
    h.undo();
    h.commit({ layers: [{ cells: [[cell("░")]] }] } as any);
    expect(h.future).toHaveLength(0);
  });
  it("composes hidden layers and independently transparent backgrounds", () => {
    const doc = {
      width: 2,
      height: 1,
      layers: [
        { visible: true, cells: [[cell("a", 4), cell("b")]] },
        { visible: true, cells: [[cell("█"), null]] },
        { visible: false, cells: [[cell("x"), cell("x")]] },
      ],
    };
    expect(compose(doc)).toEqual([[cell("█", 4), cell("b")]]);
  });
  it("flood fills only a connected region", () => {
    expect(
      flood(
        [
          [0, 1, 0],
          [0, 1, 0],
        ],
        { x: 0, y: 0 },
        (a, b) => a === b,
      ),
    ).toHaveLength(2);
  });
  it("rasterizes cardinal and diagonal lines and rectangles", () => {
    expect(line({ x: 0, y: 0 }, { x: 2, y: 2 })).toEqual([
      { x: 0, y: 0 },
      { x: 1, y: 1 },
      { x: 2, y: 2 },
    ]);
    expect(rectangle({ x: 0, y: 0 }, { x: 2, y: 2 })).toHaveLength(8);
    expect(rectangle({ x: 0, y: 0 }, { x: 2, y: 2 }, true)).toHaveLength(9);
  });
  it("resizes art preserving cells and layer metadata", () => {
    const doc = {
      width: 1,
      height: 1,
      layers: [{ id: "a", locked: true, cells: [[cell("a")]] }],
    };
    const n = resizeArt(doc, 2, 2);
    expect(n.layers[0].cells).toEqual([
      [cell("a"), null],
      [null, null],
    ]);
    expect(n.layers[0].locked).toBe(true);
    expect(doc.width).toBe(1);
  });
  it("resizes map masks and clips placements without changing original", () => {
    const d: any = {
      width: 2,
      height: 2,
      tiles: [
        [null, null],
        [null, null],
      ],
      walkability: [
        [true, false],
        [true, true],
      ],
      blocks_sight: [
        [false, true],
        [false, false],
      ],
      spawn: { x: 1, y: 1 },
      decorations: [],
      traps: [{ id: "a", x: 1, y: 1 }],
      points_of_interest: [],
      monsters: [],
      equipment: [],
      transitions: [],
      lights: [
        { id: "lamp", x: 1, y: 1, radius: 4, bright_radius: 2, enabled: true },
      ],
    };
    const n = resizeMap(d, 1, 1);
    expect(n.spawn).toEqual({ x: 0, y: 0 });
    expect(n.traps).toHaveLength(0);
    expect(n.lights).toHaveLength(0);
    expect(d.lights[0].radius).toBe(4);
    expect(d.traps).toHaveLength(1);
  });
  it("renders art without deriving walkability from visual characters", () => {
    const d: any = {
      width: 2,
      height: 1,
      tiles: [["base:floor", "base:wall"]],
      walkability: [[false, true]],
      blocks_sight: [[false, false]],
      spawn: { x: 0, y: 0 },
      decorations: [],
      traps: [],
      points_of_interest: [],
      monsters: [],
      equipment: [],
      transitions: [],
    };
    const g = mapGrid(d, {
      "tiles/base:floor": { glyph: ".", foreground: 7, background: null },
      "tiles/base:wall": { glyph: "#", foreground: 7, background: null },
    });
    expect(g[0][1]?.char).toBe("#");
    expect(d.walkability).toEqual([[false, true]]);
  });
});
