"""Export the exact schemas used by Studio for agents and external tools."""

import argparse
from pathlib import Path
from .schemas import MODELS, Manifest
from .packs import PackStore
from ..domain.mechanics import mechanics


def main():
    parser = argparse.ArgumentParser(description="Экспорт JSON Schema")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for category, model in {**MODELS, "manifest": Manifest}.items():
        PackStore.atomic_json(
            args.directory / f"{category}.schema.json", model.model_json_schema()
        )
    PackStore.atomic_json(args.directory / "mechanics.json", mechanics.schemas())
    print(f"Схемы выгружены в {args.directory}")


if __name__ == "__main__":
    main()
