"""Verify the Studio class selector and real API without spawning game windows."""

from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
from unittest.mock import patch

import uvicorn
from playwright.sync_api import expect, sync_playwright

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.tooling.server import create_app


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-launch-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        scout = store.get("classes", "base:rogue").model_dump(mode="json")
        scout.update(id="studio_scout", name="Тестовый разведчик")
        store.save("classes", "dev:studio_scout", scout, None)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root), host="127.0.0.1", port=port, log_level="error"
            )
        )
        with patch("tuidungeon.tooling.server.open_test_map") as launch:
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                for _ in range(100):
                    if server.started:
                        break
                    time.sleep(0.05)
                if not server.started:
                    raise RuntimeError("Не запустился локальный сервер")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=True,
                        executable_path=shutil.which("google-chrome")
                        or shutil.which("chromium"),
                        args=["--no-sandbox"],
                    )
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{port}")
                    page.locator('.navigation [data-category="maps"]').click()
                    page.get_by_label("Поиск по всей библиотеке").fill("base:crypt")
                    page.locator(".library-entry").click()
                    selector = page.get_by_label("Класс для запуска игры")
                    expect(selector).to_have_value("base:warrior")
                    expect(selector.locator("option")).to_have_count(4)
                    button = page.get_by_role(
                        "button", name="▶ В игровом окне", exact=True
                    )
                    for character_class in (
                        "base:warrior",
                        "base:rogue",
                        "base:wizard",
                        "dev:studio_scout",
                    ):
                        selector.select_option(character_class)
                        with page.expect_response(
                            lambda response: response.url.endswith("/api/game")
                        ) as result:
                            button.click()
                        assert result.value.status == 200, result.value.text()
                        assert (
                            result.value.request.post_data_json["character_class"]
                            == character_class
                        )
                        launch.assert_called_with(
                            root.resolve(), "base:crypt", 42, character_class
                        )
                        expect(button).to_be_enabled()
                    selector.select_option("base:wizard")
                    page.screenshot(
                        path="/tmp/tuidungeon-class-selector.png", full_page=True
                    )
                    assert not errors, errors
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=5)
    print(
        "Studio: default class, all three classes, custom pack class and API launch passed"
    )


if __name__ == "__main__":
    run()
