"""Fetches Elexon data once and shares the analysis between all endpoints."""
import asyncio
import time
from datetime import timedelta
from typing import Optional

import httpx

from services.analytics import decision_cutoff_utc, run_analysis
from services.elexon import ElexonError, fetch_wind_actuals, fetch_wind_forecasts
from services.models import Analysis
from settings import Settings


class AnalysisStore:
    def __init__(self, settings: Settings, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._settings = settings
        self._transport = transport
        self._analysis = None
        self._loaded_at = 0.0
        self._lock = None

    async def get(self) -> Analysis:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            fresh = time.monotonic() - self._loaded_at < self._settings.cache_ttl_seconds
            if self._analysis is None or not fresh:
                self._analysis = await self._build()
                self._loaded_at = time.monotonic()
            return self._analysis

    async def _build(self) -> Analysis:
        s = self._settings
        first_cutoff = decision_cutoff_utc(s.analysis_start, s.cutoff_time, s.cutoff_days_ahead, s.tz)
        last_cutoff = decision_cutoff_utc(s.analysis_end, s.cutoff_time, s.cutoff_days_ahead, s.tz)
        published_from = first_cutoff - timedelta(days=s.forecast_lookback_days)

        async with httpx.AsyncClient(
            base_url=s.elexon_base_url, timeout=s.request_timeout_seconds, transport=self._transport
        ) as client:
            (actuals, bad_actuals), (forecasts, bad_forecasts) = await asyncio.gather(
                fetch_wind_actuals(client, s.analysis_start, s.analysis_end),
                fetch_wind_forecasts(client, published_from, last_cutoff),
            )
        if not actuals or not forecasts:
            missing = "FUELHH wind actuals" if not actuals else "WINDFOR forecasts"
            raise ElexonError(f"Elexon returned no {missing} for the requested period.")

        return run_analysis(
            forecasts,
            actuals,
            start_date=s.analysis_start,
            end_date=s.analysis_end,
            cutoff_time=s.cutoff_time,
            days_ahead=s.cutoff_days_ahead,
            tz=s.tz,
            interval_minutes=s.forecast_interval_minutes,
            malformed_forecast_rows=bad_forecasts,
            malformed_actual_rows=bad_actuals,
        )
