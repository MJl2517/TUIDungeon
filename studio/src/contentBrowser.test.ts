import { describe, it, expect } from "vitest";
import {
  contentGroup,
  contentBadges,
  contentRank,
  paletteCategory,
  paletteSections,
  paletteLayer,
} from "./catalog";
import { propertySections, propertySearchText } from "./Form";
import { Entry, libraryResults } from "./model";
const entry = (category: string, details: any = {}): Entry => ({
  category,
  ref: "base:sample",
  id: "sample",
  name: "Пример",
  version: "1",
  details,
});
describe("content organization", () => {
  it("uses craft, item, school, spell level and real monster HP metadata", () => {
    expect(contentGroup(entry("recipes", { category: "smith" }))).toBe(
      "Кузнец",
    );
    expect(contentGroup(entry("equipment", { category: "materials" }))).toBe(
      "Материалы",
    );
    expect(contentGroup(entry("spells", { school: "evocation" }))).toBe(
      "Воплощение",
    );
    expect(contentBadges(entry("spells", { level: 0 }))).toContain("Заговор");
    expect(contentGroup(entry("monsters", { hit_points: 25 }))).toBe(
      "11–30 HP",
    );
    expect(contentRank(entry("monsters", { hit_points: 25 }))).toBe(25);
    expect(
      contentGroup({
        ...entry("points_of_interest"),
        features: { reading: true },
      }),
    ).toBe("Тексты для чтения");
  });
  it("includes nested recipe content in search while respecting filters", () => {
    const recipe = {
      ...entry("recipes"),
      search_text: '{"ingredients":["base:cloth"]}',
    };
    expect(libraryResults([recipe], "cloth", "all", "all")).toEqual([recipe]);
    expect(libraryResults([recipe], "cloth", "spells", "all")).toEqual([]);
    expect(
      libraryResults(
        [entry("maps", { ambient_light: "dark" })],
        "dark",
        "maps",
        "all",
      ),
    ).toHaveLength(1);
  });
  it("assigns every property exactly once and keeps unfamiliar extension fields", () => {
    const keys = [
      "id",
      "name",
      "variants",
      "result",
      "check",
      "extension_field",
      "schema_version",
    ];
    const sections = propertySections("recipes", keys);
    expect(sections.flatMap((s) => s.fields).sort()).toEqual(
      keys.filter((k) => k !== "schema_version").sort(),
    );
    expect(sections.find((s) => s.fields.includes("variants"))?.title).toBe(
      "Способы изготовления",
    );
    expect(
      sections.find((s) => s.fields.includes("extension_field"))?.title,
    ).toBe("Дополнительные свойства");
  });
  it("finds ingredients inside recipe variants without exposing schema class names", () => {
    const root = {
      $defs: {
        Variant: {
          type: "object",
          properties: {
            ingredients: { type: "array", items: { type: "string" } },
          },
        },
      },
    };
    expect(
      propertySearchText(
        "variants",
        { type: "array", items: { $ref: "#/$defs/Variant" } },
        root,
      ),
    ).toContain("Ингредиенты");
  });
});

describe("map palette purpose categories", () => {
  it("keeps ten sections, explicit roles and the original storage layer", () => {
    expect(Object.keys(paletteSections)).toEqual([
      "floor",
      "wall",
      "destructible",
      "doors",
      "traps",
      "furniture",
      "equipment",
      "special",
      "monsters",
      "service",
    ]);
    const wall = entry("tiles", { walkable: false, blocks_sight: false });
    const assets = {
      "tiles/base:sample": { map_category: "destructible", walkable: false },
    };
    expect(paletteCategory(wall)).toBe("wall");
    expect(paletteCategory(wall, assets)).toBe("destructible");
    expect(paletteLayer(wall, assets)).toBe("tiles");
    expect(
      paletteCategory(entry("tiles", { tags: ["water"], walkable: false })),
    ).toBe("floor");
    expect(
      paletteCategory(
        entry("objects", { map_category: "special", tags: ["furniture"] }),
      ),
    ).toBe("special");
    expect(
      paletteCategory(
        entry("objects", { map_category: "destructible", brush: { door: {} } }),
      ),
    ).toBe("doors");
    expect(paletteCategory(entry("points_of_interest", { storage: {} }))).toBe(
      "furniture",
    );
    expect(paletteCategory(entry("tiles", { tags: ["plants"] }))).toBe(
      "destructible",
    );
    expect(paletteCategory(entry("tiles", { tags: ["trap_decor"] }))).toBe(
      "special",
    );
    expect(
      paletteCategory(
        entry("objects", { tags: ["stairs"], brush: { transition: true } }),
      ),
    ).toBe("service");
    expect(
      paletteCategory(
        entry("objects", { tags: ["portals"], brush: { transition: true } }),
      ),
    ).toBe("special");
    for (const category of ["equipment", "traps", "monsters"])
      expect(paletteCategory(entry(category))).toBe(category);
    expect(paletteCategory(entry("spells"))).toBeNull();
  });
});
