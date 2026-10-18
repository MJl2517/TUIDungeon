"""Document workspace acceptance, entirely against a disposable packs copy.

Run after `npm run build` in studio. Requires Playwright and Edge/Chromium.
PLAYWRIGHT_BROWSER_EXECUTABLE selects another installed browser.
"""

import json
import os
import re
from pathlib import Path
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
from scripts.testing import install_test_maps


def run():
    with tempfile.TemporaryDirectory(prefix="studio-workspace-") as folder:
        root = Path(folder) / "packs"
        shutil.copytree(DEFAULT_PACKS, root, ignore=shutil.ignore_patterns(".trash"))
        install_test_maps(root)
        lab_path = root / "dev/maps/npc_lab.json"
        lab = json.loads(lab_path.read_text(encoding="utf-8"))
        lab["transitions"] = [
            {"id": "workspace_exit", "x": 2, "y": 2, "target": "base:crypt"}
        ]
        lab_path.write_text(json.dumps(lab, ensure_ascii=False), encoding="utf-8")
        (root / "dev/symbols").mkdir(exist_ok=True)
        (root / "dev/symbols/workspace_unreviewed.json").write_text(
            json.dumps(
                {
                    "id": "workspace_unreviewed",
                    "name": "Тест без согласования",
                    "glyph": "!",
                    "pixels": ["1" * 16] * 16,
                }
            ),
            encoding="utf-8",
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(root), log_level="error"))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        thread.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.05)
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get("PLAYWRIGHT_BROWSER_EXECUTABLE")
                browser = playwright.chromium.launch(
                    headless=True,
                    **(
                        {"executable_path": executable}
                        if executable
                        else {"channel": "msedge"}
                        if sys.platform == "win32"
                        else {}
                    ),
                )
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                page.set_default_timeout(15000)
                errors = []
                page.on(
                    "pageerror",
                    lambda error: (
                        errors.append(str(error)),
                        print("BROWSER ERROR", error, flush=True),
                    ),
                )
                page.goto(f"http://127.0.0.1:{port}")
                expect(page.locator(".content-entry").first).to_be_visible()
                expect(page.locator(".primary-navigation button")).to_have_count(4)
                assert page.get_by_text("Согласование графики", exact=True).count() == 0

                def open_doc(category, ref):
                    page.evaluate(
                        "route=>location.hash='#/edit/'+route", category + "/" + ref
                    )
                    expect(
                        page.locator(".document-heading .document-ref")
                    ).to_have_text(ref)

                def tab(ref):
                    page.locator(f'[role="tab"][title^="{ref} ·"]').click()

                def json_editor():
                    page.locator(".more-menu summary").click()
                    page.locator(".more-menu").get_by_role(
                        "button", name="JSON", exact=True
                    ).click()
                    page.locator(".more-menu summary").click()
                    return page.get_by_label("JSON документа")

                open_doc("maps", "base:crypt")
                page.get_by_label("Название документа", exact=True).fill(
                    "Карта один — черновик"
                )
                page.get_by_label("Масштаб карты").fill("4")
                expect(page.locator(".map-sidebar")).to_have_count(0)
                open_doc("maps", "dev:npc_lab")
                page.get_by_label("Название документа", exact=True).fill(
                    "Карта два — черновик"
                )
                page.get_by_label("Масштаб карты").fill("1")
                open_doc("npcs", "dev:merchant")
                page.locator(".property-nav").get_by_role(
                    "button", name="Магазин", exact=True
                ).click()
                expect(page.locator(".property-section")).to_have_count(1)
                page.get_by_label("Поиск свойств", exact=True).fill("приветствие")
                page.locator(".property-search-results button").first.click()
                expect(page.locator('[data-field="greeting"]')).to_have_class(
                    re.compile("field-highlight")
                )
                page.get_by_label("Поиск свойств", exact=True).fill("")
                open_doc("recipes", "base:craft_torch")
                source = json_editor()
                source.fill('{"invalid JSON buffer')
                tab("base:crypt")
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Карта один — черновик")
                expect(page.get_by_label("Масштаб карты")).to_have_value("4")
                page.locator(".document-heading").get_by_role(
                    "button", name="↶", exact=True
                ).click()
                assert (
                    page.get_by_label("Название документа", exact=True).input_value()
                    != "Карта один — черновик"
                )
                page.locator(".document-heading").get_by_role(
                    "button", name="↷", exact=True
                ).click()
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Карта один — черновик")
                tab("dev:npc_lab")
                expect(page.get_by_label("Масштаб карты")).to_have_value("1")
                # Inspector and linked documents restore their canvas session.
                page.locator(".workspace").get_by_role(
                    "button", name="Выбрать", exact=False
                ).click()
                canvas = page.get_by_label("Символьный холст", exact=True)
                canvas.click(position={"x": 8 * 16 + 8, "y": 3 * 16 + 8})
                expect(page.locator(".instance-inspector")).to_contain_text(
                    "dev:merchant"
                )
                page.get_by_role("button", name="Открыть шаблон", exact=False).click()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "dev:merchant"
                )
                tab("dev:npc_lab")
                expect(page.locator(".instance-inspector")).to_contain_text(
                    "dev:merchant"
                )
                page.get_by_role("button", name="Скрыть инспектор", exact=True).click()
                page.get_by_role("button", name="Переходы", exact=True).click()
                page.get_by_role("button", name="Открыть карту", exact=True).click()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:crypt"
                )
                tab("dev:npc_lab")
                expect(page.locator(".map-transitions-page")).to_be_visible()
                page.get_by_role("button", name="Холст", exact=True).click()
                # Intercept save until another tab is active.
                pending = []
                page.route(
                    "**/api/documents/maps/dev:npc_lab",
                    lambda route: pending.append(route)
                    if route.request.method == "PUT"
                    else route.continue_(),
                )
                page.get_by_role("button", name="Сохранить", exact=True).click()
                page.wait_for_timeout(100)
                tab("base:crypt")
                assert pending
                with page.expect_response(
                    lambda r: r.request.method == "PUT"
                    and "/api/documents/maps/dev:npc_lab" in r.url,
                    timeout=30000,
                ) as saved_response:
                    pending.pop().continue_()
                assert saved_response.value.ok, saved_response.value.text()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:crypt"
                )
                assert (
                    json.loads(
                        (root / "dev/maps/npc_lab.json").read_text(encoding="utf-8")
                    )["name"]
                    == "Карта два — черновик"
                )
                # Local package settings survive navigation, and every dirty draft blocks deletion.
                page.locator(".primary-navigation").get_by_role(
                    "button", name="Пакеты", exact=True
                ).click()
                page.locator(".pack-manager-list button").filter(
                    has_text="dev"
                ).last.click()
                page.get_by_label("Название пакета", exact=True).fill("Черновик пакета")
                tab("base:crypt")
                page.locator(".primary-navigation").get_by_role(
                    "button", name="Пакеты", exact=True
                ).click()
                expect(page.get_by_label("Название пакета", exact=True)).to_have_value(
                    "Черновик пакета"
                )
                tab("base:craft_torch")
                expect(page.get_by_label("JSON документа")).to_have_value(
                    '{"invalid JSON buffer'
                )
                page.wait_for_timeout(1200)
                # Reload offers recovery and does not write drafts to content.
                page.reload()
                page.get_by_role("button", name="Восстановить", exact=True).click()
                expect(page.get_by_label("JSON документа")).to_have_value(
                    '{"invalid JSON buffer'
                )
                expect(page.get_by_role("tab")).to_have_count(4)
                tab("base:crypt")
                expect(page.get_by_label("Масштаб карты")).to_have_value("4")
                expect(
                    page.locator(".document-heading").get_by_role(
                        "button", name="↶", exact=True
                    )
                ).to_be_disabled()
                # External changes are flagged; the in-memory version remains intact.
                path = root / "base/maps/crypt.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                raw["name"] = "External edit"
                path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                expect(
                    page.get_by_text("Файл изменён вне студии.", exact=False)
                ).to_be_visible(timeout=20000)
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Карта один — черновик")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".banner.error")).to_contain_text("Файл изменён")
                assert (
                    json.loads(path.read_text(encoding="utf-8"))["name"]
                    == "External edit"
                )
                # Unsaved close has three explicit choices.
                page.get_by_label("Закрыть вкладку: Карта один — черновик").click()
                dialog = page.get_by_role("dialog", name="Закрыть изменённый документ")
                expect(dialog.get_by_role("button")).to_have_count(3)
                dialog.get_by_role("button", name="Отмена", exact=True).click()
                for width in (1600, 800, 560):
                    page.set_viewport_size({"width": width, "height": 850})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth<=innerWidth"
                    ), width
                    expect(page.locator(".map-viewport")).to_be_visible()
                page.set_viewport_size({"width": 1600, "height": 1000})
                open_doc("npcs", "dev:speaker")
                page.locator(".property-nav").get_by_role(
                    "button", name="Графика", exact=True
                ).click()
                page.get_by_role(
                    "button", name="Символ из библиотеки", exact=True
                ).click()
                picker = page.get_by_role(
                    "dialog", name="Библиотека символов", exact=True
                )
                picker.get_by_label("Поиск контента", exact=True).fill(
                    "dev:workspace_unreviewed"
                )
                picker.locator(".content-entry").click()
                expect(picker).to_have_count(0)
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0, timeout=30000)
                assert (
                    json.loads(
                        (root / "dev/npcs/speaker.json").read_text(encoding="utf-8")
                    )["symbol"]
                    == "dev:workspace_unreviewed"
                )
                # An inactive map draft blocks deleting its package.
                tab("dev:npc_lab")
                page.get_by_label("Название документа", exact=True).fill(
                    "Несохранённая карта dev"
                )
                page.locator(".primary-navigation").get_by_role(
                    "button", name="Пакеты", exact=True
                ).click()
                expect(
                    page.get_by_role("button", name="Удалить пакет", exact=True)
                ).to_be_disabled()
                expect(page.locator(".pack-manager-form")).to_contain_text(
                    "черновик этого пакета"
                )
                tab("base:crypt")
                page.screenshot(
                    path=str(Path(tempfile.gettempdir()) / "studio-workspace.png")
                )
                # Many tabs stay scrollable; tab keys and browser history preserve drafts.
                for category, ref in [
                    ("npcs", "dev:quest_giver"),
                    ("npcs", "dev:furniture_buyer"),
                    ("equipment", "base:torch"),
                    ("equipment", "base:wood"),
                    ("recipes", "base:craft_club"),
                ]:
                    open_doc(category, ref)
                page.get_by_role("tab").last.focus()
                page.keyboard.press("Home")
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:crypt"
                )
                page.keyboard.press("End")
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:craft_club"
                )
                page.go_back()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:crypt"
                )
                page.go_forward()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:craft_club"
                )
                page.set_viewport_size({"width": 560, "height": 850})
                assert page.locator(".workspace-tabs").evaluate(
                    "e=>e.scrollWidth>e.clientWidth"
                )
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                # A different project at the same address cannot recover another project's work.
                page.wait_for_timeout(1000)
                page.route(
                    "**/api/status",
                    lambda route: route.fulfill(
                        json={"packs_dir": str(root) + "-other"}
                    ),
                )
                page.reload()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "base:craft_club"
                )
                expect(
                    page.get_by_role("dialog", name="Восстановление рабочего места")
                ).to_have_count(0)
                expect(page.get_by_role("tab")).to_have_count(1)
                page.unroute("**/api/status")
                page.reload()
                page.get_by_role("button", name="Восстановить", exact=True).click()
                expect(page.get_by_role("tab")).to_have_count(10)
                # Storage failure is visible and guards closing an edited document.
                isolated = browser.new_page()
                isolated.add_init_script(
                    "Object.defineProperty(window,'indexedDB',{get(){throw Error('Storage unavailable')}})"
                )
                isolated.goto(f"http://127.0.0.1:{port}/#/edit/maps/dev:npc_lab")
                expect(
                    isolated.get_by_label("Название документа", exact=True)
                ).to_be_visible()
                expect(isolated.locator(".statusbar")).to_contain_text(
                    re.compile("недоступно|Не удалось сохранить локальный черновик")
                )
                isolated.get_by_label("Название документа", exact=True).fill(
                    "Only in memory"
                )
                assert isolated.evaluate(
                    "()=>{const e=new Event('beforeunload',{cancelable:true});return !window.dispatchEvent(e);}"
                )
                isolated.close()
                page.set_viewport_size({"width": 1600, "height": 1000})
                # Signals are authored on the canvas, saved through the real API.
                open_doc("maps", "tiles:mechanisms_lab")
                page.get_by_label("Масштаб карты").fill("1")
                page.locator(".workspace").get_by_role(
                    "button", name="Выбрать", exact=False
                ).click()
                canvas = page.get_by_label("Символьный холст", exact=True)
                canvas.click(position={"x": 3 * 16 + 8, "y": 3 * 16 + 8})
                expect(
                    page.get_by_role("button", name="Связать на карте", exact=True)
                ).to_be_visible()
                page.get_by_label("Код механизма", exact=True).fill("")
                page.get_by_role("button", name="Связать на карте", exact=True).click()
                canvas.click(position={"x": 7 * 16 + 8, "y": 3 * 16 + 8})
                expect(
                    page.get_by_role("button", name="Убрать связь gate", exact=True)
                ).to_have_count(0)
                canvas.click(position={"x": 7 * 16 + 8, "y": 3 * 16 + 8})
                expect(
                    page.get_by_role("button", name="Убрать связь gate", exact=True)
                ).to_be_visible()
                page.screenshot(
                    path=str(Path(tempfile.gettempdir()) / "studio-mechanism-links.png")
                )
                page.keyboard.press("Escape")
                expect(
                    page.get_by_role("button", name="Связать на карте", exact=True)
                ).to_be_visible()
                page.get_by_role(
                    "button", name="Убрать связь illusion", exact=True
                ).click()
                with page.expect_response(
                    lambda r: r.request.method == "PUT"
                    and "/api/documents/maps/tiles:mechanisms_lab" in r.url,
                    timeout=30000,
                ) as saved_response:
                    page.keyboard.press("Control+s")
                assert saved_response.value.ok, saved_response.value.text()
                saved = json.loads(
                    (root / "tiles/maps/mechanisms_lab.json").read_text(
                        encoding="utf-8"
                    )
                )
                links = saved["objects"][0]["overrides"]["mechanism_targets"]
                assert "gate" in links and "illusion" not in links, links
                expect(page.locator(".document-heading .unsaved")).to_have_count(0)
                page.wait_for_function(
                    """async ({project,version}) => new Promise(resolve => {
                      const open = indexedDB.open('tuidungeon-workspaces', 1);
                      open.onsuccess = () => {
                        const db = open.result;
                        const read = db.transaction('projects').objectStore('projects').get(project);
                        read.onsuccess = () => { db.close(); resolve(read.result?.tabs?.some(t => t.ref === 'tiles:mechanisms_lab' && t.version === version)); };
                      };
                    })""",
                    arg={
                        "project": str(root),
                        "version": saved_response.value.json()["version"],
                    },
                )
                page.reload()
                page.get_by_role("button", name="Восстановить", exact=True).click()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "tiles:mechanisms_lab"
                )
                expect(
                    page.get_by_role("button", name="Убрать связь gate", exact=True)
                ).to_be_visible()
                # Receiver code is a map placement property; template stays unchanged.
                canvas = page.get_by_label("Символьный холст", exact=True)
                canvas.click(position={"x": 17 * 16 + 8, "y": 3 * 16 + 8})
                expect(page.get_by_label("Код активации", exact=True)).to_have_value(
                    "demo"
                )
                page.get_by_label("Код активации", exact=True).fill("second_signal")
                with page.expect_response(
                    lambda r: r.request.method == "PUT"
                    and "/api/documents/maps/tiles:mechanisms_lab" in r.url,
                    timeout=30000,
                ) as saved_response:
                    page.keyboard.press("Control+s")
                assert saved_response.value.ok, saved_response.value.text()
                saved = json.loads(
                    (root / "tiles/maps/mechanisms_lab.json").read_text(
                        encoding="utf-8"
                    )
                )
                assert saved["objects"][3]["activation_code"] == "second_signal"
                page.set_viewport_size({"width": 900, "height": 800})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                )
                # Missing files remain local drafts and fail to overwrite the disk.
                tab("dev:speaker")
                (root / "dev/npcs/speaker.json").unlink()
                expect(
                    page.get_by_text("Файл удалён вне студии.", exact=False)
                ).to_be_visible(timeout=20000)
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "dev:speaker"
                )
                page.wait_for_timeout(1000)
                page.reload()
                page.get_by_role("button", name="Восстановить", exact=True).click()
                expect(page.locator(".document-heading .document-ref")).to_have_text(
                    "dev:speaker"
                )
                expect(page.get_by_role("tab")).to_have_count(11)
                tab("base:craft_torch")
                expect(page.get_by_label("JSON документа")).to_have_value(
                    '{"invalid JSON buffer'
                )
                assert not errors, errors
                browser.close()
                print(
                    "PASS: independent documents, undo, async save, JSON/package recovery, conflict, map links/inspector, unreviewed symbol, deletion, narrow layouts, mechanism links/codes/save/reload"
                )
        finally:
            server.should_exit = True
            thread.join(10)
            sock.close()


if __name__ == "__main__":
    run()
