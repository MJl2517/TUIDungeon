"""Deterministic light and line of sight, independent of either frontend."""

from dataclasses import dataclass
from math import ceil, inf
from functools import lru_cache
from ..content.schemas import Cell
from ..domain.value_types import freeze

from .maps import Position

DIM_LIGHT_HINT = (
    "Тусклый свет даёт −5 к пассивным и активным проверкам внимательности и анализа."
)


def line_of_sight(start: Position, target: Position, blocks) -> bool:
    """An opaque target is visible, but walls behind it and closed corners are not."""
    if blocks[target.y][target.x] and start != target:
        return wall_face_visible(start, target, blocks)
    x, y = start.x, start.y
    dx, dy = abs(target.x - x), abs(target.y - y)
    sx, sy = (1 if x < target.x else -1), (1 if y < target.y else -1)
    error = dx - dy
    while (x, y) != (target.x, target.y):
        twice = 2 * error
        nx, ny = x, y
        if twice > -dy:
            error -= dy
            nx += sx
        if twice < dx:
            error += dx
            ny += sy
        if nx != x and ny != y and (blocks[y][nx] or blocks[ny][x]):
            return False
        x, y = nx, ny
        if (x, y) != (target.x, target.y) and blocks[y][x]:
            return False
    return True


def wall_face_visible(start: Position, target: Position, blocks) -> bool:
    """Trace to the facing surface, not a center buried inside a solid wall.

    At shallow angles a center-to-center ray enters the neighboring wall first.
    A ray to the near face/corner correctly exposes the entire first wall face.
    Grid traversal still stops at intervening walls and closed diagonal gaps.
    """
    center_x, center_y = target.x + 0.5, target.y + 0.5
    # Stop immediately outside the face. Looking just inside a corner would
    # hit an adjacent cell of the same wall before reaching the target tile.
    offset = 0.5 + 1e-6
    near_x = center_x + (
        offset if start.x > target.x else -offset if start.x < target.x else 0
    )
    near_y = center_y + (
        offset if start.y > target.y else -offset if start.y < target.y else 0
    )

    def trace(end_x, end_y):
        x, y = start.x, start.y
        sx, sy = x + 0.5, y + 0.5
        dx, dy = end_x - sx, end_y - sy
        step_x = 1 if dx > 0 else -1
        step_y = 1 if dy > 0 else -1
        delta_x = abs(1 / dx) if dx else inf
        delta_y = abs(1 / dy) if dy else inf
        next_x = ((x + 1 if dx > 0 else x) - sx) / dx if dx else inf
        next_y = ((y + 1 if dy > 0 else y) - sy) / dy if dy else inf
        while True:
            if min(next_x, next_y) > 1:
                return True
            nx, ny = x, y
            if abs(next_x - next_y) < 1e-12:
                nx, ny = x + step_x, y + step_y
                if (nx, ny) != (target.x, target.y) and (
                    blocks[y][nx] or blocks[ny][x]
                ):
                    return False
                next_x += delta_x
                next_y += delta_y
            elif next_x < next_y:
                nx += step_x
                next_x += delta_x
            else:
                ny += step_y
                next_y += delta_y
            x, y = nx, ny
            if (x, y) == (target.x, target.y):
                return True
            if (x, y) != (target.x, target.y) and blocks[y][x]:
                return False

    return any(
        trace(x, y)
        for x, y in ((near_x, near_y), (near_x, center_y), (center_x, near_y))
    )


@dataclass(frozen=True)
class LightField:
    # 0: unseen; 1: dim; 2: bright. No unexplored contents leak through a frontend.
    cells: list[list[int]]
    illumination: list[list[int]] | None = None

    def __post_init__(self):
        object.__setattr__(self, "cells", freeze(self.cells))
        object.__setattr__(self, "illumination", freeze(self.illumination))

    def at(self, position: Position) -> int:
        if 0 <= position.y < len(self.cells) and 0 <= position.x < len(self.cells[0]):
            return self.cells[position.y][position.x]
        return 0

    def level_at(self, position: Position) -> int:
        """Physical illumination, separate from visibility and navigation cues."""
        grid = self.illumination if self.illumination is not None else self.cells
        if 0 <= position.y < len(grid) and 0 <= position.x < len(grid[0]):
            return grid[position.y][position.x]
        return 0

    def inspection(self, position: Position) -> list[str]:
        strength = self.level_at(position)
        lines = [
            "Освещение: " + ("полная тьма", "тусклый свет", "яркий свет")[strength]
        ]
        if strength == 1:
            lines.append(DIM_LIGHT_HINT)
        return lines

    @classmethod
    def calculate(cls, state, *, sources=None, illumination=None, magic_sources=()):
        level = state.level
        ambient = level.definition.ambient_light if level else "dark"
        blocks = (
            level.terrain.blocks_sight
            if level
            else [[c == "#" for c in row] for row in state.dungeon.rows]
        )
        width, height = state.dungeon.width, state.dungeon.height
        no_occluders = (
            level.terrain.no_occluders if level else not any(any(r) for r in blocks)
        )
        value = {"dark": 0, "dim": 1, "bright": 2}[ambient]
        cells = (
            [list(row) for row in illumination]
            if illumination is not None
            else [[value] * width for _ in range(height)]
        )

        def illuminate(position, radius, bright_radius):
            reach = ceil(radius)
            for y in range(
                max(0, position.y - reach), min(height, position.y + reach + 1)
            ):
                for x in range(
                    max(0, position.x - reach), min(width, position.x + reach + 1)
                ):
                    distance = (x - position.x) ** 2 + (y - position.y) ** 2
                    if distance <= radius**2 and (
                        no_occluders or line_of_sight(position, Position(x, y), blocks)
                    ):
                        cells[y][x] = max(
                            cells[y][x],
                            2
                            if bright_radius > 0 and distance <= bright_radius**2
                            else 1,
                        )

        if illumination is None and level and value < 2:
            for instance in level.doors:
                if instance.door.burning:
                    illuminate(
                        Position(instance.placement.x, instance.placement.y), 4, 2
                    )
            for position, source in level.static_lights:
                illuminate(position, source.radius, source.bright_radius)
            for source in level.definition.lights:
                if source.enabled:
                    illuminate(
                        Position(source.x, source.y),
                        source.radius,
                        source.bright_radius,
                    )
        sources = sources if sources is not None else state.light_sources()
        for position, item in sources:
            if illumination is None and value < 2 and item.shining:
                illuminate(
                    position,
                    item.definition.light.radius,
                    item.definition.light.bright_radius,
                )
        if illumination is None:
            for position, radius, bright_radius in magic_sources:
                illuminate(position, radius, bright_radius)
        illumination = illumination if illumination is not None else freeze(cells)
        # These are navigation cues, not physical light. Inspection of a dark
        # adjacent cell (or the hero's own cell) must still report darkness.
        for dx, dy in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)):
            x, y = state.position.x + dx, state.position.y + dy
            if 0 <= x < width and 0 <= y < height:
                cells[y][x] = max(1, cells[y][x])
        for y, row in enumerate(cells):
            for x, strength in enumerate(row):
                if (
                    strength
                    and not no_occluders
                    and not line_of_sight(state.position, Position(x, y), blocks)
                ):
                    cells[y][x] = 0
        cells[state.position.y][state.position.x] = 2
        return cls(cells, illumination)

    def shade(self, cells, origin=(0, 0)):
        x0, y0 = origin
        return tuple(
            tuple(
                shaded_cell(cell, self.cells[y0 + y][x0 + x])
                for x, cell in enumerate(row)
            )
            for y, row in enumerate(cells)
        )


DARK_CELL = Cell(char=" ", foreground=0, background=0)


@lru_cache(maxsize=4096)
def shaded_cell(cell, strength):
    if not strength:
        return DARK_CELL
    if strength == 1 and cell:
        return Cell(
            char=cell.char, foreground=8, background=dim_background(cell.background)
        )
    return cell


def dim_background(color: int | None) -> int | None:
    """Keep background-painted art visible using a darker xterm palette color."""
    if color is None or color == 0:
        return color
    if color == 8:
        return 8  # Dark gray must not become black for background-painted walls.
    if color < 16:
        return color - 8 if color >= 8 else color
    if color >= 232:
        return 232 + (color - 232) // 2
    cube = color - 16
    red, green, blue = cube // 36, cube // 6 % 6, cube % 6
    # Retain at least one color step for nonblack backgrounds.
    return (
        16
        + max(0, (red + 1) // 2) * 36
        + max(0, (green + 1) // 2) * 6
        + max(0, (blue + 1) // 2)
    )
