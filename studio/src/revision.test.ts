import { describe, it, expect } from "vitest";
import {
  assetVersionsMatch,
  libraryResults,
  matchesEntry,
  mapMasks,
  Entry,
  History,
  clone,
} from "./model";
import { paletteLayer } from "./catalog";
import { paintObject } from "./mapTools";

const entries: Entry[] = [
  {
    category: "tiles",
    ref: "base:wall",
    id: "wall",
    name: "Стена",
    version: "a",
    asset: true,
  },
  {
    category: "objects",
    ref: "base:table",
    id: "table",
    name: "Стол",
    version: "b",
    asset: true,
  },
  {
    category: "equipment",
    ref: "other:dagger",
    id: "dagger",
    name: "Кинжал",
    version: "c",
    asset: true,
  },
];
const assets = {
  "tiles/base:wall": { glyph: "#", walkable: false },
  "objects/base:table": {
    glyph: "T",
    walkable: false,
    blocks_sight: false,
    description: "Деревянная мебель",
  },
  "equipment/other:dagger": {
    glyph: "†",
    weapon_damage: "1d4",
    variants: [{ name: "Церемониальный" }],
  },
};
const blank = () =>
  ({
    width: 3,
    height: 2,
    spawn: { x: 0, y: 0 },
    tiles: [
      ["base:floor", "base:floor", "base:floor"],
      ["base:floor", "base:floor", "base:floor"],
    ],
    walkability: [
      [true, true, true],
      [true, true, true],
    ],
    blocks_sight: [
      [false, false, false],
      [false, false, false],
    ],
    objects: [],
    equipment: [],
    doors: [],
    transitions: [],
  }) as any;

describe("global content search and asset refresh", () => {
  it("finds content outside the selected category and pack, including nested fields", () => {
    expect(
      libraryResults(entries, "кинжал", "tiles", "base", assets).map(
        (e) => e.ref,
      ),
    ).toEqual(["other:dagger"]);
    expect(
      libraryResults(entries, "", "tiles", "base", assets).map((e) => e.ref),
    ).toEqual(["base:wall"]);
    expect(matchesEntry(entries[2], "церемониальный 1d4", assets)).toBe(true);
    expect(matchesEntry(entries[1], "деревянная", assets)).toBe(true);
    expect(paletteLayer(entries[2], assets)).toBe("equipment");
    expect(
      paletteLayer({ ...entries[0], category: "spells" }, assets),
    ).toBeNull();
  });
  it("does not reload unchanged object assets and detects additions, deletions and edits", () => {
    const versions = {
      "tiles/base:wall": "a",
      "objects/base:table": "b",
      "equipment/other:dagger": "c",
    };
    expect(assetVersionsMatch(entries, versions)).toBe(true);
    expect(
      assetVersionsMatch(entries, {
        ...versions,
        "objects/base:table": "changed",
      }),
    ).toBe(false);
    expect(assetVersionsMatch(entries.slice(1), versions)).toBe(false);
    expect(
      assetVersionsMatch(
        [...entries, { ...entries[1], ref: "base:new" }],
        versions,
      ),
    ).toBe(false);
  });
});

describe("native object painting", () => {
  it("keeps surfaces separate, composes geometry and supports undo/redo", () => {
    const doc = blank(),
      history = new History(clone(doc));
    paintObject(doc, "objects", "base:table", assets["objects/base:table"], {
      x: 1,
      y: 1,
    });
    paintObject(
      doc,
      "equipment",
      "other:dagger",
      assets["equipment/other:dagger"],
      { x: 2, y: 1 },
    );
    expect(doc.tiles[1]).toEqual(["base:floor", "base:floor", "base:floor"]);
    expect(doc.walkability[1][1]).toBe(true);
    expect(mapMasks(doc, assets).walkability[1][1]).toBe(false);
    expect(doc.equipment[0].ref).toBe("other:dagger");
    history.commit(clone(doc));
    history.undo();
    expect(history.present.objects).toHaveLength(0);
    history.redo();
    expect(history.present.objects).toHaveLength(1);
    expect(() =>
      paintObject(
        doc,
        "objects",
        "base:table",
        assets["objects/base:table"],
        doc.spawn,
      ),
    ).toThrow("старт");
  });
  it("does not duplicate ids after moving an instance and erases linked transitions", () => {
    const doc = blank(),
      portal = { walkable: true, brush: { transition: true } };
    paintObject(
      doc,
      "objects",
      "base:portal",
      portal,
      { x: 1, y: 1 },
      "base:dungeon",
    );
    doc.objects[0].x = 2;
    paintObject(
      doc,
      "objects",
      "base:portal",
      portal,
      { x: 1, y: 1 },
      "base:dungeon",
    );
    expect(new Set(doc.objects.map((p: any) => p.id)).size).toBe(2);
    const parent = doc.objects.find((p: any) => p.x === 1).id;
    paintObject(doc, "objects", "", undefined, { x: 1, y: 1 }, "", true);
    expect(
      doc.transitions.some((p: any) => p.id === parent + "_transition"),
    ).toBe(false);
  });
});
