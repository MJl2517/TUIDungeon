"""Audit/import cell graphics. Dry run by default; --apply backs up packs first."""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import shutil

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import MODELS, Visual
from tuidungeon.content.migrations import migrate_map, migrate_document
from tuidungeon.content.symbols import glyph_ref, png_bytes


def drawings():
    """Small purpose-drawn silhouettes; coordinates are pixels, never game cells."""
    result = {}

    def draw(name, rects=(), lines=()):
        grid = [["0"] * 16 for _ in range(16)]
        for x, y, w, h in rects:
            for j in range(y, min(16, y + h)):
                for i in range(x, min(16, x + w)):
                    grid[j][i] = "1"
        for x, y, xx, yy in lines:
            steps = max(abs(xx - x), abs(yy - y), 1)
            for n in range(steps + 1):
                grid[round(y + (yy - y) * n / steps)][
                    round(x + (xx - x) * n / steps)
                ] = "1"
        result[name] = ["".join(r) for r in grid]

    draw("floor", [(3, 4, 1, 1), (10, 10, 1, 1), (6, 13, 1, 1)])
    draw(
        "wall",
        [
            (0, 0, 16, 1),
            (0, 7, 16, 1),
            (0, 15, 16, 1),
            (0, 0, 1, 16),
            (15, 0, 1, 16),
            (7, 0, 1, 8),
            (4, 7, 1, 9),
            (11, 7, 1, 9),
        ],
    )
    draw(
        "planks",
        [
            (0, 1, 16, 1),
            (0, 6, 16, 1),
            (0, 11, 16, 1),
            (0, 15, 16, 1),
            (5, 1, 1, 5),
            (12, 6, 1, 5),
            (7, 11, 1, 5),
        ],
    )
    draw(
        "door",
        [
            (3, 1, 10, 1),
            (3, 1, 1, 14),
            (12, 1, 1, 14),
            (3, 14, 10, 1),
            (10, 7, 1, 2),
            (6, 3, 1, 9),
        ],
    )
    draw(
        "door_open",
        [(2, 1, 11, 1), (2, 1, 1, 14), (12, 1, 1, 14), (5, 3, 1, 11), (8, 2, 1, 13)],
        [(5, 3, 8, 2), (5, 13, 8, 15)],
    )
    draw(
        "door_locked",
        [
            (3, 1, 10, 1),
            (3, 1, 1, 14),
            (12, 1, 1, 14),
            (3, 14, 10, 1),
            (7, 5, 3, 1),
            (7, 5, 1, 3),
            (9, 5, 1, 3),
            (6, 8, 5, 4),
        ],
    )
    draw(
        "bars", [(1, 1, 14, 1), (1, 14, 14, 1), *[(x, 1, 1, 14) for x in (2, 5, 9, 13)]]
    )
    draw(
        "bars_bent",
        [(1, 1, 14, 1), (1, 14, 14, 1), (2, 1, 1, 14), (13, 1, 1, 14)],
        [(5, 1, 3, 7), (3, 7, 5, 14), (10, 1, 12, 7), (12, 7, 10, 14)],
    )
    draw("slab", [(3, 1, 10, 14)], [(3, 1, 12, 14)])
    draw(
        "lamp",
        [
            (6, 1, 4, 1),
            (5, 2, 1, 3),
            (10, 2, 1, 3),
            (4, 5, 8, 1),
            (4, 6, 1, 7),
            (11, 6, 1, 7),
            (4, 13, 8, 2),
            (7, 8, 2, 3),
        ],
    )
    draw(
        "torch", [(7, 8, 2, 7), (5, 6, 6, 3), (6, 3, 4, 3), (7, 1, 2, 4), (9, 4, 2, 3)]
    )
    draw("candle", [(6, 6, 4, 8), (4, 14, 8, 1), (7, 2, 2, 3)])
    draw(
        "bed",
        [
            (2, 2, 1, 13),
            (13, 2, 1, 13),
            (3, 4, 10, 1),
            (3, 12, 10, 1),
            (4, 6, 3, 2),
            (3, 9, 10, 3),
        ],
    )
    draw("table", [(2, 5, 12, 3), (3, 8, 2, 7), (11, 8, 2, 7)])
    draw(
        "chair",
        [
            (4, 1, 1, 8),
            (10, 1, 1, 8),
            (4, 2, 7, 2),
            (3, 9, 9, 2),
            (4, 11, 1, 4),
            (10, 11, 1, 4),
        ],
    )
    draw(
        "shelf",
        [
            (2, 1, 1, 14),
            (13, 1, 1, 14),
            (2, 1, 12, 1),
            (2, 7, 12, 1),
            (2, 14, 12, 1),
            (4, 3, 2, 4),
            (8, 2, 2, 5),
            (4, 10, 5, 3),
        ],
    )
    draw(
        "chest",
        [
            (2, 5, 12, 1),
            (2, 5, 1, 9),
            (13, 5, 1, 9),
            (2, 13, 12, 1),
            (3, 9, 10, 1),
            (7, 8, 2, 4),
        ],
        [(2, 5, 5, 2), (5, 2, 10, 2), (10, 2, 13, 5)],
    )
    draw(
        "crate",
        [(2, 2, 12, 1), (2, 13, 12, 1), (2, 2, 1, 12), (13, 2, 1, 12)],
        [(3, 3, 12, 12), (3, 12, 12, 3)],
    )
    draw(
        "barrel",
        [
            (4, 2, 8, 1),
            (3, 3, 1, 10),
            (12, 3, 1, 10),
            (4, 13, 8, 1),
            (3, 5, 10, 1),
            (3, 10, 10, 1),
            (6, 3, 1, 10),
            (9, 3, 1, 10),
        ],
    )
    draw(
        "bag",
        [(6, 2, 4, 1), (5, 4, 6, 2), (3, 8, 1, 5), (12, 8, 1, 5), (4, 13, 8, 1)],
        [(5, 6, 3, 8), (10, 6, 12, 8)],
    )
    draw(
        "pot",
        [(5, 1, 6, 2), (6, 3, 4, 3), (3, 7, 1, 6), (12, 7, 1, 6), (4, 13, 8, 1)],
        [(6, 5, 3, 7), (9, 5, 12, 7)],
    )
    draw(
        "bottle",
        [
            (6, 1, 4, 2),
            (6, 3, 1, 3),
            (9, 3, 1, 3),
            (4, 7, 1, 7),
            (11, 7, 1, 7),
            (4, 14, 8, 1),
            (5, 10, 6, 3),
        ],
        [(6, 5, 4, 7), (9, 5, 11, 7)],
    )
    draw(
        "book",
        [
            (2, 2, 1, 12),
            (12, 2, 1, 12),
            (2, 2, 11, 1),
            (2, 13, 11, 1),
            (4, 3, 1, 10),
            (6, 5, 5, 1),
            (6, 8, 4, 1),
        ],
    )
    draw(
        "scroll",
        [
            (3, 2, 10, 1),
            (3, 3, 1, 10),
            (11, 3, 1, 10),
            (2, 12, 12, 2),
            (5, 5, 5, 1),
            (5, 8, 4, 1),
        ],
    )
    draw(
        "key",
        [
            (2, 3, 5, 1),
            (2, 7, 5, 1),
            (2, 3, 1, 5),
            (6, 3, 1, 5),
            (7, 5, 7, 1),
            (11, 6, 1, 3),
            (13, 6, 1, 2),
        ],
    )
    draw(
        "shield",
        [(3, 2, 10, 1), (3, 2, 1, 7), (12, 2, 1, 7), (7, 4, 1, 7), (5, 6, 6, 1)],
        [(3, 8, 7, 14), (12, 8, 7, 14)],
    )
    draw(
        "armor",
        [
            (5, 2, 6, 2),
            (2, 4, 3, 4),
            (11, 4, 3, 4),
            (4, 5, 1, 9),
            (10, 5, 1, 9),
            (4, 13, 7, 1),
        ],
    )
    draw("sword", [(6, 10, 6, 1), (8, 11, 2, 4)], [(8, 2, 8, 9), (9, 1, 9, 9)])
    draw("axe", [(7, 2, 2, 13), (9, 3, 5, 5), (3, 4, 3, 3)])
    draw("pickaxe", [(7, 6, 2, 9)], [(2, 5, 7, 2), (7, 2, 13, 5)])
    draw("tools", [(3, 2, 2, 5), (9, 10, 2, 4)], [(4, 6, 10, 12), (12, 2, 3, 13)])
    draw("bone", [(2, 2, 3, 3), (11, 11, 3, 3)], [(4, 4, 11, 11), (5, 4, 12, 11)])
    draw(
        "skull",
        [
            (4, 2, 8, 1),
            (2, 4, 1, 6),
            (13, 4, 1, 6),
            (3, 10, 10, 1),
            (5, 11, 6, 3),
            (4, 5, 3, 3),
            (9, 5, 3, 3),
            (7, 9, 2, 1),
        ],
    )
    draw(
        "gem",
        [],
        [
            (4, 3, 11, 3),
            (4, 3, 1, 7),
            (11, 3, 14, 7),
            (1, 7, 7, 14),
            (14, 7, 7, 14),
            (1, 7, 14, 7),
            (4, 3, 7, 14),
            (11, 3, 7, 14),
        ],
    )
    draw(
        "coin",
        [(4, 2, 8, 1), (2, 4, 1, 8), (13, 4, 1, 8), (4, 13, 8, 1), (7, 4, 2, 8)],
        [(2, 4, 4, 2), (11, 2, 13, 4), (2, 11, 4, 13), (11, 13, 13, 11)],
    )
    draw(
        "stairs",
        [
            (2, 2, 4, 2),
            (2, 4, 7, 2),
            (2, 6, 10, 2),
            (2, 8, 13, 2),
            (2, 10, 13, 2),
            (2, 12, 13, 2),
        ],
    )
    draw(
        "flower",
        [
            (7, 1, 2, 4),
            (3, 5, 4, 2),
            (9, 5, 4, 2),
            (7, 7, 2, 8),
            (4, 10, 3, 2),
            (9, 11, 3, 2),
        ],
    )
    draw("tree", [(6, 1, 4, 2), (4, 3, 8, 3), (2, 6, 12, 4), (7, 10, 2, 5)])
    draw(
        "fire",
        [(5, 10, 6, 3), (4, 7, 7, 3), (6, 4, 5, 3), (7, 1, 2, 4)],
        [(2, 14, 13, 14)],
    )
    draw(
        "water",
        [],
        [
            (1, 4, 4, 6),
            (4, 6, 8, 4),
            (8, 4, 12, 6),
            (1, 10, 4, 12),
            (4, 12, 8, 10),
            (8, 10, 14, 12),
        ],
    )
    draw(
        "spikes",
        [(1, 13, 14, 1)],
        [(2, 12, 4, 5), (4, 5, 6, 12), (7, 12, 9, 2), (9, 2, 11, 12), (12, 12, 14, 6)],
    )
    draw("altar", [(4, 3, 8, 2), (6, 5, 4, 6), (2, 11, 12, 3)])
    draw("anvil", [(1, 4, 14, 2), (4, 6, 7, 2), (6, 8, 3, 4), (3, 12, 10, 2)])
    draw(
        "rope",
        [],
        [(2, 3, 12, 3), (12, 3, 13, 6), (13, 6, 3, 9), (3, 9, 2, 12), (2, 12, 12, 12)],
    )
    draw(
        "food", [(3, 6, 10, 6), (4, 4, 8, 2), (5, 2, 6, 2), (4, 8, 2, 2), (8, 8, 2, 2)]
    )
    draw("staff", [(7, 4, 2, 11), (5, 1, 6, 2), (5, 2, 2, 3), (9, 2, 2, 3)])
    draw(
        "bow",
        [(5, 2, 1, 12)],
        [(5, 2, 10, 5), (10, 5, 12, 8), (12, 8, 10, 11), (10, 11, 5, 14)],
    )
    draw("boots", [(3, 2, 4, 9), (9, 2, 4, 9), (2, 11, 5, 3), (8, 11, 5, 3)])
    draw(
        "cloth",
        [(3, 2, 10, 1), (3, 2, 1, 11), (12, 2, 1, 11)],
        [(3, 12, 6, 10), (6, 10, 9, 12), (9, 12, 12, 10)],
    )
    draw(
        "wood",
        [(3, 4, 9, 7)],
        [(3, 3, 12, 3), (3, 12, 12, 12), (2, 4, 2, 11), (13, 4, 13, 11)],
    )
    draw(
        "ore",
        [],
        [
            (3, 4, 10, 2),
            (10, 2, 14, 7),
            (14, 7, 11, 13),
            (11, 13, 2, 12),
            (2, 12, 1, 7),
            (1, 7, 3, 4),
            (3, 4, 8, 8),
            (8, 8, 11, 13),
            (8, 8, 14, 7),
        ],
    )
    draw("magic", [(7, 1, 2, 14), (1, 7, 14, 2)], [(3, 3, 12, 12), (12, 3, 3, 12)])
    draw(
        "portal",
        [(6, 1, 4, 1), (3, 4, 1, 8), (12, 4, 1, 8), (6, 14, 4, 1)],
        [(3, 4, 6, 1), (9, 1, 12, 4), (3, 11, 6, 14), (9, 14, 12, 11)],
    )
    draw(
        "lever",
        [(3, 12, 10, 2), (6, 9, 4, 3), (10, 2, 3, 3)],
        [(7, 10, 11, 4), (8, 10, 12, 4)],
    )
    draw(
        "button",
        [(4, 3, 8, 1), (3, 4, 1, 8), (12, 4, 1, 8), (4, 12, 8, 1), (5, 5, 6, 6)],
    )
    draw(
        "gear",
        [
            (5, 3, 6, 1),
            (5, 12, 6, 1),
            (3, 5, 1, 6),
            (12, 5, 1, 6),
            (7, 1, 2, 4),
            (7, 11, 2, 4),
            (1, 7, 4, 2),
            (11, 7, 4, 2),
            (6, 6, 4, 4),
        ],
    )
    draw(
        "chain",
        [
            (2, 3, 6, 1),
            (2, 3, 1, 6),
            (7, 3, 1, 6),
            (2, 8, 6, 1),
            (8, 7, 6, 1),
            (8, 7, 1, 6),
            (13, 7, 1, 6),
            (8, 12, 6, 1),
        ],
    )
    draw(
        "goblin",
        [
            (3, 3, 10, 1),
            (2, 5, 1, 6),
            (13, 5, 1, 6),
            (4, 12, 8, 1),
            (4, 6, 3, 2),
            (9, 6, 3, 2),
            (6, 10, 4, 1),
            (0, 4, 2, 3),
            (14, 4, 2, 3),
        ],
    )
    draw("person", [(6, 1, 4, 4), (4, 6, 8, 5), (5, 11, 2, 4), (9, 11, 2, 4)])
    draw(
        "cloak",
        [(6, 1, 4, 2), (4, 3, 8, 2)],
        [(4, 4, 1, 14), (11, 4, 14, 14), (1, 14, 14, 14), (7, 5, 7, 12)],
    )
    draw("cart", [(2, 5, 12, 5), (3, 11, 3, 3), (10, 11, 3, 3), (1, 3, 1, 8)])
    draw(
        "barricade",
        [],
        [(1, 3, 14, 12), (1, 12, 14, 3), (1, 4, 14, 13), (1, 13, 14, 4)],
    )
    return result


def family(category, doc):
    name = doc["id"].removeprefix("terrain_")
    tests = [
        ("anvil", ("anvil",)),
        ("rope", ("rope",)),
        ("staff", ("staff", "pole")),
        ("bow", ("bow",)),
        ("boots", ("boots",)),
        ("food", ("rations", "meat", "mushroom", "gland")),
        (
            "cloth",
            ("cloth", "leather", "hide", "bandage", "poultice", "chitin", "silk"),
        ),
        ("wood", ("wood", "tinder", "branches", "fiber")),
        ("ore", ("iron", "mithril", "stone", "clay", "scrap", "glass_material")),
        (
            "magic",
            (
                "magic",
                "arcane",
                "light_",
                "spark",
                "dust",
                "resin",
                "reagent",
                "pigment",
            ),
        ),
        ("portal", ("portal", "teleport", "rift")),
        ("stairs", ("transition", "exit_")),
        ("lever", ("lever",)),
        ("button", ("button",)),
        ("gear", ("gear", "mechanism", "workpiece")),
        ("chain", ("chain",)),
        ("skull", ("skull", "corpse", "carcass")),
        ("cart", ("cart",)),
        ("table", ("nightstand",)),
        ("water", ("puddle",)),
        ("barricade", ("barricade", "barrier", "door_broken")),
        ("pickaxe", ("pickaxe",)),
        ("key", ("key", "lock")),
        ("lamp", ("lamp", "lantern")),
        ("torch", ("torch",)),
        ("candle", ("candle",)),
        ("bed", ("bed",)),
        ("chair", ("chair", "stool", "throne")),
        ("shelf", ("shelf", "cabinet", "bookcase")),
        ("chest", ("chest",)),
        ("crate", ("crate",)),
        ("barrel", ("barrel",)),
        ("bag", ("sack", "bag", "waterskin")),
        ("pot", ("pot", "urn", "jug", "vessel")),
        ("book", ("book", "diary", "manual")),
        ("scroll", ("scroll", "parchment", "note", "paper", "map_")),
        ("shield", ("shield",)),
        (
            "armor",
            ("armor", "mail", "robe", "cloak", "leather_boots", "gloves", "helmet"),
        ),
        ("sword", ("sword", "dagger", "rapier", "spear", "arrow", "bolt", "stake")),
        ("axe", ("axe", "hammer", "mace", "club")),
        ("tools", ("tool", "lockpick", "crowbar", "kit")),
        ("skull", ("skeleton", "remains")),
        ("bone", ("bone",)),
        ("coin", ("gold", "coin", "silver", "copper")),
        ("gem", ("gem", "jewel", "artifact", "amulet", "ring")),
        (
            "stairs",
            (
                "stairs",
                "steps",
            ),
        ),
        ("flower", ("flower", "herb")),
        ("tree", ("tree", "bush", "shrub")),
        ("table", ("table", "bench", "desk")),
        ("fire", ("fire", "lava", "forge", "oven")),
        ("water", ("water", "spring", "well", "current")),
    ]
    if category == "objects" and doc.get("brush", {}).get("door"):
        return "door"
    if category == "spells":
        return "magic"
    if category == "classes":
        return "magic" if "wizard" in name else "cloak" if "rogue" in name else "shield"
    if category == "races":
        return "person"
    if category == "backgrounds":
        return (
            "book"
            if any(x in name for x in ("sage", "scholar"))
            else "shield"
            if "soldier" in name
            else "tools"
        )
    if category == "monsters":
        return "goblin" if "goblin" in name else "skull"
    if name in ("flint_and_steel",):
        return "fire"
    if category == "objects" and name.startswith("door_"):
        return "door"
    if category == "equipment" and (
        doc.get("vessel")
        or any(
            x in name for x in ("potion", "flask", "oil", "poison", "extract", "ink")
        )
    ):
        return "bottle"
    for shape, words in tests:
        if any(word in name for word in words):
            return shape
    if category == "traps":
        return "spikes"
    if category == "points_of_interest" and doc.get("storage"):
        return "chest"
    if "altar" in name or "shrine" in name:
        return "altar"
    if name.startswith("floor"):
        return "planks" if "plank" in name else "floor"
    return None


def migrate(root, apply=False):
    import tcod.tileset
    import numpy as np

    project = Path(__file__).resolve().parents[1]
    root = Path(root).resolve()
    store = PackStore(root)
    before = {key: d.model_dump(mode="json") for key, d in store.documents.items()}
    pending, symbols, report = {}, {}, []
    font_meta = json.loads((project / "assets/fonts/glyphs.json").read_text())
    font = tcod.tileset.load_tilesheet(
        project / "assets/fonts/glyphs.png",
        font_meta["columns"],
        font_meta["rows"],
        font_meta["codepoints"],
    )
    import tcod.image
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        atlas = np.asarray(
            tcod.image.load(
                project / "assets/1 bit/Tilesheet/monochrome-transparent_packed.png"
            )
        )
    shapes = drawings()

    def add(identifier, name, glyph, pixels, group, source, reviewed=True):
        ref = "base:" + identifier
        raw = dict(
            schema_version=1,
            id=identifier,
            name=name,
            glyph=glyph,
            pixels=pixels,
            group=group,
            tags=[],
            reviewed=reviewed,
            source=source,
        )
        symbols.setdefault(ref, raw)
        return ref

    kenney_source = dict(
        name="Kenney 1-Bit Pack 1.2", license="CC0", location="assets/1 bit/License.txt"
    )
    for y in range(22):
        for x in range(49):
            tile = atlas[y * 16 : (y + 1) * 16, x * 16 : (x + 1) * 16]
            pixels = [
                "".join("1" if a > 127 else "0" for a in row)
                for row in tile[:, :, :3].max(axis=2)
            ]
            add(
                f"kenney_{x}_{y}",
                f"Kenney [{x}, {y}]",
                "?",
                pixels,
                "Неразобранное",
                {**kenney_source, "coordinates": [x, y]},
                False,
            )

    def character(char):
        ref = glyph_ref(char)
        if ref not in symbols:
            tile = (
                font[ord(char)]
                if ord(char) in font
                else np.zeros((font.tile_height, font.tile_width, 4), dtype=np.uint8)
            )
            yy = np.arange(16) * font.tile_height // 16
            xx = np.arange(16) * font.tile_width // 16
            pixels = [
                "".join("1" if a > 127 else "0" for a in row)
                for row in tile[yy[:, None], xx, 3]
            ]
            add(
                ref.split(":")[1],
                f"Текстовый знак {char!r} (U+{ord(char):04X})",
                char,
                pixels,
                "Текстовые знаки",
                dict(
                    name="Встроенный DejaVu/Noto",
                    license="Лицензии шрифтов в assets/fonts",
                    location="assets/fonts",
                ),
            )
        return ref

    for char in " @#.?X!†*~+':>|^/=$○abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789█▓▒░─│┌┐└┘├┤┬┴┼":
        character(char)
    hero = symbols["base:kenney_27_0"]
    add("hero", "Герой", "@", hero["pixels"], "Существа", hero["source"])

    def decorate(raw, category, suffix="", top=True):
        result = dict(raw)
        if ("glyph" in raw or "char" in raw) and (
            not raw.get("symbol")
            or top
            and "id" in raw
            and raw.get("symbol", "").startswith("base:glyph_")
            and family(category, raw)
        ):
            char = raw.get("glyph", raw.get("char", "?"))
            character(char)
            shape = family(category, raw) if top and "id" in raw else None
            if shape:
                identifier = f"visual_{category}_{raw['id']}{suffix}"
                result["symbol"] = add(
                    identifier,
                    raw.get("name", raw["id"]),
                    char,
                    shapes[shape],
                    raw.get("group") or category,
                    dict(
                        name="TUI Dungeon: ревизия графики",
                        license="Лицензия проекта",
                        location="scripts/migrate_symbols.py",
                    ),
                )
            else:
                result["symbol"] = character(char)
            report.append(
                dict(
                    category=category,
                    name=raw.get("name", suffix),
                    symbol=result["symbol"],
                    method=shape or "text",
                )
            )
        if (
            top
            and category == "objects"
            and raw.get("brush", {}).get("door")
            and not raw.get("state_symbols")
        ):
            material = raw["brush"]["door"]["material"]
            states = (
                ["closed"]
                if material == "stone"
                else ["closed", "locked", "open"]
                + (["bent"] if material == "bars" else [])
            )
            glyphs = {
                "closed": raw.get("glyph", "+"),
                "locked": "X",
                "open": "/",
                "bent": "%",
            }
            result["state_symbols"] = {}
            for state in states:
                shape = (
                    "slab"
                    if material == "stone"
                    else "bars_bent"
                    if state == "bent"
                    else "door_open"
                    if state == "open"
                    else "door_locked"
                    if state == "locked"
                    else "bars"
                    if material == "bars"
                    else "door"
                )
                result["state_symbols"][state] = add(
                    f"door_{material}_{state}",
                    f"{raw['name']}: {state}",
                    glyphs[state],
                    shapes[shape],
                    "Двери",
                    dict(
                        name="TUI Dungeon: состояния дверей", license="Лицензия проекта"
                    ),
                )
            result["symbol"] = result["state_symbols"]["closed"]
        for k, v in list(result.items()):
            if isinstance(v, dict):
                result[k] = decorate(v, category, suffix + "_" + k, False)
            elif isinstance(v, list):
                result[k] = [
                    decorate(x, category, suffix + f"_{k}_{i}", False)
                    if isinstance(x, dict)
                    else x
                    for i, x in enumerate(v)
                ]
                if k == "layers":
                    for layer in result[k]:
                        layer["cells"] = [
                            [
                                decorate(c, category, "cell", False) if c else None
                                for c in row
                            ]
                            for row in layer["cells"]
                        ]
        return result

    for key, doc in store.documents.items():
        category, ref = key
        if category == "symbols":
            continue
        raw = store.read_json(store.paths[key])
        raw = (
            migrate_map(raw) if category == "maps" else migrate_document(raw, category)
        )
        if isinstance(doc, Visual) or category in ("art", "maps"):
            updated = decorate(raw, category)
            # Visual classes with default glyphs still need an explicit library link.
            if isinstance(doc, Visual) and not updated.get("symbol"):
                updated = decorate({**updated, "glyph": doc.glyph}, category)
            if updated != raw:
                pending[store.paths[key]] = updated
    for ref, raw in symbols.items():
        key = ("symbols", ref)
        if key not in store.documents:
            pending[root / "base/symbols" / (raw["id"] + ".json")] = raw
    candidate = dict(store.documents)
    for path, raw in pending.items():
        category = path.relative_to(root).parts[1]
        ref = path.relative_to(root).parts[0] + ":" + raw["id"]
        candidate[category, ref] = MODELS[category].model_validate(raw)
    store.validate_references(candidate, store.manifests)

    def mechanics(raw):
        if isinstance(raw, dict):
            return {
                k: mechanics(v)
                for k, v in raw.items()
                if k not in {"glyph", "char", "symbol", "state_symbols"}
            }
        if isinstance(raw, list):
            return [mechanics(v) for v in raw]
        return raw

    for key, old in before.items():
        if mechanics(old) != mechanics(candidate[key].model_dump(mode="json")):
            raise RuntimeError(f"Миграция изменила механики: {key}")
    backup = None
    if apply and pending:
        backup = (
            project
            / "backups"
            / ("symbols_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        )
        shutil.copytree(root, backup)
        for path, raw in pending.items():
            PackStore.atomic_json(path, raw)
        PackStore(root)
    output = dict(
        changed=len(pending),
        assignments=len(report),
        methods=dict(Counter(r["method"] for r in report)),
        backup=str(backup) if backup else None,
        entries=report,
    )
    if apply:
        reports = project / "docs/symbol-audit"
        reports.mkdir(exist_ok=True)
        report_file = reports / "assignments.json"
        previous = json.loads(report_file.read_text()) if report_file.exists() else {}
        changes = {(r["category"], r["symbol"]): r for r in previous.get("entries", [])}
        changes.update({(r["category"], r["symbol"]): r for r in report})
        output["entries"] = list(changes.values())
        output["backups"] = sorted(
            str(p.relative_to(project)) for p in (project / "backups").glob("symbols_*")
        )
        audit = []
        for (cat, ref), doc in sorted(candidate.items()):
            if not isinstance(doc, Visual):
                continue
            links = {
                "symbol": doc.symbol,
                **{"variants." + str(n): v.symbol for n, v in enumerate(doc.variants)},
                **{"state_symbols." + k: v for k, v in doc.state_symbols.items()},
            }
            for field, link in links.items():
                target = candidate.get(("symbols", link))
                audit.append(
                    dict(
                        category=cat,
                        ref=ref,
                        name=doc.name,
                        field=field,
                        symbol=link,
                        reviewed=bool(target and target.reviewed),
                    )
                )
        if not all(row["reviewed"] for row in audit):
            raise RuntimeError(
                "В поставляемом контенте остались непроверенные назначения"
            )
        PackStore.atomic_json(report_file, output)
        PackStore.atomic_json(
            reports / "inventory.json",
            dict(
                definitions=sum(isinstance(d, Visual) for d in candidate.values()),
                assignments=audit,
            ),
        )
        curated = [
            (ref, d)
            for (cat, ref), d in candidate.items()
            if cat == "symbols" and d.reviewed and not ref.startswith("base:glyph_")
        ]
        for start in range(0, len(curated), 128):
            batch = curated[start : start + 128]
            rows = [
                [bytes((17, 21, 27, 255))] * (16 * 16)
                for _ in range(((len(batch) + 15) // 16) * 16)
            ]
            for n, (_, doc) in enumerate(batch):
                for y, row in enumerate(doc.pixels):
                    for x, c in enumerate(row):
                        if c == "1":
                            rows[n // 16 * 16 + y][n % 16 * 16 + x] = bytes(
                                (237, 200, 117, 255)
                            )
            (reports / f"sheet_{start // 128 + 1}.png").write_bytes(png_bytes(rows, 4))
        PackStore.atomic_json(
            reports / "sheets.json",
            dict(order=[ref for ref, _ in curated], columns=16, cells_per_sheet=128),
        )
    print(
        json.dumps(
            {k: v for k, v in output.items() if k != "entries"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packs-dir", type=Path, default=DEFAULT_PACKS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    migrate(args.packs_dir, args.apply)
