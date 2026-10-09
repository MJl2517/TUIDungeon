import { describe, expect, it } from "vitest";
import { effectText } from "./damage";

describe("damage reports", () => {
  it("distinguishes rolled, defended and applied damage, including immunity", () => {
    expect(
      effectText({
        kind: "damage",
        damage_type: "fire",
        raw_amount: 5,
        resolved_amount: 2,
        amount: 1,
        response: "resistant",
      }),
    ).toBe("Огонь: 5 → 2 (сопротивление); потеря HP: 1");
    expect(
      effectText({
        kind: "damage",
        damage_type: "poison",
        raw_amount: 5,
        resolved_amount: 0,
        amount: 0,
        response: "immune",
      }),
    ).toContain("5 → 0 (иммунитет)");
  });
  it("supports legacy damage and separate condition events", () => {
    expect(effectText({ kind: "damage", amount: 4 })).toBe("Без типа: 4 урона");
    expect(effectText({ kind: "condition", condition: "poisoned" })).toBe(
      "condition: poisoned",
    );
  });
});
