"""Physical item dimensions, independent of weight and equipment category."""

from typing import Literal

ItemSize = Literal["small", "medium", "large"]
ITEM_SIZES = ("small", "medium", "large")
SIZE_LABELS = {"small": "Маленький", "medium": "Средний", "large": "Большой"}
SIZE_RANK = {size: rank for rank, size in enumerate(ITEM_SIZES)}


def fits_size(size: ItemSize, maximum: ItemSize) -> bool:
    return SIZE_RANK[size] <= SIZE_RANK[maximum]


def largest_size(sizes) -> ItemSize:
    return max(sizes, key=SIZE_RANK.__getitem__, default="small")
