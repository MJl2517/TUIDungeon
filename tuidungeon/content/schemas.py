"""Versioned authoring contracts. JSON Schema drives the Studio forms."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from wcwidth import wcwidth
from ..domain.definitions import DiceExpression
from ..domain.value_types import freeze
from ..domain.doors import Material, LockQuality, LockComplexity, MATERIALS, door_glyph
from ..domain.materials import TAGS_DESCRIPTION, TAG_LABELS
from ..domain.damage import DamageType, DamageSelector

LocalId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Ref = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")]
AbilityName = Literal[
    "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"
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
    name: str
    glyph: str
    foreground: Color = 7
    background: Color | None = None
    _name = field_validator("name")(title_text)
    _glyph = field_validator("glyph")(valid_glyph)


class Visual(Document):
    variants: list[VisualVariant] = Field(
        default_factory=list,
        description="Варианты внешнего вида без копирования механик",
    )
    glyph: str = "?"
    foreground: Color = 7
    background: Color | None = None
    art: Ref | None = Field(default=None, json_schema_extra={"ref_category": "art"})
    _glyph = field_validator("glyph")(valid_glyph)


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


class EquipmentDocument(Visual):
    group: str = "Снаряжение"
    category: Literal["weapons", "armor", "consumables", "tools"] | None = None
    weight: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0
    tags: list[LocalId | Literal["поджог"]] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra={"tag_labels": TAG_LABELS},
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
    _dice = field_validator("weapon_damage")(ActionFields.damage_valid.__func__)

    @model_validator(mode="after")
    def light_hand(self):
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
    tags: list[LocalId] = Field(default_factory=list)
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
    tags: list[LocalId] = Field(default_factory=list)


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
    tags: list[LocalId] = Field(default_factory=list)

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
    required_tags: list[LocalId] = Field(default_factory=list)
    visible_tags: list[LocalId] = Field(default_factory=list)
    advantage_tags: list[LocalId] = Field(default_factory=list)
    automatic_tags: list[LocalId] = Field(default_factory=list)
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


class TrapDocument(Visual):
    group: str = "Ловушки"
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra={"tag_labels": TAG_LABELS},
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


class StorageSpec(StrictModel):
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
    group: str = "События"
    map_light: TileLight | None = None
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra={"tag_labels": TAG_LABELS},
    )
    challenge: Ref = Field(json_schema_extra={"ref_category": "challenges"})
    storage: StorageSpec | None = None
    _storage = model_validator(mode="after")(configure_storage)


class DoorSpec(StrictModel):
    material: Material = "wood"
    state: Literal["open", "closed"] = "closed"
    locked: bool = False
    lock_quality: LockQuality = "normal"
    lock_complexity: LockComplexity = "simple"
    hit_points: Positive | None = None

    @model_validator(mode="after")
    def stone_slab(self):
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
    group: str = "Прочее"
    tags: list[LocalId] = Field(
        default_factory=list,
        description=TAGS_DESCRIPTION,
        json_schema_extra={"tag_labels": TAG_LABELS},
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
                door_glyph(spec.state == "open", spec.locked, material=spec.material),
            )
            object.__setattr__(self, "foreground", MATERIALS[spec.material].color)
            object.__setattr__(self, "walkable", spec.state == "open")
            object.__setattr__(
                self, "blocks_sight", spec.state != "open" and spec.material != "bars"
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


class WorldObjectDocument(TileDocument):
    """One world object definition: furniture, a door, light or transition."""

    storage: StorageSpec | None = None
    _storage = model_validator(mode="after")(configure_storage)

    @model_validator(mode="after")
    def no_duplicate_mechanics(self):
        if self.brush.item or self.brush.trap or self.brush.interaction:
            raise ValueError(
                "Предметы, ловушки и взаимодействия размещаются из собственных шаблонов"
            )
        return self


class Cell(StrictModel):
    char: str = " "
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


class Placement(Coordinate):
    id: LocalId
    ref: Ref
    overrides: dict = Field(
        default_factory=dict,
        description="Локальные свойства шаблона; вложенные объекты объединяются, списки заменяются.",
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
        for name in ("tiles", "walkability", "blocks_sight"):
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
