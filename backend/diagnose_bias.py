"""LIVE diagnostic: is the positive bias real, or caused by how the data is lined up?

Re-runs the same analysis under different assumptions and prints one row each.
Run:  python3 diagnose_bias.py
"""
import asyncio
import math
from datetime import datetime, time, timedelta, timezone

import httpx

from services.analytics import compute_metrics, decision_cutoff_utc, run_analysis
from services.elexon import fetch_wind_actuals, fetch_wind_forecasts
from services.models import Actual, Forecast
from settings import Settings, get_settings


def hourly_mean_actuals(actuals):
    """Average the :00 and :30 half-hours so an actual covers the same hour as a forecast."""
    by_start = {a.start: a.mw for a in actuals}
    return [
        Actual(start, (mw + by_start[start + timedelta(minutes=30)]) / 2)
        for start, mw in by_start.items()
        if start.minute == 0 and start + timedelta(minutes=30) in by_start
    ]


def shifted(forecasts, hours):
    return [Forecast(f.start + timedelta(hours=hours), f.published, f.mw) for f in forecasts]


def centred_stats(analysis):
    """MAE after removing the average bias, plus correlation: both ignore a constant offset."""
    pairs = [(o.forecast, o.actual) for o in analysis.observations if o.error is not None]
    n = len(pairs)
    if not n:
        return 0, None, None
    errors = [f - a for f, a in pairs]
    mean_error = sum(errors) / n
    centred_mae = sum(abs(e - mean_error) for e in errors) / n
    mean_f, mean_a = sum(f for f, _ in pairs) / n, sum(a for _, a in pairs) / n
    cov = sum((f - mean_f) * (a - mean_a) for f, a in pairs)
    var = math.sqrt(sum((f - mean_f) ** 2 for f, _ in pairs) * sum((a - mean_a) ** 2 for _, a in pairs))
    return n, centred_mae, (cov / var if var else None)


def print_row(label, analysis):
    m = compute_metrics(analysis.observations)
    if not m["matched_intervals"]:
        print(f"{label:<50} no matched intervals")
        return
    over = sum(1 for o in analysis.observations if o.error is not None and o.error > 0) / m["matched_intervals"]
    print(f"{label:<50} n={m['matched_intervals']:>4}  MAE={m['mae_mw']:>8.1f}  bias={m['bias_mw']:>+8.1f}  over={over:>4.0%}")


async def analyse(client: httpx.AsyncClient, s: Settings):
    first = decision_cutoff_utc(s.analysis_start, s.cutoff_time, s.cutoff_days_ahead, s.tz)
    window_end = datetime.combine(s.analysis_end + timedelta(days=1), time(0), tzinfo=timezone.utc)
    actuals, _ = await fetch_wind_actuals(client, s.analysis_start, s.analysis_end)
    forecasts, _ = await fetch_wind_forecasts(client, first - timedelta(days=s.forecast_lookback_days), window_end)

    def build(fcs=forecasts, acts=actuals, cutoff=s.cutoff_time, days_ahead=s.cutoff_days_ahead):
        return run_analysis(
            fcs, acts, start_date=s.analysis_start, end_date=s.analysis_end, cutoff_time=cutoff,
            days_ahead=days_ahead, tz=s.tz, interval_minutes=s.forecast_interval_minutes,
        )

    def run(label, **kwargs):
        print_row(label, build(**kwargs))

    print("label".ljust(50), " (over = share of hours where forecast > actual)")
    print("\n1. Sensitivity to the decision-cutoff assumption (day before delivery)")
    for hh in (9, 12, 17, 23):
        run(f"cutoff {hh:02d}:00 London", cutoff=time(hh, 0))
    print("\n2. Does the bias persist with the freshest possible forecast? (hindsight, not a valid decision)")
    run("latest forecast published before each hour", cutoff=time(23, 59), days_ahead=0)
    print("\n3. Is the :00 half-hour the right actual for an hourly forecast?")
    run("actual = mean of :00 and :30 half-hours", acts=hourly_mean_actuals(actuals))
    print("\n4. Is the forecast time-aligned correctly? (current setup should win)")
    run("as built (forecast start == actual start)")
    run("forecast shifted +1 hour", fcs=shifted(forecasts, 1))
    run("forecast shifted -1 hour", fcs=shifted(forecasts, -1))
    print("\n5. Alignment with the constant bias removed (best shift = lowest centred MAE, highest correlation)")
    print("   shift -1 h means: actual at T is compared with the forecast labelled T+1h")
    for hours in range(-3, 4):
        n, centred_mae, corr = centred_stats(build(fcs=shifted(forecasts, hours)))
        corr_text = "n/a" if corr is None else f"{corr:.3f}"
        print(f"{f'forecast shifted {hours:+d} h'.ljust(50)} n={n:>4}  centred MAE={centred_mae:>8.1f}  correlation={corr_text}")


async def main():
    s = get_settings()
    async with httpx.AsyncClient(base_url=s.elexon_base_url, timeout=s.request_timeout_seconds) as client:
        await analyse(client, s)


if __name__ == "__main__":
    asyncio.run(main())
