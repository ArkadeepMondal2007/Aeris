"""Forecast selection, interval matching and accuracy metrics. No network access here."""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from services.models import Actual, Analysis, Forecast, Observation


def decision_cutoff_utc(delivery_date: date, cutoff_time: time, days_ahead: int, tz) -> datetime:
    """Latest moment a forecast may be published to count for a delivery date.

    The cutoff is a local (Europe/London) wall-clock time, so it moves by an hour
    in UTC when the clocks change.
    """
    decision_day = delivery_date - timedelta(days=days_ahead)
    return datetime.combine(decision_day, cutoff_time, tzinfo=tz).astimezone(timezone.utc)


def evaluation_grid(start_date: date, end_date: date, tz, interval_minutes: int) -> list:
    """Every delivery interval start (UTC) from local midnight of start_date to the end of end_date.

    Built in UTC steps, so a clock-change day naturally has 23 or 25 hourly intervals.
    """
    first = datetime.combine(start_date, time(0), tzinfo=tz).astimezone(timezone.utc)
    stop = datetime.combine(end_date + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    step = timedelta(minutes=interval_minutes)
    grid = []
    current = first
    while current < stop:
        grid.append(current)
        current += step
    return grid


def select_forecast(candidates: list, start: datetime, cutoff: datetime) -> Optional[Forecast]:
    """Latest forecast published at or before the cutoff.

    A forecast published after its own interval began is a hindcast, not a forecast,
    so it is never eligible.
    """
    eligible = [f for f in candidates if f.published <= cutoff and f.published < start]
    return max(eligible, key=lambda f: f.published, default=None)


def run_analysis(
    forecasts: list,
    actuals: list,
    *,
    start_date: date,
    end_date: date,
    cutoff_time: time,
    days_ahead: int,
    tz,
    interval_minutes: int,
    malformed_forecast_rows: int = 0,
    malformed_actual_rows: int = 0,
) -> Analysis:
    grid = evaluation_grid(start_date, end_date, tz, interval_minutes)
    forecasts_by_start = defaultdict(list)
    for forecast in forecasts:
        forecasts_by_start[forecast.start].append(forecast)
    actuals_by_start = {actual.start: actual for actual in actuals}

    observations = []
    for start in grid:
        local = start.astimezone(tz)
        cutoff = decision_cutoff_utc(local.date(), cutoff_time, days_ahead, tz)
        chosen = select_forecast(forecasts_by_start.get(start, []), start, cutoff)
        actual = actuals_by_start.get(start)
        observations.append(
            Observation(
                start=start,
                delivery_date=local.date(),
                local_hour=local.hour,
                published=chosen.published if chosen else None,
                forecast=chosen.mw if chosen else None,
                actual=actual.mw if actual else None,
            )
        )

    grid_set = set(grid)
    in_window, off_grid = [], []
    if grid:
        window_end = grid[-1] + timedelta(minutes=interval_minutes)
        in_window = [a for a in actuals if grid[0] <= a.start < window_end]
        off_grid = [a for a in in_window if a.start not in grid_set]
    return Analysis(
        observations=observations,
        data_quality={
            "malformed_forecast_rows": malformed_forecast_rows,
            "malformed_actual_rows": malformed_actual_rows,
            "actual_intervals_in_window": len(in_window),
            "actual_intervals_not_compared": len(off_grid),
        },
        computed_at=datetime.now(timezone.utc),
    )


def compute_metrics(observations: list) -> dict:
    """MAE, RMSE and bias over intervals that have both a forecast and an actual."""
    expected = len(observations)
    matched = [o for o in observations if o.error is not None]
    n = len(matched)
    errors = [o.error for o in matched]
    return {
        "expected_intervals": expected,
        "matched_intervals": n,
        "missing_intervals": expected - n,
        "forecast_missing_intervals": sum(1 for o in observations if o.forecast is None),
        "actual_missing_intervals": sum(1 for o in observations if o.actual is None),
        "coverage_pct": (n / expected * 100) if expected else None,
        "mae_mw": sum(abs(e) for e in errors) / n if n else None,
        "rmse_mw": math.sqrt(sum(e * e for e in errors) / n) if n else None,
        "bias_mw": sum(errors) / n if n else None,
        "mean_forecast_mw": sum(o.forecast for o in matched) / n if n else None,
        "mean_actual_mw": sum(o.actual for o in matched) / n if n else None,
    }


def breakdown(observations: list, key) -> dict:
    groups = defaultdict(list)
    for observation in observations:
        groups[key(observation)].append(observation)
    keep = ("matched_intervals", "missing_intervals", "mae_mw", "rmse_mw", "bias_mw")
    return {group: {k: compute_metrics(rows)[k] for k in keep} for group, rows in sorted(groups.items())}
