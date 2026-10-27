from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app, get_settings, get_store
from services.store import AnalysisStore
from settings import Settings

UTC = timezone.utc
SETTINGS = Settings(analysis_start=datetime(2026, 1, 2).date(), analysis_end=datetime(2026, 1, 3).date())
RUN_TIMES = [(2, 30), (4, 30), (7, 30), (9, 30), (11, 30), (15, 30), (18, 30), (22, 30)]


def _stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _forecast_rows():
    rows = []
    for day in (datetime(2025, 12, 31, tzinfo=UTC) + timedelta(days=n) for n in range(4)):
        for hour, minute in RUN_TIMES:
            published = day.replace(hour=hour, minute=minute)
            first_hour = published.replace(minute=0) - timedelta(hours=2)
            for k in range(60):
                rows.append({
                    "dataset": "WINDFOR", "publishTime": _stamp(published),
                    "startTime": _stamp(first_hour + timedelta(hours=k)), "generation": 5000 + hour,
                })
    return rows


def _actual_rows(skip=()):
    start = datetime(2026, 1, 2, tzinfo=UTC)
    return [
        {"dataset": "FUELHH", "fuelType": "WIND", "startTime": _stamp(start + timedelta(minutes=30 * i)),
         "publishTime": "2026-02-01T00:00:00Z", "generation": 5100}
        for i in range(96) if i not in skip
    ]


def _store(forecasts, actuals, status=200):
    def handler(request):
        if request.url.path.endswith("/datasets/FUELHH/stream"):
            return httpx.Response(status, json=actuals)
        return httpx.Response(status, json={"data": forecasts})

    return AnalysisStore(SETTINGS, transport=httpx.MockTransport(handler))


def _client(store):
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_does_not_need_upstream():
    assert _client(_store([], [], status=500)).get("/health").json() == {"status": "ok"}


def test_overview_matches_frontend_contract():
    body = _client(_store(_forecast_rows(), _actual_rows())).get("/api/overview").json()
    assert body["period"] == {"start": "2026-01-02", "end": "2026-01-03"}
    assert "17:00 Europe/London" in body["convention"]
    assert body["data_status"] == "ready"
    metrics = body["metrics"]
    assert metrics["expected_intervals"] == 48 and metrics["matched_intervals"] == 48
    assert metrics["missing_intervals"] == 0 and metrics["coverage_pct"] == 100.0
    assert body["data_quality"]["actual_intervals_in_window"] == 96
    assert body["data_quality"]["actual_intervals_not_compared"] == 48
    assert "never zero" in body["coverage_basis"]


def test_forecast_actuals_uses_cutoff_forecast_and_filters_dates():
    client = _client(_store(_forecast_rows(), _actual_rows()))
    rows = client.get("/api/forecast-actuals").json()["observations"]
    assert len(rows) == 48
    assert rows[0]["startTime"] == "2026-01-02T00:00:00Z"
    assert rows[0]["publishTime"] == "2026-01-01T15:30:00Z"  # 18:30 run is after the 17:00 cutoff
    assert rows[0]["error_mw"] == rows[0]["forecast_mw"] - rows[0]["actual_mw"]
    one_day = client.get("/api/forecast-actuals", params={"from": "2026-01-03", "to": "2026-01-03"}).json()
    assert one_day["count"] == 24 and one_day["observations"][0]["startTime"] == "2026-01-03T00:00:00Z"


def test_missing_actuals_are_null_and_partial():
    client = _client(_store(_forecast_rows(), _actual_rows(skip={0, 1})))  # drops 00:00 and 00:30
    body = client.get("/api/overview").json()
    assert body["data_status"] == "partial" and body["metrics"]["missing_intervals"] == 1
    first = client.get("/api/forecast-actuals").json()["observations"][0]
    assert first["actual_mw"] is None and first["error_mw"] is None and first["forecast_mw"] is not None


def test_accuracy_has_breakdowns():
    body = _client(_store(_forecast_rows(), _actual_rows())).get("/api/accuracy").json()
    assert set(body["by_date"]) == {"2026-01-02", "2026-01-03"}
    assert len(body["by_local_hour"]) == 24 and body["metrics"]["mae_mw"] is not None


def test_observations_pagination_and_status_filter():
    client = _client(_store(_forecast_rows(), _actual_rows(skip={0, 1})))
    page = client.get("/api/observations", params={"limit": 10, "offset": 5}).json()
    assert page["total"] == 48 and len(page["observations"]) == 10
    assert client.get("/api/observations", params={"status": "missing"}).json()["total"] == 1
    assert client.get("/api/observations", params={"limit": 0}).status_code == 422


def test_bad_date_ranges_return_422():
    client = _client(_store(_forecast_rows(), _actual_rows()))
    assert client.get("/api/forecast-actuals", params={"from": "2026-01-03", "to": "2026-01-02"}).status_code == 422
    assert client.get("/api/forecast-actuals", params={"from": "2025-12-01"}).status_code == 422
    assert client.get("/api/forecast-actuals", params={"from": "nonsense"}).status_code == 422


def test_upstream_failure_returns_502_not_fake_data():
    response = _client(_store(_forecast_rows(), _actual_rows(), status=500)).get("/api/overview")
    assert response.status_code == 502 and "500" in response.json()["detail"]


def test_empty_upstream_returns_502():
    response = _client(_store([], [])).get("/api/overview")
    assert response.status_code == 502 and "no FUELHH" in response.json()["detail"]


def test_missing_values_are_reported_as_missing_never_as_zero():
    forecasts = [r for r in _forecast_rows() if r["startTime"] not in ("2026-01-02T05:00:00Z", "2026-01-02T06:00:00Z")]
    for row in forecasts:
        if row["startTime"] == "2026-01-02T18:00:00Z":
            row["generation"] = None  # rows exist but carry no value
    actuals = [r for r in _actual_rows() if r["startTime"] != "2026-01-02T10:00:00Z"]
    for row in actuals:
        if row["startTime"] == "2026-01-02T14:00:00Z":
            row["generation"] = 0  # a genuine zero: must stay zero and count as matched

    client = _client(_store(forecasts, actuals))
    overview = client.get("/api/overview").json()
    m = overview["metrics"]
    assert (m["expected_intervals"], m["matched_intervals"], m["missing_intervals"]) == (48, 44, 4)
    assert m["forecast_missing_intervals"] == 3 and m["actual_missing_intervals"] == 1
    assert m["coverage_pct"] == round(44 / 48 * 100, 2)
    assert overview["data_status"] == "partial"
    assert overview["data_quality"]["malformed_forecast_rows"] > 0

    response = client.get("/api/forecast-actuals")
    assert '"error_mw":null' in response.text and "NaN" not in response.text
    rows = {r["startTime"]: r for r in response.json()["observations"]}
    for hour in ("05", "06", "18"):
        row = rows[f"2026-01-02T{hour}:00:00Z"]
        assert row["forecast_mw"] is None and row["error_mw"] is None and row["actual_mw"] == 5100
    row = rows["2026-01-02T10:00:00Z"]
    assert row["actual_mw"] is None and row["error_mw"] is None and row["forecast_mw"] is not None
    row = rows["2026-01-02T14:00:00Z"]
    assert row["actual_mw"] is not None and row["actual_mw"] == 0 and row["error_mw"] == row["forecast_mw"]

    matched = [r for r in rows.values() if r["error_mw"] is not None]
    assert len(matched) == 44
    assert abs(m["mae_mw"] - sum(abs(r["error_mw"]) for r in matched) / 44) < 0.01
    zero_filled = [abs((r["forecast_mw"] or 0) - (r["actual_mw"] or 0)) for r in rows.values()]
    assert abs(sum(zero_filled) / 48 - m["mae_mw"]) > 100  # zero-filling would give a very different MAE


def test_day_with_no_actuals_has_null_metrics_not_zero():
    actuals = [r for r in _actual_rows() if not r["startTime"].startswith("2026-01-03")]
    client = _client(_store(_forecast_rows(), actuals))
    m = client.get("/api/overview").json()["metrics"]
    assert m["missing_intervals"] == 24 and m["coverage_pct"] == 50.0
    day = client.get("/api/accuracy").json()["by_date"]["2026-01-03"]
    assert day["matched_intervals"] == 0 and day["mae_mw"] is None and day["bias_mw"] is None
    empty = client.get("/api/accuracy", params={"from": "2026-01-03", "to": "2026-01-03"}).json()["metrics"]
    assert empty["mae_mw"] is None and empty["rmse_mw"] is None and empty["bias_mw"] is None
    assert empty["coverage_pct"] == 0.0 and empty["missing_intervals"] == 24
