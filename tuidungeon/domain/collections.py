"""Versioned session collections; definitions use immutable containers instead."""


class TrackedList(list):
    def __init__(self, values=()):
        super().__init__(values)
        self.version = 0

    def touch(self):
        self.version += 1

    def append(self, value):
        super().append(value)
        self.touch()

    def extend(self, values):
        super().extend(values)
        self.touch()

    def insert(self, index, value):
        super().insert(index, value)
        self.touch()

    def pop(self, index=-1):
        value = super().pop(index)
        self.touch()
        return value

    def remove(self, value):
        super().remove(value)
        self.touch()

    def clear(self):
        super().clear()
        self.touch()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self.touch()

    def __delitem__(self, index):
        super().__delitem__(index)
        self.touch()

    def __iadd__(self, values):
        self.extend(values)
        return self

    def __imul__(self, count):
        super().__imul__(count)
        self.touch()
        return self

    def reverse(self):
        super().reverse()
        self.touch()

    def sort(self, *args, **kwargs):
        super().sort(*args, **kwargs)
        self.touch()


class EventLog(list):
    """Bounded UI history, not a persistence/replay format."""

    def __init__(self, limit=1000):
        super().__init__()
        self.limit = limit

    def append(self, event):
        super().append(event)
        if len(self) > self.limit:
            del self[: len(self) - self.limit]
