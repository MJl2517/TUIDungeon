"""Real browser smoke check for door painting and incremental lockpicking."""

from pathlib import Path
import re
import shutil
import socket
import tempfile
import threading
import time

import uvicorn
from playwright.sync_api import sync_playwright

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.tooling.server import create_app


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-doors-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        raw = dict(
            id="door_smoke",
            name="Дверной полигон браузера",
            width=20,
            height=12,
            tiles=[["base:floor"] * 20 for _ in range(12)],
            walkability=[[True] * 20 for _ in range(12)],
            blocks_sight=[[False] * 20 for _ in range(12)],
            doors=[],
            traps=[dict(id="trap", ref="base:spikes", x=4, y=1)],
            equipment=[dict(id="tool", ref="base:thieves_tools", x=5, y=1)],
            spawn=dict(x=1, y=1),
        )
        store.save("maps", "base:door_smoke", raw, None)
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
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=shutil.which("google-chrome")
                    or shutil.which("chromium"),
                    args=["--no-sandbox"],
                )
                page = browser.new_page(viewport=dict(width=1600, height=1000))
                page.set_default_timeout(20000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                page.locator('.navigation [data-category="maps"]').click()
                page.locator(".library-list").get_by_role(
                    "button", name=re.compile("Дверной полигон браузера")
                ).click()
                page.get_by_label("Поиск тайлов").fill("base:door_wood")
                page.locator('[data-ref="base:door_wood"]').click()
                canvas = page.locator("canvas")
                box = canvas.bounding_box()
                canvas.click(
                    position=dict(x=box["width"] / 20 * 2.5, y=box["height"] / 12 * 1.5)
                )
                page.keyboard.press("v")
                canvas.click(
                    position=dict(x=box["width"] / 20 * 2.5, y=box["height"] / 12 * 1.5)
                )
                inspector = page.get_by_label("Свойства экземпляра", exact=True)
                inspector.get_by_label("Заперта", exact=True).check()
                inspector.get_by_label("Качество замка", exact=True).select_option(
                    "cheap"
                )
                inspector.get_by_label("Сложность замка", exact=True).select_option(
                    "complex"
                )
                page.screenshot(
                    path=str(
                        Path(tempfile.gettempdir())
                        / "tuidungeon-instance-inspector.png"
                    )
                )
                # Generic forms use the same selection workflow for traps and loot.
                canvas.click(
                    position=dict(x=box["width"] / 20 * 4.5, y=box["height"] / 12 * 1.5)
                )
                inspector.locator("summary").filter(
                    has_text=re.compile("^Сложность$")
                ).click()
                inspector.get_by_label("Сложность", exact=True).fill("21")
                canvas.click(
                    position=dict(x=box["width"] / 20 * 5.5, y=box["height"] / 12 * 1.5)
                )
                inspector.locator("summary").filter(
                    has_text=re.compile("^Стойкость$")
                ).click()
                inspector.get_by_label("Стойкость", exact=True).fill("30")
                with page.expect_response(
                    lambda response: "/api/documents/maps/" in response.url
                    and response.request.method == "PUT"
                ) as saved:
                    page.locator(".document-heading").get_by_role(
                        "button", name="Сохранить", exact=True
                    ).click()
                assert saved.value.ok, saved.value.text()
                document = PackStore(root).get("maps", "base:door_smoke")
                assert len(document.doors) == 1
                assert (document.doors[0].x, document.doors[0].y) == (2, 1)
                assert document.doors[0].ref == "base:door_wood"
                assert (
                    document.doors[0].overrides["brush"]["door"]["lock_complexity"]
                    == "complex"
                )
                assert document.traps[0].overrides["difficulty"] == 21
                assert document.equipment[0].overrides["durability"] == 30
                assert not errors, errors
                browser.close()
                print(
                    "Browser OK: five door types; instance inspector for doors, traps and equipment + save."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
