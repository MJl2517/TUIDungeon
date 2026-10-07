"""Compatibility imports; new code uses tuidungeon.presentation.tui."""

from .presentation.tui import (
    Canvas,
    Controller,
    Layout,
    MIN_HEIGHT,
    MIN_WIDTH,
    Rect,
    View,
    render,
    run,
)

__all__ = [
    "Canvas",
    "Controller",
    "Layout",
    "MIN_HEIGHT",
    "MIN_WIDTH",
    "Rect",
    "View",
    "render",
    "run",
]
