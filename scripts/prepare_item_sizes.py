"""Fill missing author sizes without changing already assigned dimensions.

python -m scripts.prepare_item_sizes          # preview
python -m scripts.prepare_item_sizes --write  # explicit, repeatable migration
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from tuidungeon.content.packs import PROJECT_ROOT, PackStore

# Physical dimensions, deliberately independent of weight. Other items start medium.
SMALL = set(
    """acid_flask arcane_dust arcane_focus binding_resin inscribed_page mithril pigment rune_dagger
scroll_fire_bolt scroll_light scroll_mending writing_paper candle chest_key acid_reagent alchemy_reagent bandage
bitter_herb clay cloth furniture_hardware glass_material herbalism_kit iron jeweler_tools mechanical_part
medicinal_herb metal mushroom plant_fiber poison_herb poisoner_kit raw_leather stone tinder dagger dried_herbs
animal_bone chitin glass_flask herbal_extract improvised_lockpicks leather_strip poison_gland cooked_meat raw_meat
simple_poison spider_silk stone_wedge uncut_gem flint_and_steel gold healing_potion healing_poultice ink
master_lockpicks oil parchment rations spellbook terrain_artifact terrain_artifact_amulet terrain_artifact_legendary
terrain_artifact_powerful terrain_artifact_ring terrain_artifact_ring_enchanted terrain_artifact_stone
terrain_artifact_unidentified terrain_artifact_unknown terrain_artifact_weak terrain_decor_arrow terrain_decor_bolt
terrain_decor_bottle terrain_decor_gloves terrain_decor_potion_unknown terrain_key_ancient terrain_key_decor
terrain_key_important terrain_key_special thieves_tools water_flask waterskin""".split()
)
LARGE = set(
    """battering_ram carved_staff wooden_pole staff pickaxe packed_furniture terrain_decor_bow
terrain_decor_greataxe terrain_decor_greatsword terrain_decor_halberd terrain_decor_longbow terrain_decor_spear""".split()
)


def updates(root=PROJECT_ROOT):
    root = Path(root)
    for directory in [
        *sorted((root / "packs").glob("*/equipment")),
        root / "tuidungeon/content/data/equipment",
    ]:
        for path in sorted(directory.rglob("*.json")):
            raw = json.loads(path.read_text(encoding="utf8"))
            if "size" in raw:
                continue
            identifier = raw["id"]
            base = (
                "packs/base" in path.as_posix()
                or "tuidungeon/content/data" in path.as_posix()
            )
            raw["size"] = (
                "small"
                if base
                and identifier in SMALL
                or identifier in {"cactus_juice_flask", "coconut"}
                else "large"
                if base and identifier in LARGE
                else "medium"
            )
            yield path, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rows = list(updates())
    if args.write:
        for path, raw in rows:
            PackStore.atomic_json(path, raw)
        PackStore().runtime_catalog()
    print(
        "Назначено" if args.write else "Будет назначено",
        len(rows),
        dict(Counter(raw["size"] for _, raw in rows)),
    )


if __name__ == "__main__":
    main()
