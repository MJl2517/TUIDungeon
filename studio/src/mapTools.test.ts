import { describe, it, expect } from "vitest";
import { paintTile, paintObject, sampleMap } from "./mapTools";
import { brushDescription, tileFamily } from "./catalog";
import { clone, History, mapGrid, resizeMap } from "./model";

const blank = () =>
  ({
    width: 3,
    height: 2,
    spawn: { x: 0, y: 0 },
    tiles: [
      [null, null, null],
      [null, null, null],
    ],
    walkability: [
      [true, true, true],
      [true, true, true],
    ],
    blocks_sight: [
      [false, false, false],
      [false, false, false],
    ],
    traps: [],
    points_of_interest: [],
    equipment: [],
    lights: [],
    transitions: [],
  }) as any;
const options = { masks: true, mechanics: true, target: "" };
describe("map brushes", () => {
  it("reflects surfaces per cell and preserves reflection through undo, resize and erase", () => {
    const doc = blank(),
      p = { x: 1, y: 1 },
      tile = {
        walkable: true,
        blocks_sight: false,
        symbol: "test:tile",
        mirror_x: false,
      };
    const history = new History(clone(doc));
    paintTile(doc, "test:tile", tile, p, { ...options, mirror: true });
    history.commit(clone(doc));
    const assets = {
      "tiles/test:tile": tile,
      "symbols/test:tile": { glyph: "/" },
    };
    expect(mapGrid(doc, assets)[1][1]?.mirror_x).toBe(true);
    expect(
      mapGrid(doc, {
        ...assets,
        "tiles/test:tile": { ...tile, mirror_x: true },
      })[1][1]?.mirror_x,
    ).toBe(false);
    expect(resizeMap(doc, 4, 3).tile_mirrors[1][1]).toBe(true);
    history.undo();
    expect(history.present.tile_mirrors).toBeUndefined();
    history.redo();
    expect(history.present.tile_mirrors[1][1]).toBe(true);
    paintTile(doc, "test:tile", tile, p, { ...options, erase: true });
    expect(doc.tile_mirrors[1][1]).toBe(false);
  });
  it("Shift mirrors a placed object relative to its template without copying the symbol", () => {
    const doc = blank(),
      p = { x: 1, y: 1 },
      object = {
        walkable: true,
        blocks_sight: false,
        mirror_x: true,
        symbol: "test:picture",
      };
    paintObject(doc, "objects", "test:object", object, p, "", false, true);
    expect(doc.objects[0]).toMatchObject({
      ref: "test:object",
      overrides: { mirror_x: false },
    });
    expect(object.mirror_x).toBe(true);
    paintObject(doc, "objects", "test:object", object, p);
    expect(doc.objects[0].overrides).toBeUndefined();
    expect(doc.objects).toHaveLength(1);
  });
  it("creates doors over floor and replaces the door without duplicating instances", () => {
    const doc = blank();
    const p = { x: 1, y: 1 };
    doc.walkability[1][1] = false;
    doc.blocks_sight[1][1] = true;
    const tile = {
      glyph: "X",
      walkable: false,
      blocks_sight: true,
      brush: { door: { material: "wood", state: "closed", locked: true } },
    };
    paintTile(doc, "base:door_wood_locked_cheap_complex", tile, p, {
      ...options,
      mechanics: false,
      masks: false,
    });
    expect(doc.tiles[1][1]).toBe("base:floor");
    expect(doc.walkability[1][1]).toBe(true);
    expect(doc.blocks_sight[1][1]).toBe(false);
    expect(doc.doors[0].ref).toBe("base:door_wood_locked_cheap_complex");
    doc.doors[0].id = "manual_door";
    paintTile(doc, "base:door_steel_closed", tile, p, options);
    expect(doc.doors).toHaveLength(1);
    expect(doc.doors[0].ref).toBe("base:door_steel_closed");
    paintTile(doc, "base:floor", { walkable: true }, p, options);
    expect(doc.doors).toHaveLength(0);
    expect(() =>
      paintTile(doc, "base:door_steel_closed", tile, doc.spawn, options),
    ).toThrow("старт");
  });
  it("keeps item graphics on the instance and preserves a separate underlay", () => {
    const doc = blank();
    paintTile(
      doc,
      "base:dagger",
      { brush: { item: "base:dagger" } },
      { x: 1, y: 1 },
      options,
    );
    expect(doc.tiles[1][1]).toBe("base:floor");
    expect(doc.equipment[0].ref).toBe("base:dagger");
    paintTile(
      doc,
      "extra:gem",
      { brush: { item: "extra:gem", underlay: "base:stone" } },
      { x: 1, y: 1 },
      options,
    );
    expect(doc.tiles[1][1]).toBe("base:stone");
    expect(doc.equipment).toHaveLength(1);
    expect(doc.equipment[0].ref).toBe("extra:gem");
    const decorated = blank();
    decorated.tiles[1][1] = "extra:mosaic";
    paintTile(
      decorated,
      "base:dagger",
      { brush: { item: "base:dagger" } },
      { x: 1, y: 1 },
      options,
    );
    expect(decorated.tiles[1][1]).toBe("extra:mosaic");
  });
  it("creates independent ordinary map instances and replaces only brush-owned objects", () => {
    const doc = blank();
    doc.traps.push({ id: "manual", ref: "base:tripwire", x: 1, y: 1 });
    const tile = {
      walkable: true,
      blocks_sight: false,
      brush: { trap: "base:fire", light: { radius: 6, bright_radius: 3 } },
    };
    paintTile(doc, "base:fire", tile, { x: 1, y: 1 }, options);
    paintTile(doc, "base:fire", tile, { x: 2, y: 1 }, options);
    expect(doc.traps).toHaveLength(3);
    expect(new Set(doc.traps.map((p: any) => p.id)).size).toBe(3);
    paintTile(
      doc,
      "base:floor",
      { walkable: true, blocks_sight: false },
      { x: 1, y: 1 },
      options,
    );
    expect(doc.traps.map((p: any) => p.id)).toEqual([
      "manual",
      "tile_traps_2_1",
    ]);
    expect(doc.lights).toHaveLength(1);
    expect(tile.brush.light).toEqual({ radius: 6, bright_radius: 3 });
  });
  it("keeps masks and mechanics independently switchable", () => {
    const doc = blank();
    doc.walkability[1][1] = false;
    doc.blocks_sight[1][1] = true;
    paintTile(
      doc,
      "base:rune",
      {
        walkable: true,
        blocks_sight: false,
        brush: { interaction: "base:rune" },
      },
      { x: 1, y: 1 },
      { masks: false, mechanics: false, target: "" },
    );
    expect(doc.tiles[1][1]).toBe("base:rune");
    expect(doc.walkability[1][1]).toBe(false);
    expect(doc.points_of_interest).toHaveLength(0);
    expect(() =>
      paintTile(
        doc,
        "base:rune",
        { brush: { interaction: "base:rune" } },
        { x: 1, y: 1 },
        { masks: false, mechanics: true, target: "" },
      ),
    ).toThrow("проходимая");
  });
  it("requires a destination before drawing a real transition and protects spawn", () => {
    const doc = blank(),
      original = clone(doc);
    expect(() =>
      paintTile(
        doc,
        "base:portal",
        { walkable: true, brush: { transition: true } },
        { x: 1, y: 1 },
        options,
      ),
    ).toThrow("назначения");
    expect(doc).toEqual(original);
    paintTile(
      doc,
      "base:portal",
      { walkable: true, brush: { transition: true } },
      { x: 1, y: 1 },
      { ...options, target: "base:crypt" },
    );
    expect(doc.transitions[0].target).toBe("base:crypt");
    expect(() =>
      paintTile(doc, "base:wall", { walkable: false }, { x: 0, y: 0 }, options),
    ).toThrow("Старт");
  });
  it("undo/redo restores the picture together with all generated mechanics", () => {
    const h = new History(blank()),
      next = clone(h.present);
    paintTile(
      next,
      "base:chest",
      {
        walkable: true,
        brush: { interaction: "base:chest", item: "base:key" },
      },
      { x: 1, y: 1 },
      options,
    );
    h.commit(next);
    h.undo();
    expect(h.present.points_of_interest).toHaveLength(0);
    h.redo();
    expect(h.present.equipment).toHaveLength(1);
  });
  it("samples the active object layer, falls back to terrain and describes actual recipes", () => {
    const doc = blank();
    doc.tiles[1][1] = "base:floor";
    doc.traps.push({ id: "a", ref: "base:tripwire", x: 1, y: 1 });
    expect(sampleMap(doc, { x: 1, y: 1 }, "traps")?.ref).toBe("base:tripwire");
    expect(sampleMap(doc, { x: 1, y: 1 }, "monsters")?.layer).toBe("tiles");
    expect(sampleMap(doc, { x: 2, y: 1 }, "tiles")).toBeNull();
    expect(tileFamily({ tags: ["walls"] })).toBe("Архитектура");
    expect(
      brushDescription(
        {
          walkable: true,
          blocks_sight: false,
          brush: { trap: "base:tripwire" },
        },
        {
          "traps/base:tripwire": {
            name: "Растяжка",
            difficulty: 12,
            hidden: true,
          },
        },
      ).join(" "),
    ).toContain("СЛ 12 · скрытая");
    const description = brushDescription(
      {
        walkable: true,
        brush: {
          trap: "base:fire",
          interaction: "base:chest",
          item: "base:sword",
        },
      },
      {
        "traps/base:fire": {
          name: "Огонь",
          difficulty: 12,
          failure: [{ kind: "damage", dice: "1d4", amount: 1 }],
        },
        "points_of_interest/base:chest": {
          name: "Сундук",
          challenge: "base:loot",
        },
        "challenges/base:loot": {
          choices: [{ text: "Взять", success: [{ kind: "gold", amount: 5 }] }],
        },
        "equipment/base:sword": {
          name: "Меч",
          weight: 2,
          weapon_damage: "1d6",
        },
      },
    ).join(" ");
    expect(description).toContain("урон: 1d4+1");
    expect(description).toContain("золото: 5");
    expect(description).toContain("Вес 2 кг");
  });
});
