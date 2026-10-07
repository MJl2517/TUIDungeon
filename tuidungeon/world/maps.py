"""Dungeon geometry, independent of characters and the terminal."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: int
    y: int


@dataclass(frozen=True)
class DungeonMap:
    rows: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.rows
            or not self.rows[0]
            or any(len(row) != len(self.rows[0]) for row in self.rows)
        ):
            raise ValueError("Карта должна быть непустым прямоугольником")
        if any(cell not in "#." for row in self.rows for cell in row):
            raise ValueError("Карта может содержать только стены и пол")

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def walkable(self, position: Position) -> bool:
        return (
            0 <= position.x < self.width
            and 0 <= position.y < self.height
            and self.rows[position.y][position.x] == "."
        )
