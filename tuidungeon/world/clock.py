"""Adventure calendar and time of day."""

from dataclasses import dataclass


@dataclass
class GameClock:
    elapsed_minutes: int = 8 * 60

    @property
    def day(self) -> int:
        return self.elapsed_minutes // (24 * 60) + 1

    @property
    def hour(self) -> int:
        return self.elapsed_minutes // 60 % 24

    @property
    def minute(self) -> int:
        return self.elapsed_minutes % 60

    @property
    def time_of_day(self) -> str:
        if 6 <= self.hour < 12:
            return "Утро"
        if 12 <= self.hour < 18:
            return "День"
        if 18 <= self.hour < 22:
            return "Вечер"
        return "Ночь"

    def advance(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("Время не может идти назад")
        self.elapsed_minutes += minutes
