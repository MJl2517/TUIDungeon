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
