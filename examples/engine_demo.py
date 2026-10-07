"""Run from the project root: python3 -m examples.engine_demo."""

import random

from tuidungeon.application.engine import Engine
from tuidungeon.content.catalog import ContentCatalog
from tuidungeon.domain.actions import ActionContext, SpellSource
from tuidungeon.domain.actors import Hero
from tuidungeon.domain.equipment import Equipment
from tuidungeon.domain.stats import Stats
from tuidungeon.presentation.symbols import ArtLibrary
from tuidungeon.world.maps import Position


def main():
    catalog = ContentCatalog.load()
    hero = Hero.create("elf", "wizard", Stats((14, 12, 12, 16, 10, 10)), catalog=catalog, background="scholar")
    engine = Engine.new_game(hero, random.Random(42))
    goblin = engine.add_monster("goblin", Position(4, 3)).monster
    print("\n".join(ArtLibrary().load(goblin.definition.art).lines))
    print(f"{goblin.name}: HP {goblin.hp}, КД {goblin.armor_class}, скорость {goblin.speed}, инициатива {goblin.initiative:+}")
    result = engine.perform_character_action("magic", ActionContext(
        engine.dice, spell_id="detect_magic", spell_source=SpellSource.RACIAL,
    ))
    print(result.message, "Классовые ячейки:", hero.spell_slots, "Расовые применения:", hero.racial_uses)
    result = engine.perform_character_action("magic", ActionContext(engine.dice, goblin, spell_id="magic_missile"))
    print(result.message, "HP гоблина:", goblin.hp)
    hero.inventory.append(Equipment.create(catalog.equipment["chest_key"]))
    result = engine.resolve_challenge("locked_chest", "use_key")
    print(result.message, f"Деньги: {hero.gold}; опыт: {hero.experience}")
    hero.take_damage(4)
    potion = Equipment.create(catalog.equipment["healing_potion"])
    hero.inventory.append(potion)
    print(engine.use_item(potion).message, f"HP героя: {hero.hp}/{hero.max_hp}")
    print(f"Ходов: {engine.state.turns}; время: {engine.state.clock.hour:02}:{engine.state.clock.minute:02}")


if __name__ == "__main__":
    main()
