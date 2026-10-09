"""Import the curated scene tiles; existing project files are never overwritten."""

import argparse
from collections import defaultdict
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import TileDocument
from tuidungeon.content.materials import curated_material_tags


# Each list follows the bundled reference's order; explicit IDs stay readable.
# Creatures, HUD symbols and branded/numbered TUI objects are not terrain.
SECTIONS = {
    "СТЕНЫ И АРХИТЕКТУРА": (
        "walls",
        "Стены и архитектура",
        """
        wall wall_massive wall_thick wall_damaged wall_crumbling wall_block
        wall_hollow_block wall_reinforced wall_lattice wall_vertical wall_horizontal
        wall_corner_nw wall_corner_ne wall_corner_sw wall_corner_se
        wall_branch_e wall_branch_w wall_branch_s wall_branch_n wall_cross
        wall_double_vertical wall_double_horizontal wall_double_corner_nw
        wall_double_corner_ne wall_double_corner_sw wall_double_corner_se
        wall_double_branch_e wall_double_branch_w wall_double_branch_s
        wall_double_branch_n wall_double_cross wall_stub_s wall_stub_n
        wall_stub_w wall_stub_e wall_diagonal_up wall_diagonal_down wall_beams
        wooden_support reinforced_support pillar pillar_round pillar_massive
        pillar_ornate pillar_carved tower_support
    """,
    ),
    "ПОЛ": (
        "floors",
        "Полы",
        """
        floor floor_dirty floor_dusty floor_litter floor_smooth floor_tiles
        floor_mosaic floor_gravel floor_pebbles floor_polished floor_sand
        floor_rough floor_dark floor_planks floor_boardwalk floor_uneven_planks
        floor_slab floor_pavers floor_striped_tiles floor_diagonal_tiles
        floor_worn_tiles floor_ornate_tiles
    """,
    ),
    "ПРОПАСТИ, ЯМЫ И ВЫСОТА": (
        "height",
        "Пропасти и рельеф",
        """
        chasm_deep chasm_bottomless fissure depression descent ascent
        pit_small pit_deep pit_large pit_debris pit_dangerous slope_down slope_up
        slope_left slope_right height_stairs_down height_stairs_up
        slope_steep_down slope_steep_up steps_left steps_right
    """,
    ),
    "ДВЕРИ И ПРОХОДЫ": (
        "doors",
        "Двери и проходы",
        """
        door_closed door_open door_vertical door_horizontal door_wooden
        door_open_wooden door_locked door_unlocked door_barricaded door_secret
        door_stone door_massive door_grate iron_portcullis passage_blocked door_broken
    """,
    ),
    "РЕШЁТКИ И ОГРАДЫ": (
        "fences",
        "Решётки и ограды",
        """
        grate_vertical grate_horizontal grate_dense fence_wooden fence_planks
        grate_iron grate_partition gate_grated metal_bar
    """,
    ),
    "ВОДА": (
        "water",
        "Вода",
        """
        water_shallow water_deep water_flowing water_ripple water_muddy water_calm
        waterfall current_south current_north current_east current_west
        puddle puddle_small
    """,
    ),
    "ЛАВА И ОГОНЬ": (
        "fire",
        "Лава и огонь",
        """
        lava lava_bubbling lava_flow fire fire_large fire_small sparks magic_fire hot_spring
    """,
    ),
    "ЛЁД И СНЕГ": (
        "ice",
        "Лёд и снег",
        """
        ice ice_thick ice_cracked frost snow snow_deep snow_packed ice_crystals
    """,
    ),
    "ЗЕМЛЯ И ПЕЩЕРЫ": (
        "earth",
        "Земля и пещеры",
        """
        earth earth_loose earth_gravel earth_packed stone_small cliff boulder
        boulder_large stone_pale stone_dark mud mud_deep swamp
    """,
    ),
    "РАСТИТЕЛЬНОСТЬ": (
        "plants",
        "Растительность",
        """
        grass_tall grass_short grass_dry shrubs tree_clover tree_dead tree_branches
        tree tree_large tree_young bush bush_dry flowers flower_blooming vines vines_dense
    """,
    ),
    "ГРИБЫ": (
        "fungi",
        "Грибы",
        """
        mushroom_large mushroom mushroom_cap mushroom_small mushroom_thin mushroom_glowing
    """,
    ),
    "РУИНЫ И МУСОР": (
        "ruins",
        "Руины и мусор",
        """
        rubble refuse stone_chips litter shards broken_objects rubble_large
        rubble_blocked ruined_masonry rubble_dust
    """,
    ),
    "МЕБЕЛЬ": (
        "furniture",
        "Мебель",
        """
        table table_small table_long chair stool throne bed bedroll bench
        cabinet nightstand bookcase shelf desk
    """,
    ),
    "КОНТЕЙНЕРЫ": (
        "containers",
        "Контейнеры",
        """
        chest chest_open chest_treasure chest_locked barrel barrel_large barrel_small
        urn pot jug vessel_large crate crate_closed crate_reinforced sack sack_large
    """,
    ),
    "СОКРОВИЩА": (
        "treasure",
        "Сокровища",
        """
        treasure_gold treasure_coins treasure_jewels gem gem_large gem_raw coin_scatter
        treasure_gold_mark treasure_silver treasure_copper jewelry ring amulet
    """,
    ),
    "ОРУЖИЕ": (
        "weapon_decor",
        "Декорации: оружие",
        """
        decor_sword decor_dagger decor_greatsword decor_spear decor_rapier decor_staff
        decor_mace decor_bow decor_longbow decor_arrow decor_bolt decor_hammer
        decor_axe decor_greataxe decor_halberd decor_sickle
    """,
    ),
    "БРОНЯ И ЭКИПИРОВКА": (
        "armor_decor",
        "Декорации: снаряжение",
        """
        decor_shield_left decor_shield_right decor_shield_round decor_shield_large
        decor_armor decor_armor_light decor_armor_heavy decor_helmet decor_boots
        decor_gloves decor_cloak
    """,
    ),
    "РАСХОДНИКИ": (
        "supplies_decor",
        "Декорации: припасы",
        """
        decor_potion decor_potion_small decor_potion_unknown decor_food decor_meal
        decor_rations decor_oil decor_bottle
    """,
    ),
    "МАГИЧЕСКИЕ ПРЕДМЕТЫ": (
        "artifacts",
        "Артефакты",
        """
        artifact artifact_powerful artifact_weak artifact_legendary artifact_unknown
        artifact_amulet artifact_ring artifact_ring_enchanted artifact_stone
        artifact_potion artifact_unidentified
    """,
    ),
    "КНИГИ И ДОКУМЕНТЫ": (
        "books",
        "Книги и документы",
        """
        scroll scroll_magic book book_large book_closed book_ancient note paper_scrap
        map_drawing map_fragment
    """,
    ),
    "СВЕТ": (
        "lighting_decor",
        "Источники света: рисунки",
        """
        candle torch_decor torch_wall light_source light_magic light_bright lantern lantern_magic
    """,
    ),
    "ЛОВУШКИ": (
        "trap_decor",
        "Ловушки: рисунки",
        """
        spikes spikes_large spikes_hidden trap_mechanical trap_small danger_mark
        suspicious_floor pressure_plate pressure_plate_active pressure_plate_stone
        door_trap wall_falling arrow_slit arrow_slit_barrage trap_magic trap_rune
        trap_deadly trap_flood trap_acid cave_in
    """,
    ),
    "РУНЫ": (
        "runes",
        "Руны",
        """
        rune rune_cross rune_destruction rune_circle rune_active rune_observation
        rune_prohibition rune_protection rune_fire rune_water rune_air rune_earth
        rune_magic rune_weak
    """,
    ),
    "АЛТАРИ И РЕЛИГИОЗНЫЕ ОБЪЕКТЫ": (
        "shrines",
        "Алтари и святыни",
        """
        altar shrine altar_large holy_symbol temple_symbol ancient_cross altar_sun
        altar_moon sacrificial_bowl ritual_circle ritual_circle_active
    """,
    ),
    "СТАТУИ": (
        "statues",
        "Статуи",
        """
        statue statue_small statue_human statue_dark statue_massive statue_beast
    """,
    ),
    "КОСТИ И ТРУПЫ": (
        "remains",
        "Кости и останки",
        """
        remains bones bones_pile skull skeleton_remains skeleton_large corpse corpse_humanoid carcass
    """,
    ),
    "КРОВЬ": (
        "blood",
        "Кровь",
        """
        blood_drops blood_tracks blood_splashes blood_pool blood_pool_large blood_fresh
    """,
    ),
    "СЛЕДЫ": (
        "tracks",
        "Следы",
        """
        tracks_faint tracks tracks_muddy tracks_east tracks_west tracks_north tracks_south
    """,
    ),
    "ЦЕПИ, ВЕРЁВКИ И МЕХАНИЗМЫ": (
        "mechanisms",
        "Механизмы",
        """
        chain chain_heavy rope_decor rope_taut mechanism_wheel mechanism gears
        lever lever_lowered lever_on lever_off button button_round button_pressed
    """,
    ),
    "ПОРТАЛЫ": (
        "portals",
        "Порталы",
        """
        portal portal_small portal_inactive portal_dark portal_active portal_great
        portal_unstable magic_rift portal_light
    """,
    ),
    "МАГИЧЕСКИЕ ЗОНЫ": (
        "magic",
        "Магические зоны",
        """
        magic_energy magic_positive magic_negative magic_unstable magic_zone
        magic_concentrated magic_weak
    """,
    ),
    "ГАЗ, ДЫМ И ТУМАН": (
        "gas",
        "Газ, дым и туман",
        """
        fog fog_dense smoke smoke_dense gas_toxic dust_cloud
    """,
    ),
    "КИСЛОТА И ЯД": (
        "acid",
        "Кислота и яд",
        """
        acid acid_deep poison poison_surface toxic_spores
    """,
    ),
    "ПАУТИНА И СЛИЗЬ": (
        "webs",
        "Паутина и слизь",
        """
        web web_dense web_sticky slime slime_deep slime_trail
    """,
    ),
    "ЛЕСТНИЦЫ И ПЕРЕХОДЫ": (
        "stairs",
        "Лестницы и переходы",
        """
        stairs_up stairs_down transition_up transition_down exit_up exit_down
        transition_previous transition_next
    """,
    ),
    "ТЕЛЕПОРТЫ": (
        "teleports",
        "Телепорты",
        """
        teleport teleport_large teleport_unstable teleport_inactive teleport_active
    """,
    ),
    "ЗАМКИ И КЛЮЧИ": (
        "keys",
        "Замки и ключи",
        """
        key_decor key_important key_ancient key_unicode key_special lock mechanism_locked
        skip_key_1 skip_key_2 skip_key_3 skip_key_4 skip_key_5 skip_key_6 skip_key_7
    """,
    ),
    "ТОЧКИ ИНТЕРЕСА": (
        "markers",
        "Метки мест",
        """
        marker_important marker_unknown marker_interest marker_unique marker_treasure
    """,
    ),
}

PALETTE = {
    "тёмно-серый": 8,
    "серый": 246,
    "светло-серый": 250,
    "белый": 7,
    "ярко-белый": 15,
    "коричневый": 130,
    "жёлто-коричневый": 136,
    "жёлтый": 3,
    "ярко-жёлтый": 11,
    "светло-жёлтый": 229,
    "зелёный": 2,
    "светло-зелёный": 10,
    "ярко-зелёный": 46,
    "синий": 4,
    "светло-голубой": 117,
    "ярко-голубой": 14,
    "красный": 1,
    "тёмно-красный": 88,
    "ярко-красный": 9,
    "пурпурный": 5,
    "ярко-пурпурный": 13,
    "светло-фиолетовый": 183,
}

# Hazardous terrain blocks movement until an author adds suitable mechanics.
# Gates/grates block movement but transmit light. Low props may host POIs.
SOLID = {
    "door_closed",
    "door_vertical",
    "door_horizontal",
    "door_wooden",
    "door_locked",
    "door_unlocked",
    "door_barricaded",
    "door_secret",
    "door_stone",
    "door_massive",
    "passage_blocked",
    "cliff",
    "boulder",
    "boulder_large",
    "stone_pale",
    "stone_dark",
    "tree_clover",
    "tree_branches",
    "tree",
    "tree_large",
    "vines_dense",
    "mushroom_large",
    "rubble_large",
    "rubble_blocked",
    "ruined_masonry",
    "cabinet",
    "bookcase",
    "statue",
    "statue_human",
    "statue_dark",
    "statue_massive",
    "statue_beast",
    "smoke",
    "fog_dense",
    "smoke_dense",
}
OBSTACLES = {
    "chasm_deep",
    "chasm_bottomless",
    "fissure",
    "pit_small",
    "pit_deep",
    "pit_large",
    "pit_debris",
    "pit_dangerous",
    "water_deep",
    "waterfall",
    "lava",
    "lava_bubbling",
    "lava_flow",
    "fire",
    "fire_large",
    "fire_small",
    "magic_fire",
    "acid",
    "acid_deep",
    "slime_deep",
    "tree_dead",
    "tree_young",
    "mushroom_cap",
    "table",
    "table_small",
    "table_long",
    "chair",
    "stool",
    "throne",
    "bed",
    "bedroll",
    "bench",
    "nightstand",
    "shelf",
    "desk",
    "statue_small",
    "door_grate",
    "iron_portcullis",
    "spikes_large",
}
VISUAL_MECHANICS = {
    "containers": "Для содержимого и открытия добавьте точку интереса/испытание.",
    "lighting_decor": "Для настоящего освещения добавьте источник света в слое карты «Источники света».",
    "fungi": "Свечение и особые эффекты настраиваются отдельно через источники света и события.",
    "trap_decor": "Это видимая декорация. Скрытость, срабатывание и урон задайте размещением ловушки.",
    "portals": "Для перехода добавьте служебную точку перехода на другую карту.",
    "teleports": "Для телепортации добавьте служебную точку перехода на другую карту.",
    "stairs": "Направление показано рисунком; настоящий переход задаётся служебной точкой карты.",
    "height": "Высота и падение не рассчитываются; разрешённые склоны — обычные проходимые клетки.",
    "keys": "Это рисунок. Для подбираемого ключа разместите экземпляр снаряжения.",
    "weapon_decor": "Для подбора и свойств оружия разместите экземпляр снаряжения.",
    "armor_decor": "Для подбора и экипировки разместите экземпляр снаряжения.",
    "supplies_decor": "Для подбора и расходования припасов разместите экземпляр снаряжения.",
    "treasure": "Для получения сокровищ добавьте предмет или точку интереса с наградой.",
    "fire": "Свечение, урон и лечение задаются отдельно источниками света, ловушками и событиями.",
    "ice": "Скольжение и замедление не добавляются рисунком.",
    "acid": "Отравление и урон задаются отдельными ловушками и событиями.",
    "webs": "Замедление, урон и прочие последствия задаются отдельными событиями.",
    "water": "Плавание и перемещение течением не рассчитываются рисунком.",
    "gas": "Урон и отравление задаются отдельно; непрозрачные облака закрывают обзор маской.",
    "mechanisms": "Чтобы переключатель действовал, добавьте точку интереса с испытанием.",
    "doors": "Закрытые двери неподвижны; открывание и смена состояния требуют отдельной механики.",
}


def parse_source(path):
    rows = defaultdict(list)
    section = ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        else:
            parts = line.split(" - ")
            if len(parts) == 3 and len(parts[0]) == 1:
                rows[section].append(parts)
    return rows


def curated_tiles(source):
    rows = parse_source(source)
    result = []
    for section, (folder, group, identifiers) in SECTIONS.items():
        ids = identifiers.split()
        if len(ids) != len(rows[section]):
            raise ValueError(
                f"Раздел {section}: список изменён; проверьте соответствие ID"
            )
        for identifier, (glyph, name, palette) in zip(ids, rows[section]):
            if identifier.startswith("skip_") or identifier == "corpse_humanoid":
                continue
            # Wide punctuation and the hero's @ are inappropriate terrain glyphs.
            glyph = {
                "water_calm": "∿",
                "mechanism": "⊞",
                "portal_unstable": "⊘",
                "teleport_unstable": "⊗",
            }.get(identifier, glyph)
            walkable = not (
                identifier in OBSTACLES
                or folder == "walls"
                or folder == "fences"
                or identifier in SOLID
            )
            blocks_sight = folder == "walls" or identifier in SOLID
            if identifier in {"wall_lattice", "wall_beams", "wooden_support"}:
                blocks_sight = False
            if folder == "gas":
                walkable = True
            if identifier == "waterfall":
                blocks_sight = True
            tags = [
                folder,
                "walkable" if walkable else "obstacle",
                "opaque" if blocks_sight else "transparent",
            ]
            hint = VISUAL_MECHANICS.get(folder, "")
            description = (
                f"{group}. {name.capitalize()}. "
                + ("Проходимая клетка. " if walkable else "Преграда движению. ")
                + (
                    "Закрывает обзор и свет. "
                    if blocks_sight
                    else "Пропускает обзор и свет. "
                )
                + hint
            )
            doc = TileDocument(
                id=identifier,
                name=name[:1].upper() + name[1:],
                group=group,
                glyph=glyph,
                foreground={
                    "chest_treasure": 11,
                    "marker_treasure": 11,
                    "bed": 130,
                    "decor_mace": 250,
                    "blood_drops": 88,
                    "blood_tracks": 88,
                    "blood_splashes": 88,
                    "blood_pool": 88,
                    "blood_pool_large": 88,
                    "blood_fresh": 9,
                }.get(identifier, PALETTE[palette]),
                background=None,
                walkable=walkable,
                blocks_sight=blocks_sight,
                tags=tags + sorted(curated_material_tags(identifier, tags)),
                description=description.strip(),
            )
            result.append((folder, doc))
    ids = [doc.id for _, doc in result]
    if len(ids) != len(set(ids)):
        raise ValueError("Повторные ID в каталоге")
    return result


def install(source, pack):
    pack = Path(pack)
    if not (pack / "manifest.json").is_file():
        raise ValueError("Нужен существующий пакет с manifest.json")
    # Validate everything before writing, including existing documents.
    documents = curated_tiles(source)
    existing = {
        TileDocument.model_validate(PackStore.read_json(p)).id
        for p in (pack / "tiles").rglob("*.json")
    }
    pending = []
    for folder, document in documents:
        from tuidungeon.content.migrations import door_alias, compatibility

        if pack.name == "base" and (pack / "objects").is_dir() and ("base:" + document.id in compatibility()["tiles"] or door_alias("base:" + document.id)):
            continue  # Native objects must not be reintroduced as tile copies.
        if door_alias("base:" + document.id) and "door_wood" in existing:
            continue  # Consolidated libraries configure door instances on the map.
        if document.id in existing:
            continue
        target = pack / "tiles" / folder / f"{document.id}.json"
        if target.exists():
            raise ValueError(f"Файл уже существует с другим ID: {target}")
        pending.append((target, document))
    for target, document in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        PackStore.atomic_json(target, document.model_dump(mode="json"))
    return len(pending)


def main():
    parser = argparse.ArgumentParser(
        description="Добавить тайлы, сохранив существующие файлы"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "docs/reference/tui_dungeon_tileset_colored.txt",
    )
    parser.add_argument("--pack", type=Path, default=PROJECT_ROOT / "packs/base")
    args = parser.parse_args()
    print(f"Добавлено тайлов: {install(args.source, args.pack)}")


if __name__ == "__main__":
    main()
