"""Reproduce audit findings without touching authored files.

Run: python -m scripts.probe_engine_contracts
Exit 1 means a contract is still broken. This is separate from the existing suite
so the audit does not silently redefine current behavior as correct.
"""

import json

from scripts.benchmark_engine import synthetic_map
from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.tooling.sessions import TestSession
from tuidungeon.world.maps import Position


def probe():
    store = PackStore()
    raw = synthetic_map(8).model_dump()
    raw["spawn"] = {"x": 1, "y": 1}
    raw["tiles"][1][2] = "base:decor_dagger"
    tile = store.get("tiles", "base:decor_dagger")
    raw["equipment"] = [
        {"id": "tile_equipment_2_1", "x": 2, "y": 1, "ref": tile.brush.item}
    ]
    store.documents["maps", "base:benchmark"] = MapDocument.model_validate(raw)
    engine = SessionFactory(store).session("base:benchmark")
    engine.apply(Action.EAST)
    engine.pickup_item()
    engine.apply(Action.WEST)
    glyph = engine.render_cells()[1][2].char
    inspection = engine.inspect_cell(Position(2, 1))
    checks = [
        {
            "contract": "picked_up_brush_item_disappears",
            "ok": glyph != tile.glyph and tile.name not in inspection,
            "remaining_items": len(engine.state.items),
            "glyph": glyph,
            "inspection": inspection,
        }
    ]

    a = TestSession(store, {"map_ref": "base:benchmark"})
    b = TestSession(store, {"map_ref": "base:benchmark"})
    rejected = False
    try:
        store.get("maps", "base:benchmark").walkability[2][2] = False
    except (TypeError, ValueError):
        rejected = True  # A deeply immutable definition also satisfies isolation.
    leaked = any(
        not session.engine.state.level.definition.walkability[2][2]
        for session in (a, b)
    )
    checks.append(
        {
            "contract": "session_definitions_are_isolated_or_immutable",
            "ok": rejected or not leaked,
            "mutation_rejected": rejected,
            "mutation_leaked": leaked,
            "runtime_walkable": a.engine.state.dungeon.walkable(Position(2, 2)),
            "definition_walkable": a.engine.state.level.definition.walkability[2][2],
        }
    )

    item = store.get("equipment", "base:dagger")
    store.documents["equipment", "base:dagger"] = item.model_copy(
        update={"description": "base:secret"}
    )
    description = store.runtime_catalog().equipment["dagger"].description
    checks.append(
        {
            "contract": "reference_adapter_preserves_plain_text",
            "ok": description == "base:secret",
            "expected": "base:secret",
            "actual": description,
        }
    )
    return checks


if __name__ == "__main__":
    checks = probe()
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(check["ok"] for check in checks) else 1)
