import { describe, it, expect } from "vitest";
import {
  signalTargets,
  signalHighlights,
  toggleSignalTarget,
  copiedSignalPlacement,
} from "./MechanismLinks";

const assets = {
  "objects/test:lever": { name: "Рычаг", tags: ["mechanism"] },
  "objects/test:fire": { name: "Огонь", brush: { light: { radius: 4 } } },
  "objects/test:illusion": { name: "Иллюзия", illusion: true },
  "objects/test:chair": { name: "Стул" },
  "objects/test:door": { name: "Дверь", brush: { door: { material: "wood" } } },
  "objects/test:key_door": {
    name: "Ключ",
    brush: { door: { access: "unique_key" } },
  },
};
const doc = () => ({
  objects: [
    { id: "lever", ref: "test:lever", x: 1, y: 1 },
    { id: "fire", ref: "test:fire", x: 2, y: 1, activation_code: "demo" },
    { id: "illusion", ref: "test:illusion", x: 3, y: 1 },
    { id: "chair", ref: "test:chair", x: 4, y: 1 },
  ],
  doors: [
    { id: "door", ref: "test:door", x: 5, y: 1 },
    { id: "key", ref: "test:key_door", x: 6, y: 1 },
  ],
  traps: [{ id: "trap", ref: "test:trap", x: 7, y: 1 }],
  lights: [{ id: "light", x: 8, y: 1 }],
});

describe("map signal links", () => {
  it("accepts only supported receivers, including local illusion overrides", () => {
    const d = doc();
    d.objects[3] = { ...d.objects[3], overrides: { illusion: true } } as any;
    expect(
      signalTargets(d, assets)
        .map((t) => t.placement.id)
        .sort(),
    ).toEqual(["chair", "door", "fire", "illusion", "light", "trap"]);
  });
  it("click toggles explicit links without modifying a template or other placements", () => {
    const original = doc();
    const linked = toggleSignalTarget(original, assets, "lever", "door");
    expect(linked.objects[0].overrides.mechanism.trigger).toBe("lever");
    expect(linked.objects[0].overrides.mechanism_targets).toEqual(["door"]);
    expect(original.objects[0]).not.toHaveProperty("overrides");
    expect(
      toggleSignalTarget(linked, assets, "lever", "door").objects[0].overrides
        .mechanism_targets,
    ).toEqual([]);
    expect(toggleSignalTarget(original, assets, "lever", "chair")).toBe(
      original,
    );
  });
  it("shows both direct and code links once and remaps copied internal targets", () => {
    const d = toggleSignalTarget(doc(), assets, "lever", "fire");
    d.objects[0].overrides.mechanism.code = "demo";
    expect(signalHighlights(d, assets, "lever")).toEqual([d.objects[1]]);
    d.objects[0].overrides.mechanism_targets.push("door");
    const copy = copiedSignalPlacement(
      d.objects[0],
      assets,
      new Map([["fire", "copy_fire"]]),
    );
    expect(copy.overrides.mechanism_targets).toEqual(["copy_fire", "door"]);
    expect(d.objects[0].overrides.mechanism_targets).toEqual(["fire", "door"]);
  });
});
