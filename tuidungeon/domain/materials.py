"""Shared material traits; tags describe the target, not its ignition tool."""

FLAMMABLE = "flammable"
WOODEN = "wooden"
MATERIAL_TAGS = frozenset({FLAMMABLE, WOODEN})
TAG_LABELS = {FLAMMABLE: "Горючий", WOODEN: "Деревянный", "storage": "Контейнер"}
TAGS_DESCRIPTION = (
    "flammable — горючий; wooden — деревянный или с деревянными частями. "
    "Это независимые свойства. Тег «поджог» обозначает инструмент, которым поджигают. "
    "storage — контейнер с отдельным содержимым."
)


def material_details(tags):
    return [
        *(["Материал: дерево / деревянные части."] if WOODEN in tags else []),
        *(["Горючесть: горючий."] if FLAMMABLE in tags else []),
    ]


def material_search_terms(tags):
    return tuple(label for tag, label in TAG_LABELS.items() if tag in tags)
