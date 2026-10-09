"""Legacy Alt prefixes and Kitty press/release input, independent of game commands.

Protocol: https://sw.kovidgoyal.net/kitty/keyboard-protocol/
"""

from dataclasses import dataclass
import os
import re
import sys


@dataclass(frozen=True)
class KeyEvent:
    key: str = ""
    alt: bool | None = None


def decode_sequence(sequence):
    match = re.fullmatch(
        r"\x1b\[(\d+)(?::[\d:]+)?(?:;(\d+)(?::(\d+))?)?(?:;[\d:]+)?u", sequence
    )
    if match:
        code = int(match[1])
        modifiers = int(match[2] or 1) - 1
        release = match[3] == "3"
        alt = bool(modifiers & 2)
        if code in (57443, 57449):
            return KeyEvent(alt=not release or alt)
        if release:
            return KeyEvent(alt=alt)
        names = {
            27: "escape",
            13: "enter",
            9: "tab",
            127: "backspace",
            57352: "up",
            57353: "down",
            57350: "left",
            57351: "right",
            57354: "pageup",
            57355: "pagedown",
            57356: "home",
            57357: "end",
            57367: "f4",
            57368: "f5",
        }
        key = names.get(code, chr(code) if 32 <= code < 57344 else "")
        if code == 99 and modifiers & 4:
            key = "ctrl_c"
        return KeyEvent(key=key, alt=alt)
    # Kitty emits arrows using the legacy CSI form even in enhanced mode.
    match = re.fullmatch(r"\x1b\[(?:1)?(?:;(\d+)(?::(\d+))?)?([ABCD])", sequence)
    if match:
        alt = bool((int(match[1] or 1) - 1) & 2)
        return KeyEvent(
            ""
            if match[2] == "3"
            else {"A": "up", "B": "down", "C": "right", "D": "left"}[match[3]],
            alt,
        )
    match = re.fullmatch(r"\x1b\[(1|4|5|6|7|8|15)(?:;(\d+)(?::(\d+))?)?~", sequence)
    if match:
        alt = bool((int(match[2] or 1) - 1) & 2)
        return KeyEvent(
            ""
            if match[3] == "3"
            else {
                "1": "home",
                "4": "end",
                "5": "pageup",
                "6": "pagedown",
                "7": "home",
                "8": "end",
                "15": "f5",
            }[match[1]],
            alt,
        )
    return KeyEvent()


class TerminalKeyboard:
    def __init__(self, screen, curses):
        self.screen, self.curses = screen, curses
        # Native Windows uses PDCurses console input, not Kitty escape sequences.
        self.enhanced = sys.platform != "win32" and bool(
            os.environ.get("KITTY_WINDOW_ID")
            or os.environ.get("WEZTERM_PANE")
            or os.environ.get("TERM") == "xterm-kitty"
        )
        self.special = {
            curses.KEY_UP: "up",
            curses.KEY_DOWN: "down",
            curses.KEY_LEFT: "left",
            curses.KEY_RIGHT: "right",
            curses.KEY_BACKSPACE: "backspace",
            curses.KEY_ENTER: "enter",
            curses.KEY_PPAGE: "pageup",
            curses.KEY_NPAGE: "pagedown",
        }
        for name, key in (
            ("KEY_HOME", "home"),
            ("KEY_END", "end"),
            ("KEY_F4", "f4"),
            ("KEY_F5", "f5"),
        ):
            code = getattr(curses, name, None)
            if code is not None:
                self.special[code] = key
        if sys.platform == "win32":
            # PDCurses ALT_0..ALT_9; CPython may not export these constants.
            # https://github.com/wmcbrine/PDCurses/blob/master/curses.h
            self.special.update(
                {
                    getattr(curses, f"ALT_{digit}", 0x197 + digit): f"alt+{digit}"
                    for digit in range(10)
                }
            )

    def __enter__(self):
        self.screen.timeout(100)
        if hasattr(self.curses, "set_escdelay"):
            self.curses.set_escdelay(30)
        if self.enhanced:
            sys.stdout.write("\x1b[>11u")
            sys.stdout.flush()
        return self

    def __exit__(self, *args):
        if self.enhanced:
            sys.stdout.write("\x1b[<u")
            sys.stdout.flush()
        self.screen.timeout(-1)

    def normalize(self, key):
        if isinstance(key, int):
            return self.special.get(key, "")
        return {
            "\x03": "ctrl_c",
            "\x08": "backspace",
            "\x7f": "backspace",
            "\t": "tab",
            "\n": "enter",
            "\r": "enter",
            "\x1b": "escape",
        }.get(key, key.lower())

    def read(self):
        try:
            key = self.screen.get_wch()
        except self.curses.error:
            return KeyEvent()
        if key == self.curses.KEY_RESIZE:
            return KeyEvent("resize")
        if key != "\x1b":
            return KeyEvent(self.normalize(key))
        self.screen.timeout(30)
        try:
            try:
                following = self.screen.get_wch()
            except self.curses.error:
                return KeyEvent("escape")
            if following == "[":
                sequence = "\x1b["
                for _ in range(64):
                    try:
                        part = self.screen.get_wch()
                    except self.curses.error:
                        return KeyEvent()
                    if not isinstance(part, str):
                        return KeyEvent()
                    sequence += part
                    if "@" <= part <= "~":
                        return decode_sequence(sequence)
                return KeyEvent()
            return KeyEvent("alt+" + self.normalize(following))
        finally:
            self.screen.timeout(100)
