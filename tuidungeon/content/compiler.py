"""Explicit authoring-to-runtime boundary, independent of files and frontends."""

from dataclasses import dataclass, field
from functools import cached_property
from types import MappingProxyType
from threading import RLock
from typing import Mapping
from pydantic import BaseModel

from .catalog import ContentCatalog, ACTION_KINDS, ContentError
from .schemas import MODELS
from ..domain.mechanics import mechanics
from ..domain.value_types import FrozenDict


def runtime_key(ref):
    return ref.removeprefix("base:")


REFERENCE_FIELDS = {
    "equipment": ("art",),
    "spells": ("art",),
    "actions": (),
    "races": ("art", "racial_spell"),
    "classes": ("art", "starting_items", "spells", "actions"),
    "backgrounds": ("art", "classes", "starting_items"),
    "monsters": ("art", "inventory", "spells", "actions"),
    "challenges": (),
}


class CompiledCatalog(ContentCatalog):
    """Catalog definitions can be read but not replaced after compilation."""

    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise TypeError("Каталог сессии неизменяем; создайте новый снимок контента")
        super().__setattr__(name, value)

    def seal(self):
        for category in self.__dataclass_fields__:
            setattr(self, category, FrozenDict(getattr(self, category)))
        self._sealed = True
        return self


def compile_catalog(documents):
    result, sources = CompiledCatalog(), {}
    for (category, ref), doc in documents.items():
        if category not in REFERENCE_FIELDS:
            continue
        raw = doc.model_dump(mode="json")
        for name in REFERENCE_FIELDS[category]:
            value = raw.get(name)
            if isinstance(value, list):
                raw[name] = [runtime_key(v) for v in value]
            elif isinstance(value, str):
                raw[name] = runtime_key(value)
        raw.pop("schema_version", None)
        raw["id"] = runtime_key(ref)
        for name in ("glyph", "foreground", "background", "art"):
            raw.pop(name, None)
        if category == "monsters":
            raw["art"] = None
        if category == "challenges":
            raw.pop("description", None)
            for choice in raw["choices"]:
                if not choice.get("check_tag"):
                    choice.pop("check_tag", None)
        definition = result._parse(
            category, raw, ACTION_KINDS, frozenset(mechanics.entries)
        )
        getattr(result, category)[definition.id] = definition
        sources[category, definition.id] = ref
    result._validate_references(sources)
    return result.seal()


@dataclass(frozen=True)
class ContentSnapshot:
    """Pinned immutable definitions shared by independent game sessions."""

    documents: Mapping[tuple[str, str], BaseModel]
    lock: object = field(default_factory=RLock, repr=False, compare=False)

    @classmethod
    def create(cls, documents):
        return cls(MappingProxyType(dict(documents)))

    def get(self, category, ref):
        if category not in MODELS:
            raise ContentError("Неизвестная категория")
        try:
            return self.documents[category, ref]
        except KeyError:
            raise ContentError(f"Не найден {category}/{ref}") from None

    @cached_property
    def catalog(self):
        return compile_catalog(self.documents)

    def runtime_catalog(self):
        with self.lock:
            return self.catalog

    @cached_property
    def _terrains(self):
        return {}

    def terrain(self, ref):
        from ..world.terrain import Terrain

        with self.lock:
            if ref not in self._terrains:
                self._terrains[ref] = Terrain.compile(self, self.get("maps", ref))
            return self._terrains[ref]

    def snapshot(self):
        return self
