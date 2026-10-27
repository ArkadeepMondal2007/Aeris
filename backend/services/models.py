"""Plain data containers shared by the services."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class Forecast:
    start: datetime  # delivery interval start (UTC)
    published: datetime  # when this forecast became available (UTC)
    mw: float


@dataclass(frozen=True)
class Actual:
    start: datetime
    mw: float
    published: Optional[datetime] = None


@dataclass(frozen=True)
class Observation:
    """One delivery interval. None means "not available", never zero."""

    start: datetime
    delivery_date: date  # Europe/London calendar date of the interval
    local_hour: int
    published: Optional[datetime]
    forecast: Optional[float]
    actual: Optional[float]

    @property
    def error(self) -> Optional[float]:
        """forecast - actual. Positive means generation was overestimated."""
        if self.forecast is None or self.actual is None:
            return None
        return self.forecast - self.actual


@dataclass(frozen=True)
class Analysis:
    observations: list
    data_quality: dict
    computed_at: datetime
