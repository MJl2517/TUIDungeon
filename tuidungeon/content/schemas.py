"""Versioned authoring contracts. JSON Schema drives the Studio forms."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from wcwidth import wcwidth
from ..domain.definitions import DiceExpression
from ..domain.value_types import freeze
from ..domain.doors import Material, LockQuality, LockComplexity, MATERIALS, door_glyph
from ..domain.tags import TAGS_DESCRIPTION, TAG_SCHEMA
from ..domain.liquids import LiquidKind
from ..domain.damage import DamageType, DamageSelector
from ..domain.item_sizes import ItemSize

LocalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Ref = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")]
AbilityName = Literal[
    "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"
]
MapCategory = Literal[
    "auto", "floor", "wall", "destructible", "furniture", "special", "service"
]
Color = Annotated[int, Field(ge=0, le=255)]
Positive = Annotated[int, Field(ge=1)]
Nonnegative = Annotated[int, Field(ge=0)]


def valid_glyph(value: str) -> str:
    if len(value) != 1 or not value.isprintable() or wcwidth(value) != 1:
        raise ValueError("Нужен один печатный символ шириной в одну колонку")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, validate_default=True
    )

    def model_post_init(self, context):
        for name in type(self).model_fields:
            object.__setattr__(self, name, freeze(getattr(self, name)))

    def model_copy(self, *, update=None, deep=False):
        result = super().model_copy(update=update, deep=deep)
        result.model_post_init(None)
        return result


def title_text(value):
    if not value.strip() or any(not c.isprintable() for c in value):
        raise ValueError("Нужна непустая печатная строка")
    return value


def narrative_text(value):
    if any(not c.isprintable() and c not in "\n\r\t" for c in value):
        raise ValueError("Текст содержит управляющие символы")
    return value


class Document(StrictModel):
    schema_version: Literal[1] = 1
    id: LocalId
    name: Annotated[str, Field(min_length=1)]
    description: str = ""
    _name = field_validator("name")(title_text)
    _description = field_validator("description")(narrative_text)


class Manifest(StrictModel):
    schema_version: Literal[1] = 1
    id: LocalId
    name: str
    version: str = "1.0.0"
    dependencies: list[LocalId] = Field(default_factory=list)


class SymbolSource(StrictModel):
    name: str
    license: str
    location: str = ""
    coordinates: list[int] | None = None


class SymbolDocument(Document):
    """A one-cell monochrome image, independent of gameplay and tint."""

    glyph: str = "?"
    group: str = "Неразобранное"
    tags: list[str] = Field(default_factory=list)
    reviewed: bool = False
    pixels: list[str] = Field(default_factory=lambda: ["0" * 16 for _ in range(16)])
    source: SymbolSource | None = None
    _glyph = field_validator("glyph")(valid_glyph)
    _group = field_validator("group")(title_text)

    @field_validator("pixels")
    @classmethod
    def mask_size(cls, value):
        if len(value) != 16 or any(
            len(row) != 16 or set(row) - {"0", "1"} for row in value
        ):
            raise ValueError("Маска должна содержать 16 строк по 16 пикселей 0/1")
        return value

    @model_validator(mode="after")
    def reviewed_name(self):
        if self.reviewed and (
            self.group == "Неразобранное"
            or self.name.startswith(("Kenney [", "Импорт ["))
            or self.name == "Новый символ"
        ):
            raise ValueError("Перед назначением укажите название и категорию символа")
        return self


class Scores(StrictModel):
    strength: Positive = 10
    dexterity: Positive = 10
    constitution: Positive = 10
    intelligence: Positive = 10
    wisdom: Positive = 10
    charisma: Positive = 10


class Bonuses(StrictModel):
    strength: int = 0
    dexterity: int = 0
    constitution: int = 0
    intelligence: int = 0
    wisdom: int = 0
    charisma: int = 0


class DamageDefenses(StrictModel):
    resistances: list[DamageSelector] = Field(default_factory=list)
    vulnerabilities: list[DamageSelector] = Field(default_factory=list)
    immunities: list[DamageSelector] = Field(default_factory=list)


class Effect(StrictModel):
    kind: LocalId = "damage"
    amount: Nonnegative = 0
    dice: str | None = None
    condition: str = ""
    duration: Positive = 1
    damage_type: DamageType | None = Field(
        default=None,
        description="Тип урона; пусто — совместимость со старыми эффектами без типа",
    )
    params: dict = Field(
        default_factory=dict, description="Параметры зарегистрированной механики"
    )

    @field_validator("dice")
    @classmethod
    def dice_valid(cls, value):
        if value is not None:
            DiceExpression.parse(value)
        return value

    @model_validator(mode="after")
    def mechanism(self):
        from ..domain.mechanics import mechanics

        mechanics.validate_effect(self)
        return self


def active_effects(value):
    if any(e.kind in ("armor_class", "armor_bonus") for e in value):
        raise ValueError("Пассивная КД допустима только в свойствах снаряжения")
    return value


class ActionFields(StrictModel):
    id: LocalId
    name: str
    kind: Literal["attack", "dodge", "stealth", "magic", "influence", "special"] = (
        "attack"
    )
    ability: AbilityName = "strength"
    bonus: int = 0
    damage: str | None = None
    damage_type: DamageType = "bludgeoning"
    effects: list[Effect] = Field(default_factory=list)
    difficulty: Nonnegative = 10
    description: str = ""
    tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )

    _effects = field_validator("effects")(active_effects)

    _name = field_validator("name")(title_text)
    _description = field_validator("description")(narrative_text)

    @field_validator("damage")
    @classmethod
    def damage_valid(cls, value):
        if value is not None:
            DiceExpression.parse(value)
        return value


class ActionDocument(ActionFields):
    schema_version: Literal[1] = 1


class TileLight(StrictModel):
    radius: Annotated[int, Field(ge=1, le=32)] = 6
    bright_radius: Annotated[int, Field(ge=0, le=32)] = 3

    @model_validator(mode="after")
    def radii(self):
        if self.bright_radius > self.radius:
            raise ValueError("Яркий радиус не может превышать общий радиус света")
        return self


class VisualVariant(StrictModel):
    mirror_x: bool | None = None
    loot_tier: Literal["white", "bronze", "iron", "gold"] | None = None
    name: str
    glyph: str = "?"
    symbol: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "symbols"}
    )
    foreground: Color = 7
    background: Color | None = None
    _name = field_validator("name")(title_text)
    _glyph = field_validator("glyph")(valid_glyph)


class Visual(Document):
    mirror_x: bool = Field(
        default=False,
        description="Отразить изображение по горизонтали; механики не меняются",
    )
    symbol: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "symbols"}
    )
    state_symbols: dict[str, Ref] = Field(
        default_factory=dict,
        description="Графика состояний: closed/open у контейнера; closed/locked/open/bent у двери",
    )
    variants: list[VisualVariant] = Field(
        default_factory=list,
        description="Варианты внешнего вида без копирования механик",
    )
    glyph: str = "?"
    foreground: Color = 7
    background: Color | None = None
    art: Ref | None = Field(default=None, json_schema_extra={"ref_category": "art"})
    _glyph = field_validator("glyph")(valid_glyph)

    @field_validator("state_symbols")
    @classmethod
    def known_states(cls, value):
        if set(value) - {"closed", "locked", "open", "bent"}:
            raise ValueError("Неизвестное состояние графики двери")
        return value


class Aid(StrictModel):
    check_tag: LocalId = "lockpicking"
    mode: Literal["advantage", "automatic"] = "advantage"


class LightSource(StrictModel):
    radius: Annotated[int, Field(ge=1, le=32)] = 6
    bright_radius: Annotated[int, Field(ge=0, le=32)] = 3
    burn_minutes: Positive = 60
    fuel_tag: LocalId | None = None

    @model_validator(mode="after")
    def radii(self):
        if self.bright_radius > self.radius:
            raise ValueError("Яркий радиус не может превышать общий радиус света")
        return self


class VesselSpec(StrictModel):
    capacity_portions: Annotated[int, Field(ge=1, le=1000, strict=True)] = 1
    heat_safe: bool = False
    fragile: bool = False
    initial_kind: LiquidKind | None = None
    initial_portions: Annotated[int, Field(ge=0, le=1000, strict=True)] = 0

    @model_validator(mode="before")
    @classmethod
    def legacy(cls, value):
        from ..domain.liquids import migrate_vessel

        return migrate_vessel(value)

    @model_validator(mode="after")
    def contents(self):
        if self.initial_portions > self.capacity_portions or bool(
            self.initial_portions
        ) != bool(self.initial_kind):
            raise ValueError("Объём и вид содержимого сосуда не согласованы")
        return self


class WaterSourceSpec(StrictModel):
    kind: LiquidKind = "dirty_water"
    portions: Annotated[int, Field(ge=1, le=1000)] | None = Field(
        default=None,
        description="Запас порций. Пусто — неисчерпаемый источник; при исчерпании объект исчезает.",
    )


class CampfireSpec(StrictModel):
    fuel_minutes: Annotated[int, Field(ge=1, le=10000)] = 60
    fuel_tag: LocalId = "wooden"
    radius: Annotated[int, Field(ge=1, le=32)] = 5
    bright_radius: Annotated[int, Field(ge=0, le=32)] = 3

    @model_validator(mode="after")
    def radii(self):
        if self.bright_radius > self.radius:
            raise ValueError("Яркий радиус больше общего")
        return self


class RecipeOperation(StrictModel):
    kind: Literal[
        "liquid",
        "repair_item",
        "repair_object",
        "place_object",
        "place_trap",
        "coat_weapon",
        "appraise_item",
    ] = "liquid"
    target_tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    liquids: list[LiquidKind] = Field(default_factory=list)
    portions: Annotated[int, Field(ge=1, le=1000, strict=True)] = 3
    liquid_result: LiquidKind | None = None
    heat_safe: bool = False
    repair_amount: Annotated[int, Field(ge=1, le=100000)] = 10
    place_object: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "objects"}
    )
    place_trap: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "traps"}
    )
    poison_damage: Annotated[int, Field(ge=1, le=100)] = 2
    ignition: bool = False

    @model_validator(mode="before")
    @classmethod
    def legacy(cls, value):
        if isinstance(value, dict) and "volume_ml" in value:
            data = dict(value)
            volume = data.pop("volume_ml")
            if "portions" in data or type(volume) is not int or volume <= 0:
                raise ValueError("Недопустимый объём обработки")
            data["portions"] = 3 if volume == 500 else (volume + 249) // 250
            return data
        return value

    @model_validator(mode="after")
    def requirements(self):
        if self.kind == "liquid" and not self.liquids:
            raise ValueError("Укажите допустимые жидкости")
        if (self.kind == "place_object") != bool(self.place_object):
            raise ValueError("Ссылка на объект нужна только для размещения")
        if (self.kind == "place_trap") != bool(self.place_trap):
            raise ValueError("Ссылка на ловушку нужна только для установки")
        if self.kind != "liquid" and (
            self.liquids or self.liquid_result or self.heat_safe
        ):
            raise ValueError(
                "Параметры жидкости допустимы только для обработки жидкости"
            )
        if self.kind != "place_object" and self.ignition:
            raise ValueError("Зажигание допустимо только при создании объекта")
        return self


class RecipeIngredient(StrictModel):
    items: Annotated[list[Ref], Field(min_length=1, max_length=32)] = Field(
        default_factory=lambda: ["base:wood"],
        json_schema_extra={"ref_category": "equipment"},
    )
    quantity: Annotated[int, Field(ge=1, le=1000)] = 1


class RecipeOutput(StrictModel):
    item: Ref = Field(
        default="base:torch", json_schema_extra={"ref_category": "equipment"}
    )
    quantity: Annotated[int, Field(ge=1, le=1000)] = 1


class RecipeCheck(StrictModel):
    ability: AbilityName = "intelligence"
    difficulty: Annotated[int, Field(ge=0, le=100)] = 10


class RecipeVariant(StrictModel):
    result: list[RecipeOutput] | None = Field(
        default=None,
        max_length=32,
        description="Результат этого способа; пусто — общий результат рецепта",
    )
    check: RecipeCheck | None = None
    spells: list[Ref] = Field(
        default_factory=list,
        json_schema_extra={"ref_category": "spells"},
        description="Нужны знания всех перечисленных заклинаний; свиток не даёт знания",
    )
    name: str = "Обычный способ"
    ingredients: Annotated[list[RecipeIngredient], Field(max_length=32)] = Field(
        default_factory=lambda: [RecipeIngredient()]
    )
    tools: list[LocalId] = Field(default_factory=list)
    proficiencies: list[LocalId] = Field(default_factory=list)
    stations: list[Annotated[list[LocalId], Field(min_length=1, max_length=16)]] = (
        Field(
            default_factory=list,
            description="Каждая группа: одна станция из списка; нужны все группы",
        )
    )
    turns: Annotated[int, Field(ge=1, le=1000)] = 1
    _name = field_validator("name")(title_text)


class RecipeDocument(Document):
    @model_validator(mode="before")
    @classmethod
    def legacy_materials(cls, value):
        from .migrations import migrate_document

        return migrate_document(value, "recipes")

    learn_recipes: list[Ref] = Field(
        default_factory=list,
        max_length=32,
        json_schema_extra={"ref_category": "recipes"},
        description="Рецепты, открываемые успешным завершением эксперимента",
    )
    category: LocalId = "basic"
    basic_known: bool = True
    learn_on_proficiency: list[LocalId] = Field(
        default_factory=list,
        description="Рецепт изучается при получении любого из этих владений",
    )
    variants: Annotated[list[RecipeVariant], Field(min_length=1, max_length=16)] = (
        Field(default_factory=lambda: [RecipeVariant()])
    )
    result: Annotated[list[RecipeOutput], Field(max_length=32)] = Field(
        default_factory=lambda: [RecipeOutput()]
    )
    check: RecipeCheck | None = None
    operation: RecipeOperation | None = None

    @model_validator(mode="after")
    def bounded_items(self):
        if not self.operation and (
            any(
                not (v.result if v.result is not None else self.result)
                or not v.ingredients
                for v in self.variants
            )
        ):
            raise ValueError("Обычный рецепт требует ингредиенты и результат")
        if any(
            sum(r.quantity for r in (v.result if v.result is not None else self.result))
            > 1000
            for v in self.variants
        ) or any(sum(i.quantity for i in v.ingredients) > 1000 for v in self.variants):
            raise ValueError(
                "Рецепт ограничен 1000 входными и 1000 выходными предметами"
            )
        return self


class ReadingText(StrictModel):
    learn_recipes: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "recipes"}
    )
    title: Annotated[str, Field(min_length=1, max_length=200)] = "Без названия"
    pages: Annotated[list[str], Field(min_length=1, max_length=256)] = Field(
        default_factory=lambda: ["Текст записки."],
        description="Страницы текста; длинные страницы дополнительно делятся по размеру окна",
    )
    _title = field_validator("title")(title_text)

    @field_validator("pages")
    @classmethod
    def readable_pages(cls, value):
        for page in value:
            if not page.strip() or len(page) > 20000:
                raise ValueError(
                    "Страница должна содержать от 1 до 20000 символов текста"
                )
            narrative_text(page)
        return value


class EquipmentDocument(Visual):
    size: ItemSize = Field(
        default="medium",
        description="Физический размер предмета, независимый от веса и типа снаряжения",
    )

    @model_validator(mode="before")
    @classmethod
    def legacy_liquids(cls, value):
        from ..domain.liquids import migrate_vessel

        if isinstance(value, dict) and isinstance(value.get("vessel"), dict):
            return dict(value, vessel=migrate_vessel(value["vessel"], value.get("id")))
        return value

    cast_spell: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "spells"}
    )
    spell_bonus: Annotated[int, Field(ge=0, le=5)] = 0
    reading: ReadingText | None = None
    value_gold: Nonnegative | None = None
    group: str = "Снаряжение"
    category: (
        Literal["weapons", "armor", "consumables", "tools", "materials"] | None
    ) = None
    weight: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0
    tags: list[LocalId | Literal["поджог"]] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra=TAG_SCHEMA,
    )
    durability: Positive | None = None
    slot: LocalId | None = None
    properties: list[Effect] = Field(default_factory=list)
    check_aids: list[Aid] = Field(default_factory=list)
    weapon_damage: str | None = None
    damage_type: DamageType = "bludgeoning"
    damage_profile: DamageDefenses = Field(default_factory=DamageDefenses)
    weapon_ability: AbilityName = "strength"
    charges: Positive | None = None
    hands: Annotated[int, Field(ge=0, le=2)] = 0
    light: LightSource | None = None
    vessel: VesselSpec | None = None
    _dice = field_validator("weapon_damage")(ActionFields.damage_valid.__func__)

    @model_validator(mode="after")
    def light_hand(self):
        if "lockpicks" in self.tags and self.durability is None:
            object.__setattr__(self, "durability", 10)
        elif "tool" in self.tags and "lockpicks" not in self.tags:
            object.__setattr__(self, "durability", None)
        if self.cast_spell and (
            self.charges is None
            or self.slot
            or self.properties
            or self.light
            or self.vessel
        ):
            raise ValueError(
                "Свиток требует заряды и не может быть экипировкой, сосудом или иметь другие активные свойства"
            )
        if self.spell_bonus and not self.slot:
            raise ValueError("Магический фокус должен экипироваться")
        if self.vessel and self.light:
            raise ValueError(
                "Сосуд и переносной свет должны быть отдельными предметами"
            )
        if self.light and (self.slot != "hand" or self.hands != 1):
            raise ValueError("Переносной свет должен иметь slot=hand и hands=1")
        return self


def world_effect_schema(schema):
    from ..domain.spellcasting import world_spell_parameters

    schema["world_schemas"] = world_spell_parameters.schemas()
    schema["anyOf"][0]["enum"] = list(world_spell_parameters.models)


class SpellDocument(Visual):
    _effects = field_validator("effects", check_fields=False)(active_effects)
    level: Annotated[int, Field(ge=0, le=9)] = 1
    effects: list[Effect] = Field(default_factory=list)
    target: Literal["self", "other", "any", "item", "cell"] = "self"
    school: Literal[
        "abjuration",
        "conjuration",
        "divination",
        "enchantment",
        "evocation",
        "illusion",
        "necromancy",
        "transmutation",
    ] = "evocation"
    modes: Annotated[list[Literal["combat", "exploration"]], Field(min_length=1)] = (
        Field(default_factory=lambda: ["combat", "exploration"])
    )
    range: Annotated[int, Field(ge=0, le=32)] = 6
    resolution: Literal["automatic", "attack", "save"] = "automatic"
    save_ability: AbilityName | None = None
    cantrip_scaling: bool = False
    wounded_dice: str | None = None
    max_targets: Annotated[int, Field(ge=1, le=32)] = 1
    world_effect: LocalId | None = Field(
        default=None, json_schema_extra=world_effect_schema
    )
    world_parameters: dict = Field(default_factory=dict)
    concentration: bool = False
    pending_effects: list[str] = Field(default_factory=list)
    tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    _wounded = field_validator("wounded_dice")(ActionFields.damage_valid.__func__)

    @model_validator(mode="after")
    def casting_contract(self):
        from ..domain.spellcasting import world_spell_parameters

        parameters = world_spell_parameters.validate(
            self.world_effect, self.world_parameters
        )
        if self.world_effect == "projectile" and not any(
            e.kind == "damage" and e.damage_type is not None for e in self.effects
        ):
            raise ValueError("Снаряд требует эффект урона с указанным типом")
        if (
            self.concentration
            and self.world_effect
            and not hasattr(parameters, "duration")
        ):
            raise ValueError("Концентрация требует длительного эффекта исследования")
        if (self.resolution == "save") != (self.save_ability is not None):
            raise ValueError(
                "Спасбросок требует save_ability; у других бросков это поле пустое"
            )
        if self.cantrip_scaling and self.level != 0:
            raise ValueError("cantrip_scaling допустимо только у заговора")
        if len(self.modes) != len(set(self.modes)):
            raise ValueError("Повторные режимы магии")
        return self


class RaceDocument(Visual):
    tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    damage_profile: DamageDefenses = Field(default_factory=DamageDefenses)
    ability_bonuses: Bonuses = Field(default_factory=Bonuses)
    hp_per_level: Nonnegative = 0
    racial_spell: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "spells"}
    )
    racial_uses: Nonnegative = 0
    speed: Positive = 1
    order: Nonnegative = 0

    @model_validator(mode="after")
    def racial_resource(self):
        if bool(self.racial_spell) != bool(self.racial_uses):
            raise ValueError("racial_spell и racial_uses задаются вместе")
        return self


class ClassDocument(Visual):
    tool_proficiencies: list[LocalId] = Field(default_factory=list)
    starting_recipes: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "recipes"}
    )
    damage_profile: DamageDefenses = Field(default_factory=DamageDefenses)
    spellcasting_ability: AbilityName = "intelligence"
    cantrip_choices: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "spells"}
    )
    cantrips_known: Annotated[int, Field(ge=0, le=20)] = 0

    @model_validator(mode="after")
    def cantrip_selection(self):
        if set(self.cantrip_choices) & set(self.spells):
            raise ValueError(
                "Выбор заговоров не должен повторять уже известные заклинания класса"
            )
        if len(set(self.cantrip_choices)) != len(
            self.cantrip_choices
        ) or self.cantrips_known > len(self.cantrip_choices):
            raise ValueError("Неверный список или количество выбираемых заговоров")
        return self

    @field_validator("spells", "actions", check_fields=False)
    @classmethod
    def unique_refs(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Повторные ссылки")
        return value

    hit_points: Positive = 8
    starting_items: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "equipment"}
    )
    spells: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "spells"}
    )
    spell_slots: dict[Annotated[str, Field(pattern="^[1-9]$")], Nonnegative] = Field(
        default_factory=dict
    )
    actions: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "actions"}
    )
    carry_per_strength: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 5.0
    order: Nonnegative = 0


class BackgroundDocument(Visual):
    tool_proficiencies: list[LocalId] = Field(default_factory=list)
    starting_recipes: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "recipes"}
    )
    classes: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "classes"}
    )
    skills: list[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def skill_names(cls, value):
        return [title_text(name) for name in value]

    ability_bonuses: Bonuses = Field(default_factory=Bonuses)
    starting_items: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "equipment"}
    )
    tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )


class MonsterDocument(Visual):
    damage_profile: DamageDefenses = Field(default_factory=DamageDefenses)
    spellcasting_ability: AbilityName = "intelligence"
    _unique_refs = field_validator("spells", check_fields=False)(
        ClassDocument.unique_refs.__func__
    )
    stats: Scores = Field(default_factory=Scores)
    hit_points: Positive = 7
    armor_class: Nonnegative = 10
    speed: Nonnegative = 1
    initiative_bonus: int = 0
    actions: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "actions"}
    )
    special_actions: list[ActionFields] = Field(default_factory=list)
    inventory: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "equipment"}
    )
    spells: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "spells"}
    )
    spell_slots: dict[Annotated[str, Field(pattern="^[1-9]$")], Nonnegative] = Field(
        default_factory=dict
    )
    tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )

    @model_validator(mode="after")
    def unique_actions(self):
        ids = [r.removeprefix("base:") for r in self.actions] + [
            a.id for a in self.special_actions
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("Повторные действия монстра")
        return self


class Choice(StrictModel):
    _text = field_validator("text", check_fields=False)(narrative_text)
    _effects = field_validator("success", "failure", check_fields=False)(active_effects)
    id: LocalId = "choice"
    text: str = "Осмотреть"
    ability: AbilityName | None = None
    difficulty: Nonnegative = 10
    check_tag: LocalId | Literal[""] = ""
    required_tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    visible_tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    advantage_tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    automatic_tags: list[LocalId] = Field(
        default_factory=list, description=TAGS_DESCRIPTION, json_schema_extra=TAG_SCHEMA
    )
    success: list[Effect] = Field(default_factory=list)
    failure: list[Effect] = Field(default_factory=list)
    minutes: Nonnegative = 1


class ChallengeDocument(Document):
    _text = field_validator("text", check_fields=False)(narrative_text)
    text: str = "Вы находите нечто интересное."
    choices: Annotated[list[Choice], Field(min_length=1)] = Field(
        default_factory=lambda: [Choice()]
    )
    repeatable: bool = False

    @model_validator(mode="after")
    def unique_choices(self):
        if len({c.id for c in self.choices}) != len(self.choices):
            raise ValueError("Повторные варианты")
        return self


class DismantleSpec(StrictModel):
    verb: Literal["dismantle", "butcher", "harvest", "chop", "remove_barricade"] = (
        "dismantle"
    )
    tools: list[LocalId] = Field(
        default_factory=list,
        description="Нужен исправный инструмент с указанным тегом или типом урона. Для сбора и рубки он должен быть в руках.",
    )
    turns: Annotated[int, Field(ge=1, le=1000)] = 3
    fast_tool: LocalId | None = "lever"
    fast_turns: Annotated[int, Field(ge=1, le=1000)] = 1

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_wear(cls, value):
        if isinstance(value, dict) and "fast_tool_wear" in value:
            value = dict(value)
            value.pop("fast_tool_wear")
        return value

    loot: list[RecipeOutput] = Field(default_factory=list, max_length=32)
    bonus_tools: list[LocalId] = Field(
        default_factory=list,
        description="Тег инструмента или тип урона оружия, дающий дополнительную добычу",
    )
    bonus_loot: list[RecipeOutput] = Field(
        default_factory=list,
        max_length=32,
        description="Дополнительные материалы при сборе подходящим инструментом",
    )


class DestructionSpec(StrictModel):
    regrow_as: Ref | None = Field(
        default=None,
        json_schema_extra={"ref_category": "objects"},
        description="Молодое растение, остающееся после сбора до восстановления взрослого. Нужен срок восстановления.",
    )
    regrow_minutes: Annotated[int, Field(ge=1, le=1000000)] | None = Field(
        default=None,
        description="Восстановление после сбора, рубки или разрушения, в игровых минутах. Пусто — не восстанавливается. На занятой клетке появление откладывается.",
    )
    max_hp: Positive = 20
    damage_profile: DamageDefenses = Field(default_factory=DamageDefenses)
    dismantle: DismantleSpec | None = None
    remains: list[RecipeOutput] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def regrowth_requires_time(self):
        if self.regrow_as and not self.regrow_minutes:
            raise ValueError("Для молодого растения нужен срок восстановления")
        return self


class TrapDocument(Visual):
    disarm: RecipeCheck | None = None
    dismantle: DismantleSpec | None = None
    group: str = "Ловушки"
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra=TAG_SCHEMA,
    )
    map_light: TileLight | None = None
    _effects = field_validator("success", "failure", check_fields=False)(active_effects)
    hidden: bool = False
    ability: AbilityName = "dexterity"
    difficulty: Nonnegative = 12
    success: list[Effect] = Field(default_factory=list)
    failure: list[Effect] = Field(default_factory=lambda: [Effect(amount=2)])
    repeatable: bool = False
    trigger: Literal["enter"] = "enter"


class StorageItem(StrictModel):
    item: Ref = Field(json_schema_extra={"ref_category": "equipment"})
    quantity: Annotated[int, Field(ge=1, le=999)] = 1


class LockSpec(StrictModel):
    locked: bool = True
    lock_quality: LockQuality = "normal"
    lock_complexity: LockComplexity = "simple"
    key_tag: LocalId | None = Field(
        default=None, description="Тег подходящего ключа; ключ не расходуется"
    )


class StorageSpec(StrictModel):
    state: Literal["closed", "open"] = "closed"
    lock: LockSpec | None = Field(
        default=None,
        description="Общий замок: качество определяет СЛ, сложность — 1 или 10 ходов",
    )
    max_item_size: ItemSize = Field(
        default="large",
        description="Максимальный размер одной вещи. Меньшие размеры также разрешены; вес ограничен отдельно.",
    )
    open_tool: LocalId | None = None
    search_contents: bool = False
    capacity: Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)] = 1000
    personal: bool = False
    contents: list[StorageItem] = Field(default_factory=list, max_length=256)


def configure_storage(document):
    if "storage" in document.tags and document.storage is None:
        object.__setattr__(document, "storage", StorageSpec())
    elif document.storage is not None and "storage" not in document.tags:
        object.__setattr__(document, "tags", freeze([*document.tags, "storage"]))
    return document


class PointDocument(Visual):
    size: ItemSize = Field(
        default="large", description="Размер при переносе как мебели"
    )
    water_source: WaterSourceSpec | None = None

    destruction: DestructionSpec | None = None
    movable: bool = False
    weight: Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)] = 0
    map_category: MapCategory = Field(
        default="auto",
        description="Раздел палитры карты. Организует кисти; не добавляет игровые действия разрушения или переноса.",
    )
    group: str = "События"
    map_light: TileLight | None = None
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra=TAG_SCHEMA,
    )
    challenge: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "challenges"}
    )
    reading: ReadingText | None = None
    learn_recipes: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "recipes"}
    )
    storage: StorageSpec | None = None
    _storage = model_validator(mode="after")(configure_storage)

    @model_validator(mode="after")
    def interaction_required(self):
        if not (
            self.challenge
            or self.reading
            or self.storage
            or self.learn_recipes
            or self.water_source
        ):
            raise ValueError("Нужно испытание, текст для чтения или контейнер")
        return self


class DoorSpec(LockSpec):
    material: Material = "wood"
    state: Literal["open", "closed"] = "closed"
    locked: bool = False
    lock_quality: LockQuality = "normal"
    lock_complexity: LockComplexity = "simple"
    hit_points: Positive | None = None
    transmits_light: bool = Field(
        default=False, description="Пропускает свет даже в закрытом состоянии"
    )
    openable: bool = Field(
        default=True,
        description="Есть створка: можно открыть и закрыть. Выключите для неподвижной решётки.",
    )
    force_allowed: bool = Field(
        default=True, description="Разрешена попытка выламывания, в том числе ломиком"
    )
    bend_difficulty: Annotated[int, Field(ge=1, le=40)] = 20
    bent: bool = Field(
        default=False,
        description="Начальное состояние прутьев: погнуты, проход свободен",
    )
    foreground: Color | None = Field(
        default=None, description="Собственный цвет двери; пусто — цвет материала"
    )

    @model_validator(mode="after")
    def stone_slab(self):
        if self.bent and self.material != "bars":
            raise ValueError("Погнутыми могут быть только прутья")
        if not self.openable and (self.state == "open" or self.locked):
            raise ValueError("Неподвижная преграда не имеет створки и замка")
        if self.material == "stone":
            object.__setattr__(self, "state", "closed")
            object.__setattr__(self, "locked", False)
        return self


class TileBrush(StrictModel):
    """Authoring recipe: painting creates ordinary, independent map placements."""

    underlay: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "tiles"}
    )

    trap: Ref | None = Field(default=None, json_schema_extra={"ref_category": "traps"})
    interaction: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "points_of_interest"}
    )
    item: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "equipment"}
    )
    light: TileLight | None = None
    transition: bool = False
    door: DoorSpec | None = None


class TileDocument(Visual):
    map_category: MapCategory = Field(
        default="auto",
        description="Раздел палитры карты. Организует кисти; не добавляет игровые действия разрушения или переноса.",
    )
    group: str = "Прочее"
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra=TAG_SCHEMA,
    )
    walkable: bool = True
    blocks_sight: bool = False
    brush: TileBrush = Field(default_factory=TileBrush)
    _group = field_validator("group")(title_text)

    @model_validator(mode="after")
    def reachable_objects(self):
        if self.brush.door:
            spec = self.brush.door
            object.__setattr__(
                self,
                "glyph",
                door_glyph(
                    spec.state == "open",
                    spec.locked,
                    bent=spec.bent,
                    material=spec.material,
                ),
            )
            object.__setattr__(
                self,
                "foreground",
                spec.foreground
                if spec.foreground is not None
                else MATERIALS[spec.material].color,
            )
            object.__setattr__(self, "walkable", spec.state == "open" or spec.bent)
            object.__setattr__(
                self,
                "blocks_sight",
                not self.walkable
                and spec.material != "bars"
                and not spec.transmits_light,
            )
        if (
            not self.brush.door
            and not self.walkable
            and any(
                (
                    self.brush.trap,
                    self.brush.interaction,
                    self.brush.item,
                    self.brush.transition,
                )
            )
        ):
            raise ValueError(
                "Кисть с игровым объектом или переходом должна быть проходимой"
            )
        return self


class LightFixtureSpec(StrictModel):
    item: Ref = Field(json_schema_extra={"ref_category": "equipment"})
    stays_when_empty: bool = True


class WorldObjectDocument(TileDocument):
    loot_tier: Literal["white", "bronze", "iron", "gold"] | None = Field(
        default=None,
        description="Маркер будущей генерации добычи. Сейчас содержимое задаётся вручную.",
    )
    size: ItemSize = Field(
        default="large", description="Размер при переносе как мебели"
    )
    attackable: bool = Field(
        default=True,
        description="Доступно разрушение прямыми атаками. Эффекты окружения и разбор задаются отдельно.",
    )
    poisonous: bool = Field(
        default=False,
        description="При сборе даёт ядовитое растение вместо обычных ингредиентов. Внешний вид не меняется.",
    )
    rarity: Literal["common", "uncommon", "rare"] = "common"
    on_enter: list[Effect] = Field(
        default_factory=list,
        max_length=16,
        description="Воздействия при входе персонажа на клетку объекта",
    )
    _on_enter = field_validator("on_enter")(active_effects)
    light_fixture: LightFixtureSpec | None = None
    campfire: CampfireSpec | None = None
    water_source: WaterSourceSpec | None = None

    door_remains: list[RecipeOutput] = Field(default_factory=list, max_length=32)
    destruction: DestructionSpec | None = None
    movable: bool = False
    weight: Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)] = 0
    """One world object definition: furniture, a door, light or transition."""

    storage: StorageSpec | None = None
    _storage = model_validator(mode="after")(configure_storage)

    @model_validator(mode="after")
    def no_duplicate_mechanics(self):
        if self.light_fixture:
            if self.storage is None:
                object.__setattr__(
                    self,
                    "storage",
                    StorageSpec(contents=[StorageItem(item=self.light_fixture.item)]),
                )
                object.__setattr__(self, "tags", freeze([*self.tags, "storage"]))
            if sum(i.quantity for i in self.storage.contents) > 1 or any(
                i.item != self.light_fixture.item for i in self.storage.contents
            ):
                raise ValueError(
                    "В подставке допустим только один подходящий источник света"
                )
        if self.brush.item or self.brush.trap or self.brush.interaction:
            raise ValueError(
                "Предметы, ловушки и взаимодействия размещаются из собственных шаблонов"
            )
        return self


class Cell(StrictModel):
    mirror_x: bool = False
    char: str = " "
    symbol: Ref | None = Field(
        default=None, json_schema_extra={"ref_category": "symbols"}
    )
    foreground: Color = 7
    background: Color | None = None
    _glyph = field_validator("char")(valid_glyph)


class ArtLayer(StrictModel):
    id: LocalId = "layer"
    name: str = "Слой"
    visible: bool = True
    locked: bool = False
    cells: list[list[Cell | None]]


class ArtDocument(Document):
    width: Annotated[int, Field(ge=1, le=256)] = 16
    height: Annotated[int, Field(ge=1, le=256)] = 8
    layers: list[ArtLayer]

    @model_validator(mode="after")
    def dimensions(self):
        if not self.layers:
            raise ValueError("Нужен хотя бы один слой")
        if len({x.id for x in self.layers}) != len(self.layers):
            raise ValueError("Повторный id слоя")
        for layer in self.layers:
            if len(layer.cells) != self.height or any(
                len(row) != self.width for row in layer.cells
            ):
                raise ValueError(f"Размер слоя {layer.id} не совпадает с холстом")
        return self


class Coordinate(StrictModel):
    x: Nonnegative = 0
    y: Nonnegative = 0


class InitialItemState(StrictModel):
    durability: Nonnegative | None = None
    contaminated: bool = False


class Placement(Coordinate):
    @model_validator(mode="before")
    @classmethod
    def legacy_liquids(cls, value):
        if isinstance(value, dict):
            overrides = value.get("overrides", {})
            vessel = overrides.get("vessel") if isinstance(overrides, dict) else None
            if isinstance(vessel, dict) and (
                "initial_ml" in vessel or "capacity_ml" in vessel
            ):
                from ..domain.liquids import migrate_vessel, legacy_portions

                replacement = migrate_vessel(
                    vessel, value.get("ref", "").removeprefix("base:")
                )
                if "initial_ml" not in vessel and "capacity_ml" in vessel:
                    replacement.pop("initial_portions", None)
                if "initial_ml" in replacement:
                    replacement = dict(replacement)
                    if "initial_portions" in replacement:
                        raise ValueError("Нельзя смешивать старые объёмы и порции")
                    replacement["initial_portions"] = legacy_portions(
                        replacement.pop("initial_ml"), value.get("ref")
                    )
                return dict(value, overrides=dict(overrides, vessel=replacement))
        return value

    id: LocalId
    ref: Ref
    overrides: dict = Field(
        default_factory=dict,
        description="Локальные свойства шаблона; вложенные объекты объединяются, списки заменяются.",
    )
    item_state: InitialItemState | None = Field(
        default=None,
        description="Начальное состояние предмета на земле (только слой предметов)",
    )
    challenge_overrides: dict = Field(
        default_factory=dict, description="Локальные свойства испытания точки интереса"
    )


class Transition(Coordinate):
    id: LocalId
    target: Ref = Field(json_schema_extra={"ref_category": "maps"})


class MapLight(Coordinate):
    id: LocalId
    radius: Annotated[int, Field(ge=1, le=32)] = 6
    bright_radius: Annotated[int, Field(ge=0, le=32)] = 3
    enabled: bool = True

    @model_validator(mode="after")
    def radii(self):
        if self.bright_radius > self.radius:
            raise ValueError("Яркий радиус не может превышать общий радиус света")
        return self


class MapDocument(Document):
    objects: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "objects"}
    )
    doors: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "objects"}
    )
    ambient_light: Literal["dark", "dim", "bright"] = "bright"
    lights: list[MapLight] = Field(default_factory=list)
    width: Annotated[int, Field(ge=1, le=256)] = 20
    height: Annotated[int, Field(ge=1, le=256)] = 12
    tiles: list[list[Ref | None]]
    walkability: list[list[bool]]
    blocks_sight: list[list[bool]]
    tile_mirrors: list[list[bool]] = Field(
        default_factory=lambda data: [
            [False] * data["width"] for _ in range(data["height"])
        ],
        description="Горизонтальное отражение отдельных клеток поверхностей относительно шаблона",
    )
    roof: list[list[bool]] = Field(
        default_factory=lambda data: [
            [False] * data["width"] for _ in range(data["height"])
        ],
        description="Крыша отключает общий свет клетки, не перекрывая источники света.",
    )
    decorations: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "art"}
    )
    traps: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "traps"}
    )
    points_of_interest: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "points_of_interest"}
    )
    monsters: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "monsters"}
    )
    equipment: list[Placement] = Field(
        default_factory=list, json_schema_extra={"ref_category": "equipment"}
    )
    spawn: Coordinate = Field(default_factory=Coordinate)
    transitions: list[Transition] = Field(default_factory=list)

    @model_validator(mode="after")
    def map_valid(self):
        for name in ("tiles", "walkability", "blocks_sight", "roof", "tile_mirrors"):
            grid = getattr(self, name)
            if len(grid) != self.height or any(len(row) != self.width for row in grid):
                raise ValueError(f"Размер {name} не совпадает с картой")
        if (
            self.spawn.x >= self.width
            or self.spawn.y >= self.height
            or not self.walkability[self.spawn.y][self.spawn.x]
        ):
            raise ValueError("Старт героя должен быть на проходимой клетке")
        ids = set()
        occupied = {(self.spawn.x, self.spawn.y)}
        for category in (
            "decorations",
            "doors",
            "objects",
            "traps",
            "points_of_interest",
            "monsters",
            "equipment",
            "transitions",
            "lights",
        ):
            for entry in getattr(self, category):
                if (
                    getattr(entry, "item_state", None) is not None
                    and category != "equipment"
                ):
                    raise ValueError(
                        "Начальное состояние предмета допустимо только в слое equipment"
                    )
                if entry.id in ids:
                    raise ValueError("Повторный id размещения")
                ids.add(entry.id)
                if entry.x >= self.width or entry.y >= self.height:
                    raise ValueError(f"{entry.id}: за пределами карты")
                if (
                    category not in ("decorations", "lights", "doors", "objects")
                    and not self.walkability[entry.y][entry.x]
                ):
                    raise ValueError(f"{entry.id}: непроходимая клетка")
                if category == "monsters":
                    if (entry.x, entry.y) in occupied:
                        raise ValueError("Существа занимают одну клетку")
                    occupied.add((entry.x, entry.y))
        return self


MODELS = {
    "symbols": SymbolDocument,
    "recipes": RecipeDocument,
    "art": ArtDocument,
    "tiles": TileDocument,
    "objects": WorldObjectDocument,
    "maps": MapDocument,
    "monsters": MonsterDocument,
    "equipment": EquipmentDocument,
    "spells": SpellDocument,
    "actions": ActionDocument,
    "classes": ClassDocument,
    "races": RaceDocument,
    "backgrounds": BackgroundDocument,
    "challenges": ChallengeDocument,
    "traps": TrapDocument,
    "points_of_interest": PointDocument,
}
