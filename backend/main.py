"""FastAPI app: routes, CORS, validation and error handling."""
from datetime import date
from functools import lru_cache
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.analytics import breakdown, compute_metrics
from services.elexon import ElexonError
from services.models import Observation
from services.store import AnalysisStore
from settings import Settings, get_settings

app = FastAPI(title="AERIS Wind Forecast API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache
def get_store() -> AnalysisStore:
    return AnalysisStore(get_settings())


@app.exception_handler(ElexonError)
async def elexon_error_handler(_, error: ElexonError):
    return JSONResponse(status_code=502, content={"detail": str(error)})


def _stamp(moment) -> Optional[str]:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def _rounded(metrics: dict) -> dict:
    return {key: _round(value) if isinstance(value, float) else value for key, value in metrics.items()}


def _observation_json(o: Observation) -> dict:
    return {
        "startTime": _stamp(o.start),
        "publishTime": _stamp(o.published),
        "deliveryDate": o.delivery_date.isoformat(),
        "forecast_mw": o.forecast,
        "actual_mw": o.actual,
        "error_mw": _round(o.error),
    }


def _resolve_range(date_from: Optional[date], date_to: Optional[date], settings: Settings):
    start = date_from or settings.analysis_start
    end = date_to or settings.analysis_end
    if start > end:
        raise HTTPException(status_code=422, detail="'from' must not be after 'to'.")
    if start < settings.analysis_start or end > settings.analysis_end:
        raise HTTPException(
            status_code=422,
            detail=f"Dates must fall within the analysis period {settings.analysis_start} to {settings.analysis_end}.",
        )
    return start, end


def _in_range(analysis, start: date, end: date) -> list:
    return [o for o in analysis.observations if start <= o.delivery_date <= end]


def _convention(s: Settings) -> str:
    when = {0: "on the day of delivery", 1: "on the day before delivery"}.get(
        s.cutoff_days_ahead, f"{s.cutoff_days_ahead} days before delivery"
    )
    return (
        f"Assumed decision cutoff: {s.cutoff_time:%H:%M} {s.timezone_name} {when} (the brief does not specify one). "
        "Each interval uses the latest WINDFOR forecast published at or before that cutoff; forecasts published "
        f"after their own interval began are ignored. WINDFOR is {s.forecast_interval_minutes}-minute data, so only "
        "matching FUELHH intervals are compared."
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/overview")
async def overview(store: AnalysisStore = Depends(get_store), settings: Settings = Depends(get_settings)):
    analysis = await store.get()
    metrics = compute_metrics(analysis.observations)
    if metrics["matched_intervals"] == 0:
        status = "empty"
    else:
        status = "partial" if metrics["missing_intervals"] else "ready"
    return {
        "period": {"start": settings.analysis_start.isoformat(), "end": settings.analysis_end.isoformat()},
        "convention": _convention(settings),
        "cutoff": {
            "time": f"{settings.cutoff_time:%H:%M}",
            "timezone": settings.timezone_name,
            "days_ahead": settings.cutoff_days_ahead,
        },
        "resolution_minutes": settings.forecast_interval_minutes,
        "data_status": status,
        "coverage_basis": (
            "coverage_pct = matched_intervals / expected_intervals. Expected is one "
            f"{settings.forecast_interval_minutes}-minute interval per forecast hour in the period. "
            "A missing forecast or actual is null, never zero. Half-hour FUELHH values with no forecast "
            "counterpart are not counted as missing; see data_quality."
        ),
        "metrics": _rounded(metrics),
        "data_quality": analysis.data_quality,
    }


@app.get("/api/forecast-actuals")
async def forecast_actuals(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    store: AnalysisStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    start, end = _resolve_range(date_from, date_to, settings)
    rows = _in_range(await store.get(), start, end)
    return {"count": len(rows), "observations": [_observation_json(o) for o in rows]}


@app.get("/api/accuracy")
async def accuracy(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    store: AnalysisStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    start, end = _resolve_range(date_from, date_to, settings)
    rows = _in_range(await store.get(), start, end)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics": _rounded(compute_metrics(rows)),
        "by_date": {k: _rounded(v) for k, v in breakdown(rows, lambda o: o.delivery_date.isoformat()).items()},
        "by_local_hour": {str(k): _rounded(v) for k, v in breakdown(rows, lambda o: o.local_hour).items()},
    }


@app.get("/api/observations")
async def observations(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    status: Literal["all", "matched", "missing"] = "all",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store: AnalysisStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    start, end = _resolve_range(date_from, date_to, settings)
    rows = _in_range(await store.get(), start, end)
    if status != "all":
        rows = [o for o in rows if (o.error is not None) == (status == "matched")]
    page = rows[offset : offset + limit]
    return {"total": len(rows), "limit": limit, "offset": offset, "observations": [_observation_json(o) for o in page]}
