import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from services.analytics import compute_metrics, decision_cutoff_utc, evaluation_grid, run_analysis, select_forecast
from services.models import Actual, Forecast, Observation

UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")


def utc(month, day, hour=0, minute=0, year=2026):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def run(forecasts, actuals, day=date(2026, 1, 2), days_ahead=1, cutoff=time(17, 0)):
    return run_analysis(
        forecasts, actuals, start_date=day, end_date=day, cutoff_time=cutoff,
        days_ahead=days_ahead, tz=LONDON, interval_minutes=60,
    )


def at(analysis, start):
    return next(o for o in analysis.observations if o.start == start)


# --- forecast selection ---------------------------------------------------

def test_selects_latest_forecast_published_before_cutoff():
    target = utc(1, 2, 12)
    forecasts = [
        Forecast(target, utc(1, 1, 9, 30), 5000),
        Forecast(target, utc(1, 1, 15, 30), 5200),
        Forecast(target, utc(1, 1, 18, 30), 9999),
    ]
    obs = at(run(forecasts, [Actual(target, 5350)]), target)
    assert obs.forecast == 5200
    assert obs.published == utc(1, 1, 15, 30)
    assert obs.error == -150


def test_rejects_forecasts_published_after_cutoff():
    target = utc(1, 2, 12)
    obs = at(run([Forecast(target, utc(1, 1, 18, 30), 9999)], [Actual(target, 5350)]), target)
    assert obs.forecast is None and obs.published is None and obs.error is None


def test_forecast_published_exactly_at_cutoff_is_eligible():
    target = utc(1, 2, 12)
    obs = at(run([Forecast(target, utc(1, 1, 17, 0), 4200)], []), target)
    assert obs.forecast == 4200


def test_forecast_published_after_interval_start_is_never_used():
    target = utc(1, 2, 12)
    late = Forecast(target, utc(1, 2, 12, 30), 1111)
    assert select_forecast([late], target, cutoff=utc(1, 2, 18)) is None


# --- matching and missing data ---------------------------------------------

def test_matches_on_exact_start_time_only():
    forecasts = [Forecast(utc(1, 2, 12), utc(1, 1, 9, 30), 5000)]
    actuals = [Actual(utc(1, 2, 12), 5100), Actual(utc(1, 2, 12, 30), 7777)]
    analysis = run(forecasts, actuals)
    assert at(analysis, utc(1, 2, 12)).actual == 5100
    assert all(o.start.minute == 0 for o in analysis.observations)
    assert analysis.data_quality["actual_intervals_not_compared"] == 1


def test_missing_values_stay_none_and_are_counted():
    forecasts = [Forecast(utc(1, 2, h), utc(1, 1, 9, 30), 100.0) for h in (0, 1, 2)]
    actuals = [Actual(utc(1, 2, h), 90.0) for h in (1, 2, 3)]
    analysis = run(forecasts, actuals)
    assert at(analysis, utc(1, 2, 0)).actual is None
    assert at(analysis, utc(1, 2, 3)).forecast is None
    metrics = compute_metrics(analysis.observations)
    assert metrics["matched_intervals"] == 2
    assert metrics["forecast_missing_intervals"] == 21
    assert metrics["actual_missing_intervals"] == 21
    assert metrics["missing_intervals"] == 22
    assert math.isclose(metrics["coverage_pct"], 2 / 24 * 100)


def test_empty_datasets_give_no_metrics_not_zeros():
    analysis = run([], [])
    assert len(analysis.observations) == 24
    metrics = compute_metrics(analysis.observations)
    assert metrics["matched_intervals"] == 0
    assert metrics["mae_mw"] is None and metrics["rmse_mw"] is None and metrics["bias_mw"] is None
    assert metrics["coverage_pct"] == 0.0
    assert compute_metrics([])["coverage_pct"] is None


# --- metrics ----------------------------------------------------------------

def test_mae_rmse_and_bias():
    pairs = [(100, 110), (200, 190), (300, 330)]  # errors -10, +10, -30
    observations = [
        Observation(utc(1, 2, i), date(2026, 1, 2), i, utc(1, 1), f, a) for i, (f, a) in enumerate(pairs)
    ]
    metrics = compute_metrics(observations)
    assert math.isclose(metrics["mae_mw"], 50 / 3)
    assert math.isclose(metrics["rmse_mw"], math.sqrt(1100 / 3))
    assert math.isclose(metrics["bias_mw"], -10)
    assert metrics["matched_intervals"] == 3 and metrics["coverage_pct"] == 100


def test_positive_error_means_overestimate():
    obs = Observation(utc(1, 2), date(2026, 1, 2), 0, utc(1, 1), 6000, 5000)
    assert obs.error == 1000


# --- timezone and daylight saving -------------------------------------------

def test_cutoff_is_local_time_in_winter_and_summer():
    assert decision_cutoff_utc(date(2026, 1, 15), time(17), 1, LONDON) == utc(1, 14, 17)
    assert decision_cutoff_utc(date(2026, 7, 15), time(17), 1, LONDON) == utc(7, 14, 16)


def test_cutoff_moves_by_an_hour_across_spring_forward():
    # Clocks go forward on 29 March 2026.
    assert decision_cutoff_utc(date(2026, 3, 29), time(17), 1, LONDON) == utc(3, 28, 17)
    assert decision_cutoff_utc(date(2026, 3, 30), time(17), 1, LONDON) == utc(3, 29, 16)


def test_clock_change_days_have_23_and_25_intervals():
    assert len(evaluation_grid(date(2026, 3, 29), date(2026, 3, 29), LONDON, 60)) == 23
    assert len(evaluation_grid(date(2026, 10, 25), date(2026, 10, 25), LONDON, 60)) == 25
    assert len(evaluation_grid(date(2026, 1, 1), date(2026, 1, 31), LONDON, 60)) == 31 * 24


def test_delivery_date_and_cutoff_use_london_local_day():
    midnight_bst = utc(3, 29, 23)  # 00:00 on 30 March in London
    forecasts = [
        Forecast(midnight_bst, utc(3, 29, 15, 30), 100),  # 16:30 BST: before the 17:00 cutoff
        Forecast(midnight_bst, utc(3, 29, 16, 30), 999),  # 17:30 BST: too late
    ]
    analysis = run(forecasts, [], day=date(2026, 3, 30))
    obs = at(analysis, midnight_bst)
    assert obs.delivery_date == date(2026, 3, 30)
    assert obs.forecast == 100
    assert len(analysis.observations) == 24
