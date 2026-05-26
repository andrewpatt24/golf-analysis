"""Tests for FastAPI dashboard API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.repository import connect, init_schema


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "dashboard_settings.json"))
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_meta_empty_db(client: TestClient) -> None:
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    j = r.json()
    assert j["golf_rounds"] == 0
    assert j["range_shots"] == 0


def test_settings_roundtrip(client: TestClient) -> None:
    r = client.get("/api/v1/settings")
    assert r.status_code == 200
    assert r.json()["maxRounds"] == 10
    assert r.json()["troubleMinAvgStablefordPoints"] == 1.0
    assert r.json()["stablefordColorGreenMin"] == 2.0
    assert r.json()["stablefordColorYellowMin"] == 1.0
    assert r.json()["avgPuttsHighThreshold"] == 2.25
    assert r.json()["trainingDispersionRatioFlag"] == 0.1
    assert r.json()["excludedTrainingClubs"] == []
    r2 = client.put("/api/v1/settings", json={"maxRounds": 12, "calendarYear": 2026})
    assert r2.status_code == 200
    assert r2.json()["maxRounds"] == 12


def test_strategy_status(client: TestClient) -> None:
    r = client.get("/api/v1/strategy/status")
    assert r.status_code == 200
    assert r.json()["esz_dsz_in_sql"] is False


def test_strategy_overview_no_garmin_file(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(tmp_path / "missing-garmin.json"))
    r = client.get("/api/v1/strategy/overview?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["source_available"] is False
    assert j["esz_dsz_in_sql"] is False
    assert j["scoring_method"]["rounds"] == 0


def test_strategy_overview_with_fixture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(fixture))
    r = client.get("/api/v1/strategy/overview?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["source_available"] is True
    assert len(j["scorecards"]) == 1
    assert j["performance"]["mean_strokes_per_round"] == 8.0
    esz = j["esz_dsz_from_shots"]
    assert esz["holes_evaluated"] == 2
    assert len(esz["by_round"]) == 1
    assert esz["by_round"][0]["scorecard_id"] == "999001"
    assert esz["by_round"][0]["holes_evaluated"] == 2
    assert esz["by_round"][0]["dsz_success_holes"] == 1
    assert esz["dsz_success_holes"] == 1
    assert abs(float(esz["dsz_pct"] or 0) - 50.0) < 0.01
    diag = esz.get("diagnostics") or {}
    assert diag.get("dsz_basis_score_minus_tracked_outside") == 2
    assert "data_model" in esz and isinstance(esz["data_model"], dict)


def test_performance_garmin_bundle_with_fixture(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(fixture))
    r = client.get("/api/v1/performance/garmin-bundle?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["available"] is True
    assert j["round_rollups"]["rounds"] == 1


def test_range_analytics_takeaways(client: TestClient) -> None:
    r = client.get("/api/v1/range/analytics?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert "takeaways" in j
    assert isinstance(j["takeaways"], list)
    assert isinstance(j["shot_shape"], dict)


def test_range_club_compare_ok(client: TestClient) -> None:
    r = client.get("/api/v1/range/club-compare?year=2026&club_a=driver&club_b=3w")
    assert r.status_code == 200
    j = r.json()
    assert "club_a" in j
    assert j.get("error") is None


def test_access_token_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    app = create_app()
    client = TestClient(app)

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/meta").status_code == 401
    assert client.get("/api/v1/meta?token=secret-token").status_code == 200
    assert (
        client.get("/api/v1/meta", headers={"Authorization": "Bearer secret-token"}).status_code
        == 200
    )
    assert client.get("/assets/app.js").status_code != 401


def test_access_token_cookie(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    client = TestClient(create_app())

    r = client.get("/api/v1/meta?token=secret-token")
    assert r.status_code == 200
    assert client.cookies.get("golf_access_token") == "secret-token"
    assert client.get("/api/v1/meta").status_code == 200
