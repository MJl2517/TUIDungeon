"""SDL game window using the same controller and cell renderer as the TUI."""

import json
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import time

import tcod.console
import tcod.context
import tcod.event
import tcod.render
import tcod.sdl.render
import tcod.tileset

from .tui import (
    Controller,
    View,
    Layout,
    Rect,
    background_view,
    popup_layout,
    handle_click,
    map_symbols,
    map_status,
    MIN_WIDTH,
    MIN_HEIGHT,
    render,
    draw_colors,
    draw_emphasis,
)

from ..world.maps import Position
from .tilesets import (
    load_symbol_tileset,
    load_map_style,
    save_map_style,
)

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
TILE_SIZE = (12, 24)
FOREGROUND = (200, 204, 212)
BACKGROUND = (17, 21, 27)
# Match the Studio palette, including the standard 216-color cube and grays.
PALETTE = (
    [
        tuple(bytes.fromhex(value))
        for value in (
            "11151b",
            "b74445",
            "70a76a",
            "c5a15c",
            "658fcb",
            "ad77c1",
            "66b4b4",
            "c8ccd4",
            "647180",
            "f07178",
            "9bce81",
            "edc875",
            "91b8ed",
            "d6a0ec",
            "94dddd",
            "f5f1e6",
        )
    ]
    + list(product((0, 95, 135, 175, 215, 255), repeat=3))
    + [(value, value, value) for value in range(8, 239, 10)]
)
STYLE = SimpleNamespace(
    A_DIM=1 << 18, A_BOLD=1 << 19, A_REVERSE=1 << 20, error=ValueError
)
COLOR = 1 << 21


def load_tileset():
    manifest = json.loads((FONT_DIR / "glyphs.json").read_text(encoding="utf-8"))
    return tcod.tileset.load_tilesheet(
        FONT_DIR / "glyphs.png",
        manifest["columns"],
        manifest["rows"],
        manifest["codepoints"],
    )


class CellScreen:
    """Adapt the existing curses-shaped drawing calls to RGB cells."""

    curses = STYLE

    def __init__(self, console):
        self.console = console

    @staticmethod
    def attribute(foreground, background):
        return COLOR | foreground | ((256 if background is None else background) << 8)

    def addnstr(self, y, x, text, limit, attribute=0):
        self.addstr(y, x, text[:limit], attribute)

    def addstr(self, y, x, text, attribute=0):
        if not (0 <= y < self.console.height and 0 <= x < self.console.width):
            return
        text = text[: self.console.width - x]
        cells = self.console.rgb[y, x : x + len(text)]
        foreground, background = FOREGROUND, BACKGROUND
        if attribute & COLOR:
            foreground = PALETTE[attribute & 255]
            color = (attribute >> 8) & 511
            background = BACKGROUND if color == 256 else PALETTE[color]
        if attribute & STYLE.A_DIM:
            foreground = tuple(value // 2 for value in foreground)
            background = tuple(value // 2 for value in background)
        if attribute & STYLE.A_BOLD:
            foreground = (245, 241, 230)
        if attribute & STYLE.A_REVERSE:
            foreground, background = background, foreground
        cells["ch"] = [ord(char) for char in text]
        cells["fg"], cells["bg"] = foreground, background


def draw(console, controller):
    console.clear(fg=FOREGROUND, bg=BACKGROUND)
    screen = CellScreen(console)
    width, height = console.width, console.height
    rows = render(controller, width, height)
    for y, line in enumerate(rows):
        screen.addnstr(y, 0, line, width)
    draw_colors(screen, controller, width, height, screen)
    draw_emphasis(screen, controller, width, height, rows, STYLE, screen)


def map_area(width, height):
    rect = Layout.for_size(width, height).main
    return Rect(rect.x + 1, rect.y + 1, rect.width - 2, rect.height - 3)


def render_map(controller, width, height, tile_size, *, sprites=None):
    view = background_view(controller)
    if (
        not controller.engine
        or view
        not in (
            View.EXPLORE,
            View.LOOK,
            View.THROW,
            View.IGNITE,
            View.SPELL_TARGET,
            View.HAND_TARGET,
        )
        or width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):
        return None
    area = map_area(width, height)
    columns = max(1, area.width * TILE_SIZE[0] // tile_size)
    rows = max(1, area.height * TILE_SIZE[1] // tile_size)
    state = controller.engine.state
    focus = (
        controller.look_position
        if view
        in (View.LOOK, View.THROW, View.IGNITE, View.SPELL_TARGET, View.HAND_TARGET)
        else state.position
    )
    # Keep the focus centered even at world edges; off-map cells stay empty.
    if view is View.LOOK and controller.look_camera is not None:
        cx, cy = controller.look_camera.x, controller.look_camera.y
    else:
        cx, cy = focus.x - columns // 2, focus.y - rows // 2
    x0, y0 = max(0, cx), max(0, cy)
    x1, y1 = (
        min(state.dungeon.width, cx + columns),
        min(state.dungeon.height, cy + rows),
    )
    console = tcod.console.Console(columns, rows)
    console.clear(fg=FOREGROUND, bg=BACKGROUND)
    screen = CellScreen(console)
    if x1 > x0 and y1 > y0:
        cells = controller.engine.render_cells((x0, y0, x1 - x0, y1 - y0))
        light = controller.engine.lighting
        for y, row in enumerate(cells):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                char = map_symbols(controller, cell.char)
                if sprites:
                    visual_ref = getattr(cell, "visual_ref", None)
                    char = sprites.get(
                        getattr(cell, "symbol", None) or visual_ref,
                        char if visual_ref else sprites.get(("glyph", cell.char), char),
                    )
                    if getattr(cell, "mirror_x", False):
                        char = sprites.get(
                            (getattr(cell, "symbol", None) or visual_ref, "mirror_x"),
                            char,
                        )
                attribute = screen.attribute(cell.foreground, cell.background)
                if light.cells[y0 + y][x0 + x] == 1 and not getattr(
                    cell, "service_indicator", False
                ):
                    attribute |= STYLE.A_DIM
                if view in (
                    View.LOOK,
                    View.THROW,
                    View.IGNITE,
                    View.SPELL_TARGET,
                    View.HAND_TARGET,
                ) and (
                    x0 + x,
                    y0 + y,
                ) == (
                    focus.x,
                    focus.y,
                ):
                    char = "X"
                    attribute |= STYLE.A_BOLD
                    if int(time.monotonic() * 2) % 2:
                        attribute |= STYLE.A_REVERSE
                screen.addstr(y0 + y - cy, x0 + x - cx, char, attribute)
    destination = Rect(
        area.x * TILE_SIZE[0] + (area.width * TILE_SIZE[0] - columns * tile_size) // 2,
        area.y * TILE_SIZE[1] + (area.height * TILE_SIZE[1] - rows * tile_size) // 2,
        columns * tile_size,
        rows * tile_size,
    )
    return console, destination, Position(cx, cy)


def map_zoom(tile_size, event):
    delta = 0
    if isinstance(event, tcod.event.MouseWheel):
        delta = event.y * (-1 if event.flipped else 1)
    elif isinstance(event, tcod.event.KeyDown):
        if event.sym in (
            tcod.event.KeySym.PLUS,
            tcod.event.KeySym.EQUALS,
            tcod.event.KeySym.KP_PLUS,
        ):
            delta = 1
        elif event.sym in (tcod.event.KeySym.MINUS, tcod.event.KeySym.KP_MINUS):
            delta = -1
    return max(16, min(96, tile_size + (16 if delta > 0 else -16 if delta < 0 else 0)))


def draw_map_hint(console, controller):
    """Replace the full hint row so shorter hints never leave old letters."""
    area = map_area(console.width, console.height)
    hint = map_status(controller)
    suffix = " | +/-: масштаб"
    text = hint[: max(0, area.width - len(suffix))] + suffix
    CellScreen(console).addnstr(
        area.y + area.height, area.x, text.ljust(area.width), area.width
    )


def present(
    renderer, ui_render, map_render, console, controller, map_size, *, sprites=None
):
    draw(console, controller)
    frame = render_map(
        controller, console.width, console.height, map_size, sprites=sprites
    )
    area = map_area(console.width, console.height)
    popup = popup_layout(controller, console.width, console.height)
    if frame and not popup:
        draw_map_hint(console, controller)
    ui_texture = ui_render.render(console)
    map_texture = map_render.render(frame[0]) if frame else None
    output_width, output_height = renderer.output_size
    x = (output_width - console.width * TILE_SIZE[0]) // 2
    y = (output_height - console.height * TILE_SIZE[1]) // 2
    renderer.draw_color = (*BACKGROUND, 255)
    renderer.clear()
    renderer.copy(
        ui_texture,
        dest=(x, y, console.width * TILE_SIZE[0], console.height * TILE_SIZE[1]),
    )
    if frame:
        renderer.fill_rect(
            (
                x + area.x * TILE_SIZE[0],
                y + area.y * TILE_SIZE[1],
                area.width * TILE_SIZE[0],
                area.height * TILE_SIZE[1],
            )
        )
        map_texture.scale_mode = tcod.sdl.render.ScaleMode.NEAREST
        rect = frame[1]
        renderer.copy(
            map_texture, dest=(x + rect.x, y + rect.y, rect.width, rect.height)
        )
        if popup:
            overlay = popup[1]
            source = (
                overlay.x * TILE_SIZE[0],
                overlay.y * TILE_SIZE[1],
                (overlay.width + 1) * TILE_SIZE[0],
                (overlay.height + 1) * TILE_SIZE[1],
            )
            renderer.copy(
                ui_texture,
                source=source,
                dest=(x + source[0], y + source[1], source[2], source[3]),
            )
    renderer.present()
    return frame


def handle_mouse(controller, event, frame, map_size, console, window_size, output_size):
    click = (
        isinstance(event, tcod.event.MouseButtonDown)
        and event.button == tcod.event.MouseButton.LEFT
    )
    if not click and not isinstance(event, tcod.event.MouseMotion):
        return False
    # SDL uses logical window pixels; the framebuffer may have a HiDPI scale and margins.
    px = (
        event.position.x * output_size[0] / window_size[0]
        - (output_size[0] - console.width * TILE_SIZE[0]) // 2
    )
    py = (
        event.position.y * output_size[1] / window_size[1]
        - (output_size[1] - console.height * TILE_SIZE[1]) // 2
    )
    if (
        frame
        and controller.view is View.LOOK
        and not popup_layout(controller, console.width, console.height)
    ):
        rect, origin = frame[1], frame[2]
        if rect.x <= px < rect.x + rect.width and rect.y <= py < rect.y + rect.height:
            position = Position(
                origin.x + int((px - rect.x) // map_size),
                origin.y + int((py - rect.y) // map_size),
            )
            if controller.can_target_cell(position):
                changed = position != controller.look_position
                controller.look_camera = origin
                controller.look_position = position
                if click:
                    controller.handle("enter")
                return click or changed
    if click:
        return handle_click(
            controller,
            int(px // TILE_SIZE[0]),
            int(py // TILE_SIZE[1]),
            console.width,
            console.height,
        )
    return False


def handle_event(controller, event):
    """Commands use physical keys; text entry uses SDL's Unicode input."""
    if isinstance(event, tcod.event.Quit):
        controller.running = False
        return True
    if isinstance(event, tcod.event.WindowEvent):
        if event.type == "WindowClose":
            controller.running = False
        return True
    if isinstance(event, tcod.event.TextInput):
        if controller.inventory.editing or (
            controller.view is View.CRAFT and controller.craft.editing
        ):
            for char in event.text:
                controller.handle(char)
            return True
        return False
    if not isinstance(event, tcod.event.KeyDown):
        return False
    if (
        event.sym in (tcod.event.KeySym.LALT, tcod.event.KeySym.RALT)
        or event.mod & tcod.event.Modifier.ALT
    ):
        return False
    if event.scancode == tcod.event.Scancode.C and event.mod & tcod.event.Modifier.CTRL:
        controller.handle("ctrl_c")
        return True
    names = {
        tcod.event.KeySym.UP: "up",
        tcod.event.KeySym.DOWN: "down",
        tcod.event.KeySym.LEFT: "left",
        tcod.event.KeySym.RIGHT: "right",
        tcod.event.KeySym.RETURN: "enter",
        tcod.event.KeySym.KP_ENTER: "enter",
        tcod.event.KeySym.ESCAPE: "escape",
        tcod.event.KeySym.BACKSPACE: "backspace",
        tcod.event.KeySym.TAB: "tab",
        tcod.event.KeySym.PAGEUP: "pageup",
        tcod.event.KeySym.PAGEDOWN: "pagedown",
        tcod.event.KeySym.HOME: "home",
        tcod.event.KeySym.END: "end",
        tcod.event.KeySym.F5: "f5",
        tcod.event.KeySym.F4: "f4",
    }
    key = names.get(event.sym, "")
    if not key and not (
        controller.inventory.editing
        or (controller.view is View.CRAFT and controller.craft.editing)
    ):
        if tcod.event.Scancode.A <= event.scancode <= tcod.event.Scancode.Z:
            key = chr(ord("a") + event.scancode - tcod.event.Scancode.A)
        elif 32 <= event.sym < 127:
            key = chr(event.sym)
    if key:
        if (
            controller.engine
            and controller.engine.active_craft
            and event.repeat
            and key in ("right", " ")
        ):
            return False
        controller.handle(key)
        return True
    return False


def run(
    seed=None,
    symbols="unicode",
    catalog=None,
    map_ref=None,
    store=None,
    test_map=False,
    save_path=None,
    test_profile=None,
    test_class=None,
):
    controller = Controller(
        seed,
        symbols=symbols,
        catalog=catalog,
        map_ref=map_ref,
        store=store,
        test_map=test_map,
        save_path=save_path,
        test_profile=test_profile,
        test_class=test_class,
    )
    controller.windowed = True
    controller.map_style = saved_style = load_map_style()
    tileset = load_tileset()
    with tcod.context.new(
        columns=100,
        rows=28,
        tileset=tileset,
        vsync=True,
        title="TUI Dungeon — F11: полный экран",
        argv=[],
    ) as context:
        window = context.sdl_window
        window.min_size = (MIN_WIDTH * TILE_SIZE[0], MIN_HEIGHT * TILE_SIZE[1])
        window.stop_text_input()
        renderer = context.sdl_renderer
        if renderer is None:
            raise RuntimeError("Для карты нужен SDL-рендерер")
        atlas = tcod.render.SDLTilesetAtlas(renderer, tileset)
        ui_render = tcod.render.SDLConsoleRender(atlas)
        map_render = tcod.render.SDLConsoleRender(atlas)
        kenney_render, map_sprites = None, None
        map_size = 32
        frame = None
        editing = False
        dirty, last_blink = True, None
        while controller.running:
            blink = int(time.monotonic() * 2) % 2
            if dirty or (
                controller.view
                in (
                    View.LOOK,
                    View.THROW,
                    View.IGNITE,
                    View.SPELL_TARGET,
                    View.HAND_TARGET,
                )
                and blink != last_blink
            ):
                if (
                    controller.map_style in ("symbols", "kenney_1bit")
                    and kenney_render is None
                ):
                    try:
                        from ..content.packs import PackStore

                        documents = (controller.store or PackStore()).documents
                        map_tileset, map_sprites = load_symbol_tileset(
                            tileset, documents
                        )
                        kenney_atlas = tcod.render.SDLTilesetAtlas(
                            renderer, map_tileset
                        )
                        kenney_render = tcod.render.SDLConsoleRender(kenney_atlas)
                    except (OSError, ValueError, RuntimeError) as error:
                        controller.map_style = "text"
                        controller.message = f"Не удалось загрузить символы: {error}"
                if controller.map_style != saved_style:
                    try:
                        save_map_style(controller.map_style)
                    except OSError as error:
                        controller.message = f"Не удалось сохранить оформление: {error}"
                    saved_style = controller.map_style
                console = context.new_console(
                    min_columns=MIN_WIDTH, min_rows=MIN_HEIGHT
                )
                frame = present(
                    renderer,
                    ui_render,
                    kenney_render
                    if controller.map_style in ("symbols", "kenney_1bit")
                    else map_render,
                    console,
                    controller,
                    map_size,
                    sprites=map_sprites
                    if controller.map_style in ("symbols", "kenney_1bit")
                    else None,
                )
                dirty = False
            last_blink = blink
            for event in tcod.event.wait(0.1):
                if (
                    isinstance(event, tcod.event.KeyDown)
                    and event.sym == tcod.event.KeySym.F11
                ):
                    if not event.repeat:
                        window.fullscreen = not window.fullscreen
                        dirty = True
                    continue
                if isinstance(
                    event, (tcod.event.MouseMotion, tcod.event.MouseButtonDown)
                ):
                    dirty = (
                        handle_mouse(
                            controller,
                            event,
                            frame,
                            map_size,
                            console,
                            window.size,
                            renderer.output_size,
                        )
                        or dirty
                    )
                    continue
                if (
                    frame is not None
                    and not editing
                    and not popup_layout(controller, console.width, console.height)
                ):
                    new_size = map_zoom(map_size, event)
                    if new_size != map_size:
                        map_size, dirty = new_size, True
                        controller.look_camera = None
                        continue
                dirty = handle_event(controller, event) or dirty
                text_editing = controller.inventory.editing or (
                    controller.view is View.CRAFT and controller.craft.editing
                )
                if editing != text_editing:
                    editing = text_editing
                    if editing:
                        window.start_text_input()
                    else:
                        window.stop_text_input()
