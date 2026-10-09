import type { Doc } from "./model";

export const damageLabels: Record<string, string> = {
  bludgeoning: "Дробящий",
  piercing: "Колющий",
  slashing: "Рубящий",
  acid: "Кислота",
  cold: "Холод",
  fire: "Огонь",
  lightning: "Электрический",
  thunder: "Громовой",
  force: "Силовой",
  necrotic: "Некротический",
  psychic: "Психический",
  radiant: "Лучистый",
  poison: "Ядовитый",
  physical: "Физический (3 типа)",
  elemental: "Элементальный (5 типов)",
  mystic: "Мистический (4 типа)",
  toxic: "Токсический (яд)",
};

export function effectText(effect: Doc): string {
  if (effect.kind !== "damage")
    return `${effect.kind}: ${effect.condition || effect.amount}`;
  const type = damageLabels[effect.damage_type] ?? "Без типа";
  const response: Record<string, string> = {
    resistant: "сопротивление",
    vulnerable: "уязвимость",
    immune: "иммунитет",
    cancelled: "сопротивление и уязвимость отменяют друг друга",
    normal: "обычный",
  };
  if (effect.raw_amount == null) return `${type}: ${effect.amount} урона`;
  return `${type}: ${effect.raw_amount} → ${effect.resolved_amount} (${response[effect.response] ?? effect.response}); потеря HP: ${effect.amount}`;
}
