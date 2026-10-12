"""Session-owned timed magic, never written into authored item or map data."""

from dataclasses import dataclass, field
from uuid import uuid4
from .maps import Position


@dataclass
class MagicPlacement:
    kind: str
    turns: int
    map_ref: str | None = None
    position: Position | None = None
    item_id: str | None = None
    concentration: bool = False
    params: dict = field(default_factory=dict)
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    spell_id: str | None = None
    scroll_definition: str | None = None
