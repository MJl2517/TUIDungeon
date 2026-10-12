"""Read-only engine benchmark; synthetic maps live only in memory.

Run: python -m scripts.benchmark_engine --sizes 32 100 256 --repeat 3
Output is JSON so two revisions can be compared without timing assertions in tests.
"""

import argparse
from copy import copy
import gc
import json
import platform
from statistics import median
from time import perf_counter
from unittest.mock import patch

from tuidungeon.application.engine import Action
from tuidungeon.application.factories import SessionFactory
from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.world.lighting import LightField


def measure(operation, repeat):
    operation()  # Warm caches; includes normal GC during each measured operation.
    samples = []
    for _ in range(repeat):
        gc.collect()
        start = perf_counter()
        operation()
        samples.append((perf_counter() - start) * 1000)
    return round(median(samples), 3)


def after_move(engine, operation):
    direction = [Action.EAST]

    def sample():
        engine.apply(direction[0])
        direction[0] = Action.WEST if direction[0] is Action.EAST else Action.EAST
        return operation()

    return sample


def synthetic_map(size, *, items=0, lights=0, ambient="bright"):
    return MapDocument(
        id="benchmark",
        name="Synthetic benchmark",
        width=size,
        height=size,
        tiles=[["base:floor"] * size for _ in range(size)],
        walkability=[[True] * size for _ in range(size)],
        blocks_sight=[[False] * size for _ in range(size)],
        spawn={"x": size // 2, "y": size // 2},
        ambient_light=ambient,
        equipment=[
            {
                "id": f"item_{i}",
                "ref": "base:healing_potion",
                "x": i % size,
                "y": i // size % size,
            }
            for i in range(items)
        ],
        lights=[
            {
                "id": f"light_{i}",
                "x": (i * 7) % size,
                "y": (i * 11) % size,
                "radius": 6,
                "bright_radius": 3,
            }
            for i in range(lights)
        ],
    )


def scenario(store, size, repeat, *, items=0, lights=0, ambient="bright"):
    definition = synthetic_map(size, items=items, lights=lights, ambient=ambient)
    local = copy(store)
    local.documents = dict(store.documents)
    local.documents[("maps", "base:benchmark")] = definition
    encoded = definition.model_dump_json().encode()
    raw = json.loads(encoded)
    factory = SessionFactory(local)
    engine = factory.session("base:benchmark", seed=42)
    with patch.object(LightField, "calculate", wraps=LightField.calculate) as calls:
        engine.render_cells()
        light_calls = calls.call_count

    return {
        "size": size,
        "items": items,
        "lights": lights,
        "ambient": ambient,
        "map_json_bytes": len(encoded),
        "light_calculations_per_frame": light_calls,
        "median_ms": {
            "json_decode": measure(lambda: json.loads(encoded), repeat),
            "schema_validation": measure(
                lambda: MapDocument.model_validate(raw), repeat
            ),
            "session_from_prebuilt_catalog": measure(
                lambda: factory.session("base:benchmark", seed=42), repeat
            ),
            "wait_command_only": measure(lambda: engine.apply(Action.WAIT), repeat),
            "move_pair_command_only": measure(
                lambda: (engine.apply(Action.EAST), engine.apply(Action.WEST)), repeat
            ),
            "lighting": measure(lambda: engine.lighting, repeat),
            "render_cells": measure(engine.render_cells, repeat),
            "move_and_lighting": measure(
                after_move(engine, lambda: engine.lighting), repeat
            ),
            "move_and_viewport": measure(
                after_move(
                    engine,
                    lambda: engine.render_cells(
                        (
                            max(0, size // 2 - 40),
                            max(0, size // 2 - 12),
                            min(80, size),
                            min(24, size),
                        )
                    ),
                ),
                repeat,
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[32, 100, 256])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--packs-dir")
    args = parser.parse_args()
    if args.repeat < 1 or any(not 4 <= size <= 256 for size in args.sizes):
        parser.error("repeat >= 1; sizes must be between 4 and 256")
    store = PackStore(args.packs_dir) if args.packs_dir else PackStore()
    # Synthetic scenarios deliberately use stable base content IDs.
    store.get("equipment", "base:healing_potion")
    store.get("tiles", "base:floor")
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repeat": args.repeat,
        "documents": len(store.documents),
        "pack_reload_warm_filesystem_ms": measure(store.reload, args.repeat),
        "runtime_catalog_ms": measure(store.runtime_catalog, args.repeat),
        "scenarios": [],
    }
    for size in args.sizes:
        result["scenarios"].append(scenario(store, size, args.repeat))
    for options in (
        {"items": 1000},
        {"lights": 100, "ambient": "dark"},
        {"ambient": "dark"},
    ):
        result["scenarios"].append(scenario(store, 100, args.repeat, **options))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
