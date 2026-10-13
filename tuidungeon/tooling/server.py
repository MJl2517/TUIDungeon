"""Loopback-only Studio API. No shell commands or arbitrary paths are accepted."""

from pathlib import Path
import json
import socket
from typing import Literal
from urllib.error import URLError
from urllib.request import urlopen
import threading
import sys
import webbrowser
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError, BaseModel, ConfigDict, Field
from ..content.packs import (
    PackStore,
    ContentError,
    Conflict,
    Referenced,
    PROJECT_ROOT,
    DEFAULT_PACKS,
)
from ..content.schemas import MODELS
from ..content.migrations import migrate_map, migrate_document
from ..domain.mechanics import mechanics
from ..presentation.art import import_txt
from .launcher import open_test_map


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SaveRequest(RequestModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: dict
    version: str | None = None


class VersionRequest(RequestModel):
    version: str


class GameRequest(RequestModel):
    map_ref: str
    seed: int = 42
    character_class: str = "base:warrior"


class SandboxRequest(RequestModel):
    monster: str
    action: str
    seed: int = 0
    difficulty: int = Field(default=12, ge=0)
    spell_id: str | None = None
    target: Literal["hero", "self"] = "hero"


LABELS = {
    "symbols": "Символы",
    "recipes": "Рецепты",
    "art": "Графика",
    "tiles": "Поверхности",
    "objects": "Объекты окружения",
    "maps": "Подземелья",
    "monsters": "Монстры",
    "equipment": "Предметы",
    "spells": "Заклинания",
    "actions": "Действия",
    "classes": "Классы",
    "races": "Расы",
    "backgrounds": "Предыстории",
    "challenges": "Испытания",
    "traps": "Ловушки",
    "points_of_interest": "Точки интереса",
}
ASSET_CATEGORIES = frozenset(
    {
        "symbols",
        "spells",
        "classes",
        "races",
        "backgrounds",
        "art",
        "tiles",
        "objects",
        "traps",
        "points_of_interest",
        "monsters",
        "equipment",
        "actions",
        "challenges",
    }
)


def template(store, category):
    candidates = [doc for (c, _), doc in store.documents.items() if c == category]
    if candidates:
        raw = candidates[0].model_dump(mode="json")
    else:
        raw = {"id": "new_object", "name": "Новый объект"}
        if category == "points_of_interest":
            raw["challenge"] = next(
                (ref for c, ref in store.documents if c == "challenges"),
                next(iter(store.manifests)) + ":new_challenge",
            )
        elif category == "maps":
            raw.update(
                width=20,
                height=12,
                tiles=[[None] * 20 for _ in range(12)],
                walkability=[[True] * 20 for _ in range(12)],
                blocks_sight=[[False] * 20 for _ in range(12)],
                roof=[[False] * 20 for _ in range(12)],
                tile_mirrors=[[False] * 20 for _ in range(12)],
            )
        elif category == "art":
            raw.update(
                width=16,
                height=8,
                layers=[
                    {
                        "id": "base",
                        "name": "Основной",
                        "cells": [[None] * 16 for _ in range(8)],
                    }
                ],
            )
    raw["id"] = "new_object"
    raw["name"] = "Новый объект"
    if category == "art":
        raw.update(
            width=16,
            height=8,
            layers=[
                {
                    "id": "base",
                    "name": "Основной",
                    "visible": True,
                    "locked": False,
                    "cells": [[None] * 16 for _ in range(8)],
                }
            ],
        )
    if category in ("tiles", "objects"):
        raw.update(
            glyph=".",
            foreground=7,
            background=None,
            art=None,
            description="",
            group="Прочее",
            tags=[],
            walkable=True,
            blocks_sight=False,
            brush={},
        )
    if category == "maps":
        raw["tile_mirrors"] = [[False] * 20 for _ in range(12)]
        raw.update(
            lights=[],
            ambient_light="bright",
            width=20,
            height=12,
            tiles=[[None] * 20 for _ in range(12)],
            walkability=[[True] * 20 for _ in range(12)],
            blocks_sight=[[False] * 20 for _ in range(12)],
            roof=[[False] * 20 for _ in range(12)],
            spawn={"x": 1, "y": 1},
            decorations=[],
            objects=[],
            doors=[],
            traps=[],
            points_of_interest=[],
            monsters=[],
            equipment=[],
            transitions=[],
        )
    return MODELS[category].model_validate(raw).model_dump(mode="json")


def create_app(root=None, dist=None):
    store = PackStore(root) if root else PackStore()
    app = FastAPI(title="TUI Dungeon Studio", docs_url=None, redoc_url=None)
    app.state.store = store

    @app.get("/api/status")
    def status():
        return {"studio": "TUI Dungeon Studio", "packs_dir": str(store.root.resolve())}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        if host not in ("127.0.0.1", "localhost"):
            return JSONResponse(
                {"detail": "Студия доступна только локально"}, status_code=403
            )
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse(
                {"detail": "Запрос с другого сайта запрещён"}, status_code=403
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ContentError)
    async def content_error(request, error):
        return JSONResponse(
            {"detail": str(error)},
            status_code=409 if isinstance(error, (Conflict, Referenced)) else 422,
        )

    @app.exception_handler(ValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            {
                "detail": [
                    {"path": ".".join(map(str, e["loc"])), "message": e["msg"]}
                    for e in error.errors()
                ]
            },
            status_code=422,
        )

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.get("/api/library")
    def library():
        store.reload()
        usage_index = store.reference_index()
        return {
            "packs": [m.model_dump() for m in store.manifests.values()],
            "categories": LABELS,
            "documents": [
                {
                    "category": c,
                    "ref": r,
                    "id": d.id,
                    "name": d.name,
                    "description": getattr(d, "description", ""),
                    "asset": c in ASSET_CATEGORIES,
                    "version": store.versions[(c, r)],
                    "glyph": getattr(d, "glyph", None),
                    "symbol": getattr(d, "symbol", None),
                    "usage_count": len(usage_index.get((c, r), ())),
                    "source_name": getattr(getattr(d, "source", None), "name", None),
                    "classes": getattr(d, "classes", []),
                    "group": getattr(d, "group", None),
                    "tags": getattr(d, "tags", []),
                    "details": {
                        key: getattr(d, key)
                        for key in (
                            "category",
                            "map_category",
                            "level",
                            "school",
                            "hit_points",
                            "armor_class",
                            "speed",
                            "kind",
                            "basic_known",
                            "walkable",
                            "blocks_sight",
                            "ambient_light",
                            "width",
                            "height",
                            "reviewed",
                        )
                        if getattr(d, key, None) is not None
                    },
                    "features": {
                        key: bool(getattr(d, key, None))
                        for key in ("reading", "storage", "map_light")
                    },
                    "search_text": d.model_dump_json()
                    if c not in ("maps", "art")
                    else "",
                }
                for (c, r), d in store.documents.items()
            ],
        }

    @app.get("/api/assets")
    def assets():
        categories = ASSET_CATEGORIES
        with store.lock:
            store.reload()
            return {
                "documents": {
                    f"{c}/{r}": doc.model_dump(mode="json")
                    for (c, r), doc in store.documents.items()
                    if c in categories
                },
                "versions": {
                    f"{c}/{r}": v
                    for (c, r), v in store.versions.items()
                    if c in categories
                },
            }

    @app.get("/api/schemas")
    def schemas():
        return {
            "schemas": {c: m.model_json_schema() for c, m in MODELS.items()},
            "mechanics": mechanics.schemas(),
            "templates": {c: template(store, c) for c in MODELS},
        }

    @app.get("/api/documents/{category}/{ref}")
    def get_document(category, ref):
        store.reload()
        return store.envelope(category, ref)

    @app.put("/api/documents/{category}/{ref}")
    def save_document(category, ref, request: SaveRequest):
        from ..content.symbols import bind_legacy_visuals
        from ..content.schemas import Visual

        with store.lock:
            store.reload()
            raw = request.document
            if category in MODELS and (
                issubclass(MODELS[category], Visual) or category in ("art", "maps")
            ):
                raw = (
                    migrate_map(raw)
                    if category == "maps"
                    else migrate_document(raw, category)
                )
                raw = MODELS[category].model_validate(raw).model_dump(mode="json")
                raw = bind_legacy_visuals(store, raw, ref.split(":")[0])
            return store.save(category, ref, raw, request.version)

    @app.post("/api/validate/{category}/{ref}")
    def validate_document(category, ref, request: SaveRequest):
        store.reload()
        doc = MODELS.get(category)
        if not doc:
            raise ContentError("Неизвестная категория")
        raw = (
            migrate_map(request.document)
            if category == "maps"
            else migrate_document(request.document, category)
        )
        model = doc.model_validate(raw)
        candidate = dict(store.documents)
        candidate[(category, ref)] = model
        store.validate_references(candidate, store.manifests)
        return {"valid": True}

    @app.delete("/api/documents/{category}/{ref}")
    def delete_document(category, ref, request: VersionRequest):
        store.delete(category, ref, request.version)
        return {"deleted": True}

    @app.post("/api/packs")
    def create_pack(raw: dict):
        return store.create_pack(raw).model_dump()

    @app.get("/api/packs/{pack}")
    def get_pack(pack):
        return store.pack_envelope(pack)

    @app.put("/api/packs/{pack}")
    def save_pack(pack, request: SaveRequest):
        return store.save_pack(pack, request.document, request.version)

    @app.delete("/api/packs/{pack}")
    def delete_pack(pack, request: VersionRequest):
        return store.delete_pack(pack, request.version)

    @app.post("/api/art/import")
    def import_art(raw: dict):
        from ..content.symbols import resolve_text

        store.reload()
        document = import_txt(
            raw.get("text", ""),
            raw.get("id", "imported"),
            raw.get("name", "Импорт TXT"),
        ).model_dump(mode="json")
        refs = resolve_text(store, raw.get("text", "") + " ", raw.get("pack", "base"))
        for layer in document["layers"]:
            for row in layer["cells"]:
                for cell in row:
                    cell["symbol"] = refs.get(cell["char"], "base:glyph_0020")
        return document

    @app.post("/api/symbols/resolve-text")
    def resolve_typed_symbols(raw: dict):
        from ..content.symbols import resolve_text

        store.reload()
        return {
            "symbols": resolve_text(store, raw.get("text", ""), raw.get("pack", "base"))
        }

    @app.post("/api/art/check")
    def check_art(raw: dict):
        from ..content.schemas import valid_glyph

        issues = []
        for index, layer in enumerate(raw.get("document", {}).get("layers", [])):
            for y, row in enumerate(layer.get("cells", [])):
                for x, cell in enumerate(row):
                    if cell is None:
                        continue
                    try:
                        valid_glyph(cell.get("char", ""))
                    except ValueError as error:
                        issues.append(
                            {"layer": index, "x": x, "y": y, "message": str(error)}
                        )
        return {"issues": issues}

    @app.get("/api/art/{ref}/export")
    def export_art(ref):
        from ..content.symbols import appearance
        from ..world.graphics import compose

        doc = store.get("art", ref)
        return {
            "text": "\n".join(
                "".join(appearance(store.documents, c)[0] if c else " " for c in row)
                for row in compose(doc)
            )
            + "\n"
        }

    @app.post("/api/game")
    def launch_game(request: GameRequest):
        store.reload()
        store.get("maps", request.map_ref)
        store.get("classes", request.character_class)
        from ..application.factories import create_test_hero
        from ..content.packs import runtime_key

        create_test_hero(store.runtime_catalog(), runtime_key(request.character_class))
        try:
            open_test_map(
                store.root, request.map_ref, request.seed, request.character_class
            )
        except OSError as error:
            raise HTTPException(
                503, f"Не удалось открыть игровое окно: {error}"
            ) from error
        return {"started": True, "map_ref": request.map_ref}

    @app.post("/api/sandbox")
    def sandbox(request: SandboxRequest):
        import random
        from ..application.factories import SessionFactory
        from ..content.packs import runtime_key
        from ..domain.actors import Monster
        from ..domain.actions import ActionContext, ActionRegistry
        from ..domain.rules import Dice

        store.get("monsters", request.monster)
        factory = SessionFactory(store)
        target = factory.hero()
        monster = Monster.create(runtime_key(request.monster), catalog=factory.catalog)
        if request.target == "self":
            target = monster
        result = monster.perform(
            request.action,
            ActionContext(
                Dice(random.Random(request.seed)),
                target=target,
                difficulty=request.difficulty,
                spell_id=runtime_key(request.spell_id) if request.spell_id else None,
            ),
            ActionRegistry.default(),
        )
        return {
            "performed": result.performed,
            "success": result.success,
            "message": result.message,
            "roll": result.check.roll if result.check else None,
            "total": result.check.total if result.check else None,
            "target": {
                "hp": target.hp,
                "max_hp": target.max_hp,
                "conditions": target.conditions,
            },
            "actor": {
                "hp": monster.hp,
                "conditions": monster.conditions,
                "spell_slots": monster.spell_slots,
                "cantrip_uses": monster.cantrip_uses,
                "max_cantrip_uses": monster.max_cantrip_uses,
            },
            "effects": [e.payload() for e in result.effects],
        }

    web = Path(dist) if dist else PROJECT_ROOT / "studio/dist"
    if (web / "index.html").is_file() and (web / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(web / "index.html")
    else:

        @app.get("/")
        def missing():
            return JSONResponse(
                {"detail": "Соберите интерфейс: cd studio && npm ci && npm run build"},
                status_code=503,
            )

    return app


def serve(port=8765, open_browser=True, root=None):
    import uvicorn

    url = f"http://127.0.0.1:{port}"
    packs_dir = Path(root).resolve() if root else Path(DEFAULT_PACKS).resolve()
    with socket.socket() as probe:
        probe.settimeout(1)
        occupied = probe.connect_ex(("127.0.0.1", port)) == 0
    if occupied:
        try:
            with urlopen(url + "/api/status", timeout=2) as response:
                status = json.load(response)
        except (URLError, OSError, ValueError):
            status = None
        if status != {"studio": "TUI Dungeon Studio", "packs_dir": str(packs_dir)}:
            raise OSError(
                f"Порт {port} занят другим сервером. Выберите другой: --port {port + 1 if port < 65535 else 8765}"
            )
        print(f"Студия уже запущена: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        return

    app = create_app(root)
    if (
        not (PROJECT_ROOT / "studio/dist/index.html").is_file()
        or not (PROJECT_ROOT / "studio/dist/assets").is_dir()
    ):
        setup = ".\\setup.bat" if sys.platform == "win32" else "./setup.sh"
        raise ValueError(f"Интерфейс не собран. Выполните {setup}")
    if open_browser:
        timer = threading.Timer(
            1.0, webbrowser.open, args=(f"http://127.0.0.1:{port}",)
        )
        timer.daemon = True
        timer.start()
    print(
        f"TUI Dungeon Studio: http://127.0.0.1:{port} — Ctrl+C для остановки",
        flush=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
