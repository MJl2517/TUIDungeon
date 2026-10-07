"""One-cell glyph palettes and reusable text art, without terminal dependencies."""

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata


def single_cell(character: str) -> bool:
    return (
        len(character) == 1
        and character.isprintable()
        and unicodedata.category(character)[0] not in {"C", "M"}
        and unicodedata.east_asian_width(character) not in {"W", "F"}
    )


@dataclass(frozen=True)
class GlyphTheme:
    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    wall: str
    floor: str
    hero: str = "@"
    monster: str = "M"

    def __post_init__(self):
        if any(
            not single_cell(getattr(self, field)) for field in self.__dataclass_fields__
        ):
            raise ValueError("Символы темы должны занимать одну клетку терминала")

    @classmethod
    def named(cls, name: str) -> "GlyphTheme":
        if name == "ascii":
            return cls("+", "+", "+", "+", "-", "|", "#", ".")
        if name == "unicode":
            return cls("┌", "┐", "└", "┘", "─", "│", "█", "·")
        raise ValueError(f"Неизвестный набор символов: {name}")


@dataclass(frozen=True)
class TextArt:
    lines: tuple[str, ...]

    def __post_init__(self):
        if not self.lines or any(
            not single_cell(character) for row in self.lines for character in row
        ):
            raise ValueError("Арт должен содержать печатные одноклеточные символы")

    @property
    def width(self) -> int:
        return max(map(len, self.lines), default=0)

    @property
    def height(self) -> int:
        return len(self.lines)

    def fit(self, width: int, height: int) -> tuple[str, ...]:
        return tuple(row[: max(0, width)] for row in self.lines[: max(0, height)])


class ArtLibrary:
    def __init__(self, root: Path | str | None = None):
        self.root = (
            Path(root)
            if root is not None
            else Path(__file__).resolve().parents[1] / "assets" / "art"
        )

    def load(self, art_id: str, style: str = "ascii") -> TextArt:
        if re.fullmatch(r"[a-z][a-z0-9_]*", art_id) is None or style not in {
            "ascii",
            "unicode",
        }:
            raise ValueError("Некорректный id арта или стиль")
        path = self.root / f"{art_id}.{style}.txt"
        if style == "unicode" and not path.is_file():
            path = self.root / f"{art_id}.ascii.txt"
        return TextArt(tuple(path.read_text(encoding="utf-8").splitlines()))
