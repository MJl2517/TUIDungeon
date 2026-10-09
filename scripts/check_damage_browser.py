"""Exercise typed damage authoring and reports in an actual local browser."""

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
    with tempfile.TemporaryDirectory(prefix="dungeon-damage-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        store = PackStore(root)
        raw = store.get("monsters", "base:goblin").model_dump(mode="json")
        raw["special_actions"] = [
            dict(
                id="damage_probe",
                name="Проверка урона",
                kind="special",
                effects=[dict(kind="damage", amount=5, damage_type="cold")],
            )
        ]
        store.save(
            "monsters", "base:goblin", raw, store.versions["monsters", "base:goblin"]
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
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Не запустился локальный сервер")
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
                page.locator('.navigation [data-category="monsters"]').click()
                page.get_by_label("Поиск по всей библиотеке").fill("base:goblin")
                page.locator(".library-entry").filter(
                    has=page.get_by_text("Гоблин", exact=True)
                ).click()
                page.get_by_label("Тип урона", exact=True).last.select_option("fire")
                resistance = (
                    page.locator("fieldset")
                    .filter(
                        has=page.locator("legend", has_text="Сопротивления (½ урона)")
                    )
                    .last
                )
                resistance.get_by_role("button", name="+ Добавить", exact=True).click()
                resistance.locator("select").select_option("fire")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                saved = PackStore(root).get("monsters", "base:goblin")
                assert saved.damage_profile.resistances == ["fire"]
                assert saved.special_actions[0].effects[0].damage_type == "fire"
                page.get_by_label("Действие монстра").select_option("damage_probe")
                page.get_by_label("Цель песочницы").select_option("self")
                page.locator(".sandbox").get_by_label("Сложность", exact=True).fill("0")
                with page.expect_response(
                    lambda r: r.url.endswith("/api/sandbox")
                ) as response:
                    page.get_by_role(
                        "button", name="Выполнить действие", exact=True
                    ).click()
                result = response.value.json()["effects"][0]
                assert (
                    result["raw_amount"],
                    result["resolved_amount"],
                    result["amount"],
                ) == (5, 2, 2)
                expect(page.locator(".sandbox-result")).to_contain_text(
                    "Огонь: 5 → 2 (сопротивление)"
                )
                page.screenshot(path="/tmp/tuidungeon-damage-browser.png")
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
    print(
        "PASS: browser forms persist damage type and defenses; sandbox shows 5 → 2 resisted damage"
    )


if __name__ == "__main__":
    run()
