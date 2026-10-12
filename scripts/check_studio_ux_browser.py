"""Studio UX smoke test on disposable packs; requires Playwright and a browser.

Set PLAYWRIGHT_BROWSER_EXECUTABLE when using an installed Edge/Chrome.
"""

import os
import json
from pathlib import Path
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
    with tempfile.TemporaryDirectory(prefix="dungeon-studio-ux-") as directory:
        root = Path(directory) / "packs"
        shutil.copytree(DEFAULT_PACKS, root)
        lab_path = root / "dev/maps/crafting_lab.json"
        lab = json.loads(lab_path.read_text(encoding="utf-8"))
        lab["equipment"].append(dict(id="ux_spare_oil", ref="base:oil", **lab["spawn"]))
        lab_path.write_text(json.dumps(lab, ensure_ascii=False), encoding="utf-8")
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
                page = browser.new_page(viewport=dict(width=1600, height=1000))
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}")

                # Catalog pages must respond to the mouse wheel, not just to
                # programmatic scroll_into_view (which also scrolls overflow:hidden).
                def wheel_to_bottom(selector):
                    panel = page.locator(selector)
                    expect(panel).to_be_visible()
                    assert panel.evaluate("e => e.scrollHeight > e.clientHeight")
                    panel.evaluate("e => e.scrollTop = 0")
                    box = panel.bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 20)
                    page.mouse.wheel(0, 100000)
                    page.wait_for_function(
                        "s => { const e = document.querySelector(s); "
                        "return e.scrollTop > 0 && "
                        "e.scrollTop + e.clientHeight >= e.scrollHeight - 2; }",
                        arg=selector,
                    )

                page.locator(".home-card").first.wait_for()
                wheel_to_bottom(".studio-home")
                for size in [(1600, 1000), (800, 640)]:
                    page.set_viewport_size(dict(zip(("width", "height"), size)))
                    for category in ["equipment", "tiles", "objects", "recipes"]:
                        page.locator(
                            f'.navigation [data-category="{category}"]'
                        ).click()
                        page.locator(".content-entry").first.wait_for()
                        wheel_to_bottom(".library-page")
                        expect(page.locator(".content-pagination")).to_be_in_viewport()
                page.set_viewport_size(dict(width=1600, height=1000))
                # Tag editing is checked on disposable content, including persistence.
                page.get_by_role("button", name="Предметы", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:pickaxe")
                page.locator(".content-entry").click()
                wheel_to_bottom(".mechanics-form")
                tag_search = page.get_by_label("Поиск игровых тегов", exact=True)
                tag_search.fill("свят")
                expect(
                    page.get_by_role("checkbox", name="Святой", exact=True)
                ).to_be_visible()
                page.get_by_role("checkbox", name="Святой", exact=True).check()
                tag_search.fill("holy")
                expect(
                    page.get_by_role("checkbox", name="Святой", exact=True)
                ).to_be_checked()
                tag_search.fill("state_burning")
                expect(page.locator(".tag-picker")).to_contain_text("Теги не найдены")
                tag_search.fill("камен")
                expect(
                    page.get_by_role("checkbox", name="Каменный", exact=True)
                ).to_be_visible()
                expect(
                    page.get_by_role("checkbox", name="Святой", exact=True)
                ).to_have_count(0)
                tag_search.fill("")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                assert {"holy", "metal", "wooden"} <= set(
                    PackStore(root).get("equipment", "base:pickaxe").tags
                )
                page.set_viewport_size(dict(width=800, height=640))
                tag_search.fill("poison")
                page.locator(".tag-picker").scroll_into_view_if_needed()
                page.screenshot(
                    path=str(Path(tempfile.gettempdir()) / "tuidungeon-tag-picker.png")
                )
                page.set_viewport_size(dict(width=1600, height=1000))
                # Renewable resources are edited through the shared object schema.
                page.locator('.navigation [data-category="objects"]').click()
                page.get_by_label("Поиск контента").fill("base:medicinal_flower")
                page.locator(".content-entry").click()
                recovery = page.get_by_label(
                    "Восстановление через (игровые минуты)", exact=True
                )
                expect(recovery).to_have_value("1440")
                recovery.fill("7")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                assert (
                    PackStore(root)
                    .get("objects", "base:medicinal_flower")
                    .destruction.regrow_minutes
                    == 7
                )
                page.reload()
                page.locator('.navigation [data-category="objects"]').click()
                page.get_by_label("Поиск контента").fill("base:medicinal_flower")
                page.locator(".content-entry").click()
                expect(recovery).to_have_value("7")
                page.locator('.navigation [data-category="objects"]').click()
                page.get_by_label("Поиск контента").fill("base:corpse")
                page.locator(".content-entry").click()
                page.get_by_role(
                    "button", name="+ Добавить: начальное содержимое", exact=True
                ).click()
                loot = page.get_by_role(
                    "button", name="Подбираемый предмет", exact=True
                )
                loot.click()
                picker = page.get_by_role(
                    "dialog", name="Подбираемый предмет", exact=True
                )
                picker.get_by_label("Поиск контента").fill("base:bandage")
                picker.locator(".content-entry").click()
                page.get_by_label("Количество предметов", exact=True).fill("2")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                corpse = PackStore(root).get("objects", "base:corpse")
                assert corpse.storage.contents[0].item == "base:bandage"
                assert corpse.storage.contents[0].quantity == 2
                assert corpse.walkable and corpse.map_category == "special"
                page.get_by_role("button", name="Рецепты", exact=True).click()
                page.get_by_label("Поиск контента").fill("base:craft_club")
                page.locator(".content-entry").click()
                work = page.get_by_role(
                    "region", name="Способы изготовления", exact=True
                )
                expect(work).to_be_visible()
                variants = work.locator(".recipe-variant-fields")
                variant_count = variants.count()
                first_variant = variants.first
                assert "RecipeVariant" not in page.locator("body").inner_text()
                assert "RecipeIngredient" not in page.locator("body").inner_text()
                page.get_by_label("Поиск свойств", exact=True).fill("ингредиенты")
                expect(
                    page.get_by_role("region", name="Основное", exact=True)
                ).to_have_count(0)
                expect(work).to_be_visible()
                page.get_by_label("Поиск свойств", exact=True).fill("")
                page.get_by_role("link", name="Способы изготовления").click()
                first_variant.get_by_role(
                    "button", name="Материал 1", exact=True
                ).click()
                picker = page.get_by_role("dialog", name="Материал 1", exact=True)
                picker.get_by_label("Поиск контента").fill("base:cloth")
                expect(picker.locator(".content-entry")).to_have_count(1)
                picker.locator(".content-entry").click()
                expect(page.get_by_role("dialog")).to_have_count(0)
                expect(
                    first_variant.get_by_role("button", name="Материал 1", exact=True)
                ).to_contain_text("base:cloth")
                first_variant.get_by_label("Количество предметов", exact=True).fill("3")
                first_variant.get_by_label("Ходы изготовления", exact=True).fill("4")
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                saved = PackStore(root).get("recipes", "base:craft_club")
                assert saved.variants[0].ingredients[0].items == ["base:cloth"]
                assert saved.variants[0].ingredients[0].quantity == 3
                assert saved.variants[0].turns == 4
                page.get_by_role(
                    "button", name="+ Добавить: способ", exact=True
                ).click()
                expect(variants).to_have_count(variant_count + 1)
                work.get_by_role(
                    "button", name=f"Удалить: Способ {variant_count + 1}", exact=False
                ).click()
                expect(variants).to_have_count(variant_count)
                page.get_by_role("button", name="Сохранить", exact=True).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                # Native modal must trap focus and Escape must restore it.
                material = first_variant.get_by_role(
                    "button", name="Материал 1", exact=True
                )
                material.click()
                expect(picker.get_by_label("Поиск контента")).to_be_focused()
                page.keyboard.press("Escape")
                expect(material).to_be_focused()
                # Global search crosses sections, while selected filters still apply.
                page.keyboard.press("Control+k")
                picker = page.get_by_role("dialog", name="Поиск по проекту", exact=True)
                picker.get_by_label("Поиск контента").fill("base:wood")
                picker.get_by_label("Раздел контента").select_option("equipment")
                expect(
                    picker.locator(".content-entry").filter(
                        has=page.get_by_text("Древесина", exact=True)
                    )
                ).to_be_visible()
                picker.get_by_label("Пакет контента").select_option("dev")
                for entry in picker.locator(".content-entry").all():
                    expect(entry).to_contain_text("dev:")
                expect(
                    picker.locator('.content-entry[data-ref="base:wood"]')
                ).to_have_count(0)
                picker.get_by_role("button", name="Сбросить", exact=True).click()
                expect(picker.get_by_label("Поиск контента")).to_have_value("")
                page.keyboard.press("Escape")
                page.locator('.navigation [data-category="spells"]').click()
                page.get_by_label("Уровень заклинания").select_option("0")
                cards = page.locator(".content-entry")
                expect(cards.first).to_be_visible()
                for badge in cards.locator(".content-badges").all_text_contents():
                    assert "Заговор" in badge
                page.get_by_label("Категория контента").select_option("Преобразование")
                for badge in cards.locator(".content-badges").all_text_contents():
                    assert "Преобразование" in badge
                page.get_by_label("Сортировка контента").select_option("name_desc")
                page.get_by_label("Поиск контента").fill("base:mending")
                expect(cards).to_have_count(1)
                cards.click()
                # Registered effect parameters survive the new sectioned form.
                page.get_by_label("Поиск свойств", exact=True).fill(
                    "Починка инструментов"
                )
                expect(
                    page.get_by_label("Починка инструментов", exact=True)
                ).to_be_visible()
                expect(
                    page.get_by_label("Починка оружия и доспехов", exact=True)
                ).to_be_visible()
                # Library pagination and narrow desktop windows.
                page.locator('.navigation [data-category="tiles"]').click()
                expect(
                    page.get_by_role("navigation", name="Страницы контента")
                ).to_be_visible()
                page.get_by_role("button", name="Далее →", exact=True).click()
                expect(
                    page.get_by_role("navigation", name="Страницы контента")
                ).to_contain_text("2 /")
                for width in (1024, 800):
                    page.set_viewport_size(dict(width=width, height=768))
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    ), width
                # Map editor: ten purpose sections, global search and independent floor.
                page.set_viewport_size(dict(width=1600, height=1000))
                page.locator('.navigation [data-category="maps"]').click()
                page.get_by_label("Поиск контента").fill("dev:crafting_lab")
                page.locator(".content-entry").click()
                palette = page.locator(".map-palette")
                sections = palette.get_by_label("Разделы палитры")
                names = [
                    "Пол",
                    "Стены",
                    "Разрушаемые тайлы",
                    "Двери",
                    "Ловушки",
                    "Мебель",
                    "Предметы",
                    "Особое",
                    "Существа",
                    "Служебные",
                ]
                expect(sections.get_by_role("button")).to_have_count(10)
                for name in names:
                    expect(
                        sections.get_by_role("button", name=name, exact=True)
                    ).to_be_visible()
                sections.get_by_role("button", name="Стены", exact=True).click()
                expect(
                    palette.locator('[data-ref="base:wall_massive"]')
                ).to_be_visible()
                expect(palette.locator('[data-ref="base:wall_damaged"]')).to_have_count(
                    0
                )
                sections.get_by_role(
                    "button", name="Разрушаемые тайлы", exact=True
                ).click()
                expect(
                    palette.locator('[data-ref="base:wall_damaged"]')
                ).to_be_visible()
                expect(palette.locator('[data-ref="base:wall_massive"]')).to_have_count(
                    0
                )
                sections.get_by_role("button", name="Мебель", exact=True).click()
                expect(palette.locator('[data-ref="base:bed"]')).to_be_visible()
                expect(
                    palette.locator('[data-ref="base:terrain_chest"]')
                ).to_be_visible()
                palette.locator('[data-ref="base:bed"]').click()
                canvas = page.locator("canvas")
                box = canvas.bounding_box()
                canvas.click(
                    position=dict(
                        x=16.5 * (box["width"] - 2) / lab["width"],
                        y=8.5 * (box["height"] - 2) / lab["height"],
                    )
                )
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                saved_map = page.request.get(
                    f"http://127.0.0.1:{port}/api/documents/maps/dev:crafting_lab"
                ).json()["document"]
                assert saved_map["tiles"][8][16] == "base:floor"
                assert any(
                    e["ref"] == "base:bed" and (e["x"], e["y"]) == (16, 8)
                    for e in saved_map["objects"]
                )
                palette.get_by_label("Поиск кистей").fill("base:dagger")
                expect(palette.locator(".palette-tile")).to_have_count(1)
                palette.locator(".palette-tile").click()
                expect(
                    sections.get_by_role("button", name="Предметы", exact=True)
                ).to_have_attribute("aria-pressed", "true")
                sections.get_by_role("button", name="Особое", exact=True).click()
                expect(palette.locator('[data-ref="base:portal"]')).to_be_visible()
                sections.get_by_role("button", name="Служебные", exact=True).click()
                expect(palette.get_by_label("Слой карты")).to_have_value("spawn")
                palette.get_by_label("Слой карты").select_option("lights")
                expect(palette).to_contain_text("Клик добавит свет")
                palette.get_by_label("Слой карты").select_option("roof")
                expect(
                    palette.get_by_role("button", name="Крыша", exact=True)
                ).to_be_visible()
                expect(palette).to_contain_text("сохраняя пол и объекты")
                page.get_by_title("Прямоугольник · R", exact=True).click()
                box = canvas.bounding_box()

                def roof_point(x, y):
                    return dict(
                        x=box["x"] + (x + 0.5) * (box["width"] - 2) / lab["width"],
                        y=box["y"] + (y + 0.5) * (box["height"] - 2) / lab["height"],
                    )

                page.mouse.move(**roof_point(15, 7))
                page.mouse.down()
                page.mouse.move(**roof_point(16, 8), steps=4)
                page.mouse.up()
                page.keyboard.press("KeyE")
                page.mouse.click(**roof_point(15, 7))
                # Undo and redo retain the mask without touching the furniture.
                page.keyboard.press("Control+z")
                page.keyboard.press("Control+Shift+z")
                page.locator(".document-heading").get_by_role(
                    "button", name="Сохранить", exact=True
                ).click()
                expect(page.locator(".unsaved")).to_have_count(0)
                covered = page.request.get(
                    f"http://127.0.0.1:{port}/api/documents/maps/dev:crafting_lab"
                ).json()["document"]
                assert not covered["roof"][7][15]
                assert (
                    covered["roof"][7][16]
                    and covered["roof"][8][15]
                    and covered["roof"][8][16]
                )
                assert covered["tiles"] == saved_map["tiles"]
                assert covered["objects"] == saved_map["objects"]
                assert covered["walkability"] == saved_map["walkability"]
                assert covered["blocks_sight"] == saved_map["blocks_sight"]
                page.screenshot(
                    path=str(Path(tempfile.gettempdir()) / "tuidungeon-roof-layer.png")
                )
                sections.get_by_role("button", name="Пол", exact=True).click()
                page.keyboard.press("KeyB")
                for width in (1024, 800):
                    page.set_viewport_size(dict(width=width, height=768))
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    ), width
                page.set_viewport_size(dict(width=1600, height=1000))
                page.screenshot(
                    path=str(
                        Path(tempfile.gettempdir())
                        / "tuidungeon-palette-categories.png"
                    )
                )
                assert not errors, errors
                browser.close()
                print(
                    "Studio UX OK: tag search by Russian name/key, grouped flags, save, derived-state exclusion; plant recovery timer edit/save/reload; corpse container loot edit/save; recipe sections, nested property search, material picker, save, add/remove, focus/Escape, global search, filters, spell levels, dynamic parameters, pagination, narrow windows; ten map palette sections, cross-section search, furniture over floor and roof paint/erase/undo/save; editor-only UI."
                )
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    run()
