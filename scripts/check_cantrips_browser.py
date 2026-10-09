"""Exercise spell schemas, choice of cantrips and targeting in an actual browser."""

from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time

import uvicorn
from playwright.sync_api import expect, sync_playwright

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import MapDocument
from tuidungeon.tooling.server import create_app
from tuidungeon.domain.equipment import Equipment


def run():
    with tempfile.TemporaryDirectory(prefix="dungeon-cantrips-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        raw = MapDocument(
            id="cantrip_probe",
            name="Проверка заговоров",
            width=12,
            height=8,
            tiles=[["base:floor"] * 12 for _ in range(8)],
            walkability=[[True] * 12 for _ in range(8)],
            blocks_sight=[[False] * 12 for _ in range(8)],
            spawn={"x": 4, "y": 4},
            ambient_light="bright",
        ).model_dump(mode="json")
        PackStore.atomic_json(root / "base/maps/cantrip_probe.json", raw)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        app = create_app(root)
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
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
                page = browser.new_page(viewport=dict(width=1600, height=1100))
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                page.locator('.navigation [data-category="spells"]').click()
                page.get_by_label("Поиск по всей библиотеке").fill("base:light")
                page.locator(".library-entry").filter(
                    has=page.get_by_text("Свет", exact=True)
                ).click()
                page.get_by_label("Длительность", exact=True).fill("12")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                assert (
                    PackStore(root)
                    .get("spells", "base:light")
                    .world_parameters["duration"]
                    == 12
                )
                page.get_by_label("Механика исследования", exact=True).select_option(
                    "repair"
                )
                expect(
                    page.get_by_label("Починка инструментов", exact=True)
                ).to_have_value("1")
                expect(
                    page.get_by_label("Починка оружия и доспехов", exact=True)
                ).to_have_value("1d4")
                # Leave the unsaved draft through an explicit discard, never save a
                # nonsensical light/repair hybrid into the fixture.
                page.reload()
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_label("Поиск по всей библиотеке").fill("base:cantrip_probe")
                page.locator(".library-entry").filter(
                    has=page.get_by_text("Проверка заговоров", exact=True)
                ).click()
                page.get_by_role(
                    "button", name="▶ Тестировать карту", exact=True
                ).click()
                modal = page.locator(".playtest")
                modal.get_by_label("Тестовый класс").select_option("base:wizard")
                modal.get_by_label("Огненный снаряд", exact=True).uncheck()
                modal.get_by_label("Пляшущие огоньки", exact=True).check()
                with page.expect_response(
                    lambda r: r.url.endswith("/api/sessions")
                ) as response:
                    modal.get_by_role("button", name="Начать тест", exact=True).click()
                initial = response.value.json()
                assert {
                    s["id"] for s in initial["hero"]["spells"] if s["level"] == 0
                } == {"light", "mending", "dancing_lights"}
                item = initial["hero"]["inventory"][0]["id"]
                repair_select = modal.get_by_label(
                    "Предмет для заговора Починка (класс)"
                )
                repair_button = modal.get_by_role(
                    "button", name="Починка · 1 кл.", exact=True
                )
                expect(repair_select).to_be_disabled()
                expect(repair_button).to_be_disabled()
                session = app.state.sessions[initial["id"]]
                with session.lock:
                    hero = session.engine.state.hero
                    tools = [
                        Equipment.create(hero.catalog.equipment[s])
                        for s in ("crowbar", "thieves_tools")
                    ]
                    for tool in tools:
                        tool.wear(1)
                    hero.inventory.extend(tools)
                modal.get_by_label("Предмет для заговора Свет (класс)").select_option(
                    item
                )
                with page.expect_response(
                    lambda r: r.url.endswith("/commands")
                ) as response:
                    modal.get_by_role("button", name="Свет · 1 кл.", exact=True).click()
                lit = response.value.json()
                expect(modal.locator(f'[data-item-id="{item}"]')).to_contain_text(
                    "Свечение [glowing]: 12 ход."
                )
                page.screenshot(path="/tmp/tuidungeon-glowing-item-browser.png")
                expect(repair_select.locator("option")).to_have_text(
                    [
                        "Выберите предмет",
                        "Ломик (4/5)",
                        "Воровские инструменты (9/10)",
                    ]
                )
                assert lit["turns"] == 1
                assert (
                    lit["hero"]["cantrip_uses"] == initial["hero"]["cantrip_uses"] - 1
                )
                modal.get_by_role(
                    "button", name="Пляшущие огоньки · 6 кл.", exact=True
                ).click()
                with page.expect_response(
                    lambda r: r.url.endswith("/commands")
                ) as response:
                    modal.locator("canvas").click(
                        position=dict(x=5.5 * 12 * 1.3, y=4.5 * 20 * 1.3)
                    )
                dancing = response.value.json()
                assert dancing["hero"]["concentrating"]
                assert dancing["turns"] == 2
                with page.expect_response(
                    lambda r: r.url.endswith("/commands")
                ) as response:
                    modal.get_by_role(
                        "button",
                        name="Короткий отдых · заговоры +модификатор",
                        exact=True,
                    ).click()
                assert not response.value.json()["hero"]["concentrating"]
                expect(modal.locator(f'[data-item-id="{item}"]')).not_to_contain_text(
                    "Свечение"
                )
                for tool in tools:
                    repair_select.select_option(tool.instance_id)
                    with page.expect_response(
                        lambda r: r.url.endswith("/commands")
                    ) as repair_response:
                        repair_button.click()
                    assert repair_response.value.status == 200
                    assert tool.durability == tool.definition.durability
                expect(repair_select).to_be_disabled()
                expect(repair_button).to_be_disabled()
                expect(repair_select.locator("option")).to_have_text(
                    [
                        "Нет повреждённых предметов с прочностью",
                    ]
                )
                page.screenshot(path="/tmp/tuidungeon-cantrips-browser.png")
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
    print(
        "PASS: spell forms, three cantrips, casts, concentration and filtered repair targets in browser"
    )


if __name__ == "__main__":
    run()
