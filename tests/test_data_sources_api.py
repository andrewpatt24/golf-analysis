"""Data sources API."""

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
    monkeypatch.setenv("GOLF_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(tmp_path / "secrets.json"))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("GOLF_ON_COURSE_PLAYBOOK", str(tmp_path / "playbook.json"))
    return TestClient(create_app())


def test_list_data_sources(client: TestClient) -> None:
    r = client.get("/api/v1/data-sources")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()["sources"]}
    assert "rapsodo" in ids
    assert "garmin_golf" in ids


def test_put_rapsodo_credentials(client: TestClient) -> None:
    r = client.put(
        "/api/v1/data-sources/credentials/rapsodo",
        json={"bearer": "x" * 20, "authorization_scheme": "JWT"},
    )
    assert r.status_code == 200
    assert r.json()["credentials"]["rapsodo"]["configured"] is True
    assert r.json()["persisted_to_cloud"] is False


def test_put_rapsodo_persists_to_gcs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOLF_DATA_BUCKET", "test-bucket")
    called: list[bool] = []

    def fake_upload() -> bool:
        called.append(True)
        return True

    monkeypatch.setattr(
        "golf_analysis.api.routers.data_sources.upload_credentials_to_gcs",
        fake_upload,
    )
    r = client.put(
        "/api/v1/data-sources/credentials/rapsodo",
        json={"bearer": "y" * 20, "authorization_scheme": "JWT"},
    )
    assert r.status_code == 200
    assert r.json()["persisted_to_cloud"] is True
    assert called


def test_garth_json_credentials(client: TestClient, tmp_path: Path) -> None:
    token = '{"access_token": "abc", "refresh_token": "def", "token_type": "bearer"}'
    r = client.post(
        "/api/v1/data-sources/credentials/garth-json",
        json={"content": token},
    )
    assert r.status_code == 200
    assert (tmp_path / "garth" / "oauth2_token.json").is_file()
    assert r.json()["credentials"]["garmin"]["configured"] is True


def test_import_local_blocked_on_cloud(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DATA_BUCKET", "test-bucket")
    r = client.post("/api/v1/data-sources/credentials/import-local")
    assert r.status_code == 400


def test_refresh_starts_job(client: TestClient) -> None:
    r = client.post("/api/v1/data-sources/local_ingest/refresh")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    import time

    for _ in range(30):
        j = client.get(f"/api/v1/data-sources/jobs/{job_id}")
        assert j.status_code == 200
        if j.json()["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.2)
    assert j.json()["status"] in ("succeeded", "failed")
