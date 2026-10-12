"""Real-browser acceptance check against temporary packs; never edits user content."""

from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.sync_api import sync_playwright
from tuidungeon.content.packs import DEFAULT_PACKS
from tuidungeon.tooling.server import create_app
from scripts.testing import install_test_maps


def run():
    artifacts = Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="dungeon-browser-") as temporary:
        root = Path(temporary) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        install_test_maps(root)
        with socket.socket() as socket_:
            socket_.bind(("127.0.0.1", 0))
            port = socket_.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root), host="127.0.0.1", port=port, log_level="error"
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        try:
            with sync_playwright() as p:
                chrome = shutil.which("google-chrome") or shutil.which("chromium")
                browser = p.chromium.launch(
                    headless=True, executable_path=chrome, args=["--no-sandbox"]
                )
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                page.locator('.navigation [data-category="maps"]').click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Склеп забытых")
                ).click()
                page.get_by_label("Название документа", exact=True).wait_for()
                page.wait_for_function(
                    "document.querySelector('[aria-label=\"Название документа\"]')?.value==='Склеп забытых'"
                )
                page.locator("canvas").wait_for()
                page.screenshot(path=str(artifacts / "tuidungeon-studio-map.png"))
                page.locator('.navigation [data-category="art"]').click()
                page.locator(".library").get_by_role(
                    "button", name="+ Создать", exact=True
                ).click()
                page.get_by_label("ID нового документа").fill("smoke_art")
                page.get_by_label("Название нового документа").fill("Пробный арт")
                page.get_by_role("button", name="Создать документ", exact=True).click()
                canvas = page.locator("canvas")
                canvas.click(position={"x": 27, "y": 45})
                page.locator(".inspector h3").filter(has_text="Слои").get_by_role(
                    "button", name="+", exact=True
                ).click()
                page.get_by_label("Имя слоя").nth(1).fill("Детали")
                page.locator(".glyph-palettes").get_by_role(
                    "button", name="░", exact=True
                ).click()
                canvas.click(position={"x": 45, "y": 45})
                page.get_by_title("Ctrl+Z", exact=True).click()
                page.get_by_title("Ctrl+Shift+Z", exact=True).click()
                page.locator(".layer-row").nth(1).get_by_title(
                    "Блокировка"
                ).get_by_role("checkbox").check()
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).click()
                page.locator(".unsaved").wait_for(state="hidden")
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).wait_for()
                art = page.request.get(
                    f"http://127.0.0.1:{port}/api/documents/art/base:smoke_art"
                ).json()["document"]
                assert (
                    len(art["layers"]) == 2
                    and art["layers"][1]["locked"]
                    and art["layers"][1]["cells"][1][2]["char"] == "░"
                ), art
                page.get_by_role(
                    "button", name="Открыть библиотеку", exact=True
                ).click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Goblin")
                ).click()
                page.get_by_role(
                    "button", name="Открыть библиотеку", exact=True
                ).click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Пробный арт")
                ).click()
                art2 = page.request.get(
                    f"http://127.0.0.1:{port}/api/documents/art/base:smoke_art"
                ).json()["document"]
                assert art == art2
                page.screenshot(path=str(artifacts / "tuidungeon-studio-art.png"))
                page.locator('.navigation [data-category="monsters"]').click()
                page.locator(".library").get_by_role(
                    "button", name="+ Создать", exact=True
                ).click()
                page.get_by_label("ID нового документа").fill("smoke_monster")
                page.get_by_label("Название нового документа").fill("Страж")
                page.get_by_role("button", name="Создать документ", exact=True).click()
                page.get_by_label("Рисунок", exact=True).click()
                page.get_by_role("dialog", name="Рисунок", exact=True).get_by_label(
                    "Поиск контента"
                ).fill("base:smoke_art")
                page.get_by_role("dialog", name="Рисунок", exact=True).locator(
                    ".content-entry"
                ).click()
                page.screenshot(
                    path=str(artifacts / "tuidungeon-studio-form-before.png")
                )
                try:
                    page.get_by_label("Хиты", exact=True).fill("19")
                except Exception:
                    page.screenshot(
                        path=str(artifacts / "tuidungeon-studio-form-failed.png")
                    )
                    print("Browser errors:", errors, flush=True)
                    raise
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).click()
                page.locator(".unsaved").wait_for(state="hidden")
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).wait_for()
                page.get_by_label("Действие монстра").select_option("dirty_strike")
                page.get_by_role(
                    "button", name="Выполнить действие", exact=True
                ).click()
                page.locator(".sandbox-result").wait_for()
                page.screenshot(path=str(artifacts / "tuidungeon-studio-monster.png"))
                page.locator('.navigation [data-category="maps"]').click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Склеп забытых")
                ).click()
                page.wait_for_function(
                    "document.querySelector('[aria-label=\"Название документа\"]')?.value==='Склеп забытых'"
                )
                page.get_by_role("button", name="Дублировать", exact=True).click()
                page.get_by_label("ID нового документа").fill("smoke_map")
                page.get_by_label("Название нового документа").fill(
                    "Проверочное подземелье"
                )
                page.get_by_role("button", name="Создать документ", exact=True).click()
                page.get_by_label("Слой карты").select_option("walkability")
                page.get_by_label("Разрешить проход", exact=True).uncheck()
                # Red mask on visually unchanged floor at (9,9).
                canvas = page.locator("canvas")
                canvas.click(position={"x": 9.5 * 15.6, "y": 9.5 * 26})
                page.get_by_label("Слой карты").select_option("monsters")
                page.locator('.palette-tile[data-ref="base:smoke_monster"]').click()
                canvas.click(position={"x": 18.5 * 15.6, "y": 7.5 * 26})
                page.get_by_label("Слой карты").select_option("decorations")
                page.locator('.palette-tile[data-ref="base:smoke_art"]').click()
                # 16x8 art fits at x=0,y=0; transparent cells preserve tiles.
                canvas.click(position={"x": 7, "y": 10})
                page.get_by_role("button", name="Карта", exact=True).click()
                page.get_by_label("Освещение карты", exact=True).select_option("dark")
                page.get_by_role("button", name="Палитра", exact=True).click()
                page.get_by_label("Слой карты").select_option("lights")
                canvas.click(position={"x": 4.5 * 15.6, "y": 4.5 * 26})
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).click()
                page.locator(".unsaved").wait_for(state="hidden")
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).wait_for()
                saved = page.request.get(
                    f"http://127.0.0.1:{port}/api/documents/maps/base:smoke_map"
                ).json()["document"]
                assert (
                    not saved["walkability"][9][9]
                    and saved["tiles"][9][9] == "base:floor"
                )
                assert (
                    any(m["ref"] == "base:smoke_monster" for m in saved["monsters"])
                    and saved["decorations"]
                )
                assert (
                    saved["ambient_light"] == "dark"
                    and saved["lights"][0]["radius"] == 6
                )
                assert not errors, errors
                browser.close()
                print(
                    "Browser OK: art layers + undo/redo + reopen, monster form + sandbox, map masks + placements."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
