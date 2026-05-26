"""On-course playbook and strategy API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.api.on_course_playbook_store import load_playbook, save_playbook
from golf_analysis.on_course_strategy import build_on_course_course_summary
from golf_analysis.repository import connect, init_schema


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("GOLF_ON_COURSE_PLAYBOOK", str(tmp_path / "playbook.json"))
    return TestClient(create_app())


def test_playbook_defaults_and_save(client: TestClient, tmp_path: Path) -> None:
    r = client.get("/api/v1/on-course/playbook")
    assert r.status_code == 200
    j = r.json()
    assert j["swingCue"] == "TEMPO"
    assert "puttingRoutine" in j
    assert "Dominant eye" in j["puttingRoutine"]
    assert len(j["pitchRows"]) == 7

    r2 = client.put(
        "/api/v1/on-course/playbook",
        json={"swingCue": "SMOOTH", "chipNotes": "Putt when you can"},
    )
    assert r2.status_code == 200
    assert r2.json()["swingCue"] == "SMOOTH"
    assert r2.json()["chipNotes"] == "Putt when you can"
    assert load_playbook()["swingCue"] == "SMOOTH"


def test_on_course_yardages_filter(client: TestClient, tmp_path: Path) -> None:
    r = client.get("/api/v1/on-course/yardages?year=2026&min_carry=100")
    assert r.status_code == 200
    assert "clubs" in r.json()


def test_course_strategy_where_focus(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(fixture))
    courses = client.get("/api/v1/on-course/courses?year=2026").json()["courses"]
    assert courses
    slug = courses[0]["course_slug"]
    r = client.get(f"/api/v1/on-course/course-strategy/{slug}?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["course_name"]
    assert "attack_holes" in j
    assert "where_to_improve" in j["holes"][0]
    assert "top_improvement" in j["holes"][0]
    assert "note" in j
    assert "swing" not in j["summary_line"].lower()


def test_build_on_course_course_summary_trouble() -> None:
    holes = [
        {
            "hole_number": 1,
            "par": 4,
            "stroke_index": 5,
            "yardage_yards": 400,
            "plays_count": 2,
            "avg_vs_par": 1.5,
            "avg_stableford_points": 0.5,
            "trouble_hole": True,
            "trouble_reasons": ["Low Stableford avg (0.50 < 1.0)"],
            "penalty_rate": 0.35,
            "penalty_count": 1,
            "fairway_decided": 2,
            "fairway_hit": 0,
            "fairway_left": 1,
            "fairway_right": 1,
            "esz_evaluated_count": 0,
            "blowup_count": 0,
        },
        {
            "hole_number": 2,
            "par": 3,
            "stroke_index": 12,
            "yardage_yards": 180,
            "plays_count": 2,
            "avg_vs_par": 0.0,
            "avg_stableford_points": 2.5,
            "trouble_hole": False,
            "trouble_reasons": [],
        },
    ]
    out = build_on_course_course_summary(
        course_name="Test",
        course_slug="test",
        rounds_count=1,
        holes=holes,
    )
    assert 2 in out["attack_holes"]
    assert 1 in out["caution_holes"]
    assert out["holes"][0]["where_to_improve"]
    assert "driver" in out["holes"][0]["top_improvement"].lower() or "lay up" in out["holes"][0]["top_improvement"].lower()


def test_build_hole_top_improvement_penalties() -> None:
    from golf_analysis.on_course_strategy import build_hole_top_improvement

    tip = build_hole_top_improvement(
        {
            "penalty_rate": 0.4,
            "fairway_decided": 3,
            "fairway_hit": 1,
            "fairway_left": 0,
            "fairway_right": 2,
            "esz_evaluated_count": 0,
            "blowup_count": 0,
        }
    )
    assert "driver" in tip.lower() or "lay up" in tip.lower()
