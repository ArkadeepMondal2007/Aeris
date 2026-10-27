import asyncio
from datetime import date, datetime, timezone

import httpx
import pytest

from services.elexon import (
    ElexonError, fetch_wind_actuals, fetch_wind_forecasts, normalize_actuals, normalize_forecasts, parse_time,
)

UTC = timezone.utc


def test_naive_timestamps_are_rejected_not_assumed_utc():
    assert parse_time("2026-01-02T12:00:00") is None
    assert parse_time("2026-01-02T12:00:00Z") == datetime(2026, 1, 2, 12, tzinfo=UTC)
    assert parse_time("2026-01-02T13:00:00+01:00") == datetime(2026, 1, 2, 12, tzinfo=UTC)
    assert parse_time(None) is None


def test_forecast_rows_with_missing_generation_are_skipped_not_zeroed():
    rows = [
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 5000},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T13:00:00Z", "generation": None},
        {"publishTime": "2026-01-01T09:30:00Z", "startTime": "bad", "generation": 1},
        "not a row",
    ]
    forecasts, malformed = normalize_forecasts(rows)
    assert [f.mw for f in forecasts] == [5000.0]
    assert malformed == 3


def test_duplicate_forecast_rows_collapse_to_one():
    row = {"publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T12:00:00Z", "generation": 5000}
    forecasts, _ = normalize_forecasts([row, dict(row, generation=5100)])
    assert len(forecasts) == 1 and forecasts[0].mw == 5100


def test_actuals_keep_wind_only_and_latest_revision():
    rows = [
        {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-02T12:30:00Z", "generation": 5000},
        {"fuelType": "WIND", "startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-02T13:00:00Z", "generation": 5050},
        {"fuelType": "CCGT", "startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-02T13:00:00Z", "generation": 1},
        {"fuelType": "WIND", "startTime": "2026-01-02T12:30:00Z", "generation": None},
    ]
    actuals, malformed = normalize_actuals(rows)
    assert [(a.start.minute, a.mw) for a in actuals] == [(0, 5050.0)]
    assert malformed == 1


def _client(handler):
    return httpx.AsyncClient(base_url="https://example.test/api", transport=httpx.MockTransport(handler))


def test_requests_use_documented_parameters():
    seen = {}

    def handler(request):
        seen[request.url.path] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})

    async def go():
        async with _client(handler) as client:
            await fetch_wind_actuals(client, date(2026, 1, 1), date(2026, 1, 31))
            await fetch_wind_forecasts(
                client, datetime(2025, 12, 26, 17, tzinfo=UTC), datetime(2026, 1, 30, 17, tzinfo=UTC)
            )

    asyncio.run(go())
    assert seen["/api/datasets/FUELHH/stream"] == {
        "settlementDateFrom": "2026-01-01", "settlementDateTo": "2026-01-31", "fuelType": "WIND",
    }
    assert seen["/api/datasets/WINDFOR/stream"] == {
        "publishDateTimeFrom": "2025-12-26T17:00:00Z", "publishDateTimeTo": "2026-01-30T17:00:00Z",
    }


@pytest.mark.parametrize(
    "response",
    [
        lambda r: httpx.Response(500, text="boom"),
        lambda r: httpx.Response(200, text="<html>not json</html>"),
        lambda r: httpx.Response(200, json={"unexpected": True}),
        lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")),
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("down")),
    ],
)
def test_upstream_failures_raise_elexon_error(response):
    async def go():
        async with _client(response) as client:
            await fetch_wind_actuals(client, date(2026, 1, 1), date(2026, 1, 31))

    with pytest.raises(ElexonError):
        asyncio.run(go())
