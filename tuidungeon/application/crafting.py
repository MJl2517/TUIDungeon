"""Validated crafting commands shared by the three game clients."""

from dataclasses import asdict, dataclass, field
from ..domain.crafting import CraftWork, ingredient_choices
from ..domain.equipment import Equipment
from ..domain.rules import Ability
from ..world.maps import Position
from ..world.state import ItemPlacement

STATION_NAMES = dict(
    heat="Источник тепла (костёр / печь / горн)",
    campfire="Костёр",
    forge="Горн",
    anvil="Наковальня",
    workbench="Верстак",
    alchemy_table="Алхимический стол",
    oven="Печь",
)

CRAFT_CATEGORIES = {
    "basic": "Базовые",
    "herbalist": "Травник",
    "alchemist": "Алхимик",
    "smith": "Кузнец",
    "carpenter": "Плотник",
    "tinker": "Жестянщик",
    "leatherworker": "Кожевник",
    "weaver": "Ткач",
    "woodcarver": "Резчик",
    "cook": "Повар",
    "poisoner": "Отравитель",
    "mason": "Каменщик",
    "glassblower": "Стеклодув",
    "potter": "Гончар",
    "jeweler": "Ювелир",
    "cobbler": "Сапожник",
    "brewer": "Пивовар",
    "calligrapher": "Каллиграф",
    "magic": "Магический крафт",
    "experiment": "Эксперименты",
    "other": "Прочее",
}


def operation_summary(recipe):
    from ..domain.liquids import LIQUID_NAMES, portion_text

    op = recipe.operation
    if not op:
        return ""
    if op.kind == "liquid":
        result = (
            LIQUID_NAMES[op.liquid_result]
            if op.liquid_result
            else "жидкость расходуется; пустая тара сохраняется"
        )
        return (
            f"{portion_text(op.portions)}: "
            + " / ".join(LIQUID_NAMES[k] for k in op.liquids)
            + " → "
            + result
            + (". Нужен нагреваемый сосуд." if op.heat_safe else ".")
        )
    if op.kind == "place_trap":
        return "Установить ловушку на свободной соседней клетке; срабатывает при входе."
    if op.kind == "appraise_item":
        return "Определить стоимость предмета; оценка сохраняется с экземпляром. Продажа будет доступна после появления торговли."
    if op.kind == "coat_weapon":
        return f"Покрыть колющее или рубящее оружие ядом: +{op.poison_damage} ядовитого урона при следующем попадании. Промах не расходует покрытие."
    if op.kind in ("repair_item", "repair_object"):
        return f"Восстановить до {op.repair_amount} прочности при завершении."
    return "Создать объект на выбранной соседней клетке." + (
        " Нужен действующий источник зажигания." if op.ignition else ""
    )


@dataclass
class CraftAssessment:
    ref: str
    recipe: object
    variant: int
    reasons: list[str] = field(default_factory=list)
    ingredients: list[dict] = field(default_factory=list)
    selected: list[tuple] = field(default_factory=list, repr=False)
    target: object = None
    target_object: str | None = None
    targets: list[dict] = field(default_factory=list)
    destination: tuple[int, int] | None = None
    destinations: list[dict] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)

    def require(self, name, met, reason):
        self.conditions.append(
            dict(name=name, met=bool(met), reason=reason if not met else None)
        )
        if not met:
            self.reasons.append(reason)

    @property
    def available(self):
        return not self.reasons

    def payload(self, catalog):
        v = self.recipe.variants[self.variant]
        return dict(
            ref=self.ref,
            name=self.recipe.name,
            description=self.recipe.description,
            category=self.recipe.category,
            variant=self.variant,
            method=v.name,
            turns=v.turns,
            check=(v.check or self.recipe.check).model_dump(mode="json")
            if (v.check or self.recipe.check)
            else None,
            spells=list(v.spells),
            spell_names=[
                catalog.spells[r.removeprefix("base:")].name for r in v.spells
            ],
            learns=[catalog.recipes[r].name for r in self.recipe.learn_recipes],
            tools=list(v.tools),
            tool_names=[
                next((d.name for d in catalog.equipment.values() if t in d.tags), t)
                for t in v.tools
            ],
            proficiency_names=[
                next((d.name for d in catalog.equipment.values() if t in d.tags), t)
                for t in v.proficiencies
            ],
            proficiencies=list(v.proficiencies),
            stations=[list(s) for s in v.stations],
            station_names=[
                [STATION_NAMES.get(t, t) for t in group] for group in v.stations
            ],
            ingredients=self.ingredients,
            conditions=self.conditions,
            result=[
                {
                    **r.model_dump(mode="json"),
                    **{
                        key: value
                        for key, value in asdict(item.definition).items()
                        if key
                        in (
                            "name",
                            "description",
                            "weight",
                            "category",
                            "durability",
                            "charges",
                            "hands",
                            "weapon_damage",
                            "damage_type",
                            "light",
                            "properties",
                            "spell_bonus",
                            "cast_spell",
                        )
                    },
                    "category": item.category,
                    "weight": item.weight,
                    "hands": item.hands,
                }
                for r in (v.result if v.result is not None else self.recipe.result)
                for item in (
                    Equipment.create(catalog.equipment[r.item.removeprefix("base:")]),
                )
            ],
            operation=self.recipe.operation.model_dump(mode="json")
            if self.recipe.operation
            else None,
            operation_summary=operation_summary(self.recipe),
            targets=self.targets,
            target=self.target.instance_id if self.target else self.target_object,
            destination=self.destination,
            destinations=self.destinations,
            target_description=(
                self.target.name
                if self.target
                else next(
                    (t["name"] for t in self.targets if t["id"] == self.target_object),
                    "",
                )
            ),
            available=self.available,
            reasons=self.reasons,
        )


class CraftCommands:
    def craft_sources(self):
        hero, state = self.state.hero, self.state
        result = [(i, "Инвентарь", hero.inventory) for i in hero.inventory]
        light = self.lighting
        for placement, item in state.items:
            p = Position(placement.x, placement.y)
            if abs(p.x - state.position.x) + abs(
                p.y - state.position.y
            ) <= 1 and light.at(p):
                result.append((item, f"Земля ({p.x}, {p.y})", state.items))
        for container in self.nearby_containers():
            result.extend(
                (i, container.definition.name, container.items) for i in container.items
            )
        return [
            entry
            for entry in result
            if entry[0].usable
            and not entry[0].equipped
            and not entry[0].lit
            and not entry[0].glow
        ]

    def craft_stations(self):
        level = self.state.level
        if not level:
            return set()
        result = set()
        light, p = self.lighting, self.state.position
        for category in ("objects", "points_of_interest", "traps"):
            for placement in getattr(level.definition, category):
                pos = Position(placement.x, placement.y)
                if abs(p.x - pos.x) + abs(p.y - pos.y) <= 1 and light.at(pos):
                    definition = level.store.resolve(category, placement)
                    if getattr(definition, "campfire", None):
                        obj = self.world_object(placement.id)
                        if not obj or not obj.state.lit or not obj.state.fuel_minutes:
                            continue
                    result.update(definition.tags)
        return result

    def assess_craft(
        self, ref, variant=None, *, work=None, target=None, destination=None
    ):
        recipe = work.recipe if work else self.catalog.recipes.get(ref)
        if recipe is None:
            raise ValueError("Неизвестный рецепт")
        if variant is None:
            variants = [
                self.assess_craft(
                    ref, n, work=work, target=target, destination=destination
                )
                for n in range(len(recipe.variants))
            ]
            return min(
                variants,
                key=lambda a: (
                    len(a.reasons),
                    recipe.variants[a.variant].turns,
                    a.variant,
                ),
            )
        if type(variant) is not int or not 0 <= variant < len(recipe.variants):
            raise ValueError("Неизвестный способ изготовления")
        a = CraftAssessment(ref, recipe, variant)
        hero, v = self.state.hero, recipe.variants[variant]
        if not work and ref not in hero.known_recipes:
            a.reasons.append("Рецепт не изучен.")
        if hero.hp <= 0:
            a.reasons.append("Персонаж без сознания.")
        if self.lockpick_attempt:
            a.reasons.append("Сначала завершите взлом.")
        strength = self.lighting.level_at(self.state.position)
        a.require(
            "Тусклый или яркий свет" if recipe.category == "basic" else "Яркий свет",
            strength >= (1 if recipe.category == "basic" else 2),
            "В полной тьме изготовление невозможно."
            if strength == 0
            else "В полутьме доступны только базовые рецепты.",
        )

        def tool_name(tag):
            return next(
                (d.name for d in self.catalog.equipment.values() if tag in d.tags), tag
            )

        for tag in v.tools:
            a.require(
                "Наличие: " + tool_name(tag),
                any(i.usable and tag in i.tags for i in hero.inventory),
                "Нет исправного инструмента: " + tag,
            )
        for proficiency in v.proficiencies:
            a.require(
                "Владение: " + tool_name(proficiency),
                proficiency in hero.tool_proficiencies,
                "Нет владения инструментом: " + proficiency,
            )
        known_spells = {s.id for s in hero.known_spells}
        for spell in v.spells:
            name = self.catalog.spells[spell.removeprefix("base:")].name
            a.require(
                "Знание заклинания: " + name,
                spell.removeprefix("base:") in known_spells,
                "Нужно знать заклинание: " + name,
            )
        stations = self.craft_stations() if v.stations else set()
        for alternatives in v.stations:
            name = " / ".join(STATION_NAMES.get(t, t) for t in alternatives)
            a.require(
                "Наличие рядом: " + name,
                stations.intersection(alternatives),
                "Нужна станция рядом: " + name,
            )
        self.assess_operation(a, work=work, target=target, destination=destination)
        if not work:
            sources = [
                entry for entry in self.craft_sources() if entry[0] is not a.target
            ]
            from collections import Counter

            sources = [
                entry
                for entry in sources
                if not set(v.tools).intersection(entry[0].tags)
            ]
            choices_for_all = ingredient_choices(
                v.ingredients, Counter(self.item_ref(i) for i, _, _ in sources)
            )
            selected_ids = set()
            for number, requirement in enumerate(v.ingredients):
                choices = []
                for item_ref in requirement.items:
                    found = [
                        entry
                        for entry in sources
                        if self.item_ref(entry[0]) == item_ref
                        and entry[0].instance_id not in selected_ids
                        and not set(v.tools).intersection(entry[0].tags)
                    ]
                    choices.append((item_ref, found))
                chosen, found = next(
                    (
                        entry
                        for entry in choices
                        if choices_for_all and entry[0] == choices_for_all[number]
                    ),
                    max(choices, key=lambda x: min(len(x[1]), requirement.quantity)),
                )
                picked = found[: requirement.quantity]
                selected_ids.update(i.instance_id for i, _, _ in picked)
                a.selected.extend(picked)
                labels = [
                    self.catalog.equipment[r.removeprefix("base:")].name
                    for r in requirement.items
                ]
                a.ingredients.append(
                    dict(
                        name=" / ".join(labels),
                        required=requirement.quantity,
                        available=len(found),
                        chosen=chosen,
                        chosen_name=self.catalog.equipment[
                            chosen.removeprefix("base:")
                        ].name,
                        sources=[
                            dict(name=i.name, source=label, id=i.instance_id)
                            for i, label, _ in picked
                        ],
                    )
                )
                if len(picked) < requirement.quantity:
                    a.reasons.append(
                        f"Не хватает: {' / '.join(labels)} ({len(picked)}/{requirement.quantity})."
                    )
            extra_weight = sum(
                i.weight for i, _, owner in a.selected if owner is not hero.inventory
            )
            if (
                extra_weight
                and hero.carried_weight + extra_weight > hero.max_carry_weight + 1e-9
            ):
                a.reasons.append(
                    "Недостаточно нагрузки для заготовки из соседних материалов."
                )
        return a

    @staticmethod
    def item_ref(item):
        return item.id if ":" in item.id else "base:" + item.id

    def craft_list(self, category=None, *, available_only=False):
        """Cheap catalog; full requirements belong to the selected recipe only."""
        result = []
        for ref in sorted(
            self.state.hero.known_recipes,
            key=lambda r: (
                self.catalog.recipes[r].category,
                self.catalog.recipes[r].name.casefold(),
            ),
        ):
            recipe = self.catalog.recipes[ref]
            if category is not None and recipe.category != category:
                continue
            if available_only and not self.assess_craft(ref).available:
                continue
            result.append(
                dict(
                    ref=ref,
                    name=recipe.name,
                    description=recipe.description,
                    category=recipe.category,
                    turns=min(v.turns for v in recipe.variants),
                    requires_proficiency=all(
                        bool(v.proficiencies) for v in recipe.variants
                    ),
                    variants=[
                        dict(variant=n, method=v.name, turns=v.turns)
                        for n, v in enumerate(recipe.variants)
                    ],
                )
            )
        return result

    def _craft_result(self, performed, message, minutes=0):
        from .engine import ActionResult

        if performed:
            self.events.append(dict(kind="craft", message=message))
        return ActionResult(performed, minutes, message)

    def start_craft(self, ref, variant=None, *, target=None, destination=None):
        if self.active_craft:
            return self._craft_result(False, "Сначала приостановите текущую работу.")
        try:
            a = self.assess_craft(ref, variant, target=target, destination=destination)
        except ValueError as error:
            return self._craft_result(False, str(error))
        if (
            a.recipe.operation
            and a.recipe.operation.kind in ("place_object", "place_trap")
            and destination is None
        ):
            return self._craft_result(
                False, "Выберите соседнюю клетку для строительства."
            )
        if not a.available:
            if denial := self.light_denial(1 if a.recipe.category == "basic" else 2):
                return denial
            return self._craft_result(False, " ".join(a.reasons))
        definition = self.catalog.equipment.get("craft_workpiece")
        if definition is None:
            return self._craft_result(False, "В пакете нет шаблона заготовки.")
        item = Equipment.create(definition)
        item.work = CraftWork(
            ref,
            a.recipe,
            a.variant,
            [i for i, _, _ in a.selected],
            target=a.target,
            target_id=a.target.instance_id if a.target else None,
            target_object=a.target_object,
            destination=a.destination,
            map_ref=self.state.level.ref if self.state.level else None,
        )
        if a.target:
            self.state.hero.inventory.remove(a.target)
        # Validation completes before any ownership changes. Reserve exact instances.
        for ingredient, _, owner in a.selected:
            owner[:] = [
                entry
                for entry in owner
                if (entry[1] if isinstance(entry, tuple) else entry) is not ingredient
            ]
        self.state.hero.inventory.append(item)
        self.active_craft = item.instance_id
        return self._craft_result(
            True, f"Начато: {a.recipe.name}. →/Space: следующий ход; Esc: пауза."
        )

    def workpiece(self, identifier):
        if identifier and identifier.startswith("world:"):
            return self.world_workpiece(identifier)
        return next(
            (
                i
                for i in self.state.hero.inventory
                if i.instance_id == identifier and i.work
            ),
            None,
        )

    def resume_craft(self, identifier):
        if self.active_craft and self.active_craft != identifier:
            return self._craft_result(False, "Сначала приостановите текущую работу.")
        item = self.workpiece(identifier)
        if item is None:
            return self._craft_result(False, "Заготовка отсутствует в инвентаре.")
        a = self.assess_craft(item.work.recipe_ref, item.work.variant, work=item.work)
        if not a.available:
            if denial := self.light_denial(1 if a.recipe.category == "basic" else 2):
                return denial
            return self._craft_result(False, " ".join(a.reasons))
        if a.target and not item.work.target:
            self.state.hero.inventory.remove(a.target)
            item.work.target = a.target
        self.active_craft = identifier
        return self._craft_result(True, f"Продолжение: {item.name}.")

    def pause_craft(self):
        item = self.workpiece(self.active_craft)
        self.active_craft = None
        if item and not item.instance_id.startswith("world:"):
            self.release_repair_target(item.work)
        return self._craft_result(
            bool(item),
            f"Работа приостановлена. {item.name}." if item else "Нет текущей работы.",
        )

    def cancel_craft(self, identifier):
        item = self.workpiece(identifier)
        if item is None:
            return self._craft_result(False, "Заготовка отсутствует в инвентаре.")
        if (
            self.lockpick_attempt
            or self.state.hero.hp <= 0
            or self.active_craft not in (None, identifier)
        ):
            return self._craft_result(False, "Сейчас нельзя разобрать заготовку.")
        self.state.hero.inventory.remove(item)
        self.state.hero.inventory.extend(item.work.ingredients)
        if item.work.target:
            self.state.hero.inventory.append(item.work.target)
        if self.active_craft == identifier:
            self.active_craft = None
        return self._craft_result(
            True, "Заготовка разобрана: все вложенные материалы возвращены."
        )

    def advance_craft(self):
        if self.active_craft and self.active_craft.startswith("world:"):
            return self.advance_world_work()
        item = self.workpiece(self.active_craft)
        if item is None:
            self.active_craft = None
            return self._craft_result(False, "Нет текущей работы.")
        work = item.work
        a = self.assess_craft(work.recipe_ref, work.variant, work=work)
        if not a.available:
            self.release_repair_target(work)
            self.active_craft = None
            if denial := self.light_denial(1 if a.recipe.category == "basic" else 2):
                return denial
            return self._craft_result(
                False, "Работа приостановлена. " + " ".join(a.reasons)
            )
        self._advance(1)
        work.progress += 1
        if work.progress < work.total:
            # A light may expire on this step; preserve progress and stop immediately.
            if not self.assess_craft(
                work.recipe_ref, work.variant, work=work
            ).available:
                self.release_repair_target(work)
                self.active_craft = None
                self.light_denial(1 if work.recipe.category == "basic" else 2)
                return self._craft_result(
                    True, f"{item.name}. Условия изменились; работа приостановлена.", 1
                )
            return self._craft_result(True, item.name, 1)
        variant = work.recipe.variants[work.variant]
        check = variant.check or work.recipe.check
        if check:
            roll = self.state.hero.ability_check(
                self.dice,
                Ability[check.ability.upper()],
                check.difficulty,
                skill=check.skill,
                tool=next(iter(variant.proficiencies), None),
            )
            if not roll.success:
                work.progress = 0
                self.release_repair_target(work)
                self.active_craft = None
                return self._craft_result(
                    True,
                    f"Проверка {roll.total}/{check.difficulty} неудачна. Материалы сохранены; работу нужно повторить.",
                    1,
                )
        outputs = [
            Equipment.create(self.catalog.equipment[r.item.removeprefix("base:")])
            for r in (
                variant.result if variant.result is not None else work.recipe.result
            )
            for _ in range(r.quantity)
        ]
        outputs.extend(self.finish_operation(work))
        learned = self.learn_recipes(work.recipe.learn_recipes)
        self.state.hero.inventory.remove(item)
        self.active_craft = None
        grounded = (
            self.state.hero.carried_weight + sum(i.weight for i in outputs)
            > self.state.hero.max_carry_weight + 1e-9
        )
        for output in outputs:
            if grounded:
                p = self.state.position
                self.state.items.append(
                    (
                        ItemPlacement(
                            output.instance_id, self.item_ref(output), p.x, p.y
                        ),
                        output,
                    )
                )
            else:
                self.state.hero.inventory.append(output)
        return self._craft_result(
            True,
            "Изготовлено: "
            + (", ".join(i.name for i in outputs) or work.recipe.name)
            + (". Результат на земле: превышена нагрузка." if grounded else ".")
            + (
                " Открыто: "
                + ", ".join(self.catalog.recipes[r].name for r in learned)
                + "."
                if learned
                else ""
            ),
            1,
        )
