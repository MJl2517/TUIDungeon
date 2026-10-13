"""Local-file browser check: PYTHONPATH=. python scripts/check_tileset_viewer.py."""

import os
from pathlib import Path
import re
import json
import runpy
import shutil
import tempfile
import threading

from playwright.sync_api import expect, sync_playwright


def run():
    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel=os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL") or None,
            executable_path=os.environ.get("PLAYWRIGHT_BROWSER_EXECUTABLE")
            or (
                (shutil.which("chromium") or shutil.which("google-chrome"))
                if not os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL")
                else None
            ),
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((root / "tools/tileset-viewer/index.html").as_uri())
        page.wait_for_function("ready")
        canvas = page.locator("#atlas")
        bounds = canvas.bounding_box()

        def cell(row, col):
            return bounds["x"] + 30 + (col - 1) * 33 + 16, bounds["y"] + 30 + (
                row - 1
            ) * 33 + 16

        page.mouse.move(*cell(2, 3))
        expect(page.locator("#hover")).to_have_text("№ 52 · строка 2 · столбец 3")
        page.mouse.click(*cell(1, 1))
        page.keyboard.down("Shift")
        page.mouse.click(*cell(1, 3))
        expect(page.locator("#count")).to_have_text("Выбрано: 2")
        page.mouse.move(*cell(2, 1))
        page.mouse.down()
        page.mouse.move(*cell(2, 4), steps=8)
        page.mouse.up()
        expect(page.locator("#count")).to_have_text("Выбрано: 6")
        assert (
            "Ячейки: 1, 3, 50, 51, 52, 53" in page.locator("#selection").input_value()
        )
        page.mouse.click(*cell(1, 3))
        page.keyboard.up("Shift")
        expect(page.locator("#count")).to_have_text("Выбрано: 5")
        page.mouse.click(*cell(3, 2))
        expect(page.locator("#count")).to_have_text("Выбрано: 1")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Shift+Enter")
        assert "Ячейки: 100, 101" in page.locator("#selection").input_value()
        page.locator("#zoom").select_option("48")
        assert "Ячейки: 100, 101" in page.locator("#selection").input_value()
        page.locator("#copy").click()
        expect(page.locator("#status")).to_have_text(re.compile("скопирован|Ctrl\\+C"))
        page.locator("#clear").click()
        expect(page.locator("#selection")).to_have_value("")
        for sheet in ("color", "input", "mono"):
            page.locator("#sheet").select_option(sheet)
            page.wait_for_function("ready")
            expect(page.locator("#count")).to_have_text("Выбрано: 0")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#zoom").select_option("24")
        page.mouse.move(bounds["x"] + 30 + 12, bounds["y"] + 30 + 12)
        screenshot = root / "saves/qa/tileset-viewer.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot))
        assert not errors, errors
        check_progress(browser, root)
        browser.close()
        print(
            "Tileset viewer: hover, selection, Shift drag, keyboard, zoom, sheets and mobile OK"
        )


def check_progress(browser, root):
    """Save to a disposable file, then load in a fresh browser context."""
    module = runpy.run_path(str(root / "tools/tileset-viewer/server.py"))
    original = (root / "tools/tileset-viewer/progress.json").read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        progress = Path(directory) / "progress.json"
        progress.write_bytes(original)
        (progress.parent / "tasks.json").write_text("[]", encoding="utf-8")
        server = module["create_server"](progress)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto(url)
            page.wait_for_function("ready && progressReady")
            # Start from a known state without changing the actual repository file.
            page.evaluate(
                "progress = {mono: [], color: [], input: []}; select(52, false); select(53, true)"
            )
            page.locator("#added").check()
            expect(page.locator("#save-state")).to_have_text(
                "Есть несохранённые отметки"
            )
            page.locator("#save").click()
            expect(page.locator("#save-state")).to_contain_text(
                "Сохранено в progress.json"
            )
            assert json.loads(progress.read_text())["mono"] == [52, 53]
            saved = progress.read_bytes()
            # Invalid data and requests from other websites must not overwrite marks.
            response = page.request.post(
                url + "/progress.json",
                data={"mono": [0], "color": [], "input": []},
                headers={"Origin": url},
            )
            assert response.status == 400
            response = page.request.post(
                url + "/progress.json",
                data={"mono": [], "color": [], "input": []},
                headers={"Origin": "https://example.com"},
            )
            assert response.status == 403
            assert progress.read_bytes() == saved
            page.close()
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto(url)
            page.wait_for_function("ready && progressReady")
            page.evaluate("select(52, false)")
            expect(page.locator("#added")).to_be_checked()
            page.evaluate("select(54, true)")
            assert page.locator("#added").evaluate("node => node.indeterminate")
            page.locator("#sheet").select_option("color")
            page.wait_for_function("ready")
            page.evaluate("select(52, false)")
            expect(page.locator("#added")).not_to_be_checked()
            page.locator("#sheet").select_option("mono")
            page.wait_for_function("ready")
            page.evaluate("select(52, false)")
            page.locator("#added").uncheck()
            page.locator("#save").click()
            expect(page.locator("#save-state")).to_contain_text(
                "Сохранено в progress.json"
            )
            assert json.loads(progress.read_text())["mono"] == [53]
            page.locator("#zoom").select_option("24")
            page.screenshot(path=str(root / "saves/qa/tileset-progress.png"))
            page.wait_for_function("tasksReady")
            page.evaluate(
                "selected.clear(); for(let n=1;n<=6;n++) selected.add(n); updateSelection()"
            )
            page.locator("#prompt").fill("Деревья — рубить и поджигать.")
            page.locator("#add-task").click()
            page.evaluate(
                "selected.clear(); for(let n=7;n<=12;n++) selected.add(n); updateSelection()"
            )
            page.locator("#prompt").fill("Камни — собирать руками.")
            page.locator("#add-task").click()
            page.locator("#save-tasks").click()
            expect(page.locator("#tasks-state")).to_contain_text("Сохранены tasks.json")
            requests = (progress.parent / "tile-requests.md").read_text(
                encoding="utf-8"
            )
            assert "Тайлы 1–6" in requests and "Тайлы 7–12" in requests
            assert "Деревья — рубить" in requests and "[1, 12]" in requests
            page.reload()
            page.wait_for_function("ready && tasksReady")
            expect(page.locator("#task-list li")).to_have_count(2)
            page.locator("#task-list li").first.get_by_text(
                "Править", exact=True
            ).click()
            expect(page.locator("#prompt")).to_have_value(
                "Деревья — рубить и поджигать."
            )
            page.locator("#prompt").fill("Деревья — восстановление за 10 дней.")
            page.locator("#add-task").click()
            page.locator("#task-list li").last.get_by_text(
                "Удалить", exact=True
            ).click()
            page.locator("#save-tasks").click()
            expect(page.locator("#tasks-state")).to_contain_text("Сохранены tasks.json")
            requests = (progress.parent / "tile-requests.md").read_text(
                encoding="utf-8"
            )
            assert "10 дней" in requests and "Камни" not in requests
            # A second tab with unsaved work must not resurrect the completed task.
            stale = browser.new_page()
            stale.goto(url)
            stale.wait_for_function("ready && tasksReady")
            stale.evaluate("select(20, false)")
            stale.locator("#prompt").fill("Несохранённая новая партия")
            stale.locator("#add-task").click()
            page.locator("#task-list li").get_by_text("Выполнено", exact=True).click()
            expect(page.locator("#tasks-state")).to_contain_text("перенесено в архив")
            expect(page.locator("#pending-count")).to_have_text("0")
            expect(page.locator("#completed-count")).to_have_text("1")
            assert "10 дней" not in (progress.parent / "tile-requests.md").read_text(
                encoding="utf-8"
            )
            stale.locator("#save-tasks").click()
            expect(stale.locator("#tasks-state")).to_contain_text("изменились")
            expect(stale.locator("#task-list li[data-task-id]")).to_have_count(2)
            stale.on("dialog", lambda dialog: dialog.accept())
            stale.close()
            # Follow-up becomes a separate pending task; its source stays archived.
            page.locator("#show-completed").click()
            page.locator("#task-list li").get_by_text(
                "Создать доработку", exact=True
            ).click()
            expect(page.locator("#prompt")).to_have_value(
                "Деревья — восстановление за 10 дней."
            )
            page.locator("#prompt").fill("Деревья — восстановление за 20 дней.")
            page.locator("#add-task").click()
            page.locator("#save-tasks").click()
            expect(page.locator("#tasks-state")).to_contain_text("Сохранены tasks.json")
            requests = (progress.parent / "tile-requests.md").read_text(
                encoding="utf-8"
            )
            assert "20 дней" in requests and "10 дней" not in requests
            page.reload()
            page.wait_for_function("ready && tasksReady")
            expect(page.locator("#pending-count")).to_have_text("1")
            expect(page.locator("#completed-count")).to_have_text("1")
            page.locator("#show-completed").click()
            page.locator("#task-list summary").click()
            expect(page.locator("#task-list p").last).to_have_text(
                "Деревья — восстановление за 10 дней."
            )
            page.screenshot(path=str(root / "saves/qa/tileset-task-archive.png"))
            page.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    assert (root / "tools/tileset-viewer/progress.json").read_bytes() == original
    print("Marks: save, fresh context, sheet isolation, unmark and invalid writes OK")


if __name__ == "__main__":
    run()
