"""Browser regression: PYTHONPATH=. python scripts/check_map_orientation.py.

Uses an isolated copy of packs. Requires Playwright and installed Edge/Chromium.
"""

import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

import numpy as np
from playwright.sync_api import expect, sync_playwright
import uvicorn

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import Placement
from tuidungeon.tooling.server import create_app, ensure_studio_build


def run():
    ensure_studio_build()
    with tempfile.TemporaryDirectory(prefix="orientation-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root, ignore=shutil.ignore_patterns(".trash"))
        path = root / "tiles/maps/orientation_test.json"
        path.write_text(
            json.dumps(
                dict(
                    id="orientation_test",
                    name="Проверка ориентации",
                    width=8,
                    height=6,
                    tiles=[["base:floor"] * 8 for _ in range(6)],
                    walkability=[[True] * 8 for _ in range(6)],
                    blocks_sight=[[False] * 8 for _ in range(6)],
                    spawn=dict(x=0, y=0),
                    ambient_light="bright",
                )
            ),
            encoding="utf-8",
        )
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(root), host="127.0.0.1", port=0, log_level="error"
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(200):
                if server.started:
                    break
                time.sleep(0.05)
            port = server.servers[0].sockets[0].getsockname()[1]
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    channel=os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL", "msedge"),
                )
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}/")
                page.get_by_role("button", name="Карты", exact=True).click()
                page.get_by_label("Поиск контента").fill("tiles:orientation_test")
                page.locator(".content-entry").click()
                page.get_by_role("button", name="Разрушаемые тайлы", exact=True).click()
                page.get_by_label("Поиск кистей").fill("tiles:rails_247")
                page.locator('[data-ref="tiles:rails_247"]').click()
                canvas = page.get_by_label("Символьный холст", exact=True)
                ghost = page.get_by_label("Предпросмотр кисти", exact=True)
                box = canvas.bounding_box()
                x, y = box["x"] + 2.5 * 32, box["y"] + 2.5 * 32
                page.mouse.move(x, y)
                expect(ghost).to_be_visible()

                def pixels():
                    data = ghost.evaluate(
                        "c => ({w:c.width,h:c.height,p:Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data)})"
                    )
                    return np.array(data["p"]).reshape(data["h"], data["w"], 4)[
                        2:-2, 2:-2
                    ]

                original = pixels()
                page.keyboard.down("Shift")
                expect(
                    page.get_by_text("Отражение включено", exact=False)
                ).to_be_visible()
                np.testing.assert_array_equal(pixels(), original[:, ::-1])
                assert not np.array_equal(original, pixels()), (
                    "Rail preview must actually change"
                )
                page.mouse.wheel(0, 100)
                expect(page.get_by_label("Направление кисти")).to_have_value("90")
                np.testing.assert_array_equal(pixels(), np.rot90(original, -1)[:, ::-1])
                scroll = page.locator(".map-viewport").evaluate(
                    "e=>[e.scrollLeft,e.scrollTop]"
                )
                page.mouse.click(x, y)
                page.keyboard.up("Shift")
                page.mouse.move(x + 32, y)
                page.mouse.wheel(0, -100)
                expect(page.get_by_label("Направление кисти")).to_have_value("0")
                np.testing.assert_array_equal(pixels(), original)
                assert (
                    page.locator(".map-viewport").evaluate(
                        "e=>[e.scrollLeft,e.scrollTop]"
                    )
                    == scroll
                )
                page.mouse.move(10, 10)
                expect(ghost).to_have_count(0)
                page.get_by_role("button", name="JSON", exact=True).click()
                draft = json.loads(page.get_by_label("JSON документа").input_value())
                rail = next(
                    o for o in draft["objects"] if o["ref"] == "tiles:rails_247"
                )
                assert (rail["x"], rail["y"]) == (2, 2)
                assert rail["overrides"] == {"mirror_x": True, "rotation": 90}
                with page.expect_response(
                    lambda r: r.request.method == "PUT" and "/api/documents/" in r.url
                ) as response:
                    page.get_by_role("button", name="Сохранить", exact=True).click()
                assert response.value.ok, response.value.text()
                saved = json.loads(path.read_text(encoding="utf-8"))
                assert [Placement.model_validate(o) for o in saved["objects"]] == [
                    Placement.model_validate(o) for o in draft["objects"]
                ]
                store = PackStore(root)
                obj = store.snapshot().resolve(
                    "objects", store.get("maps", "tiles:orientation_test").objects[0]
                )
                assert obj.rotation == 90 and obj.mirror_x
                page.reload()
                page.get_by_role("button", name="Карты", exact=True).click()
                page.get_by_label("Поиск контента").fill("tiles:orientation_test")
                page.locator(".content-entry").click()
                page.get_by_role("button", name="JSON", exact=True).click()
                loaded = json.loads(page.get_by_label("JSON документа").input_value())
                assert loaded["objects"] == saved["objects"]
                assert not errors, errors
                browser.close()
                print(
                    "Studio: ghost pixels, Shift mirror, wheel both ways, placement and saved reload OK"
                )
        finally:
            server.should_exit = True
            thread.join(10)


if __name__ == "__main__":
    run()
