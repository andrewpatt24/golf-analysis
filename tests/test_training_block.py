"""Training block planner and API tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.training_block_planner import build_training_block
from golf_analysis.training_block_store import get_active_block, load_training_block_doc


def test_build_training_block_assigns_drills() -> None:
    block = build_training_block(
        calendar_year=2026,
        n_sessions=4,
        garmin_scoring={"rounds": 5, "proxy_putting_load": {"putts_per_hole": 2.05}},
        rapsodo_insights=["7i: dispersion focus"],
        flagged_clubs=["driver", "5w", "3h"],
    )
    assert block["sessions_planned"] == 4
    assert len(block["sessions"]) == 4
    assert block["coach_summary"]
    assert all(s.get("drill_id") for s in block["sessions"])
    assert any(s["drill_id"].startswith("range_") for s in block["sessions"])
    ids = [s["drill_id"] for s in block["sessions"]]
    assert len(ids) == len(set(ids))


def test_training_block_api_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_TRAINING_BLOCK", str(tmp_path / "training_block.json"))
    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(tmp_path / "lib.db"))
    monkeypatch.setenv("GOLF_ACCESS_TOKENS_FILE", str(tmp_path / "access_tokens.json"))
    monkeypatch.delenv("GOLF_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOLF_ACCESS_TOKENS", raising=False)

    db = tmp_path / "lib.db"
    db.write_bytes(b"")

    client = TestClient(create_app())

    r = client.get("/api/v1/plans/training-block")
    assert r.status_code == 200
    body = r.json()
    assert body["sessions_planned"] >= 1
    assert body["coach_summary"]
    assert body["sessions"][0]["drill_id"]

    idx = body["sessions"][0]["index"]
    r = client.patch(f"/api/v1/plans/training-block/sessions/{idx}/complete", json={})
    assert r.status_code == 200
    assert r.json()["sessions"][0]["completed_at"]

    r = client.post("/api/v1/plans/training-block/regenerate")
    assert r.status_code == 400

    for s in body["sessions"]:
        client.patch(f"/api/v1/plans/training-block/sessions/{s['index']}/complete", json={})

    r = client.post("/api/v1/plans/training-block/regenerate")
    assert r.status_code == 200
    assert r.json()["block_id"] != body["block_id"]

    assert get_active_block() is not None
    assert load_training_block_doc()["active_block"] is not None
