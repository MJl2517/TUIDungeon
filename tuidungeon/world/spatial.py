"""Cell buckets rebuilt only after membership/placement changes."""


class CellIndex:
    def __init__(self, coordinates):
        self.coordinates = coordinates
        self._key = None

    def synchronize(self, entries):
        key = (id(entries), entries.version)
        if key == self._key:
            return self
        self.buckets = {}
        self.lights = []
        self.instances = {}
        for entry in entries:
            self.buckets.setdefault(self.coordinates(entry), []).append(entry)
            if isinstance(entry, tuple):
                self.instances[entry[1].instance_id] = entry
                if entry[1].definition.light:
                    self.lights.append(entry)
        self._key = key
        return self

    def at(self, x, y):
        return tuple(self.buckets.get((x, y), ()))

    def region(self, x, y, width, height):
        if len(self.buckets) < width * height:
            for (cx, cy), entries in self.buckets.items():
                if x <= cx < x + width and y <= cy < y + height:
                    yield from entries
            return
        for cy in range(y, y + height):
            for cx in range(x, x + width):
                yield from self.buckets.get((cx, cy), ())
