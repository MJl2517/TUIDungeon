"""Exercise tile search and painting in a browser using temporary content."""

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
from playwright.sync_api import expect, sync_playwright

from tuidungeon.content.packs import DEFAULT_PACKS
from tuidungeon.tooling.server import create_app


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-tiles-browser-") as temporary:
        root = Path(temporary) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
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
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started, "Studio did not start"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=shutil.which("google-chrome")
                    or shutil.which("chromium"),
                    args=["--no-sandbox"],
                )
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                page.set_default_timeout(15000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                try:
                    expect(page.locator(".home-card")).to_have_count(13, timeout=15000)
                except AssertionError:
                    print("Initial Studio state:", page.locator("body").inner_text())
                    print("Browser errors:", errors)
                    raise
                page.locator(".loading-overlay").wait_for(state="hidden")
                page.screenshot(
                    path=str(Path(tempfile.gettempdir()) / "tuidungeon-studio-home.png")
                )
                page.locator('.navigation [data-category="maps"]').click()
                page.locator(".library").get_by_role(
                    "button", name="+ Создать", exact=True
                ).click()
                page.get_by_label("ID нового документа").fill("tiles_acceptance")
                page.get_by_label("Название нового документа").fill("Проверка тайлов")
                page.get_by_role("button", name="Создать документ", exact=True).click()
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Проверка тайлов")
                assert page.locator(".navigation").bounding_box()["width"] < 80
                expect(page.locator(".library")).to_have_count(0)
                page.get_by_label("Развернуть навигацию").click()
                assert page.locator(".navigation").bounding_box()["width"] >= 180
                page.get_by_label("Свернуть навигацию").click()
                cards = page.locator(".palette-grid .palette-tile")
                group = page.get_by_label("Группа тайлов")
                query = page.get_by_label("Поиск тайлов")
                expect(cards).to_have_count(441)
                group.select_option(label="Двери и проходы")
                expect(cards).to_have_count(16)
                query.fill("ДВЕРЬ transparent")
                expect(cards).to_have_count(4)
                query.fill("╫")
                expect(cards).to_have_count(1)
                door = page.locator('.palette-tile[data-ref="base:door_grate"]')
                expect(door).to_have_attribute(
                    "title", re.compile("Движение запрещено")
                )
                door.hover()
                expect(page.locator(".palette-detail")).to_contain_text(
                    "Пропускает обзор и свет"
                )
                door.click()
                canvas = page.locator("canvas")

                def paint(x, y):
                    size = canvas.bounding_box()
                    width = int(page.get_by_label("Ширина карты").input_value())
                    height = int(page.get_by_label("Высота карты").input_value())
                    canvas.click(
                        position={
                            "x": (x + 0.5) * (size["width"] - 2) / width,
                            "y": (y + 0.5) * (size["height"] - 2) / height,
                        }
                    )

                def choose(identifier):
                    group.select_option(label="Все группы")
                    query.fill(identifier)
                    page.locator(f'.palette-tile[data-ref="base:{identifier}"]').click()

                paint(3, 3)
                choose("wall_massive")
                paint(4, 3)
                choose("floor_tiles")
                paint(5, 3)
                page.get_by_label("Начальные маски тайла", exact=True).uncheck()
                paint(4, 3)
                page.get_by_title("Ctrl+Z", exact=True).click()
                page.get_by_title("Ctrl+Shift+Z", exact=True).click()
                query.fill("несуществующий_тайл")
                expect(cards).to_have_count(0)
                paint(6, 3)
                expect(page.locator(".statusbar")).to_contain_text("Тайлы не найдены")
                query.fill("")
                page.get_by_label("Начальные маски тайла", exact=True).check()
                page.get_by_label("Свойства тайлов").select_option("mechanics")
                expect(cards).to_have_count(191)
                page.get_by_label("Сортировка палитры").select_option("id")
                choose("torch_wall")
                paint(7, 3)
                choose("pressure_plate")
                paint(2, 1)
                choose("decor_dagger")
                paint(3, 1)
                choose("chest")
                paint(4, 1)
                choose("portal")
                page.get_by_label("Карта назначения").select_option("base:dungeon")
                paint(5, 1)
                page.get_by_role("button", name="Карта", exact=True).click()
                page.get_by_label("Освещение карты", exact=True).select_option("bright")
                page.get_by_role("button", name="Палитра", exact=True).click()
                page.get_by_label("Ширина карты").fill("100")
                page.get_by_label("Высота карты").fill("40")
                page.get_by_role("button", name="Изменить", exact=True).click()

                def save():
                    page.locator(".document-heading").get_by_role(
                        "button", name="Сохранить", exact=True
                    ).click()
                    page.locator(".unsaved").wait_for(state="hidden")
                    response = page.request.get(
                        f"http://127.0.0.1:{port}/api/documents/maps/base:tiles_acceptance"
                    )
                    assert response.ok, response.text()
                    return response.json()["document"]

                saved = save()
                assert saved["tiles"][3][3] == "base:door_grate"
                assert (saved["walkability"][3][3], saved["blocks_sight"][3][3]) == (
                    False,
                    False,
                )
                assert (
                    saved["tiles"][3][4] == "base:floor_tiles"
                    and saved["blocks_sight"][3][4]
                )
                assert saved["tiles"][3][6] is None
                assert (
                    len(saved["lights"])
                    == len(saved["traps"])
                    == len(saved["equipment"])
                    == len(saved["points_of_interest"])
                    == len(saved["transitions"])
                    == 1
                )

                view = page.locator(".map-viewport")
                view.scroll_into_view_if_needed()
                box = view.bounding_box()
                start_x = min(400, box["width"] - 30)
                start_y = min(
                    250,
                    box["height"] - 30,
                    page.viewport_size["height"] - box["y"] - 30,
                )
                start_scroll = view.evaluate("e=>e.scrollLeft")
                max_scroll = view.evaluate("e=>e.scrollWidth-e.clientWidth")
                page.evaluate(
                    "window.contextBlocked=false;document.addEventListener('contextmenu',e=>window.contextBlocked=e.defaultPrevented)"
                )
                page.mouse.move(box["x"] + start_x, box["y"] + start_y)
                page.mouse.down(button="right")
                page.mouse.move(box["x"] + 30, box["y"] + 30, steps=10)
                page.mouse.up(button="right")
                expected_scroll = min(max_scroll, start_scroll + start_x - 30)
                actual_scroll = view.evaluate("e=>e.scrollLeft")
                assert expected_scroll > start_scroll
                assert abs(actual_scroll - expected_scroll) < 5, (
                    box,
                    start_x,
                    start_y,
                    actual_scroll,
                    expected_scroll,
                )
                assert page.evaluate("window.contextBlocked")
                expect(page.locator(".unsaved")).to_have_count(0)
                page.keyboard.down("Space")
                page.mouse.move(box["x"] + 300, box["y"] + 180)
                page.mouse.down()
                page.mouse.move(box["x"] + 100, box["y"] + 70, steps=10)
                page.mouse.up()
                page.keyboard.up("Space")
                expect(page.locator(".unsaved")).to_have_count(0)
                page.keyboard.press("Digit0")
                query.fill("")
                page.get_by_label("Свойства тайлов").select_option("all")
                page.locator(".map-options .layer-badge").click()
                page.keyboard.press("KeyI")
                expect(page.get_by_title("Пипетка · I", exact=True)).to_have_class(
                    re.compile("active")
                )
                query.focus()
                query.press("b")
                expect(page.get_by_title("Пипетка · I", exact=True)).to_have_class(
                    re.compile("active")
                )
                query.fill("")
                page.locator(".map-options .layer-badge").click()
                paint(3, 3)
                expect(
                    page.locator('.palette-tile[data-ref="base:door_grate"]')
                ).to_have_attribute("aria-pressed", "true")
                paint(9, 4)
                saved = save()
                assert saved["tiles"][4][9] == "base:door_grate"
                before = float(page.get_by_label("Масштаб карты").input_value())
                page.mouse.move(box["x"] + 200, box["y"] + 200)
                page.keyboard.down("Control")
                page.mouse.wheel(0, -100)
                page.keyboard.up("Control")
                expect(page.get_by_label("Масштаб карты")).not_to_have_value(
                    str(before)
                )
                page.locator(".map-options .layer-badge").click()
                page.keyboard.press("Digit0")
                page.screenshot(
                    path=str(
                        Path(tempfile.gettempdir()) / "tuidungeon-studio-tiles.png"
                    )
                )

                page.get_by_role(
                    "button", name="▶ Тестировать карту", exact=True
                ).click()
                page.get_by_label("Тестовая раса").select_option("base:human")
                page.get_by_label("Тестовый класс").select_option("base:warrior")
                page.get_by_role("button", name="Начать тест", exact=True).click()
                page.locator(".play-layout").wait_for()

                def move():
                    with page.expect_response(
                        lambda r: "/commands" in r.url and r.request.method == "POST"
                    ) as result:
                        page.get_by_role("button", name="D →", exact=True).click()
                    return result.value.json()

                state = move()
                assert state["traps"][0]["triggered"]
                state = move()
                inventory = len(state["hero"]["inventory"])
                with page.expect_response(
                    lambda r: "/commands" in r.url and r.request.method == "POST"
                ) as result:
                    page.get_by_role("button", name="G · Подобрать", exact=True).click()
                state = result.value.json()
                assert (
                    len(state["hero"]["inventory"]) == inventory + 1
                    and not state["ground"]
                )
                with page.expect_response(
                    lambda r: "/commands" in r.url and r.request.method == "POST"
                ) as result:
                    page.get_by_role(
                        "button", name="Забрать ценности", exact=True
                    ).click()
                assert result.value.json()["hero"]["gold"] > 0
                move()
                assert move()["map"] == "base:dungeon"
                with page.expect_response(lambda r: "/reset" in r.url) as result:
                    page.get_by_role("button", name="Перезапустить", exact=True).click()
                reset = result.value.json()
                assert not reset["traps"][0]["triggered"] and len(reset["ground"]) == 1
                page.get_by_role("button", name="Закрыть", exact=True).click()
                assert (
                    page.request.get(
                        f"http://127.0.0.1:{port}/api/documents/maps/base:tiles_acceptance"
                    ).json()["document"]
                    == saved
                )
                page.get_by_role(
                    "button", name="Открыть библиотеку", exact=True
                ).click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Проверка тайлов")
                ).click()
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Проверка тайлов")
                page.locator('.navigation [data-category="tiles"]').click()
                page.locator(".library .search").fill("╫ transparent door_grate")
                expect(page.locator(".library-list .library-entry")).to_have_count(1)
                page.locator(".library-list .library-entry").click()
                expect(page.get_by_label("Группа тайлов", exact=True)).to_have_value(
                    "Двери и проходы"
                )
                assert not errors, errors
                browser.close()
                print(
                    "Browser OK: home, single collapsible navigation, visual palette + filters, masks, generated mechanics, pan + hotkeys + eyedropper, save/reopen, Python playtest + reset."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
