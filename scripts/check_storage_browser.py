"""Real browser smoke test for storage UI using copied content."""

from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time

import uvicorn
from playwright.sync_api import expect, sync_playwright

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.tooling.server import create_app


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-storage-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        fixture = (
            Path(__file__).resolve().parents[1] / "tests/fixtures/storage_lab.json"
        )
        store.save(
            "maps",
            "dev:storage_lab",
            store.read_json(fixture),
            store.versions.get(("maps", "dev:storage_lab")),
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
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=shutil.which("google-chrome")
                    or shutil.which("chromium"),
                    args=["--no-sandbox"],
                )
                page = browser.new_page(viewport=dict(width=1440, height=1000))
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_label("Поиск по всей библиотеке").fill("dev:storage_lab")
                page.locator(".library-entry").click()
                page.get_by_title("Выбрать · V", exact=True).click()
                page.locator(".map-editor canvas").click(
                    position=dict(x=4.5 * 15.6, y=4.5 * 26)
                )
                page.locator(".instance-field > summary").filter(
                    has_text="Контейнер"
                ).click()
                expect(
                    page.get_by_label(
                        "Личный (можно класть вещи; не обновляется)", exact=True
                    )
                ).to_be_checked()
                capacity = page.get_by_label("Вместимость, кг", exact=True)
                expect(capacity).to_have_value("1000")
                capacity.fill("2000")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                page.get_by_role(
                    "button", name="▶ Тестировать карту", exact=True
                ).click()
                page.get_by_label("Тестовый класс").select_option("base:warrior")
                with page.expect_response(
                    lambda r: r.url.endswith("/api/sessions")
                    and r.request.method == "POST"
                ) as response:
                    page.get_by_role("button", name="Начать тест", exact=True).click()
                initial = response.value.json()
                session_id = initial["id"]

                def open_container(name):
                    page.locator(".play-layout aside section").filter(
                        has=page.get_by_role("heading", name=name, exact=True)
                    ).get_by_role(
                        "button", name="Открыть контейнер", exact=True
                    ).click()

                open_container("Личный сундук")
                dialog = page.get_by_role("dialog", name="Обмен с контейнером")
                expect(dialog).to_be_visible()
                left, right = (
                    dialog.locator(".storage-pane").nth(0),
                    dialog.locator(".storage-pane").nth(1),
                )
                expect(right.locator(".storage-row")).to_have_count(2)
                page.keyboard.press("Enter")
                slider = dialog.get_by_label("Количество для переноса")
                expect(slider).to_have_value("1")
                page.keyboard.press("End")
                page.keyboard.press("ArrowLeft")
                expect(slider).to_have_value("2")
                page.screenshot(path="/tmp/tuidungeon-storage-browser.png")
                with page.expect_response(lambda r: "/commands" in r.url) as response:
                    page.keyboard.press("Enter")
                state = response.value.json()
                private = next(
                    c for c in state["containers"] if c["id"] == "personal_chest"
                )
                assert private["items"][0]["quantity"] == 1
                assert state["turns"] == initial["turns"]
                expect(slider).to_have_count(0)
                right.locator(".storage-row").nth(1).click()
                page.keyboard.press("F5")
                expect(slider).to_have_value("1")
                page.keyboard.press("Backspace")
                expect(slider).to_have_count(0)
                page.keyboard.press("Tab")
                expect(left).to_have_class("storage-pane active")
                left.locator(".storage-row").first.click()
                with page.expect_response(lambda r: "/commands" in r.url) as response:
                    page.keyboard.press("Enter")
                state = response.value.json()
                assert state["log"][-1]["performed"]
                private = next(
                    c for c in state["containers"] if c["id"] == "personal_chest"
                )
                assert (
                    len(private["items"]) == 3 and not private["items"][-1]["equipped"]
                )
                page.keyboard.press("Backspace")
                expect(dialog).to_have_count(0)

                loot_name = next(
                    c["name"] for c in state["containers"] if c["id"] == "loot_sack"
                )
                open_container(loot_name)
                page.keyboard.press("ArrowLeft")
                expect(dialog.get_by_role("button", name="Положить →")).to_be_disabled()
                page.keyboard.press("w")
                page.keyboard.press("Enter")
                expect(slider).to_have_count(0)
                page.keyboard.press("ArrowRight")
                page.keyboard.press("Enter")
                expect(slider).to_have_value("1")
                with page.expect_response(lambda r: "/commands" in r.url) as response:
                    page.keyboard.press("Enter")
                state = response.value.json()
                assert state["position"] == initial["position"] and state["turns"] == 0
                illegal = page.request.post(
                    f"http://127.0.0.1:{port}/api/sessions/{session_id}/commands",
                    data=dict(
                        command="storage_transfer",
                        placement="loot_sack",
                        item=state["hero"]["stacks"][0]["id"],
                        deposit=True,
                    ),
                )
                assert illegal.ok and not illegal.json()["log"][-1]["performed"]
                bad_quantity = page.request.post(
                    f"http://127.0.0.1:{port}/api/sessions/{session_id}/commands",
                    data=dict(
                        command="storage_transfer",
                        placement="loot_sack",
                        item="missing",
                        quantity=True,
                    ),
                )
                assert bad_quantity.status == 422
                reset = page.request.post(
                    f"http://127.0.0.1:{port}/api/sessions/{session_id}/reset", data={}
                ).json()
                assert [c["weight"] for c in reset["containers"]] == [
                    c["weight"] for c in initial["containers"]
                ]
                assert not errors, errors
                browser.close()
                print(
                    "Browser OK: two panes, slider, cancel, single/stack transfers, personal/loot restrictions, blocked movement, strict API and reset."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
