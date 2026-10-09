"""Check fire through real Studio UI using temporary packs and a loopback server."""

from pathlib import Path
import re
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
    with tempfile.TemporaryDirectory(prefix="dungeon-fire-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        store.save(
            "maps",
            "base:fire_smoke",
            dict(
                id="fire_smoke",
                name="Проверка огня в браузере",
                width=10,
                height=8,
                tiles=[["base:floor"] * 10 for _ in range(8)],
                walkability=[[True] * 10 for _ in range(8)],
                blocks_sight=[[False] * 10 for _ in range(8)],
                ambient_light="bright",
                spawn=dict(x=3, y=3),
                doors=[
                    dict(
                        id="wood",
                        ref="base:door_wood",
                        x=4,
                        y=3,
                        overrides={"brush": {"door": {"hit_points": 20}}},
                    ),
                    dict(id="bars", ref="base:door_bars", x=6, y=3),
                    dict(id="slab", ref="base:door_stone", x=3, y=4),
                ],
                equipment=[
                    dict(id=f"sample_{i}", ref=f"base:{name}", x=3, y=3)
                    for i, name in enumerate(("flint_and_steel", "oil", "acid_flask"))
                ],
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
                    "button", name=re.compile("Проверка огня в браузере")
                ).click()
                page.get_by_role(
                    "button", name="▶ Тестировать карту", exact=True
                ).click()
                modal = page.locator(".playtest")
                modal.get_by_role("button", name="Начать тест", exact=True).click()
                expect(
                    modal.get_by_role("heading", name="Снаряжение и свет")
                ).to_be_visible()

                def action(callback):
                    with page.expect_response(
                        lambda r: "/commands" in r.url and r.request.method == "POST"
                    ) as response:
                        callback()
                    assert response.value.ok, response.value.text()
                    return response.value.json()

                def click_cell(x, y):
                    modal.locator("canvas").click(
                        position=dict(x=(x + 0.5) * 12 * 1.3, y=(y + 0.5) * 20 * 1.3)
                    )

                for _ in range(3):
                    action(
                        lambda: modal.get_by_role(
                            "button", name="G · Подобрать", exact=True
                        ).click()
                    )
                oil = modal.locator(".playtest-item").filter(has_text="Масло").first
                oil.get_by_role("button", name="Бросить на клетку", exact=True).click()
                state = action(lambda: click_cell(4, 3))
                assert state["oil"] == [dict(x=4, y=3, turns=5)]
                flint = modal.locator(".playtest-item").filter(
                    has_text="Кремень и кресало"
                )
                flint.get_by_role("button", name="Поджечь", exact=True).click()
                state = action(lambda: click_cell(4, 3))
                assert state["oil"] == []
                assert state["doors"][0]["hp"] == 10
                assert state["cells"][3][4]["foreground"] == 9
                state = action(
                    lambda: modal.get_by_role(
                        "button", name="Ждать", exact=True
                    ).click()
                )
                assert state["doors"][0]["hp"] == 5
                assert state["cells"][3][4]["foreground"] == 130
                state = action(
                    lambda: modal.get_by_role(
                        "button", name="Ждать", exact=True
                    ).click()
                )
                assert state["doors"][0]["hp"] == 0
                acid = modal.locator(".playtest-item").filter(has_text="Флакон кислоты")
                acid.get_by_role("button", name="Бросить на клетку", exact=True).click()
                state = action(lambda: click_cell(6, 3))
                bars = next(d for d in state["doors"] if d["id"] == "bars")
                assert bars["hp"] < 20
                assert bars["corroding"] or bars["hp"] == 0
                slab = next(p for p in state["nearby"] if p["id"] == "slab")
                assert [c["id"] for c in slab["choices"]] == ["attack"]
                page.screenshot(
                    path=str(
                        Path(tempfile.gettempdir()) / "tuidungeon-fire-browser.png"
                    )
                )
                with page.expect_response(
                    lambda r: r.url.endswith("/reset") and r.request.method == "POST"
                ) as reset:
                    modal.get_by_role(
                        "button", name="Перезапустить", exact=True
                    ).click()
                fresh = reset.value.json()
                assert fresh["oil"] == []
                assert [d["hp"] for d in fresh["doors"]] == [20, 20, 30]
                assert not any(d["burning"] or d["corroding"] for d in fresh["doors"])
                expect(
                    modal.get_by_role("heading", name="Масло на клетках", exact=True)
                ).to_have_count(0)
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
        print("Browser oil, ignition, turn colors, acid/bars, slab and reset: OK")


if __name__ == "__main__":
    run()
