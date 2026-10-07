"""Compatibility imports; new code uses tuidungeon.application.engine."""

from .application.engine import Action, ActionResult, Engine, test_dungeon

__all__ = ["Action", "ActionResult", "Engine", "test_dungeon"]
