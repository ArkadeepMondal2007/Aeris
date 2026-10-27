# AERIS backend

FastAPI service that rebuilds which WINDFOR wind forecast was available at a historical
day-ahead buying decision (January 2026), matches it to FUELHH actual wind generation, and
serves accuracy metrics to the AERIS React frontend. Data comes only from the public Elexon
Insights API (no API key). It never substitutes mock data: if Elexon fails, the API returns an error.

## Run locally

Requires Python 3.9+.

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # optional; defaults already match
uvicorn main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Tests and live check

```bash
pytest                # unit tests, mocked Elexon responses, no network
python live_check.py  # LIVE: runs the real pipeline against the real Elexon API
python diagnose_bias.py  # LIVE: tests how sensitive the results are to the method choices
python verify_coverage.py  # LIVE: independent recount of coverage and missing values
```

Passing `pytest` proves the logic and the API wiring on mocked data. Only `live_check.py`
(and the running app) prove the live Elexon connection.

## Files

| File | Role |
| --- | --- |
| `main.py` | Routes, CORS, validation, error handling |
| `settings.py` | Configuration from environment variables / `.env` |
| `services/elexon.py` | Elexon requests, timeouts, normalising and de-duplicating rows |
| `services/analytics.py` | Cutoff, forecast selection, matching, metrics (pure functions, no network) |
| `services/store.py` | Fetches once, caches (default 1 hour), shared by all endpoints |
| `services/models.py` | Small data classes |
| `live_check.py` | Separate live connectivity/pipeline check |
| `diagnose_bias.py` | Live sensitivity analysis (cutoff, forecast age, matching, time alignment) |
| `verify_coverage.py` | Live independent recount of every hour; flags any missing value that became zero |
| `tests/` | Unit and API tests |

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /health` | Service is up (does not call Elexon) |
| `GET /api/overview` | Period, cutoff description, metrics, coverage, data quality |
| `GET /api/forecast-actuals?from=&to=` | Chart rows: `startTime`, `publishTime`, `forecast_mw`, `actual_mw`, `error_mw` |
| `GET /api/accuracy?from=&to=` | Metrics plus breakdowns by date and by London hour |
| `GET /api/observations?from=&to=&status=&limit=&offset=` | Paginated table (`status`: all, matched, missing) |

`from`/`to` are `YYYY-MM-DD` delivery dates inside the analysis period; others return 422.
Upstream problems return 502 with a message. Missing values are `null`, never 0.
Error is `forecast - actual`: positive means generation was overestimated.

## Method and assumptions

1. **Decision cutoff (assumption).** The brief does not give an hour. Default: 17:00
   Europe/London on the day before delivery (`DECISION_CUTOFF_TIME`, `DECISION_DAYS_AHEAD`).
   Forecasts published at or before it are eligible; later ones are never used.
2. **Selection.** For each interval, the eligible forecast with the latest `publishTime`.
3. **Resolution.** Verified from live data: every WINDFOR `startTime` is on the hour, while FUELHH
   is half-hourly. Intervals are matched on exact `startTime`, so only the on-the-hour FUELHH
   values are compared. The `:30` actuals are reported as `actual_intervals_not_compared`;
   they are not averaged, interpolated or counted as missing forecasts.
4. **Hindcasts ignored.** Live data contains rows published up to 25.5 hours *after* their own
   `startTime`. A forecast published after its interval began is never eligible.
5. **Time zones.** All timestamps are UTC. The cutoff and delivery dates use Europe/London rules,
   so the cutoff shifts by an hour in UTC across clock changes and clock-change days have 23 or 25
   hourly intervals. Timezone-naive timestamps from the API are rejected, not guessed.
6. **Metrics.** MAE, RMSE and bias use only intervals with both values. `missing_intervals`
   = expected - matched. `coverage_pct` = matched / expected, where expected is every hourly
   interval in the period.
7. **Duplicates.** Duplicate forecast rows collapse to one; duplicate actuals keep the latest `publishTime`.

## Missing data and coverage

- A missing forecast or actual is `null` in the API and `None` internally. It is never defaulted
  to zero, and metrics skip it. A genuine `0` MW from Elexon is kept as `0` and counts as matched.
- Rows with a missing or non-numeric `generation` are skipped and counted in
  `data_quality.malformed_*_rows`. If the latest eligible forecast row is unusable, the previous
  eligible vintage is used, because the unusable row carries no forecast.
- `expected_intervals` is built from the analysis period (one per forecast hour), not from whatever
  the API returned, so an hour with no rows at all is reported as missing rather than silently absent.
- `missing_intervals` = expected - matched. `coverage_pct` = matched / expected.
  **Its denominator is hourly intervals.** FUELHH also has `:30` half-hours with no hourly forecast
  to compare against; they are not "missing", and are reported separately as
  `data_quality.actual_intervals_in_window` and `actual_intervals_not_compared`
  (for January 2026: 1,488 and 744). Read in those terms, 744 of 1,488 FUELHH half-hours
  are compared.
- If Elexon returns no rows at all for either dataset, the API returns a 502, not an empty success.
- Verified by `tests/test_api.py` (gaps, null rows, a genuine zero, a day with no actuals) and,
  against live data, by `verify_coverage.py`.

## Findings and caveats (measured live, January 2026, default 17:00 cutoff)

Produced by `live_check.py` and `diagnose_bias.py` against the real Elexon API during development.
Re-run them to reproduce; Elexon data can be revised, so exact figures may change.

| Quantity | Value |
| --- | --- |
| Matched hourly intervals | 744 of 744 (100% coverage, 0 malformed rows) |
| MAE / RMSE | 1,968 MW / 2,435 MW |
| Bias (forecast - actual) | +1,817 MW (mean forecast 13,398 MW vs mean actual 11,581 MW) |
| Hours where forecast > actual | 88% |
| MAE with the constant bias removed | 1,278 MW; correlation 0.954 |

**The forecasts follow the shape of actual generation but run high, consistently.**
This did not change under any method choice tested:

| Variant | MAE (MW) | Bias (MW) | Forecast > actual |
| --- | --- | --- | --- |
| Cutoff 09:00 day before | 2,128 | +1,852 | 85% |
| Cutoff 12:00 | 2,003 | +1,806 | 85% |
| **Cutoff 17:00 (default)** | **1,968** | **+1,817** | **88%** |
| Cutoff 23:00 | 1,919 | +1,713 | 88% |
| Latest forecast before each hour (hindsight, not a valid decision) | 1,794 | +1,593 | 87% |
| Actual = mean of the `:00` and `:30` half-hours | 1,981 | +1,817 | 88% |

- **The cutoff assumption matters for MAE, not for the conclusion.** Moving the cutoff from
  09:00 to 23:00 changes MAE by about 10%; later cutoffs are more accurate because forecasts are fresher.
- **Cause not established.** The bias could be genuine over-forecasting, or a scope difference.
  Elexon describes WINDFOR as covering wind farms visible to the ESO that have operational
  metering; whether FUELHH WIND covers exactly the same farms was not confirmed. The two
  datasets alone cannot separate these explanations.
- **Time alignment.** Shifting the forecast by whole hours (bias removed) gives a shallow minimum
  between -1 h and 0 h (centred MAE 1,276 vs 1,278 MW). That rules out a gross labelling error
  but cannot show whether a WINDFOR `startTime` marks the start or the end of its hour. Matching
  on exact `startTime` is kept.

## Docker

```bash
docker build -t aeris-backend .
docker run --rm -p 8000:8000 --env-file .env aeris-backend
```

Set `CORS_ORIGINS` to your deployed frontend origin (comma-separated for several). Hosts that
inject `PORT` (Heroku, Render) are supported.

## Connect the frontend

In the frontend folder, `.env` should contain `VITE_API_BASE_URL=http://localhost:8000`.
Start the backend first, then `npm run dev`; the header should show "API online".

## Known limitations

- Tied to one analysis period, set by `ANALYSIS_START` / `ANALYSIS_END`.
- The cache is in memory, per process, and lost on restart.
- Hourly forecasts are compared with the `:00` half-hour. Using the mean of the two half-hours
  was tested and changes MAE by under 1% (see Findings).
- Whether a WINDFOR hour is labelled by its start or its end could not be determined from the data.
- Elexon's WINDFOR covers wind farms visible to the system operator, so it may differ from total national wind.
- No normalised (percentage) error metric is provided.
