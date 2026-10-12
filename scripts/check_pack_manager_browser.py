"""Real browser acceptance for editing packs while a map draft stays open."""

import os
from pathlib import Path
import re
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
    with tempfile.TemporaryDirectory(prefix="dungeon-pack-manager-") as folder:
        root = Path(folder) / "packs"
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
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=os.environ.get("PLAYWRIGHT_BROWSER_EXECUTABLE")
                    or shutil.which("chromium")
                    or shutil.which("google-chrome"),
                )
                page = browser.new_page(viewport=dict(width=1440, height=1000))
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}")
                manager = page.get_by_role("dialog", name="Пакеты контента", exact=True)

                def open_manager():
                    page.get_by_role(
                        "button", name="Пакеты контента", exact=True
                    ).click()
                    expect(manager.get_by_label("Название пакета")).to_be_enabled()

                def save_pack():
                    with page.expect_response(
                        lambda r: "/api/packs/" in r.url and r.request.method == "PUT"
                    ) as result:
                        manager.get_by_role(
                            "button", name="Сохранить пакет", exact=True
                        ).click()
                    assert result.value.status == 200, result.value.text()
                    expect(
                        manager.get_by_role("button", name="Закрыть", exact=True)
                    ).to_be_enabled()

                def create_pack(identifier, name, dependency=None):
                    manager.get_by_role(
                        "button", name="+ Новый пакет", exact=True
                    ).click()
                    manager.get_by_label("ID пакета", exact=True).fill(identifier)
                    manager.get_by_label("Название пакета", exact=True).fill(name)
                    base_dependency = manager.get_by_role(
                        "checkbox", name=re.compile(r" · base$")
                    )
                    expect(base_dependency).to_be_checked()
                    if dependency:
                        manager.get_by_role(
                            "checkbox", name=re.compile(r" · " + dependency + "$")
                        ).check()
                    manager.get_by_role(
                        "button", name="Создать пакет", exact=True
                    ).click()
                    expect(
                        manager.get_by_label("ID пакета", exact=True)
                    ).to_be_disabled()
                    expect(manager.get_by_label("ID пакета", exact=True)).to_have_value(
                        identifier
                    )
                    expect(
                        manager.get_by_label("Название пакета", exact=True)
                    ).to_be_enabled()

                open_manager()
                create_pack("browser_pack", "Пакет испытаний")
                manager.get_by_label("Название пакета", exact=True).fill(
                    "Демо для друзей"
                )
                manager.get_by_label("Версия пакета", exact=True).fill("1.2.3")
                manager.get_by_role("checkbox", name=re.compile(r" · base$")).uncheck()
                with page.expect_response(
                    lambda r: "/api/packs/browser_pack" in r.url
                    and r.request.method == "PUT"
                ) as result:
                    page.keyboard.press("Control+s")
                assert result.value.status == 200
                expect(
                    manager.get_by_role("button", name="Закрыть", exact=True)
                ).to_be_enabled()
                manager.get_by_role("button", name="Закрыть", exact=True).click()
                manifest = PackStore(root).manifests["browser_pack"]
                assert (manifest.name, manifest.version, manifest.dependencies) == (
                    "Демо для друзей",
                    "1.2.3",
                    [],
                )

                # Reproduce the reported error on an unsaved map, then fix dependencies in place.
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_role("button", name="+ Создать", exact=True).click()
                creation = page.locator(".creation-modal")
                creation.locator("select").select_option("browser_pack")
                creation.get_by_label("ID нового документа", exact=True).fill(
                    "test_dungeon"
                )
                creation.get_by_label("Название нового документа", exact=True).fill(
                    "Черновик подземелья"
                )
                creation.get_by_role(
                    "button", name="Создать документ", exact=True
                ).click()
                page.locator(".map-editor canvas").click(position=dict(x=39, y=65))
                with page.expect_response(
                    lambda r: "/api/documents/maps/browser_pack:test_dungeon" in r.url
                    and r.request.method == "PUT"
                ) as result:
                    page.get_by_role("button", name="Сохранить", exact=True).click()
                assert result.value.status == 422, result.value.text()
                expect(page.get_by_role("alert")).to_contain_text("зависимост")
                open_manager()
                expect(manager.get_by_label("ID пакета", exact=True)).to_have_value(
                    "browser_pack"
                )
                expect(
                    manager.get_by_role("button", name="Удалить пакет", exact=True)
                ).to_be_disabled()
                expect(manager).to_contain_text("черновик")
                manager.get_by_role("checkbox", name=re.compile(r" · base$")).check()
                save_pack()
                manager.get_by_role("button", name="Закрыть", exact=True).click()
                expect(
                    page.get_by_label("Название документа", exact=True)
                ).to_have_value("Черновик подземелья")
                expect(page.locator(".unsaved")).to_have_count(1)
                with page.expect_response(
                    lambda r: "/api/documents/maps/browser_pack:test_dungeon" in r.url
                    and r.request.method == "PUT"
                ) as result:
                    page.get_by_role("button", name="Сохранить", exact=True).click()
                assert result.value.status == 200, result.value.text()
                expect(page.locator(".unsaved")).to_have_count(0)

                open_manager()
                manager.get_by_role("checkbox", name=re.compile(r" · base$")).uncheck()
                with page.expect_response(
                    lambda r: "/api/packs/browser_pack" in r.url
                    and r.request.method == "PUT"
                ) as result:
                    manager.get_by_role(
                        "button", name="Сохранить пакет", exact=True
                    ).click()
                assert result.value.status == 422
                expect(manager.get_by_role("alert")).to_contain_text("зависимост")
                manager.get_by_role("checkbox", name=re.compile(r" · base$")).check()
                create_pack("browser_child", "Зависимый пакет", "browser_pack")
                listing = manager.get_by_role("complementary", name="Список пакетов")
                listing.get_by_role(
                    "button", name=re.compile("Демо для друзей")
                ).click()
                expect(
                    manager.get_by_role("button", name="Удалить пакет", exact=True)
                ).to_be_disabled()
                expect(manager).to_contain_text("От пакета зависят")
                for width in (800, 600):
                    page.set_viewport_size(dict(width=width, height=640))
                    assert manager.evaluate("e => e.scrollWidth <= e.clientWidth")
                page.screenshot(
                    path=str(
                        Path(tempfile.gettempdir()) / "tuidungeon-pack-manager.png"
                    )
                )
                page.set_viewport_size(dict(width=1440, height=1000))
                listing.get_by_role(
                    "button", name=re.compile("Зависимый пакет")
                ).click()
                expect(manager.get_by_label("ID пакета", exact=True)).to_have_value(
                    "browser_child"
                )
                page.once("dialog", lambda d: d.accept())
                with page.expect_response(
                    lambda r: "/api/packs/browser_child" in r.url
                    and r.request.method == "DELETE"
                ) as result:
                    manager.get_by_role(
                        "button", name="Удалить пакет", exact=True
                    ).click()
                assert result.value.status == 200
                assert Path(result.value.json()["archive"]).is_dir()
                expect(
                    manager.get_by_role("button", name="Закрыть", exact=True)
                ).to_be_enabled()
                listing.get_by_role(
                    "button", name=re.compile("Демо для друзей")
                ).click()
                expect(manager.get_by_label("ID пакета", exact=True)).to_have_value(
                    "browser_pack"
                )
                page.once("dialog", lambda d: d.accept())
                with page.expect_response(
                    lambda r: "/api/packs/browser_pack" in r.url
                    and r.request.method == "DELETE"
                ) as result:
                    manager.get_by_role(
                        "button", name="Удалить пакет", exact=True
                    ).click()
                assert result.value.status == 200
                archive = Path(result.value.json()["archive"])
                assert (archive / "maps" / "test_dungeon.json").is_file()
                expect(manager.get_by_label("ID пакета", exact=True)).to_have_value(
                    "base"
                )
                expect(
                    manager.get_by_role("button", name="Удалить пакет", exact=True)
                ).to_be_disabled()
                manager.get_by_role("button", name="Закрыть", exact=True).click()
                expect(page.locator(".library-page")).to_be_visible()
                assert not errors, errors
                browser.close()
                print(
                    "Pack manager browser passed: create, rename, version, Ctrl+S, dependencies, draft preservation, save retry, guards, archive deletion, small windows."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
