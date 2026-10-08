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
} from "./model";
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
