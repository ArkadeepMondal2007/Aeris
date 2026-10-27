"""Configuration, read from environment variables or a local .env file."""
import os
from dataclasses import dataclass
from datetime import date, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    analysis_start: date = date(2026, 1, 1)
    analysis_end: date = date(2026, 1, 31)
    timezone_name: str = "Europe/London"
    cutoff_time: time = time(17, 0)
    cutoff_days_ahead: int = 1
    forecast_interval_minutes: int = 60
    forecast_lookback_days: int = 5
    request_timeout_seconds: float = 60.0
    cache_ttl_seconds: int = 3600
    cors_origins: tuple = ("http://localhost:5173",)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


def _read(name, default, cast=str):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw.strip())
    except ValueError as error:
        raise ValueError(f"Invalid value for {name}: {raw!r}") from error


def load_settings() -> Settings:
    load_dotenv()
    d = Settings()
    origins = _read("CORS_ORIGINS", "")
    settings = Settings(
        elexon_base_url=_read("ELEXON_BASE_URL", d.elexon_base_url).rstrip("/"),
        analysis_start=_read("ANALYSIS_START", d.analysis_start, date.fromisoformat),
        analysis_end=_read("ANALYSIS_END", d.analysis_end, date.fromisoformat),
        timezone_name=_read("TIMEZONE", d.timezone_name),
        cutoff_time=_read("DECISION_CUTOFF_TIME", d.cutoff_time, time.fromisoformat),
        cutoff_days_ahead=_read("DECISION_DAYS_AHEAD", d.cutoff_days_ahead, int),
        forecast_interval_minutes=_read("FORECAST_INTERVAL_MINUTES", d.forecast_interval_minutes, int),
        forecast_lookback_days=_read("FORECAST_LOOKBACK_DAYS", d.forecast_lookback_days, int),
        request_timeout_seconds=_read("REQUEST_TIMEOUT_SECONDS", d.request_timeout_seconds, float),
        cache_ttl_seconds=_read("CACHE_TTL_SECONDS", d.cache_ttl_seconds, int),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) or d.cors_origins,
    )
    if settings.analysis_start > settings.analysis_end:
        raise ValueError("ANALYSIS_START must not be after ANALYSIS_END")
    if settings.forecast_interval_minutes <= 0:
        raise ValueError("FORECAST_INTERVAL_MINUTES must be positive")
    settings.tz  # fails fast on an unknown timezone name
    return settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()
