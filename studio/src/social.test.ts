import { describe, expect, it } from "vitest";
import { tradePreview, propertySections } from "./Form";
import { mapGrid, resizeMap } from "./model";
import { paletteCategory, paletteLayer } from "./catalog";

describe("NPC authoring", () => {
  it("shares the creature palette while keeping an independent placement layer", () => {
    const entry: any = { category: "npcs", ref: "dev:merchant" };
    expect(paletteCategory(entry)).toBe("monsters");
    expect(paletteLayer(entry, {})).toBe("npcs");
    const doc: any = {
      width: 2,
      height: 1,
      spawn: { x: 0, y: 0 },
      tiles: [[null, null]],
      npcs: [{ id: "n", ref: entry.ref, x: 1, y: 0 }],
      equipment: [],
    };
    expect(
      mapGrid(doc, { "npcs/dev:merchant": { glyph: "n" } })[0][1]?.char,
    ).toBe("n");
    expect(resizeMap(doc, 2, 2).npcs).toHaveLength(1);
    expect(
      propertySections("npcs", ["id", "topics", "trade", "quests"]).map(
        (s) => s.title,
      ),
    ).toEqual(["Основное", "Разговор", "Магазин", "Задания"]);
  });
  it("previews condition before bargaining and avoids profitable buybacks", () => {
    const rule = { buy: 10, sell: 20 };
    expect(tradePreview(rule, 50, 0)).toEqual([10, 5]);
    expect(tradePreview(rule, 50, 10)).toEqual([9, 5]);
    expect(tradePreview(rule, 50, -10)).toEqual([11, 4]);
    expect(tradePreview({ buy: 10, sell: 10 }, 100, 10)).toEqual([9, 9]);
    expect(tradePreview(rule, 0, 10)).toEqual([1, 0]);
  });
});
