"""Exploration spell strategies. Definitions and handlers share parameter schemas."""

from abc import ABC, abstractmethod
from dataclasses import replace

from ..domain.actions import (
    ActionOutcome,
    SpellSource,
    spell_check,
    scaled_spell_effects,
)
from ..domain.definitions import DiceExpression
from ..domain.equipment import Equipment, ItemGlow
from ..domain.spellcasting import world_spell_parameters
from ..world.maps import Position
from ..world.magic import MagicPlacement
from ..world.lighting import line_of_sight


class WorldSpell(ABC):
    persistent = False

    @abstractmethod
    def validate(self, engine, spell, target, option, params):
        """Return an error before any resource, time or randomness is consumed."""

    @abstractmethod
    def apply(self, engine, spell, target, option, params):
        """Execute a validated cast without advancing time."""


class BoundLight(WorldSpell):
    persistent = True

    def validate(self, e, s, target, option, params):
        if not isinstance(target, Equipment) or not any(
            i is target for i in e.state.hero.inventory
        ):
            return "Выберите предмет в своём инвентаре."

    def apply(self, e, s, target, option, params):
        e.magic_effects[:] = [m for m in e.magic_effects if m.kind != "light"]
        e.add_magic(s, params, item_id=target.instance_id)
        e._glowing_items[target.instance_id] = target
        return ActionOutcome(
            True,
            True,
            f"{target.name}: получено Свечение [glowing] на {params.duration} ходов; "
            f"яркий радиус {params.bright_radius}, общий {params.radius} кл. Рука не нужна.",
        )


class Repair(WorldSpell):
    def validate(self, e, s, target, option, params):
        if not isinstance(target, Equipment) or not any(
            i is target for i in e.state.hero.inventory
        ):
            return "Выберите предмет в своём инвентаре."
        if (
            target.durability is None
            or target.durability >= target.definition.durability
        ):
            return "У предмета нет повреждений, которые можно починить."

    def apply(self, e, s, target, option, params):
        amount = (
            params.tool_amount
            if target.category == "tools"
            else DiceExpression.parse(params.equipment_dice).roll(e.dice)
        )
        before = target.durability
        target.repair(amount)
        return ActionOutcome(
            True,
            True,
            f"Починка: {target.name}, +{target.durability - before} стойкости ({target.durability}/{target.definition.durability}).",
        )


class Projectile(WorldSpell):
    def validate(self, e, s, target, option, params):
        error = e.spell_cell_error(target, s.range)
        if error:
            return error
        if not (
            e.spell_creature(target) or e.spell_doors(target) or target in e.state.oil
        ):
            return "Нужны существо, дверь или масло. Разрушение прочих объектов пока не реализовано."

    def apply(self, e, s, target, option, params):
        creature = e.spell_creature(target)
        doors = e.spell_doors(target)
        if creature:
            check, hit = spell_check(e.state.hero, creature, s, e.dice)
        else:
            check = (
                e.dice.check(
                    e.state.hero.stats.score(e.state.hero.spellcasting_ability),
                    10,
                    bonus=e.state.hero.proficiency_bonus,
                )
                if s.resolution == "attack"
                else None
            )
            hit = check is None or check.success
        outcomes = []
        amount = 0
        if hit:
            for effect in scaled_spell_effects(
                s, e.state.hero, creature or e.state.hero
            ):
                rolled = effect.amount + (
                    effect.dice.roll(e.dice) if effect.dice else 0
                )
                if effect.kind == "damage":
                    # Cell damage owns oil, ignition, door defenses and concentration.
                    amount += e.damage_cell(
                        target,
                        rolled,
                        effect.damage_type,
                        ignite="ignite" in s.tags,
                        outcomes=outcomes,
                    )
                elif creature:
                    outcomes.extend(
                        e.actions.effects.apply_all(
                            (replace(effect, amount=rolled, dice=None),),
                            creature,
                            e.dice,
                        )
                    )
            if "cool" in s.tags:
                for door in doors:
                    door.door.burning = False
        roll = (
            f" d20 {check.roll} + {check.modifier} = {check.total} против {check.difficulty}."
            if check
            else ""
        )
        return ActionOutcome(
            True,
            hit,
            f"{s.name}: "
            + (f"нанесено {amount} урона." if hit else "промах / успешный спасбросок.")
            + roll,
            check,
            tuple(outcomes),
        )


class Marker(WorldSpell):
    persistent = True

    def validate(self, e, s, target, option, params):
        error = e.spell_cell_error(
            target, s.range, require_visible=s.world_effect != "dancing_lights"
        )
        if error:
            return error
        if s.world_effect in (
            "dancing_lights",
            "hand",
            "illusion",
        ) and not e.state.walkable(target):
            return "Для временного эффекта выберите клетку пола."

    def apply(self, e, s, target, option, params):
        e.magic_effects[:] = [m for m in e.magic_effects if m.kind != s.world_effect]
        e.add_magic(s, params, position=target)
        return ActionOutcome(True, True, f"{s.name}: {params.duration} ходов.")


class Tricks(Marker):
    def validate(self, e, s, target, option, params):
        error = super().validate(e, s, target, option, params)
        if error:
            return error
        if option not in ("ignite", "extinguish", "mark", "noise"):
            return "Выберите эффект: ignite (поджечь), extinguish (погасить), mark (метка), noise (звук)."
        if option == "ignite" and not (
            target in e.state.oil
            or any(
                d.door.material == "wood" and not d.door.destroyed
                for d in e.spell_doors(target)
            )
        ):
            return "Поджечь можно деревянную дверь или масло."
        if option == "extinguish" and not any(
            d.door.burning for d in e.spell_doors(target)
        ):
            return "На клетке нет горящей двери."

    def apply(self, e, s, target, option, params):
        if option == "mark":
            return super().apply(e, s, target, option, params)
        if option == "ignite":
            for d in e.spell_doors(target):
                d.door.ignite()
            e.damage_cell(target, 0, "fire", ignite=True)
        elif option == "extinguish":
            for d in e.spell_doors(target):
                d.door.burning = False
        else:
            e.events.append(
                dict(
                    kind="noise",
                    x=target.x,
                    y=target.y,
                    message="Магический звук. Реакции AI пока отсутствуют.",
                )
            )
        return ActionOutcome(
            True,
            True,
            f"{s.name}: {dict(ignite='поджог', extinguish='огонь погашен', noise='звук')[option]}.",
        )


class Illusion(Marker):
    def validate(self, e, s, target, option, params):
        error = super().validate(e, s, target, option, params)
        if error:
            return error
        if option not in (None, "mark", "noise"):
            return "Выберите неподвижную иллюзию или звук."

    def apply(self, e, s, target, option, params):
        if option == "noise":
            e.events.append(
                dict(
                    kind="noise",
                    x=target.x,
                    y=target.y,
                    message="Иллюзорный звук. Реакции AI пока отсутствуют.",
                )
            )
            return ActionOutcome(True, True, "Малая иллюзия создала звук.")
        return super().apply(e, s, target, option, params)


class Noise(WorldSpell):
    def validate(self, e, s, target, option, params):
        pass

    def apply(self, e, s, target, option, params):
        p = e.state.position
        e.events.append(
            dict(
                kind="noise",
                x=p.x,
                y=p.y,
                message="Громовой шум. Реакции AI пока отсутствуют.",
            )
        )
        return ActionOutcome(True, True, "Раздался громовой шум.")


class WorldSpellRegistry:
    def __init__(self):
        self.handlers = {}

    def register(self, kind, handler):
        if kind in self.handlers or kind not in world_spell_parameters.models:
            raise ValueError(f"Повторная механика или отсутствует схема: {kind}")
        self.handlers[kind] = handler


world_spells = WorldSpellRegistry()
for _kind, _handler in (
    ("light", BoundLight()),
    ("repair", Repair()),
    ("projectile", Projectile()),
    ("hand", Marker()),
    ("illusion", Illusion()),
    ("dancing_lights", Marker()),
    ("tricks", Tricks()),
    ("elementalism", Tricks()),
    ("noise", Noise()),
):
    world_spells.register(_kind, _handler)


class MagicCommands:
    def spell_item_targets(self, spell):
        """Use the cast validator for item menus, without spending time or resources."""
        if spell.target != "item":
            return []
        handler = world_spells.handlers.get(spell.world_effect)
        if handler is None:
            return []
        params = world_spell_parameters.validate(
            spell.world_effect, dict(spell.world_parameters)
        )
        return [
            item
            for item in self.state.hero.inventory
            if handler.validate(self, spell, item, None, params) is None
        ]

    def known_spell(self, spell_id, source):
        hero = self.state.hero
        if source is SpellSource.CLASS:
            return next((s for s in hero.class_spells if s.id == spell_id), None)
        if (
            source is SpellSource.RACIAL
            and hero.racial_spell
            and hero.racial_spell.id == spell_id
        ):
            return hero.racial_spell

    def spell_doors(self, p):
        return self.state.level.index("doors").at(p.x, p.y) if self.state.level else ()

    def spell_creature(self, p):
        return next(
            (
                m.monster
                for m in self.state.actor_index.at(p.x, p.y)
                if m.monster.hp > 0
            ),
            None,
        )

    def spell_cell_error(self, target, reach, *, require_visible=True):
        if not self._inside(target):
            return "Выберите клетку карты."
        p = self.state.position
        if max(abs(target.x - p.x), abs(target.y - p.y)) > reach:
            return f"Цель дальше {reach} клеток."
        blocks = (
            self.state.level.terrain.blocks_sight
            if self.state.level
            else [[c == "#" for c in row] for row in self.state.dungeon.rows]
        )
        if (require_visible and not self.lighting.at(target)) or not line_of_sight(
            p, target, blocks
        ):
            return "Цель не видна: темно или обзор закрыт."

    def add_magic(self, spell, params, **target):
        effect = MagicPlacement(
            spell.world_effect,
            params.duration + 1,
            map_ref=self.state.level.ref if self.state.level else None,
            concentration=spell.concentration,
            spell_id=spell.id,
            params=params.model_dump(),
            **target,
        )
        if effect.concentration:
            self.state.hero.concentration_id = effect.instance_id
        self.magic_effects.append(effect)

    def cast_world_spell(self, spell, source, target=None, option=None):
        hero = self.state.hero
        if self.lockpick_attempt or hero.hp <= 0:
            return ActionOutcome(False, False, "Магия сейчас недоступна.")
        if "exploration" not in spell.modes:
            return ActionOutcome(
                False,
                False,
                "Этот заговор предназначен для будущего боя; проверить его можно в песочнице.",
            )
        handler = world_spells.handlers.get(spell.world_effect)
        if not handler:
            return ActionOutcome(
                False, False, "Механика исследования не зарегистрирована."
            )
        params = world_spell_parameters.validate(
            spell.world_effect, dict(spell.world_parameters)
        )
        error = handler.validate(self, spell, target, option, params)
        if error:
            return ActionOutcome(False, False, error)
        available = (
            hero.cantrip_uses > 0
            if spell.level == 0
            else (
                hero.racial_uses > 0
                if source is SpellSource.RACIAL
                else hero.spell_slots.get(spell.level, 0) > 0
            )
        )
        if not available:
            return ActionOutcome(False, False, "Магический ресурс исчерпан.")
        if source is SpellSource.RACIAL:
            hero.consume_racial_spell()
        else:
            hero.consume_class_slot(spell.id)
        result = handler.apply(self, spell, target, option, params)
        self.events.append(
            dict(
                kind="spell",
                spell=spell.id,
                message=result.message,
                roll=result.check.roll if result.check else None,
                total=result.check.total if result.check else None,
                success=result.success,
                effects=[o.payload() for o in result.effects],
            )
        )
        self._advance(1)
        self.sync_magic()
        if spell.pending_effects:
            result = replace(
                result,
                message=result.message
                + " Позже: "
                + "; ".join(spell.pending_effects)
                + ".",
            )
        return result

    def sync_magic(self):
        hero = self.state.hero
        if hero.hp <= 0:
            hero.concentration_id = None
        self.magic_effects[:] = [
            m
            for m in self.magic_effects
            if m.turns > 0
            and (not m.concentration or m.instance_id == hero.concentration_id)
        ]
        if not any(m.instance_id == hero.concentration_id for m in self.magic_effects):
            hero.concentration_id = None
        lights = {
            m.item_id: m for m in self.magic_effects if m.kind == "light" and m.item_id
        }
        for item_id in tuple(self._glowing_items):
            if item_id not in lights:
                self._glowing_items.pop(item_id).glow = None
        for item_id, effect in lights.items():
            item = self._glowing_items.get(item_id)
            if item is None:
                item = self._find_magic_item(item_id)
                if item is None:
                    continue
                self._glowing_items[item_id] = item
            item.glow = ItemGlow(
                effect.turns, effect.params["radius"], effect.params["bright_radius"]
            )

    def _find_magic_item(self, item_id):
        """Resolve a binding once after loading; normal frames use cached instances."""
        item = next(
            (i for i in self.state.hero.inventory if i.instance_id == item_id), None
        )
        if item is not None:
            return item
        states = list(self.levels.values()) if self.levels else [self.state]
        for state in states:
            entry = state.item_index.instances.get(item_id)
            if entry:
                return entry[1]
            inventories = [p.monster.inventory for p in state.monsters]
            if state.level:
                inventories.extend(c.items for c in state.level.containers)
            for inventory in inventories:
                item = next((i for i in inventory if i.instance_id == item_id), None)
                if item is not None:
                    return item

    def prune_magic_items(self):
        """Called on commands/save, never scans ground items on every frame."""
        bound = {m.item_id for m in self.magic_effects if m.item_id}
        if not bound:
            return
        states = list(self.levels.values()) if self.levels else [self.state]
        present = {i.instance_id for i in self.state.hero.inventory}
        if bound.issubset(present):
            return
        for state in states:
            present.update(bound.intersection(state.item_index.instances))
            if bound.issubset(present):
                return
            present.update(
                i.instance_id for p in state.monsters for i in p.monster.inventory
            )
            if state.level:
                present.update(
                    i.instance_id for c in state.level.containers for i in c.items
                )
        self.magic_effects[:] = [
            m for m in self.magic_effects if not m.item_id or m.item_id in present
        ]
        self.sync_magic()

    def advance_magic(self):
        for m in self.magic_effects:
            m.turns -= 1
        self.sync_magic()

    def magic_lights(self):
        self.sync_magic()
        result = []
        for m in self.magic_effects:
            if m.kind not in ("light", "dancing_lights"):
                continue
            position = (
                m.position
                if m.map_ref == (self.state.level.ref if self.state.level else None)
                else None
            )
            if m.item_id:
                position = (
                    self.state.position
                    if any(
                        i.instance_id == m.item_id for i in self.state.hero.inventory
                    )
                    else None
                )
                if position is None:
                    entry = self.state.item_index.instances.get(m.item_id)
                    position = Position(entry[0].x, entry[0].y) if entry else None
            if position is not None:
                result.append((position, m.params["radius"], m.params["bright_radius"]))
        return tuple(result)

    @property
    def active_hand(self):
        self.sync_magic()
        ref = self.state.level.ref if self.state.level else None
        return next(
            (m for m in self.magic_effects if m.kind == "hand" and m.map_ref == ref),
            None,
        )

    @property
    def magic_hand_range(self):
        hand = self.active_hand
        spell = self.catalog.spells.get(hand.spell_id) if hand else None
        return spell.range if spell else 4

    def use_magic_hand(self, target):
        """Remote pickup/open/trigger; no attacks or lockpicking, no extra charge."""
        from .engine import ActionResult

        hand = self.active_hand
        if not hand or self.lockpick_attempt or self.state.hero.hp <= 0:
            return ActionResult(False, 0, "Волшебная рука не активна.")
        error = self.spell_cell_error(target, self.magic_hand_range)
        if error:
            return ActionResult(False, 0, error)
        entries = self.state.item_index.at(target.x, target.y)
        item = next(
            ((p, i) for p, i in entries if i.weight <= hand.params["max_weight"]), None
        )
        doors = [
            d
            for d in self.spell_doors(target)
            if not d.door.opened
            and not d.door.locked
            and not d.door.destroyed
            and d.door.material != "stone"
        ]
        containers = (
            self.state.level.index("containers").at(target.x, target.y)
            if self.state.level
            else ()
        )
        traps = (
            self.state.level.index("traps").at(target.x, target.y)
            if self.state.level
            else ()
        )
        trap = next(
            (t for t in traps if not t.triggered or t.definition.repeatable), None
        )
        if item:
            self.state.items.remove(item)
            item[1].lit = False
            self.state.hero.inventory.append(item[1])
            message = f"Волшебная рука принесла: {item[1].name}."
        elif doors:
            doors[0].door.opened = True
            message = "Волшебная рука открыла незапертую дверь."
        elif trap:
            trap.triggered = True
            # A hand is not a creature: contact triggers consume the placement,
            # but character-target effects cannot harm a nonexistent actor.
            message = (
                "Ловушка сработала на волшебную руку; существо на клетке не стоит."
            )
            self.events.append(
                dict(
                    kind="trap",
                    placement=trap.placement.id,
                    success=True,
                    message=message,
                    effects=[],
                )
            )
        elif containers:
            container = containers[0]
            item = next(
                (i for i in container.items if i.weight <= hand.params["max_weight"]),
                None,
            )
            if item is None:
                return ActionResult(
                    False, 0, "В контейнере нет достаточно лёгкого предмета."
                )
            container.items.remove(item)
            self.state.hero.inventory.append(item)
            message = f"Волшебная рука достала из контейнера: {item.name}."
        else:
            return ActionResult(
                False,
                0,
                "Нет незапертой двери, ловушки, контейнера или лёгкого предмета.",
            )
        hand.position = target
        self._advance(1)
        return ActionResult(True, 1, message)
