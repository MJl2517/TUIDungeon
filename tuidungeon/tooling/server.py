"""Loopback-only Studio API. No shell commands or arbitrary paths are accepted."""

from pathlib import Path
from typing import Literal
import threading
import sys
import webbrowser
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError, BaseModel, ConfigDict, Field
from ..content.packs import PackStore, ContentError, Conflict, Referenced, PROJECT_ROOT
from ..content.schemas import MODELS, Scores
from ..content.migrations import migrate_map, migrate_document
from ..domain.mechanics import mechanics
from ..presentation.art import import_txt, export_txt
from .sessions import TestSession
from .launcher import open_test_map


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SaveRequest(RequestModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: dict
    version: str | None = None


class VersionRequest(RequestModel):
    version: str


class SessionRequest(RequestModel):
    cantrips: list[str] | None = None
    model_config = ConfigDict(extra="forbid", strict=True)
    map_ref: str
    race: str = "base:human"
    character_class: str = "base:warrior"
    seed: int = 0
    scores: list[int] = Field(
        default_factory=lambda: [14, 12, 13, 10, 10, 8], min_length=6, max_length=6
    )
    background: str | None = None
    viewport_width: int | None = Field(default=None, ge=1, le=256)
    viewport_height: int | None = Field(default=None, ge=1, le=256)


class GameRequest(RequestModel):
    map_ref: str
    seed: int = 42
    character_class: str = "base:warrior"


class CommandRequest(RequestModel):
    spell_id: str | None = None
    source: Literal["class", "racial"] = "class"
    option: str | None = None
    command: str
    placement: str | None = None
    choice: str | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    item: str | None = None
    quantity: int = Field(default=1, ge=1, le=10000)
    deposit: bool = False


class SandboxRequest(RequestModel):
    monster: str
    action: str
    seed: int = 0
    difficulty: int = Field(default=12, ge=0)
    spell_id: str | None = None
    target: Literal["hero", "self"] = "hero"


LABELS = {
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
        raw.update(
            lights=[],
            ambient_light="bright",
            width=20,
            height=12,
            tiles=[[None] * 20 for _ in range(12)],
            walkability=[[True] * 20 for _ in range(12)],
            blocks_sight=[[False] * 20 for _ in range(12)],
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
    sessions = {}
    app = FastAPI(title="TUI Dungeon Studio", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.sessions = sessions

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
                    "classes": getattr(d, "classes", []),
                    "group": getattr(d, "group", None),
                    "tags": getattr(d, "tags", []),
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
        return store.save(category, ref, request.document, request.version)

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

    @app.post("/api/art/import")
    def import_art(raw: dict):
        return import_txt(
            raw.get("text", ""),
            raw.get("id", "imported"),
            raw.get("name", "Импорт TXT"),
        ).model_dump(mode="json")

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
        return {"text": export_txt(store.get("art", ref))}

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

    @app.post("/api/sessions")
    def create_session(request: SessionRequest):
        store.reload()
        if len(sessions) >= 32:
            raise HTTPException(429, "Закройте одну из тестовых сессий")
        Scores.model_validate(dict(zip(Scores.model_fields, request.scores)))
        session = TestSession(store, request.model_dump())
        sessions[session.id] = session
        return session.snapshot()

    def session(identifier):
        if identifier not in sessions:
            raise HTTPException(404, "Сессия не найдена")
        return sessions[identifier]

    @app.post("/api/sessions/{identifier}/commands")
    def command(identifier, request: CommandRequest):
        return session(identifier).command(**request.model_dump())

    @app.post("/api/sessions/{identifier}/reset")
    def reset(identifier):
        s = session(identifier)
        s.reset()
        return s.snapshot()

    @app.delete("/api/sessions/{identifier}")
    def close(identifier):
        session(identifier)
        del sessions[identifier]
        return {"closed": True}

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
