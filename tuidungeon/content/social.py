"""Validate authored quest targets before a session can mutate anything."""

from .catalog import ContentError


def validate_social(documents):
    def target(map_ref, identifier, layers):
        doc = documents["maps", map_ref]
        if not any(p.id == identifier for layer in layers for p in getattr(doc, layer)):
            raise ContentError(f"{map_ref}: не найдена цель {identifier}")

    for (category, ref), doc in documents.items():
        if category == "quests":
            for stage in doc.stages:
                if stage.report_to:
                    target(stage.report_to.map_ref, stage.report_to.npc_id, ("npcs",))
                consumed = [o.item for o in stage.objectives if o.consume]
                if len(set(consumed)) != len(consumed):
                    raise ContentError(
                        f"{ref}: объедините передаваемые одинаковые предметы в одну цель"
                    )
                for o in stage.objectives:
                    if o.kind == "visit":
                        m = documents["maps", o.map_ref]
                        if o.x + o.width > m.width or o.y + o.height > m.height:
                            raise ContentError(
                                f"{ref}: область цели за пределами карты"
                            )
                    elif o.kind not in ("bring", "craft"):
                        layers = (
                            ("npcs",)
                            if o.kind == "talk"
                            else ("points_of_interest",)
                            if o.kind == "read"
                            else ("objects", "points_of_interest", "traps")
                        )
                        target(o.map_ref, o.target_id, layers)
        elif category == "npcs":
            for t in doc.topics:
                for c in t.conditions:
                    if c.stage and (
                        not c.quest
                        or c.stage
                        not in {s.id for s in documents["quests", c.quest].stages}
                    ):
                        raise ContentError(f"{ref}: неизвестный этап в условии вопроса")
