"""Map-local signals shared by both clients and stored with the game."""

from ..content.placements import activation_targets
from ..world.maps import Position
from ..world.objects import ObjectState


class MechanismCommands:
    def sync_mechanisms(self):
        for state in self.levels.values():
            level = state.level
            if getattr(level, "_mechanisms_definition", None) is not level.definition:
                targets = activation_targets(level.store.documents, level.definition)
                sources = []
                for p in level.definition.objects:
                    definition = level.store.resolve("objects", p)
                    if not definition.mechanism:
                        continue
                    spec = definition.mechanism
                    linked = set(definition.mechanism_targets)
                    if spec.code:
                        linked.update(
                            i
                            for i, (_, t) in targets.items()
                            if t.activation_code == spec.code
                        )
                    sources.append((p, spec, linked & targets.keys()))
                level._mechanism_plan = targets, sources
                level._mechanisms_definition = level.definition
            targets, sources = level._mechanism_plan
            signals = {}
            for p, spec, linked in sources:
                source = level.object_states.setdefault(p.id, ObjectState())
                before = source.mechanism_on
                if spec.trigger == "pressure_plate":
                    source.mechanism_on = (
                        state is self.state and state.position == Position(p.x, p.y)
                    )
                    if source.mechanism_on and before is not True:
                        self.quest_event("activate_mechanism", target_id=p.id)
                elif source.mechanism_on is None:
                    source.mechanism_on = spec.initially_on
                for identifier in linked:
                    signals[identifier] = (
                        signals.get(identifier, False) or source.mechanism_on
                    )
            for identifier in targets:
                previous = level.object_states.get(identifier)
                if previous and previous.activation_on is not None:
                    signals.setdefault(identifier, False)
            for identifier, enabled in signals.items():
                layer, p = targets[identifier]
                receiver = level.object_states.get(identifier)
                if receiver is None:
                    definition = (
                        level.store.resolve("objects", p)
                        if layer == "objects"
                        else None
                    )
                    receiver = level.object_states[identifier] = ObjectState(
                        hp=definition.destruction.max_hp
                        if definition and definition.destruction
                        else None
                    )
                if receiver.activation_on == enabled:
                    continue
                if layer == "doors":
                    instance = next(
                        (d for d in level.doors if d.placement.id == identifier), None
                    )
                    if instance is None:
                        continue
                    door = instance.door
                    if door.destroyed or door.bent:
                        receiver.activation_on = enabled
                        continue
                    if (
                        door.access == "unique_key"
                        or door.travel
                        or not door.openable
                        or door.material == "stone"
                        or instance.brace
                    ):
                        continue
                    if not enabled and self._mechanism_cell_occupied(state, p):
                        continue  # Retry when the obstructing creature/item moves.
                    door.opened = enabled
                    if enabled:
                        door.locked = False
                elif layer == "traps":
                    trap = next(
                        (t for t in level.traps if t.placement.id == identifier), None
                    )
                    if trap:
                        trap.disabled = not enabled
                elif layer == "objects":
                    definition = level.store.resolve("objects", p)
                    if (
                        definition.illusion
                        and not enabled
                        and self._mechanism_cell_occupied(state, p)
                    ):
                        continue
                receiver.activation_on = enabled

    def _mechanism_cell_occupied(self, state, placement):
        p = Position(placement.x, placement.y)
        return (
            (state is self.state and state.position == p)
            or state.item_index.at(p.x, p.y)
            or state.level.index("npcs").at(p.x, p.y)
            or any(m.monster.hp > 0 for m in state.actor_index.at(p.x, p.y))
        )

    def toggle_mechanism(self, identifier):
        target = self.world_object(identifier)
        if (
            not self._world_ready(target)
            or self.active_craft
            or self.lockpick_attempt
            or not target.definition.mechanism
            or target.definition.mechanism.trigger != "lever"
        ):
            return self._craft_result(False, "Механизм недоступен.")
        spec = target.definition.mechanism
        current = target.state.mechanism_on
        target.state.mechanism_on = not (
            spec.initially_on if current is None else current
        )
        self.sync_mechanisms()
        self.quest_event("activate_mechanism", target_id=identifier)
        self._advance(1)
        return self._craft_result(
            True,
            "Рычаг включён." if target.state.mechanism_on else "Рычаг выключен.",
            1,
        )
