# AERIS — Wind Forecast Intelligence

A full-stack analytics tool that answers one question for a UK power procurement team: **how good were the wind-generation forecasts that were actually available when the day-ahead buying decision was made?**

For each hour of January 2026, the backend reconstructs the forecast that existed at the decision cutoff, matches it to the actual wind generation, and calculates forecast accuracy. The React frontend displays the results as KPIs, charts and a filterable data table.

All data comes from two public Elexon BMRS datasets, with no API key required:

- **FUELHH** – actual half-hourly generation (filtered to `fuelType = WIND`)
- **WINDFOR** – wind-generation forecasts (`startTime`, `publishTime`, `generation`)

This is a historical analysis tool. It does not execute trades and has no live market feed.

---

## Live demo

<!-- Replace both placeholders after deploying, then delete this comment. -->

| Part | URL |
| --- | --- |
| Frontend (Vercel) | `https://YOUR-APP.vercel.app` |
| Backend API docs (Heroku / Render) | `https://YOUR-API-HOST/docs` |

> The backend fetches from Elexon on the first request and caches the result for an hour, so the first page load can take a few seconds. Free hosting tiers may also need time to wake up.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.9+, FastAPI, httpx (async), uvicorn |
| Frontend | React 18, Vite, React Router, Recharts, Lucide icons, plain CSS |
| Tests | pytest (backend) |
| Packaging | Docker (backend) |

---

## Repository structure

```text
.
├── README.md
├── backend/                     FastAPI service
│   ├── main.py                  Routes, CORS, validation, error handling
│   ├── settings.py              Configuration from environment variables / .env
│   ├── services/
│   │   ├── __init__.py
│   │   ├── models.py            Small data classes (Forecast, Actual, Observation, Analysis)
│   │   ├── elexon.py            Elexon requests, timeouts, normalising and de-duplicating rows
│   │   ├── analytics.py         Cutoff logic, forecast selection, matching, metrics (no network)
│   │   └── store.py             Fetches once, caches for an hour, shared by all endpoints
│   ├── tests/
│   │   ├── test_analytics.py    Selection, matching, metrics, missing data, DST edge cases
│   │   ├── test_elexon.py       Row normalisation, duplicates, upstream-failure handling
│   │   └── test_api.py          Endpoint contract, pagination, validation, 502s, missing values
│   ├── check_elexon.py          Prints the raw shape of the Elexon responses
│   ├── live_check.py            LIVE: runs the full pipeline against the real API
│   ├── diagnose_bias.py         LIVE: sensitivity of results to cutoff, matching and alignment
│   ├── verify_coverage.py       LIVE: independent hour-by-hour recount of missing data
│   ├── requirements.txt         Runtime dependencies
│   ├── requirements-dev.txt     Runtime + pytest
│   ├── pytest.ini               Test configuration
│   ├── Dockerfile               Container image for the API
│   ├── .env.example             Documented configuration with defaults
│   └── README.md                Backend details, method, findings and caveats
│
└── frontend/                    React + Vite application
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example             VITE_API_BASE_URL
    └── src/
        ├── main.jsx             Entry point and router
        ├── app/                 App.jsx (routes), navigation.js (sidebar items)
        ├── components/
        │   ├── layout/          AppShell, Sidebar, Header
        │   ├── common/          KpiCard, DataPanel, loading / error / empty states
        │   ├── charts/          Forecast-vs-actual chart, error chart, shared tooltip
        │   ├── filters/         DateRangeFilter
        │   ├── tables/          ObservationsTable with pagination
        │   └── InsightsPanel.jsx
        ├── pages/               OverviewPage, DataExplorerPage, NotFoundPage
        ├── services/            apiClient.js (fetch wrapper), forecastService.js (endpoints, response cleaning)
        ├── hooks/               useApi.js (request lifecycle, cancellation, refresh)
        ├── utils/               time, formatters, statistics, csvExport
        └── styles/              variables.css (design tokens), layout.css, components.css
```

> If your frontend folder has a different name, adjust the paths in the commands below. A Vite project also contains some generated files that are not listed here.

---

## How to start the application

Start the backend first, then the frontend.

### Prerequisites

- Python 3.9 or newer
- Node.js 18 or newer and npm
- Internet access (the backend calls the public Elexon API)
- Docker (optional)

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env              # optional: the defaults already work
python3 -m uvicorn main:app --reload --port 8000
```

Check that it is running:

- Health check: <http://localhost:8000/health> returns `{"status":"ok"}`
- Interactive API docs: <http://localhost:8000/docs>
- Example data: <http://localhost:8000/api/overview>

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env              # sets VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Open <http://localhost:5173>. The header should show **API online**.

### 3. Backend with Docker (optional)

```bash
cd backend
docker build -t aeris-backend .
docker run --rm -p 8000:8000 --env-file .env aeris-backend
```

---

## Configuration

### Backend (`backend/.env`, all optional)

| Variable | Default | Meaning |
| --- | --- | --- |
| `ANALYSIS_START` / `ANALYSIS_END` | `2026-01-01` / `2026-01-31` | Delivery dates analysed (Europe/London, inclusive) |
| `DECISION_CUTOFF_TIME` | `17:00` | Local time by which a forecast must have been published |
| `DECISION_DAYS_AHEAD` | `1` | Days before delivery that the decision is made |
| `TIMEZONE` | `Europe/London` | Time zone for the cutoff and delivery dates |
| `FORECAST_INTERVAL_MINUTES` | `60` | WINDFOR resolution (verified from live data) |
| `FORECAST_LOOKBACK_DAYS` | `5` | How far before the first cutoff to fetch forecasts |
| `CACHE_TTL_SECONDS` | `3600` | How long fetched data is reused |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout for each Elexon request |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins, comma-separated |
| `ELEXON_BASE_URL` | `https://data.elexon.co.uk/bmrs/api/v1` | Elexon API base URL |

### Frontend (`frontend/.env`)

| Variable | Example | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Where the backend is running |

No secrets are used anywhere in this project.

---

## API endpoints

| Route | Purpose |
| --- | --- |
| `GET /health` | Service is up (does not call Elexon) |
| `GET /api/overview` | Period, cutoff description, metrics, coverage, data quality |
| `GET /api/forecast-actuals?from=&to=` | Chart rows: `startTime`, `publishTime`, `forecast_mw`, `actual_mw`, `error_mw` |
| `GET /api/accuracy?from=&to=` | Metrics plus breakdowns by date and by London hour |
| `GET /api/observations?from=&to=&status=&limit=&offset=` | Paginated table (`status`: `all`, `matched`, `missing`) |

Invalid parameters return `422`. Upstream Elexon failures return `502` with a message. The API never substitutes mock data.

---

## How the analysis works

1. **Decision cutoff.** For each delivery hour, only forecasts published at or before the cutoff are eligible. The brief does not state a cutoff hour, so the default is an **assumption: 17:00 Europe/London on the day before delivery**, configurable in `.env`.
2. **Forecast selection.** The latest eligible forecast by `publishTime`, not the newest forecast available today. A forecast published after its own delivery hour began is never used.
3. **Matching.** WINDFOR is hourly and FUELHH is half-hourly, so intervals are matched on exact `startTime`. The `:30` actuals have no forecast to compare against and are reported separately, not counted as missing.
4. **Error and metrics.**
   - Error = forecast − actual (positive means generation was overestimated)
   - MAE = mean(|error|), RMSE = √mean(error²), Bias = mean(error)
5. **Missing data.** A missing forecast or actual is `null`, never zero, and is excluded from metrics. A genuine 0 MW value is kept. `coverage_pct` = matched ÷ expected hourly intervals.
6. **Time zones.** All timestamps are UTC. The cutoff uses Europe/London rules, so it shifts across clock changes, and clock-change days have 23 or 25 hourly intervals.

Full method, assumptions and data-quality notes are in [`backend/README.md`](backend/README.md).

---

## Tests and verification

```bash
cd backend
python3 -m pytest              # unit and API tests with mocked Elexon responses (no network)
python3 live_check.py          # LIVE: full pipeline against the real Elexon API
python3 verify_coverage.py     # LIVE: independent recount; flags any missing value that became zero
python3 diagnose_bias.py       # LIVE: how sensitive the results are to method choices
```

- `pytest` proves the logic and API wiring on mocked data. It does not prove the live Elexon connection; the three live scripts do that.
- The frontend has no automated tests.

---

## Results (measured live, January 2026, default 17:00 cutoff)

| Metric | Value |
| --- | --- |
| Matched hourly intervals | 744 of 744 (100% coverage) |
| MAE | 1,968 MW |
| RMSE | 2,435 MW |
| Bias (forecast − actual) | +1,817 MW |
| Mean forecast vs mean actual | 13,398 MW vs 11,581 MW |

Forecasts follow the shape of actual generation (correlation ≈ 0.95) but run consistently high, exceeding actuals in about 88% of hours. This persisted under every cutoff (09:00–23:00), with the freshest possible forecast, and with half-hour-averaged actuals. Whether it reflects genuine over-forecasting or a scope difference between the two datasets cannot be determined from these datasets alone. The cutoff assumption changes MAE by roughly 10% (2,128 MW at 09:00 down to 1,919 MW at 23:00) but not the overall conclusion. Details are in `backend/README.md`.

Figures were measured against the live API during development and may change if Elexon revises its data.

---

## Deployment

**Backend (Heroku, Render or any Docker host).** Deploy the `backend/` folder using its `Dockerfile`. The container listens on the `PORT` provided by the host. Set `CORS_ORIGINS` to your deployed frontend URL (for example `https://YOUR-APP.vercel.app`).

**Frontend (Vercel).** Set the project root to `frontend`, and add the environment variable `VITE_API_BASE_URL` pointing at the deployed backend (no trailing slash). Because the app uses client-side routing, add `frontend/vercel.json` so that refreshing a page such as `/explorer` works:

```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/" }] }
```

Redeploy the frontend after changing `VITE_API_BASE_URL`, because Vite reads it at build time.

---

## Known limitations

- Tied to a single analysis period, set by `ANALYSIS_START` / `ANALYSIS_END`.
- The cache is in memory and per process, so it resets on restart.
- The decision cutoff hour is an assumption, because the brief does not specify one.
- Whether a WINDFOR hour is labelled by its start or its end could not be determined from the data.
- No normalised (percentage) error metric is provided.
- No authentication, since the project handles only public data.
