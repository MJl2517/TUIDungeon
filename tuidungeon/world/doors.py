"""Door placements and interaction descriptions owned by one level."""

from dataclasses import dataclass, field
from uuid import uuid4

from ..content.schemas import Placement, TileDocument
from ..domain.doors import Door, DoorChoice
from ..domain.equipment import find_lockpicks


def door_placements(store, definition):
    """Explicit placements plus compatibility for older static door tiles."""
    result = list(definition.doors)
    occupied = {(p.x, p.y) for p in result}
    templates = {
        ref
        for (category, ref), tile in store.documents.items()
        if category in ("tiles", "objects") and tile.brush.door
    }
    for y, row in enumerate(definition.tiles):
        for x, ref in enumerate(row):
            if ref in templates and (x, y) not in occupied:
                result.append(Placement(id=f"tile_doors_{x}_{y}", ref=ref, x=x, y=y))
    return result


def door_category(store, ref):
    return "objects" if ("objects", ref) in store.documents else "tiles"


@dataclass
class DoorInstance:
    placement: Placement
    definition: TileDocument
    door: Door
    instance_id: str = field(default_factory=lambda: str(uuid4()))

    # The interaction contract is shared with points of interest. The door
    # command handler owns resolution; this object only describes choices.
    @property
    def challenge(self):
        return self

    @property
    def completed(self):
        return self.door.destroyed

    @property
    def text(self):
        return "\n".join(self.door.inspection())

    def available_choices(self, hero):
        door = self.door
        if door.destroyed or door.bent:
            return ()
        if door.material == "stone":
            return (
                DoorChoice(
                    "attack",
                    "Разрушить плиту: кирка / дробящий урон; оружию −1d4 прочности",
                ),
            )
        if door.opened:
            return (DoorChoice("close", "Закрыть дверь"),)
        tools = find_lockpicks(hero.inventory)
        tool_hint = (
            f"инструменты {tools.durability}/{tools.definition.durability}; провал: −1 прочность"
            if tools and tools.durability is not None
            else "инструменты в наличии; провал: износ"
            if tools
            else "нужны исправные воровские инструменты"
        )
        choices = [
            DoorChoice(
                "pick",
                f"Вскрыть замок: ЛОВ, СЛ {door.lock_dc}, {door.lock_turns} ход(ов); {tool_hint}",
            )
        ]
        if not door.locked:
            choices = [DoorChoice("open", "Открыть дверь")]
        choices.append(
            DoorChoice(
                "force",
                f"Выломать: СИЛ, СЛ {door.force_dc}; ломик в руке даёт преимущество",
            )
        )
        if door.material == "bars":
            choices.append(DoorChoice("bend", "Согнуть прутья и пролезть: СИЛ, СЛ 20"))
        if door.material not in ("adamantine", "steel"):
            choices.append(
                DoorChoice("attack", "Атаковать дверь: оружию −1d4 прочности")
            )
        if door.material == "wood" and not door.burning:
            if any(item.can_ignite for item in hero.inventory):
                choices.append(DoorChoice("ignite", "Поджечь: 5 урона огнём в минуту"))
        if door.material in ("steel", "bars") and any(
            "acid" in item.tags and item.usable for item in hero.inventory
        ):
            choices.append(
                DoorChoice("acid", "Бросить кислоту: 2d6 ×2 по металлу и коррозия")
            )
        if (
            door.material == "adamantine"
            and hero.character_class.id.removeprefix("base:") == "wizard"
        ):
            if any(
                spell.id.removeprefix("base:") == "daylight"
                for spell in hero.class_spells
            ):
                choices.append(
                    DoorChoice(
                        "daylight",
                        "Дневной свет: превратить дверь в каменную плиту (ячейка 3 ур.)",
                    )
                )
        return tuple(choices)
