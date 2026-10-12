"""Reviewed base-pack traits, never runtime guesses from names or colours."""

from ..domain.tags import interaction_tags
from .materials import curated_material_tags

# Explicit starter-material choices. Mixed items may belong to several sets.
MATERIALS = {
    "stone": """stone floor cave_wall wall cracked_barrier shrine stone_tablet
        boulder boulder_large cliff stone_dark stone_pale stone_small
        floor_dark floor_diagonal_tiles floor_gravel floor_mosaic floor_ornate_tiles
        floor_pavers floor_pebbles floor_rough floor_slab floor_smooth floor_striped_tiles
        floor_tiles floor_worn_tiles rubble rubble_blocked rubble_dust rubble_large
        ruined_masonry stone_chips pressure_plate_stone forge""",
    "wooden": "wood club stake cart workbench alchemy_table quest_board",
    "metal": """sword dagger crowbar pickaxe mail flint_and_steel cooking_pot lamp
        chest_key iron metal_scrap mechanical_part anvil chain chain_heavy gears
        gate_grated grate_dense grate_horizontal grate_iron grate_partition
        grate_vertical metal_bar lock mechanism_locked spikes spikes_hidden spikes_large
        decor_axe decor_greataxe decor_greatsword decor_halberd decor_hammer decor_helmet
        decor_mace decor_rapier decor_sickle decor_spear decor_armor_heavy
        decor_arrow decor_bolt key_ancient key_decor key_important key_special
        treasure_coins coin_scatter treasure_copper treasure_gold treasure_silver""",
    "iron": "iron mail cooking_pot anvil grate_iron grate_partition metal_bar",
    "silver": "treasure_silver",
    "gold": "treasure_gold",
    "copper": "treasure_copper",
    "glass": "glass_material acid_flask water_flask healing_potion decor_bottle decor_potion_unknown",
    "ceramic": "jug pot urn oven",
    "cloth": "cloth bandage robe bedroll decor_cloak decor_gloves",
    "leather": "raw_leather leather waterskin decor_boots decor_armor_light",
    "paper": """parchment spellbook book book_ancient book_closed book_large
        map_drawing map_fragment note paper_scrap scroll scroll_magic
        crafting_manual paper_note strangers_diary""",
    "bone": "bones bones_pile remains skeleton_large skeleton_remains skull skeleton",
    "organic": """raw_leather leather waterskin cloth plant_fiber tinder rations
        mushroom medicinal_herb bitter_herb poison_herb dried_herbs healing_poultice
        carcass corpse bones bones_pile skeleton_large skeleton_remains skull""",
    "fiber": "plant_fiber rope improvised_rope rope_decor rope_taut tinder",
    "soil": "earth earth_gravel earth_loose earth_packed soil mud mud_deep swamp floor_dirty",
    "sand": "floor_sand",
    "liquid": "oil acid_flask ink poison poison_surface acid acid_deep hot_spring blood_pool blood_pool_large",
}
MATERIALS = {tag: frozenset(ids.split()) for tag, ids in MATERIALS.items()}
MAGIC_IDS = frozenset(
    """artifact artifact_amulet artifact_legendary artifact_powerful
    artifact_ring artifact_ring_enchanted artifact_stone artifact_unidentified
    artifact_unknown artifact_weak scroll_magic lantern_magic light_magic magic_fire
    magic_negative magic_positive magic_weak magic_zone magic_concentrated magic_energy
    magic_unstable magic_rift portal portal_active portal_dark portal_great portal_inactive
    portal_light portal_small portal_unstable teleport teleport_active teleport_inactive
    teleport_large teleport_unstable rune rune_active rune_air rune_circle rune_cross
    rune_earth rune_magic rune_observation rune_prohibition rune_protection rune_water
    rune_weak rune_destruction rune_fire trap_magic trap_rune ritual_circle ritual_circle_active""".split()
)


def curated_gameplay_tags(category, raw):
    """Authoring defaults for reviewed bundled IDs. Custom packs stay explicit."""
    tags = set(raw.get("tags", ()))
    identifier = raw["id"].removeprefix("terrain_")
    if category in {"equipment", "tiles", "objects", "points_of_interest", "traps"}:
        tags.update(curated_material_tags(raw["id"], tags))
        for tag, ids in MATERIALS.items():
            if identifier in ids:
                tags.add(tag)
        if "wooden" in tags or tags & {"cloth", "leather", "paper", "fiber"}:
            tags.add("flammable")
        if (
            "walls" in tags
            and "wooden" not in tags
            and identifier not in {"reinforced_support", "tower_support"}
        ):
            tags.add("stone")
        if "statues" in tags:
            tags.add("stone")
        if "plants" in tags or "fungi" in tags:
            tags.add("organic")
        if "water" in tags or identifier == "hot_spring":
            tags.update({"water", "liquid"})
        if tags & {"webs"}:
            tags.add("sticky")
        if identifier in MAGIC_IDS or "magic" in tags:
            tags.add("magic")
        if raw["id"] == "terrain_shrine" or identifier == "holy_symbol":
            tags.add("holy")
        if identifier in {
            "poison_herb",
            "poison",
            "poison_surface",
            "gas_toxic",
            "toxic_spores",
        }:
            tags.add("poison")
        if identifier in {
            "acid_reagent",
            "acid_flask",
            "acid",
            "acid_deep",
            "trap_acid",
        }:
            tags.add("acid")
        if identifier in {"medicinal_herb", "dried_herbs", "healing_poultice"}:
            tags.add("medicinal")
        if identifier in {
            "medicinal_herb",
            "bitter_herb",
            "poison_herb",
            "plant_fiber",
            "dried_herbs",
        }:
            tags.add("plants")
        if identifier in {"oil", "wood", "tinder"}:
            tags.add("fuel")
        if "mechanisms" in tags and identifier not in {"rope_decor", "rope_taut"}:
            tags.add("mechanism")
        if tags & {"portals", "teleports"}:
            tags.add("portal")
        if identifier in {
            "book",
            "book_ancient",
            "book_closed",
            "book_large",
            "spellbook",
            "crafting_manual",
            "strangers_diary",
        }:
            tags.add("book")
    if category == "equipment":
        if raw.get("category") == "tools" and (
            raw.get("check_aids")
            or identifier.endswith(("_tools", "_kit"))
            or identifier
            in {"pickaxe", "crowbar", "flint_and_steel", "master_lockpicks"}
        ):
            tags.add("tool")
        if raw.get("slot") == "armor" and any(
            e["kind"] == "armor_class" for e in raw.get("properties", ())
        ):
            tags.add("armor")
        if identifier in {"robe", "decor_boots", "decor_cloak", "decor_gloves"}:
            tags.add("clothing")
        if identifier.startswith("key_"):
            tags.add("key")
        if identifier == "mushroom":
            tags.update({"fungi", "edible", "food"})
        if identifier == "rations":
            tags.add("edible")
    if category == "races" and identifier in {"human", "elf", "dwarf"}:
        tags.update({"humanoid", "living", "organic"})
    if category == "monsters" and identifier == "goblin":
        tags.update({"living", "organic"})
    if category == "monsters" and identifier == "skeleton":
        tags.add("bone")
    if category == "spells":
        tags.add("magic")
    if category == "objects" and identifier == "hot_spring":
        tags.discard("fire")  # hot water is not a flame; retain its visual group.
    if "поджог" in tags:
        tags.add("ignite")  # retain the saved legacy tag and its existing permission.
    if category in {"equipment", "tiles", "objects", "points_of_interest", "traps"}:
        tags.update(curated_material_tags(raw["id"], tags))
    return tags


def classification(category, raw):
    """Includes derived fields, but never writes computed flags into author tags."""
    data = {**raw, "tags": sorted(curated_gameplay_tags(category, raw))}
    return interaction_tags(data, category=category)
