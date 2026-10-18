import { describe, expect, it } from "vitest";
import {
  blankMask,
  fillMask,
  paintMask,
  transformMask,
  visual,
} from "./symbolModel";
import { History } from "./model";

describe("symbol documents", () => {
  it("previews the initial lever state while plates start released", () => {
    const assets = {
      "symbols/test:on": { glyph: "/" },
      "symbols/test:off": { glyph: "L" },
    };
    const doc = {
      state_symbols: { on: "test:on", off: "test:off" },
      mechanism: { trigger: "lever", initially_on: true },
    };
    expect(visual(doc, assets).char).toBe("/");
    expect(
      visual(
        { ...doc, mechanism: { ...doc.mechanism, initially_on: false } },
        assets,
      ).char,
    ).toBe("L");
    expect(
      visual(
        { ...doc, mechanism: { ...doc.mechanism, trigger: "pressure_plate" } },
        assets,
      ).char,
    ).toBe("L");
  });
  it("container states share one template and keep the loot color", () => {
    const chest = {
      symbol: "tiles:closed",
      state_symbols: { closed: "tiles:closed", open: "tiles:open" },
      storage: { state: "closed" },
      foreground: 220,
    };
    const assets = {
      "symbols/tiles:closed": { glyph: "C" },
      "symbols/tiles:open": { glyph: "U" },
    };
    expect(visual(chest, assets)).toMatchObject({
      symbol: "tiles:closed",
      char: "C",
      foreground: 220,
    });
    expect(
      visual({ ...chest, storage: { state: "open" } }, assets),
    ).toMatchObject({ symbol: "tiles:open", char: "U", foreground: 220 });
  });
  it("initial bent state chooses the grille state symbol", () => {
    const doc = {
      symbol: "tiles:intact",
      state_symbols: { bent: "tiles:bent" },
      brush: { door: { state: "closed", bent: true } },
    };
    const assets = {
      "symbols/tiles:intact": { glyph: "|" },
      "symbols/tiles:bent": { glyph: "%" },
    };
    expect(visual(doc, assets).symbol).toBe("tiles:bent");
    expect(visual(doc, assets).char).toBe("%");
  });
  it("fills enclosed regions and leaves surrounding pixels intact", () => {
    let mask = blankMask();
    const border = [];
    for (let i = 2; i <= 6; i++)
      border.push(
        { x: i, y: 2 },
        { x: i, y: 6 },
        { x: 2, y: i },
        { x: 6, y: i },
      );
    mask = paintMask(mask, border, "1");
    const filled = fillMask(mask, { x: 4, y: 4 }, "1");
    expect(filled[4]).toBe("0011111000000000");
    expect(filled[1]).toBe("0".repeat(16));
    expect(mask[4][4]).toBe("0");
  });
  it("transforms and undo/redo preserve exact masks", () => {
    const original = paintMask(
      blankMask(),
      [
        { x: 1, y: 2 },
        { x: 2, y: 2 },
      ],
      "1",
    );
    let next = original;
    for (let i = 0; i < 4; i++) next = transformMask(next, "rotate");
    expect(next).toEqual(original);
    expect(transformMask(transformMask(original, "flipX"), "flipX")).toEqual(
      original,
    );
    const history = new History({ pixels: original });
    history.commit({ pixels: transformMask(original, "flipY") });
    history.undo();
    expect(history.present.pixels).toEqual(original);
    history.redo();
    expect(history.present.pixels[13][1]).toBe("1");
  });
  it("resolves object states and legacy glyphs through one catalog", () => {
    const assets = {
      "symbols/base:closed": { glyph: "+" },
      "symbols/base:open": { glyph: "'" },
      "symbols/base:glyph_002e": { glyph: "." },
    };
    expect(
      visual(
        {
          glyph: "?",
          symbol: "base:closed",
          state_symbols: { open: "base:open" },
          brush: { door: { state: "open" } },
        },
        assets,
      ),
    ).toMatchObject({ symbol: "base:open", char: "'" });
    expect(visual({ glyph: "." }, assets).symbol).toBe("base:glyph_002e");
  });
});
