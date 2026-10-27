"""Fetches wind data from the Elexon Insights API and normalises it.

Endpoints and parameters were checked against Elexon's documentation and a live
response: FUELHH/stream takes settlementDateFrom/To and fuelType; WINDFOR/stream
takes publishDateTimeFrom/To.
"""
import math
from datetime import date, datetime, timezone
from typing import Optional

import httpx

from services.models import Actual, Forecast

EARLIEST = datetime.min.replace(tzinfo=timezone.utc)


class ElexonError(Exception):
    """The upstream API failed or returned something unusable."""


def parse_time(value) -> Optional[datetime]:
    """Parse an ISO timestamp to UTC. Timezone-naive values are rejected, not guessed."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def parse_number(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def normalize_forecasts(rows: list):
    """Returns (forecasts, malformed_row_count). A missing generation is skipped, never zero."""
    unique = {}
    malformed = 0
    for row in rows:
        row = row if isinstance(row, dict) else {}
        start, published = parse_time(row.get("startTime")), parse_time(row.get("publishTime"))
        mw = parse_number(row.get("generation"))
        if start is None or published is None or mw is None:
            malformed += 1
            continue
        unique[(published, start)] = Forecast(start=start, published=published, mw=mw)
    return list(unique.values()), malformed


def normalize_actuals(rows: list):
    """Returns (actuals, malformed_row_count). Duplicate intervals keep the latest publishTime."""
    unique = {}
    malformed = 0
    for row in rows:
        row = row if isinstance(row, dict) else {}
        if row.get("fuelType") != "WIND":
            continue
        start, published = parse_time(row.get("startTime")), parse_time(row.get("publishTime"))
        mw = parse_number(row.get("generation"))
        if start is None or mw is None:
            malformed += 1
            continue
        previous = unique.get(start)
        if previous is None or (published or EARLIEST) >= (previous.published or EARLIEST):
            unique[start] = Actual(start=start, mw=mw, published=published)
    return list(unique.values()), malformed


async def _get_rows(client: httpx.AsyncClient, path: str, params: dict) -> list:
    try:
        response = await client.get(path, params=params)
    except httpx.TimeoutException as error:
        raise ElexonError(f"Elexon API timed out for {path}.") from error
    except httpx.HTTPError as error:
        raise ElexonError(f"Could not reach the Elexon API for {path}: {error}") from error
    if response.status_code != 200:
        raise ElexonError(f"Elexon API returned status {response.status_code} for {path}: {response.text[:200]}")
    try:
        body = response.json()
    except ValueError as error:
        raise ElexonError(f"Elexon API returned invalid JSON for {path}.") from error
    rows = body.get("data") if isinstance(body, dict) else body
    if not isinstance(rows, list):
        raise ElexonError(f"Elexon API returned an unexpected response shape for {path}.")
    return rows


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def fetch_wind_actuals(client: httpx.AsyncClient, start_date: date, end_date: date):
    rows = await _get_rows(
        client,
        "/datasets/FUELHH/stream",
        {"settlementDateFrom": start_date.isoformat(), "settlementDateTo": end_date.isoformat(), "fuelType": "WIND"},
    )
    return normalize_actuals(rows)


async def fetch_wind_forecasts(client: httpx.AsyncClient, published_from: datetime, published_to: datetime):
    rows = await _get_rows(
        client,
        "/datasets/WINDFOR/stream",
        {"publishDateTimeFrom": _iso(published_from), "publishDateTimeTo": _iso(published_to)},
    )
    return normalize_forecasts(rows)
