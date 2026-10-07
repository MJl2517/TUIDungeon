"""Versioned authoring contracts. JSON Schema drives the Studio forms."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from wcwidth import wcwidth
from ..domain.definitions import DiceExpression

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


class Effect(StrictModel):
    kind: LocalId = "damage"
    amount: Nonnegative = 0
    dice: str | None = None
    condition: str = ""
    duration: Positive = 1
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


class Visual(Document):
    glyph: str = "?"
    foreground: Color = 7
    background: Color | None = None
    art: Ref | None = Field(default=None, json_schema_extra={"ref_category": "art"})
    _glyph = field_validator("glyph")(valid_glyph)


class Aid(StrictModel):
    check_tag: LocalId = "lockpicking"
    mode: Literal["advantage", "automatic"] = "advantage"


class EquipmentDocument(Visual):
    weight: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0
    tags: list[LocalId] = Field(default_factory=list)
    durability: Positive | None = None
    slot: LocalId | None = None
    properties: list[Effect] = Field(default_factory=list)
    check_aids: list[Aid] = Field(default_factory=list)
    weapon_damage: str | None = None
    weapon_ability: AbilityName = "strength"
    charges: Positive | None = None
    _dice = field_validator("weapon_damage")(ActionFields.damage_valid.__func__)


class SpellDocument(Visual):
    _effects = field_validator("effects", check_fields=False)(active_effects)
    level: Annotated[int, Field(ge=0, le=9)] = 1
    effects: list[Effect] = Field(default_factory=list)
    target: Literal["self", "other", "any"] = "self"


class RaceDocument(Visual):
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
    ability_bonuses: Bonuses = Field(default_factory=Bonuses)
    starting_items: list[Ref] = Field(
        default_factory=list, json_schema_extra={"ref_category": "equipment"}
    )
    tags: list[LocalId] = Field(default_factory=list)


class MonsterDocument(Visual):
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
    _effects = field_validator("success", "failure", check_fields=False)(active_effects)
    hidden: bool = False
    ability: AbilityName = "dexterity"
    difficulty: Nonnegative = 12
    success: list[Effect] = Field(default_factory=list)
    failure: list[Effect] = Field(default_factory=lambda: [Effect(amount=2)])
    repeatable: bool = False
    trigger: Literal["enter"] = "enter"


class PointDocument(Visual):
    challenge: Ref = Field(json_schema_extra={"ref_category": "challenges"})


class TileDocument(Visual):
    walkable: bool = True
    blocks_sight: bool = False


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


class Transition(Coordinate):
    id: LocalId
    target: Ref = Field(json_schema_extra={"ref_category": "maps"})


class MapDocument(Document):
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
            "traps",
            "points_of_interest",
            "monsters",
            "equipment",
            "transitions",
        ):
            for entry in getattr(self, category):
                if entry.id in ids:
                    raise ValueError("Повторный id размещения")
                ids.add(entry.id)
                if entry.x >= self.width or entry.y >= self.height:
                    raise ValueError(f"{entry.id}: за пределами карты")
                if category != "decorations" and not self.walkability[entry.y][entry.x]:
                    raise ValueError(f"{entry.id}: непроходимая клетка")
                if category == "monsters":
                    if (entry.x, entry.y) in occupied:
                        raise ValueError("Существа занимают одну клетку")
                    occupied.add((entry.x, entry.y))
        return self


MODELS = {
    "art": ArtDocument,
    "tiles": TileDocument,
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
