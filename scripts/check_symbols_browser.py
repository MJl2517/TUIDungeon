"""Exercise pixel editing, portable PNGs and assignments on disposable packs."""

import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time

from playwright.sync_api import expect, sync_playwright
import uvicorn

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.tooling.server import create_app


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-symbols-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        seed_store = PackStore(root)
        seed_store.save(
            "maps",
            "base:symbol_test",
            dict(
                id="symbol_test",
                name="Проверка символов",
                width=5,
                height=5,
                tiles=[["base:floor"] * 5 for _ in range(5)],
                walkability=[[True] * 5 for _ in range(5)],
                blocks_sight=[[False] * 5 for _ in range(5)],
                spawn=dict(x=1, y=1),
                equipment=[dict(id="test_pickaxe", ref="base:pickaxe", x=2, y=2)],
            ),
            None,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root), host="127.0.0.1", port=port, log_level="error"
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.05)
        try:
            expect.set_options(timeout=20000)
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=os.environ.get("PLAYWRIGHT_BROWSER_EXECUTABLE")
                    or shutil.which("chromium")
                    or shutil.which("google-chrome"),
                )
                page = browser.new_page(viewport=dict(width=1440, height=900))
                errors = []
                page.on(
                    "pageerror",
                    lambda e: (
                        errors.append(str(e)),
                        print("BROWSER ERROR", str(e), flush=True),
                    ),
                )
                page.goto(f"http://127.0.0.1:{port}")
                page.locator(".home-card").first.wait_for()
                page.get_by_role("button", name="Предметы", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:pickaxe")
                page.locator(".content-entry").click()
                expect(
                    page.get_by_label("Символ из библиотеки", exact=True)
                ).to_be_visible()
                page.get_by_label("Символ из библиотеки", exact=True).click()
                dialog = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                dialog.get_by_role(
                    "button", name="+ Нарисовать символ", exact=True
                ).click()
                dialog.get_by_label("ID символа", exact=True).fill("browser_test")
                dialog.get_by_label("Название символа", exact=True).fill(
                    "Тестовая кирка"
                )
                dialog.get_by_label("Текстовый знак символа", exact=True).fill("/")
                canvas = dialog.get_by_label("Пиксельный холст 16×16", exact=True)
                canvas.click(position=dict(x=90, y=90))
                dialog.get_by_role("button", name="Отменить", exact=True).click()
                dialog.get_by_role("button", name="Повторить", exact=True).click()
                dialog.get_by_label(
                    "Название и текстовый знак согласованы", exact=True
                ).check()
                dialog.get_by_role(
                    "button", name="Сохранить и назначить", exact=True
                ).click()
                expect(dialog).to_have_count(0)
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                store = PackStore(root)
                created = store.get("symbols", "base:browser_test")
                assert created.pixels[4][4] == "1"
                assert (
                    store.get("equipment", "base:pickaxe").symbol == "base:browser_test"
                )
                # Duplicate-and-assign changes the definition, not the shared source.
                page.get_by_label("Символ из библиотеки", exact=True).click()
                dialog = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                dialog.get_by_role(
                    "button", name="Дублировать и назначить", exact=True
                ).click()
                dialog.get_by_label("ID символа", exact=True).fill("browser_copy")
                dialog.get_by_role("button", name="Повернуть 90°", exact=True).click()
                dialog.get_by_role(
                    "button", name="Сохранить и назначить", exact=True
                ).click()
                expect(dialog).to_have_count(0)
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                # Reopen, export and import the exact transparent PNG mask.
                page.get_by_role("button", name="Символы", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:browser_copy")
                page.locator(".content-entry").click()
                with page.expect_download() as download:
                    page.get_by_role("button", name="Экспорт PNG", exact=True).click()
                png = Path(directory) / "roundtrip.png"
                download.value.save_as(png)
                page.get_by_label("Импорт PNG символов", exact=True).set_input_files(
                    png
                )
                page.get_by_label(
                    "Подтверждаю преобразование цветов в одноцветную маску", exact=True
                ).check()
                page.get_by_role("button", name="В текущий рисунок", exact=True).click()
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                store.reload()
                assert store.get("symbols", "base:browser_copy").pixels[4][11] == "1"
                assert store.get("symbols", "base:browser_test").pixels[4][4] == "1"
                # Batch assignments require an explicit preview and preserve mechanics.
                page.get_by_role(
                    "button", name="Согласование графики", exact=True
                ).click()
                page.get_by_label("Поиск назначений", exact=True).fill("base:pickaxe")
                page.get_by_role("button", name="Выбрать найденные", exact=True).click()
                page.get_by_role(
                    "button", name="Назначить выбранным (1)", exact=True
                ).click()
                dialog = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                dialog.get_by_label("Поиск контента").fill("base:browser_test")
                dialog.locator(".content-entry").click()
                expect(page.locator(".assignment-confirm")).to_be_visible()
                page.get_by_role(
                    "button", name="Сохранить назначения", exact=True
                ).click()
                expect(page.locator(".assignment-confirm")).to_have_count(0)
                store.reload()
                assert (
                    store.get("equipment", "base:pickaxe").symbol == "base:browser_test"
                )
                assert store.get("equipment", "base:pickaxe").weight == 3.0
                # A visual variant uses the same picker as the base definition.
                page.get_by_role("button", name="Предметы", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:pickaxe")
                page.locator(".content-entry").click()
                page.get_by_role("button", name="+ Добавить: вид", exact=True).click()
                variant = page.locator("fieldset.form-array").filter(
                    has=page.locator("legend").filter(has_text="Варианты внешнего вида")
                )
                variant.get_by_label("Название", exact=True).fill("Проверочный вариант")
                variant.get_by_label("Символ из библиотеки", exact=True).click()
                dialog = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                dialog.get_by_label("Поиск контента").fill("base:browser_copy")
                dialog.locator(".content-entry").click()
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                store.reload()
                assert (
                    store.get("equipment", "base:pickaxe").variants[0].symbol
                    == "base:browser_copy"
                )
                # Per-instance assignment and variant reset must not alter its template.
                page.get_by_role("button", name="Карты", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:symbol_test")
                page.locator(".content-entry").click()
                page.get_by_title("Выбрать · V", exact=True).click()
                page.locator(".map-viewport canvas").click(position=dict(x=80, y=80))
                inspector = page.get_by_role("region", name="Свойства экземпляра")
                expect(inspector).to_be_visible()
                inspector.get_by_label(
                    "Вариант внешнего вида", exact=True
                ).select_option("0")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                store.reload()
                assert (
                    store.get("maps", "base:symbol_test")
                    .equipment[0]
                    .overrides["symbol"]
                    == "base:browser_copy"
                )
                inspector.get_by_label(
                    "Вариант внешнего вида", exact=True
                ).select_option("default")
                inspector.locator("summary").filter(
                    has_text="Символ из библиотеки"
                ).click()
                inspector.get_by_label("Символ из библиотеки", exact=True).first.click()
                dialog = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                dialog.get_by_label("Поиск контента").fill("base:browser_copy")
                dialog.locator(".content-entry").click()
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                store.reload()
                assert (
                    store.get("maps", "base:symbol_test")
                    .equipment[0]
                    .overrides["symbol"]
                    == "base:browser_copy"
                )
                assert (
                    store.get("equipment", "base:pickaxe").symbol == "base:browser_test"
                )
                # Map preview is square and uses the same symbol resources.
                page.get_by_role("button", name="Карты", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:crypt")
                page.locator(".content-entry").click()
                canvas = page.locator(".map-viewport canvas")
                expect(canvas).to_be_visible()
                mapdoc = store.get("maps", "base:crypt")
                box = canvas.bounding_box()
                assert (
                    round(box["width"] / mapdoc.width)
                    == round(box["height"] / mapdoc.height)
                    == 32
                )
                page.locator("main").get_by_role(
                    "button", name="Символы", exact=True
                ).click()
                page.locator("main").get_by_role(
                    "button", name="Текст", exact=True
                ).click()
                page.set_viewport_size(dict(width=800, height=640))
                page.screenshot(path="/tmp/tuidungeon-symbol-studio.png")
                assert not errors, errors
                browser.close()
                print(
                    "Symbols browser OK: pixel stroke/undo/redo, creation, assignment, duplicate isolation, rotation, PNG alpha roundtrip, batch preview/save, variant and per-instance assignment, square map and text/symbol modes; no browser errors."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
