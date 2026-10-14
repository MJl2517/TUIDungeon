"""Nearby service graphics replace object art without changing its mechanics."""

from .maps import Position
from .graphics import glyph_cell
from ..content.symbols import appearance


def nearby_locks(state):
    level = state.level
    if not level:
        return []
    result = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            p = Position(state.position.x + dx, state.position.y + dy)
            for instance in level.index("doors").at(p.x, p.y):
                lock = instance.door
                if lock.locked and not lock.passable:
                    result.append((instance, lock))
            for container in level.index("containers").at(p.x, p.y):
                if container.locked:
                    result.append((container, container.lock))
    return result


def draw_lock_indicators(engine, cells, region, targets):
    x, y, width, height = region
    state, level = engine.state, engine.state.level
    for instance, lock in targets:
        p = instance.placement
        position = Position(p.x, p.y)
        if (
            not (x <= p.x < x + width and y <= p.y < y + height)
            or position == state.position
            or not engine._within_reach(p)
            or not engine.lighting.level_at(position)
            or any(m.monster.hp > 0 for m in state.actor_index.at(p.x, p.y))
        ):
            continue
        indicator = level.store.lock_indicator(
            lock.lock_complexity, level.ref.split(":")[0]
        )
        char, symbol = (
            appearance(level.store.documents, indicator[1])
            if indicator
            else ("l" if lock.lock_complexity == "simple" else "L", None)
        )
        lower = cells[p.y - y][p.x - x]
        background = lower.background if lower else None
        door = getattr(instance, "door", None)
        if door and door.burning:
            background = door.display_color()
        cells[p.y - y][p.x - x] = glyph_cell(
            char,
            lock.lock_color,
            background,
            "service/lock_" + lock.lock_complexity,
            symbol,
            True,
            mirror_x=indicator[1].mirror_x if indicator else False,
            rotation=indicator[1].rotation if indicator else 0,
        )
