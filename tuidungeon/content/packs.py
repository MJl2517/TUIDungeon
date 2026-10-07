"""Validated packs, references, optimistic concurrency and atomic document writes."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from .schemas import MODELS, Manifest
from .catalog import ContentCatalog, ContentError, ACTION_KINDS, no_duplicate_fields
from ..domain.mechanics import mechanics

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKS = PROJECT_ROOT / "packs"
REF_FIELDS = {
    "art": "art",
    "racial_spell": "spells",
    "spells": "spells",
    "actions": "actions",
    "starting_items": "equipment",
    "inventory": "equipment",
    "challenge": "challenges",
    "tiles": "tiles",
    "target": "maps",
}


class Conflict(ContentError):
    pass


class Referenced(ContentError):
    pass


def split_ref(ref):
    if not isinstance(ref, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]*:[a-z][a-z0-9_]*", ref
    ):
        raise ContentError("Нужна ссылка pack_id:local_id")
    return ref.split(":")


def runtime_key(ref):
    return ref.removeprefix("base:")


def references(raw, category):
    """Yield (category, reference, field path) using typed contract field names."""

    def visit(value, key="", path="", placement_category=None):
        if isinstance(value, dict):
            for k, v in value.items():
                context = (
                    ("art" if k == "decorations" else k)
                    if category == "maps"
                    and k
                    in (
                        "decorations",
                        "traps",
                        "points_of_interest",
                        "monsters",
                        "equipment",
                    )
                    else placement_category
                )
                yield from visit(v, k, f"{path}.{k}".strip("."), context)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from visit(v, key, f"{path}[{i}]", placement_category)
        elif isinstance(value, str) and ":" in value:
            destination = placement_category if key == "ref" else REF_FIELDS.get(key)
            if destination:
                yield destination, value, path

    yield from visit(raw)


class PackStore:
    def __init__(self, root=DEFAULT_PACKS):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self.reload()

    def reload(self):
        with self.lock:
            manifests = {}
            documents = {}
            paths = {}
            versions = {}
            for path in sorted(self.root.glob("*/manifest.json")):
                if not path.resolve().is_relative_to(self.root):
                    raise ContentError("Пакет должен находиться внутри packs/")
                manifest = Manifest.model_validate(self.read_json(path))
                if manifest.id != path.parent.name:
                    raise ContentError(f"{path}: id пакета не совпадает с папкой")
                if manifest.id in manifests:
                    raise ContentError("Повторный пакет")
                manifests[manifest.id] = manifest
                for category, model in MODELS.items():
                    for file in sorted((path.parent / category).rglob("*.json")):
                        if not file.resolve().is_relative_to(self.root):
                            raise ContentError(
                                "Контент должен находиться внутри packs/"
                            )
                        try:
                            data = file.read_bytes()
                            doc = model.model_validate(
                                json.loads(
                                    data.decode("utf-8"),
                                    object_pairs_hook=no_duplicate_fields,
                                )
                            )
                        except (ValueError, OSError) as error:
                            raise ContentError(f"{file}: {error}") from error
                        key = (category, f"{manifest.id}:{doc.id}")
                        if key in documents:
                            raise ContentError(f"{file}: повторный id {key[1]}")
                        documents[key] = doc
                        paths[key] = file
                        versions[key] = sha256(data).hexdigest()
            if not manifests:
                raise ContentError("Нет пакетов контента")
            self.validate_dependencies(manifests)
            self.validate_references(documents, manifests)
            self.manifests, self.documents, self.paths, self.versions = (
                manifests,
                documents,
                paths,
                versions,
            )

    @staticmethod
    def read_json(path):
        try:
            return json.loads(
                path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_fields
            )
        except (ValueError, OSError) as error:
            raise ContentError(f"{path}: {error}") from error

    @staticmethod
    def version(path):
        return sha256(path.read_bytes()).hexdigest() if path.exists() else None

    @staticmethod
    def validate_dependencies(manifests):
        done = set()
        active = set()

        def visit(identifier):
            if identifier in active:
                raise ContentError(f"Цикл зависимостей: {identifier}")
            if identifier in done:
                return
            if identifier not in manifests:
                raise ContentError(f"Отсутствует зависимость {identifier}")
            active.add(identifier)
            for dep in manifests[identifier].dependencies:
                visit(dep)
            active.remove(identifier)
            done.add(identifier)

        for identifier in manifests:
            visit(identifier)

    @staticmethod
    def validate_references(documents, manifests):
        def allowed(pack):
            result = {pack}
            for dep in manifests[pack].dependencies:
                result.update(allowed(dep))
            return result

        for (category, ref), doc in documents.items():
            pack = split_ref(ref)[0]
            for destination, target, path in references(
                doc.model_dump(mode="json"), category
            ):
                if (destination, target) not in documents:
                    raise ContentError(
                        f"{ref}.{path}: неизвестная ссылка {destination}/{target}"
                    )
                if split_ref(target)[0] not in allowed(pack):
                    raise ContentError(
                        f"{ref}: пакет ссылки {target} не указан в зависимостях"
                    )
            if category == "maps":
                for entry in doc.decorations:
                    art = documents[("art", entry.ref)]
                    if (
                        entry.x + art.width > doc.width
                        or entry.y + art.height > doc.height
                    ):
                        raise ContentError(
                            f"{ref}: рисунок {entry.id} выходит за карту"
                        )

    def get(self, category, ref):
        if category not in MODELS:
            raise ContentError("Неизвестная категория")
        split_ref(ref)
        if (category, ref) not in self.documents:
            raise ContentError(f"Не найден {category}/{ref}")
        return self.documents[(category, ref)]

    def envelope(self, category, ref):
        key = (category, ref)
        return {
            "document": self.get(category, ref).model_dump(mode="json"),
            "version": self.versions[key],
            "usages": self.usages(category, ref),
            "warnings": self.warnings(category, ref),
        }

    def usages(self, category, ref):
        return [
            {"category": c, "ref": r, "field": path}
            for (c, r), doc in self.documents.items()
            for dest, target, path in references(doc.model_dump(mode="json"), c)
            if dest == category and target == ref
        ]

    def warnings(self, category, ref):
        if category != "maps":
            return []
        doc = self.get(category, ref)
        reachable = {(doc.spawn.x, doc.spawn.y)}
        pending = list(reachable)
        while pending:
            x, y = pending.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (
                    0 <= nx < doc.width
                    and 0 <= ny < doc.height
                    and doc.walkability[ny][nx]
                    and (nx, ny) not in reachable
                ):
                    reachable.add((nx, ny))
                    pending.append((nx, ny))
        isolated = [
            {"x": x, "y": y}
            for y in range(doc.height)
            for x in range(doc.width)
            if doc.walkability[y][x] and (x, y) not in reachable
        ]
        return (
            [{"message": f"Недостижимых клеток: {len(isolated)}", "cells": isolated}]
            if isolated
            else []
        )

    def save(self, category, ref, raw, expected_version):
        with self.lock:
            pack, identifier = split_ref(ref)
            if category not in MODELS or pack not in self.manifests:
                raise ContentError("Неизвестная категория или пакет")
            document = MODELS[category].model_validate(raw)
            if document.id != identifier:
                raise ContentError("id зафиксирован; используйте дублирование")
            key = (category, ref)
            path = self.paths.get(
                key,
                self.root
                / pack
                / category
                / f"{identifier}{'.art' if category == 'art' else ''}.json",
            )
            if self.version(path) != expected_version:
                raise Conflict(
                    "Файл изменён другим редактором. Перечитайте документ перед сохранением."
                )
            # Re-read external edits before validating the transaction.
            self.reload()
            candidate = dict(self.documents)
            candidate[key] = document
            self.validate_references(candidate, self.manifests)
            if self.version(path) != expected_version:
                raise Conflict("Файл изменён во время проверки")
            self.atomic_json(path, document.model_dump(mode="json"))
            self.reload()
            return self.envelope(category, ref)

    def delete(self, category, ref, expected_version):
        with self.lock:
            self.reload()
            key = (category, ref)
            self.get(category, ref)
            if self.versions[key] != expected_version:
                raise Conflict("Файл изменён другим редактором")
            usages = self.usages(category, ref)
            if usages:
                raise Referenced(
                    "Объект используется: " + ", ".join(u["ref"] for u in usages)
                )
            self.paths[key].unlink()
            self.reload()

    def create_pack(self, raw):
        with self.lock:
            manifest = Manifest.model_validate(raw)
            if manifest.id in self.manifests:
                raise Conflict("Пакет уже существует")
            candidate = dict(self.manifests)
            candidate[manifest.id] = manifest
            self.validate_dependencies(candidate)
            self.atomic_json(
                self.root / manifest.id / "manifest.json",
                manifest.model_dump(mode="json"),
            )
            for category in MODELS:
                (self.root / manifest.id / category).mkdir(exist_ok=True)
            self.reload()
            return manifest

    @staticmethod
    def atomic_json(path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp = tempfile.mkstemp(
            dir=path.parent, prefix=".studio-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(raw, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def runtime_catalog(self):
        """Adapt validated authoring definitions to the existing pure domain objects."""
        result = ContentCatalog()
        sources = {}

        def adapt(value):
            if isinstance(value, list):
                return [adapt(v) for v in value]
            if isinstance(value, dict):
                return {k: adapt(v) for k, v in value.items()}
            if isinstance(value, str) and re.fullmatch(
                r"[a-z][a-z0-9_]*:[a-z][a-z0-9_]*", value
            ):
                return runtime_key(value)
            return value

        for (category, ref), doc in self.documents.items():
            if category not in result.__dataclass_fields__:
                continue
            raw = adapt(doc.model_dump(mode="json"))
            raw.pop("schema_version", None)
            raw["id"] = runtime_key(ref)
            for key in ("glyph", "foreground", "background"):
                raw.pop(key, None)
            if category != "monsters":
                raw.pop("art", None)
            else:
                raw["art"] = (
                    None  # Portraits are rendered by the shared art compositor.
                )
            if category == "challenges":
                raw.pop("description", None)
                for choice in raw["choices"]:
                    if not choice.get("check_tag"):
                        choice.pop("check_tag", None)
            definition = result._parse(
                category, raw, ACTION_KINDS, frozenset(mechanics.entries)
            )
            getattr(result, category)[definition.id] = definition
            sources[(category, definition.id)] = ref
        result._validate_references(sources)
        return result
