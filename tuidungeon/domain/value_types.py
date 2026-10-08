"""JSON-compatible immutable containers used at the content boundary."""


def _immutable(*args, **kwargs):
    raise TypeError("Определение контента неизменяемо; создайте новый документ")


class FrozenList(list):
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = (
        _immutable
    )
    reverse = sort = __iadd__ = __imul__ = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


class FrozenDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = (
        __ior__
    ) = _immutable

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


def freeze(value):
    if isinstance(value, (FrozenList, FrozenDict)):
        return value
    if isinstance(value, list):
        return FrozenList(freeze(v) for v in value)
    if isinstance(value, dict):
        return FrozenDict((k, freeze(v)) for k, v in value.items())
    return value
