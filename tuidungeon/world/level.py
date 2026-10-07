"""Session-owned placements; authored documents never contain runtime state."""

from dataclasses import dataclass, field
from uuid import uuid4
from ..domain.challenges import TextChallenge


@dataclass
class TrapInstance:
    placement: object
    definition: object
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    triggered: bool = False


@dataclass
class PointInstance:
    placement: object
    definition: object
    challenge: TextChallenge
    instance_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Level:
    ref: str
    definition: object
    store: object
    cells: list
    traps: list[TrapInstance] = field(default_factory=list)
    points: list[PointInstance] = field(default_factory=list)
    items: list = field(default_factory=list)

    def nearby(self, position):
        return [
            p
            for p in self.points
            if abs(position.x - p.placement.x) + abs(position.y - p.placement.y) <= 1
        ]

    def render_cells(self, state):
        from ..content.schemas import Cell

        cells = [list(row) for row in self.cells]

        def draw(definition, p):
            cells[p.y][p.x] = Cell(
                char=definition.glyph,
                foreground=definition.foreground,
                background=definition.background,
            )

        for trap in self.traps:
            if not trap.definition.hidden or trap.triggered:
                draw(trap.definition, trap.placement)
        for point in self.points:
            draw(point.definition, point.placement)
        for placement, item in self.items:
            draw(self.store.get("equipment", placement.ref), placement)
        for monster in state.monsters:
            if monster.monster.hp > 0:
                ref = getattr(monster.monster, "definition_ref", None)
                if ref:
                    draw(self.store.get("monsters", ref), monster.position)
        cells[state.position.y][state.position.x] = Cell(char="@", foreground=15)
        return cells
