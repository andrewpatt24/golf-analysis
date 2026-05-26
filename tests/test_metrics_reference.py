"""Tests for canonical metrics reference API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.metrics_reference import PROXY_ESZ, build_metrics_reference, proxy_tile_spec
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


def test_build_metrics_reference_has_esz_dsz() -> None:
    doc = build_metrics_reference()
    assert doc["version"] == 1
    assert doc["scoring_zone"]["esz"]["title"] == PROXY_ESZ["title"]
    assert any(t["key"] == "proxy_dsz" for t in doc["proxy_tiles"])
    assert len(doc["trends"]["metrics"]) >= 10


def test_proxy_tile_spec_known_keys() -> None:
    assert proxy_tile_spec("proxy_fairway")["title"] == "Fairway"
    assert proxy_tile_spec("unknown") is None


def test_reference_endpoint(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(tmp_path / "missing.json"))
    r = client.get("/api/v1/reference?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == 1
    assert j["year"] == 2026
    assert j["engine_snapshot"]["source_available"] is False
    assert "proxy_tiles" in j
