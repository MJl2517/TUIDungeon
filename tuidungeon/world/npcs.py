"""Peaceful stationary people and their session-owned belongings."""

from dataclasses import dataclass, field
from ..content.schemas import NpcDocument, Placement
from ..domain.definitions import ChallengeChoice


@dataclass
class NpcInstance:
    placement: Placement
    definition: NpcDocument
    items: list = field(default_factory=list)
    topics: dict = field(default_factory=dict)
    bargain: dict | None = None

    @property
    def text(self):
        return self.definition.greeting

    def available_choices(self, hero):
        return (ChallengeChoice("talk", "Поговорить", minutes=0),)
