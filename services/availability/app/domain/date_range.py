import datetime as dt
from dataclasses import dataclass

from .errors import InvalidDateRange

MAX_NIGHTS = 30


@dataclass(frozen=True)
class DateRange:
    check_in: dt.date
    check_out: dt.date
    max_nights: int = MAX_NIGHTS

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise InvalidDateRange("check_out debe ser posterior a check_in")
        if (self.check_out - self.check_in).days > self.max_nights:
            raise InvalidDateRange(f"rango excede {self.max_nights} noches")

    @property
    def nights(self) -> list[dt.date]:
        n = (self.check_out - self.check_in).days
        return [self.check_in + dt.timedelta(days=i) for i in range(n)]
