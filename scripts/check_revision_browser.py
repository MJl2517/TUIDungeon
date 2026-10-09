"""Real browser: no polling flicker, global search and native object placement."""

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
from tuidungeon.application.factories import SessionFactory


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-revision-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        store.create_pack(
            dict(id="sample", name="Поисковый пакет", dependencies=["base"])
        )
        store.save(
            "tiles",
            "sample:floor_probe",
            dict(id="floor_probe", name="Другой пол"),
            None,
        )
        store.save(
            "maps",
            "base:revision_smoke",
            dict(
                id="revision_smoke",
                name="Проверка ревизии",
                width=12,
                height=10,
                tiles=[["base:floor"] * 12 for _ in range(10)],
                walkability=[[True] * 12 for _ in range(10)],
                blocks_sight=[[False] * 12 for _ in range(10)],
                spawn=dict(x=1, y=1),
                ambient_light="bright",
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
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=shutil.which("google-chrome")
                    or shutil.which("chromium"),
                    args=["--no-sandbox"],
                )
                page = browser.new_page(viewport=dict(width=1600, height=1000))
                page.set_default_timeout(20000)
                errors = []
                requests = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url))
                page.goto(f"http://127.0.0.1:{port}")
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_label("Пакет библиотеки").select_option("sample")
                page.get_by_label("Поиск по всей библиотеке").fill("щит")
                result = page.locator(".library-entry").filter(has_text="base:shield")
                expect(result).to_have_count(1)
                result.click()
                expect(page.locator(".document-heading h1")).to_have_text("Щит")
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_label("Пакет библиотеки").select_option("all")
                page.locator(".library-list").get_by_role(
                    "button", name="Проверка ревизии", exact=False
                ).click()
                canvas = page.locator(".map-editor canvas")
                canvas.wait_for()
                expect(page.locator(".loading-overlay")).to_have_count(0)
                # Instrument the real canvas and loading overlay across two polls.
                page.evaluate("""() => {
                  window.originalCanvas = document.querySelector('.map-editor canvas');
                  window.canvasResets=0; window.loadingFlashes=0;
                  for (const key of ['width','height']) {
                    const descriptor=Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype,key);
                    Object.defineProperty(HTMLCanvasElement.prototype,key,{...descriptor,set(value){
                      if(this===window.originalCanvas)window.canvasResets++;
                      descriptor.set.call(this,value);
                    }});
                  }
                  new MutationObserver(records => {
                    for(const record of records)for(const node of record.addedNodes)
                      if(node.nodeType===1 && (node.matches('.loading-overlay')||node.querySelector('.loading-overlay')))window.loadingFlashes++;
                  }).observe(document.querySelector('main'),{childList:true,subtree:true});
                }""")
                before_assets = sum(url.endswith("/api/assets") for url in requests)
                box = canvas.bounding_box()
                for i in range(20):
                    page.mouse.move(box["x"] + 25 + i * 3, box["y"] + 50)
                page.wait_for_timeout(11000)
                assert page.evaluate(
                    "window.loadingFlashes===0 && window.canvasResets===0 && window.originalCanvas===document.querySelector('.map-editor canvas')"
                )
                assert (
                    sum(url.endswith("/api/assets") for url in requests)
                    == before_assets
                )
                # External asset edits refresh in the background without resetting the draft.
                page.get_by_label("Название документа", exact=True).fill(
                    "Несохранённый черновик"
                )
                raw = store.get("equipment", "base:dagger").model_dump(mode="json")
                raw["description"] = "external_probe_changed"
                store.save(
                    "equipment",
                    "base:dagger",
                    raw,
                    store.versions["equipment", "base:dagger"],
                )
                search = page.locator(".map-palette input[placeholder]")
                search.fill("external_probe_changed")
                expect(
                    page.locator('.palette-tile[data-ref="base:dagger"]')
                ).to_be_visible()
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Несохранённый черновик")
                assert page.evaluate(
                    "window.loadingFlashes===0 && window.originalCanvas===document.querySelector('.map-editor canvas')"
                )
                search.fill("")
                page.get_by_label("Пакет палитры").select_option("sample")
                page.get_by_label("Свойства тайлов").select_option("blocking")
                search.fill("base:shield")
                expect(page.locator(".palette-tile")).to_have_count(1)
                page.locator('.palette-tile[data-ref="base:shield"]').click()
                expect(page.get_by_label("Слой карты")).to_have_value("equipment")

                def cell(x, y):
                    canvas.click(position=dict(x=(x + 0.5) * 15.6, y=(y + 0.5) * 26))

                cell(4, 3)
                search.fill("base:table")
                page.locator('.palette-tile[data-ref="base:table"]').click()
                expect(page.get_by_label("Слой карты")).to_have_value("objects")
                cell(3, 3)
                page.keyboard.press("v")
                cell(4, 3)
                page.get_by_label("Вариант внешнего вида").select_option("0")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                stored = PackStore(root).get("maps", "base:revision_smoke")
                assert stored.tiles[3][3] == stored.tiles[3][4] == "base:floor"
                assert stored.objects[0].ref == "base:table"
                assert stored.equipment[0].ref == "base:shield"
                assert stored.equipment[0].overrides["glyph"] == "]"
                engine = SessionFactory(PackStore(root)).session("base:revision_smoke")
                assert not engine.state.level.terrain.walkability[3][3]
                assert engine.state.level.terrain.walkability[3][4]
                page.screenshot(path="/tmp/tuidungeon-revision-browser.png")
                assert not errors, errors
                browser.close()
                print(
                    "Browser OK: two unchanged polls without flashes/reloads/canvas resets; background edits preserve draft; global search ignores filters; native placement, variant and engine geometry."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
