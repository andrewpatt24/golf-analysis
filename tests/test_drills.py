"""Drill catalog and session store tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.drills.catalog import (
    append_session,
    expected_total_attempts,
    find_drill,
    format_session_summary,
    load_category_catalog,
    load_drill_sessions_doc,
    toggle_favorite,
)


def test_putting_catalog_has_gate_drill() -> None:
    drills = load_category_catalog("putting")
    assert len(drills) >= 21
    gate = next(d for d in drills if d["id"] == "gate_drill")
    assert gate["attempts_per_distance"] == 10
    assert gate["category"] == "putting"
    assert expected_total_attempts(gate) == 20  # 2 distances × 10


def test_chipping_catalog() -> None:
    drills = load_category_catalog("chipping")
    assert len(drills) == 4
    assert all(d.get("category") == "chipping" for d in drills)
    compass = next(d for d in drills if d["id"] == "chip_nsew_compass")
    assert expected_total_attempts(compass) == 64
    par18 = next(d for d in drills if d["id"] == "chip_par_18_challenge")
    assert par18["tracking_type"] == "points_based"
    assert par18["attempts_per_distance"] == 9


def test_catalog_no_duplicate_ids() -> None:
    from golf_analysis.drills.catalog import validate_catalog_no_duplicate_ids

    validate_catalog_no_duplicate_ids()
    ids = []
    from golf_analysis.drills.catalog import load_all_catalog

    for drills in load_all_catalog().values():
        ids.extend(str(d["id"]) for d in drills)
    assert len(ids) == len(set(ids))
    assert len(ids) == 25 + 6  # 21 putting + 4 chipping + 6 range


def test_range_catalog() -> None:
    drills = load_category_catalog("range")
    assert len(drills) == 6
    dispersion = next(d for d in drills if d["id"] == "range_dispersion")
    assert dispersion["tracking_type"] == "club_focus_session"
    assert dispersion["rapsodo_mode"] == "range"
    assert "driver" in dispersion["suggested_clubs"]


def test_club_focus_session_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from golf_analysis.drills.catalog import format_session_summary

    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    row = append_session(
        drill_id="range_dispersion",
        result={"club": "driver", "aim": "20 yd window", "completed": True},
    )
    assert row["result"]["club"] == "driver"
    found = find_drill("range_dispersion")
    assert found is not None
    summary = format_session_summary(row, found[1])
    assert "driver" in summary
    assert "✓" in summary


def test_session_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    row = append_session(drill_id="gate_drill", result={"score": 8, "total": 10})
    assert row["drill_id"] == "gate_drill"
    doc = load_drill_sessions_doc()
    assert len(doc["sessions"]) == 1
    found = find_drill("gate_drill")
    assert found is not None
    summary = format_session_summary(doc["sessions"][0], found[1])
    assert summary == "8/10"


def test_favorites_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    favs = toggle_favorite("six_foot_test")
    assert "six_foot_test" in favs
    favs = toggle_favorite("six_foot_test")
    assert "six_foot_test" not in favs


def test_drill_session_stats_and_enriched_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timedelta, timezone

    from golf_analysis.drills.catalog import (
        days_since_last_played,
        drill_session_stats,
        enrich_drill,
        expected_duration_minutes,
    )

    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    gate = next(d for d in load_category_catalog("putting") if d["id"] == "gate_drill")
    gate_duration = expected_duration_minutes(gate)
    assert gate_duration is not None and gate_duration > 0

    append_session(drill_id="gate_drill", result={"score": 8, "total": 10})
    stats = drill_session_stats()
    assert stats["gate_drill"]["session_count"] == 1
    assert stats["gate_drill"]["last_played_at"]
    assert stats["gate_drill"]["days_since_last_played"] == 0

    enriched = enrich_drill(gate, stats=stats)
    assert enriched["expected_duration_minutes"] == gate_duration
    assert enriched["session_count"] == 1
    assert enriched["last_played_at"] is not None

    unplayed = enrich_drill(next(d for d in load_category_catalog("putting") if d["id"] == "six_foot_test"), stats=stats)
    assert unplayed["session_count"] == 0
    assert unplayed["last_played_at"] is None
    assert unplayed["days_since_last_played"] is None

    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    assert days_since_last_played(old) == 5


def test_drills_api_enriched_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from golf_analysis.drills.catalog import expected_duration_minutes

    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(tmp_path / "lib.db"))
    monkeypatch.setenv("GOLF_ACCESS_TOKENS_FILE", str(tmp_path / "access_tokens.json"))
    monkeypatch.delenv("GOLF_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOLF_ACCESS_TOKENS", raising=False)
    client = TestClient(create_app())

    append_session(drill_id="gate_drill", result={"score": 9, "total": 10})

    r = client.get("/api/v1/drills/catalog?category=putting")
    assert r.status_code == 200
    gate = next(d for d in r.json()["drills"] if d["id"] == "gate_drill")
    assert gate["expected_duration_minutes"] == expected_duration_minutes(
        next(d for d in load_category_catalog("putting") if d["id"] == "gate_drill")
    )
    assert gate["session_count"] == 1
    assert gate["last_played_at"]
    assert gate["days_since_last_played"] == 0


def test_drill_override_and_session_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timedelta, timezone

    from golf_analysis.drills.catalog import (
        delete_session,
        load_effective_category_catalog,
        reset_drill_overrides,
        update_drill,
        update_session,
    )

    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    row = append_session(drill_id="gate_drill", result={"score": 8, "total": 10}, notes="first try")

    updated = update_drill("gate_drill", {"expected_duration_minutes": 25, "title": "My Gate Drill"})
    assert updated["expected_duration_minutes"] == 25
    assert updated["title"] == "My Gate Drill"
    effective = next(d for d in load_effective_category_catalog("putting") if d["id"] == "gate_drill")
    assert effective["expected_duration_minutes"] == 25

    old_time = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    edited = update_session(
        row["id"],
        result={"score": 9, "total": 10},
        notes="corrected",
        logged_at=old_time,
    )
    assert edited["result"]["score"] == 9
    assert edited["notes"] == "corrected"
    assert edited["logged_at"].startswith(old_time[:10])

    delete_session(row["id"])
    doc = load_drill_sessions_doc()
    assert doc["sessions"] == []

    reset = reset_drill_overrides("gate_drill")
    assert reset["title"] == "The Gate Drill"
    doc = load_drill_sessions_doc()
    assert "gate_drill" not in doc.get("overrides", {})


def test_drills_api_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(tmp_path / "lib.db"))
    monkeypatch.setenv("GOLF_ACCESS_TOKENS_FILE", str(tmp_path / "access_tokens.json"))
    monkeypatch.delenv("GOLF_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOLF_ACCESS_TOKENS", raising=False)
    client = TestClient(create_app())

    row = append_session(drill_id="gate_drill", result={"score": 7, "total": 10})

    r = client.patch("/api/v1/drills/gate_drill", json={"expected_duration_minutes": 30})
    assert r.status_code == 200
    assert r.json()["expected_duration_minutes"] == 30
    assert r.json()["is_customized"] is True

    r = client.patch(
        f"/api/v1/drills/sessions/{row['id']}",
        json={"result": {"score": 10, "total": 10}, "notes": "perfect"},
    )
    assert r.status_code == 200
    assert r.json()["summary"] == "10/10"
    assert r.json()["notes"] == "perfect"

    r = client.delete(f"/api/v1/drills/sessions/{row['id']}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_drills_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DRILL_SESSIONS", str(tmp_path / "drill_sessions.json"))
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(tmp_path / "lib.db"))
    monkeypatch.setenv("GOLF_ACCESS_TOKENS_FILE", str(tmp_path / "access_tokens.json"))
    monkeypatch.delenv("GOLF_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOLF_ACCESS_TOKENS", raising=False)
    client = TestClient(create_app())

    r = client.get("/api/v1/drills/catalog?category=putting")
    assert r.status_code == 200
    assert len(r.json()["drills"]) >= 21

    r = client.post(
        "/api/v1/drills/sessions",
        json={"drill_id": "streak_builder", "result": {"streak": 12}},
    )
    assert r.status_code == 200
    assert r.json()["summary"] == "Streak 12"

    r = client.get("/api/v1/drills/sessions?drill_id=streak_builder")
    assert r.status_code == 200
    assert len(r.json()["sessions"]) == 1
