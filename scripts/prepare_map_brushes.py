"""Attach reusable mechanics to the curated base tiles without changing maps."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tuidungeon.content.packs import PackStore
from tuidungeon.content.schemas import MODELS, TileBrush, TileLight


def prepare(root=PROJECT_ROOT / "packs"):
    store = PackStore(root)
    candidate = dict(store.documents)
    writes = {}
    linked = 0

    def add(category, raw):
        document = MODELS[category].model_validate(raw)
        key = (category, "base:" + document.id)
        if key not in candidate:
            candidate[key] = document
            writes[key] = (
                store.root / "base" / category / "terrain" / (document.id + ".json"),
                document,
            )
        return key[1]

    for (category, ref), tile in list(store.documents.items()):
        if category != "tiles" or not ref.startswith("base:") or not tile.tags:
            continue
        if any(tile.brush.model_dump().values()):
            continue  # Preserve author-customized recipes on repeated runs.
        tags = set(tile.tags)
        identifier = "terrain_" + tile.id
        visual = dict(
            id=identifier,
            name=tile.name,
            glyph=tile.glyph,
            foreground=tile.foreground,
            background=tile.background,
        )
        brush = {}
        hint = ""
        walkable = tile.walkable
        glyph = tile.glyph

        hazard = tags & {"trap_decor", "acid", "fire"} or tile.id in {
            "gas_toxic",
            "toxic_spores",
            "magic_negative",
            "rune_destruction",
            "rune_fire",
        }
        if hazard and tile.id not in {"sparks", "hot_spring", "danger_mark"}:
            poisoned = tags & {"acid"} or tile.id in {"gas_toxic", "toxic_spores"}
            effects = [{"kind": "damage", "dice": "1d4", "amount": 1}]
            if poisoned:
                effects.append(
                    {"kind": "condition", "condition": "poisoned", "duration": 10}
                )
            hidden = tile.id in {"spikes_hidden", "suspicious_floor"}
            brush["trap"] = add(
                "traps",
                dict(
                    **visual,
                    description="Проверка при входе; провал причиняет 1d4 + 1 урона."
                    + (" Отравление отображается как состояние." if poisoned else ""),
                    hidden=hidden,
                    ability="constitution" if poisoned else "dexterity",
                    difficulty=12,
                    failure=effects,
                    repeatable=not bool(tags & {"trap_decor"}),
                ),
            )
            walkable = True
            if hidden:
                glyph = "."
            hint = "При входе: проверка СЛ 12; при провале 1d4 + 1 урона. " + (
                "Повторяется при каждом входе."
                if not tags & {"trap_decor"}
                else "Одноразовая ловушка."
            )

        if tags & {"lighting_decor", "fire"} or tile.id in {
            "mushroom_glowing",
            "rune_active",
            "ritual_circle_active",
            "magic_energy",
            "magic_concentrated",
        }:
            radius = 3 if tile.id in {"candle", "sparks", "mushroom_glowing"} else 6
            brush["light"] = TileLight(
                radius=radius, bright_radius=max(1, radius // 2)
            ).model_dump()
            hint += f" Источник света: радиус {radius} клеток."

        if (
            tags & {"containers", "treasure", "shrines", "books", "markers"}
            or ("runes" in tags and not brush.get("trap"))
            or tile.id in {"magic_positive", "magic_zone", "magic_weak"}
        ):
            if "containers" in tags and tile.id in {
                "chest_locked",
                "chest_reinforced",
                "crate_reinforced",
            }:
                raw = store.get("challenges", "base:locked_chest").model_dump(
                    mode="json"
                )
                raw.update(
                    id=identifier,
                    name=tile.name,
                    text=f"{tile.name}. Замок закрыт: выберите способ открытия.",
                )
            else:
                if tags & {"containers", "treasure"}:
                    effects = [
                        {
                            "kind": "gold",
                            "dice": "1d6",
                            "amount": 4 if "treasure" in tags else 0,
                        }
                    ]
                    text = "Забрать ценности"
                    narrative = "Здесь могут остаться ценности. Что вы сделаете?"
                elif tags & {"shrines"} or tile.id == "magic_positive":
                    effects = [{"kind": "heal", "amount": 6}]
                    text = "Принять благословение (восстановить до 6 HP)"
                    narrative = "Тихое святилище хранит исцеляющую силу."
                else:
                    effects = [{"kind": "experience", "amount": 3}]
                    text = "Изучить (3 опыта)"
                    narrative = (
                        "Знаки и подробности могут рассказать больше об этом месте."
                    )
                raw = dict(
                    id=identifier,
                    name=tile.name,
                    text=narrative,
                    choices=[dict(id="examine", text=text, success=effects, minutes=1)],
                )
            challenge = add("challenges", raw)
            brush["interaction"] = add(
                "points_of_interest",
                dict(
                    **visual,
                    description="Доступно по Enter с клетки или по соседству. Награда однократная.",
                    challenge=challenge,
                ),
            )
            walkable = True
            hint += " Взаимодействие по Enter с клетки или рядом; однократная награда."

        if tags & {
            "weapon_decor",
            "armor_decor",
            "supplies_decor",
            "artifacts",
            "keys",
        } and tile.id not in {"lock", "mechanism_locked"}:
            base_item = {
                "decor_oil": "oil",
                "decor_food": "rations",
                "decor_meal": "rations",
                "decor_rations": "rations",
                "decor_potion": "healing_potion",
                "decor_potion_small": "healing_potion",
                "artifact_potion": "healing_potion",
            }.get(tile.id)
            if base_item:
                raw = store.get("equipment", "base:" + base_item).model_dump(
                    mode="json"
                )
                raw.update(visual)
            else:
                raw = dict(
                    **visual,
                    description="Предмет из каталога окружения. Его можно подобрать, осмотреть и носить.",
                    category="tools",
                    weight=0.5,
                    tags=[tile.id],
                )
                if "weapon_decor" in tags:
                    damage = (
                        "2d6"
                        if tile.id in {"decor_greatsword", "decor_greataxe"}
                        else "1d4"
                        if tile.id
                        in {"decor_dagger", "decor_arrow", "decor_bolt", "decor_sickle"}
                        else "1d6"
                    )
                    raw.update(
                        category="weapons",
                        weight=2.0,
                        slot="weapon",
                        hands=2
                        if tile.id
                        in {
                            "decor_greatsword",
                            "decor_greataxe",
                            "decor_halberd",
                            "decor_longbow",
                        }
                        else 1,
                        weapon_damage=damage,
                        tags=["weapon", tile.id],
                    )
                elif "armor_decor" in tags:
                    shield = "shield" in tile.id
                    raw.update(
                        category="armor",
                        weight=3.0,
                        slot="shield"
                        if shield
                        else "armor"
                        if "armor" in tile.id
                        else "head"
                        if "helmet" in tile.id
                        else "feet"
                        if "boots" in tile.id
                        else "hands"
                        if "gloves" in tile.id
                        else "back",
                        hands=1 if shield else 0,
                    )
                    if shield:
                        raw["properties"] = [{"kind": "armor_bonus", "amount": 2}]
                    elif "armor" in tile.id:
                        raw["properties"] = [
                            {
                                "kind": "armor_class",
                                "amount": 16 if "heavy" in tile.id else 12,
                            }
                        ]
                if tile.id in {"decor_arrow", "decor_bolt"}:
                    raw.update(
                        category="consumables",
                        weight=0.05,
                        slot=None,
                        hands=0,
                        weapon_damage=None,
                        tags=["ammunition", tile.id],
                        charges=1,
                    )
            brush["item"] = add("equipment", raw)
            brush["underlay"] = "base:floor"
            walkable = True
            hint += " Подбираемый предмет с весом и свойствами снаряжения."

        if tags & {"stairs", "portals", "teleports"}:
            brush["transition"] = True
            walkable = True
            hint = "При входе переносит на старт выбранной карты. Карту назначения задайте в палитре."
        if not brush:
            continue
        updated = tile.model_copy(
            update=dict(
                brush=TileBrush.model_validate(brush),
                walkable=walkable,
                glyph=glyph,
                description=tile.name + ". " + hint.strip(),
                tags=[tag for tag in tile.tags if tag not in {"walkable", "obstacle"}]
                + ["walkable" if walkable else "obstacle"],
            )
        )
        # model_copy does not validate; validate the full document before staging.
        updated = MODELS["tiles"].model_validate(updated.model_dump(mode="json"))
        key = ("tiles", ref)
        candidate[key] = updated
        writes[key] = (store.paths[key], updated)
        linked += 1

    PackStore.validate_references(candidate, store.manifests)
    for path, document in writes.values():
        PackStore.atomic_json(path, document.model_dump(mode="json"))
    return linked, len(writes)


if __name__ == "__main__":
    linked, files = prepare()
    print(f"Кистей с механикой: {linked}; записано документов: {files}")
