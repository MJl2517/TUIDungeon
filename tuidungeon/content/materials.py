"""Reviewed material assignments for the bundled catalog, used by import tools.

These are authoring defaults, not runtime inference. Custom packs and instance
overrides remain free to describe fireproof wood or metal furniture explicitly.
"""

from ..domain.materials import FLAMMABLE, WOODEN

WOODEN_OBJECTS = frozenset(
    """
bed bench bookcase cabinet chair desk nightstand shelf stool table table_long
table_small throne barrel barrel_large barrel_small chest chest_locked chest_open
chest_treasure crate crate_closed crate_reinforced fence_planks fence_wooden
door_wood door_barricaded door_broken door_closed door_open door_vertical
door_horizontal door_wooden door_open_wooden door_locked door_unlocked door_trap
floor_planks floor_boardwalk floor_uneven_planks wooden_support wall_beams
tree tree_branches tree_clover tree_dead tree_large tree_young
decor_arrow decor_bolt decor_axe decor_bow decor_greataxe decor_halberd
decor_hammer decor_longbow decor_mace decor_sickle decor_spear decor_staff
decor_shield_large decor_shield_left decor_shield_right decor_shield_round
torch_decor torch_wall staff shield torch pickaxe
""".split()
)

FLAMMABLE_OBJECTS = WOODEN_OBJECTS | frozenset(
    """
bedroll ink leather oil parchment rations robe rope spellbook
book book_ancient book_closed book_large map_drawing map_fragment note paper_scrap
scroll scroll_magic sack sack_large candle rope_decor rope_taut
decor_armor_light decor_boots decor_cloak decor_gloves decor_food decor_meal
decor_rations decor_oil bush bush_dry flower_blooming flowers grass_dry
grass_short grass_tall shrubs vines vines_dense mushroom mushroom_cap
mushroom_glowing mushroom_large mushroom_small mushroom_thin
web web_dense web_sticky floor_litter broken_objects litter refuse corpse
corpse_humanoid carcass
""".split()
)


def curated_material_tags(identifier, tags=()):
    identifier = identifier.removeprefix("terrain_")
    result = set()
    if identifier in WOODEN_OBJECTS:
        result.add(WOODEN)
    if identifier in FLAMMABLE_OBJECTS or set(tags) & {
        "furniture",
        "books",
        "plants",
        "fungi",
    }:
        result.add(FLAMMABLE)
    return result
