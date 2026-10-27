"""LIVE cross-check of missing-data and coverage numbers.

Recounts every hour straight from the raw Elexon rows with its own simple logic (it does not use
services.analytics), then compares each hour with what the pipeline returned. A missing value that
the pipeline turned into zero, or a zero it turned into missing, shows up as a mismatch.
Run:  python3 verify_coverage.py
"""
import asyncio
from datetime import datetime, time, timedelta, timezone

import httpx

from services.store import AnalysisStore
from settings import Settings, get_settings

UTC = timezone.utc


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


async def rows_from(client, path, params):
    response = await client.get(path, params=params)
    response.raise_for_status()
    body = response.json()
    return body["data"] if isinstance(body, dict) else body


def count_raw(label, rows):
    zeros = sum(1 for r in rows if r.get("generation") == 0 and is_number(r.get("generation")))
    nulls = sum(1 for r in rows if not is_number(r.get("generation")))
    print(f"{label:<9} raw rows={len(rows):>6}   generation == 0: {zeros}   null/non-numeric: {nulls}")


async def check(client: httpx.AsyncClient, s: Settings, store: AnalysisStore) -> bool:
    tz = s.tz

    def cutoff_for(start):
        decision_day = start.astimezone(tz).date() - timedelta(days=s.cutoff_days_ahead)
        return datetime.combine(decision_day, s.cutoff_time, tzinfo=tz).astimezone(UTC)

    first = datetime.combine(s.analysis_start, time(0), tzinfo=tz).astimezone(UTC)
    stop = datetime.combine(s.analysis_end + timedelta(days=1), time(0), tzinfo=tz).astimezone(UTC)
    hours, t = [], first
    while t < stop:
        hours.append(t)
        t += timedelta(minutes=s.forecast_interval_minutes)

    actual_rows = await rows_from(client, "/datasets/FUELHH/stream", {
        "settlementDateFrom": s.analysis_start.isoformat(), "settlementDateTo": s.analysis_end.isoformat(),
        "fuelType": "WIND"})
    forecast_rows = await rows_from(client, "/datasets/WINDFOR/stream", {
        "publishDateTimeFrom": (cutoff_for(first) - timedelta(days=s.forecast_lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishDateTimeTo": cutoff_for(hours[-1]).strftime("%Y-%m-%dT%H:%M:%SZ")})
    count_raw("FUELHH", actual_rows)
    count_raw("WINDFOR", forecast_rows)

    actual_at = {stamp(r["startTime"]): r["generation"] for r in actual_rows if is_number(r.get("generation"))}
    candidates = {}
    for r in forecast_rows:
        if is_number(r.get("generation")):
            candidates.setdefault(stamp(r["startTime"]), []).append((stamp(r["publishTime"]), r["generation"]))

    expected = {}
    for hour in hours:
        usable = [c for c in candidates.get(hour, []) if c[0] <= cutoff_for(hour) and c[0] < hour]
        expected[hour] = (max(usable)[1] if usable else None, actual_at.get(hour))

    both = sum(1 for f, a in expected.values() if f is not None and a is not None)
    no_forecast = [h for h, (f, _) in expected.items() if f is None]
    no_actual = [h for h, (_, a) in expected.items() if a is None]
    print(f"\nIndependent recount over {len(hours)} hourly intervals:")
    print(f"  with forecast and actual: {both}   missing forecast: {len(no_forecast)}   missing actual: {len(no_actual)}")
    print(f"  coverage = {both / len(hours):.2%}   (FUELHH half-hours in window: "
          f"{sum(1 for h in actual_at if first <= h < stop)}; only the on-the-hour ones have a forecast to compare)")
    for label, missing in (("forecast", no_forecast), ("actual", no_actual)):
        if missing:
            print(f"  first missing {label} hours:", ", ".join(f"{h:%d %b %H:%M}Z" for h in missing[:10]))

    analysis = await store.get()
    mismatches = []
    for o in analysis.observations:
        if (o.forecast, o.actual) != expected[o.start]:
            mismatches.append((o.start, (o.forecast, o.actual), expected[o.start]))
    print(f"\nPipeline vs independent, hour by hour ({len(analysis.observations)} hours compared):")
    if mismatches:
        print(f"  MISMATCH in {len(mismatches)} hours (pipeline vs independent), first few:")
        for start, got, want in mismatches[:10]:
            print(f"    {start:%d %b %H:%M}Z pipeline={got} independent={want}")
        return False
    print("  MATCH: every forecast and actual agrees, including where a value is missing (None) or genuinely 0.")
    return True


async def main():
    s = get_settings()
    async with httpx.AsyncClient(base_url=s.elexon_base_url, timeout=s.request_timeout_seconds) as client:
        await check(client, s, AnalysisStore(s))


if __name__ == "__main__":
    asyncio.run(main())
