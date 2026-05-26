"""Manual course catalog and pre-round hole planning."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.course_layout.manual_courses import get_manual_course, list_manual_courses
from golf_analysis.on_course_prep import (
    build_on_course_prep,
    pick_club_for_carry,
)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "lib.db"
    from golf_analysis.repository import connect, init_schema

    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("GOLF_ON_COURSE_PLAYBOOK", str(tmp_path / "playbook.json"))
    return TestClient(create_app())


def test_woldingham_manual_catalog() -> None:
    courses = list_manual_courses()
    assert any(c["course_slug"] == "woldingham-white" for c in courses)
    layout = get_manual_course("woldingham-white")
    assert layout is not None
    assert layout["course_name"] == "Woldingham Golf Club"
    assert layout["par_total"] == 71
    assert layout["yardage_total"] == 6376
    assert len(layout["holes"]) == 18
    assert layout["holes"][0]["hole_number"] == 1
    assert layout["holes"][0]["yardage_yards"] == 383
    assert layout["holes"][-1]["hole_number"] == 18
    assert layout["holes"][-1]["yardage_yards"] == 491


def test_pick_club_for_carry() -> None:
    clubs = [
        {"club": "driver", "mean_carry_yards": 250, "needs_work": False},
        {"club": "7i", "mean_carry_yards": 160, "needs_work": False},
    ]
    club, carry = pick_club_for_carry(165, clubs)
    assert club == "7i"
    assert carry == 160


def test_build_prep_par3_and_profile() -> None:
    clubs = [
        {"club": "driver", "mean_carry_yards": 250, "needs_work": False},
        {"club": "pw", "mean_carry_yards": 120, "needs_work": False},
    ]
    out = build_on_course_prep(
        course_slug="woldingham-white",
        calendar_year=2026,
        clubs=clubs,
        garmin_export=None,
    )
    assert out["course_name"] == "Woldingham Golf Club"
    assert out["tee_name"] == "White"
    assert len(out["holes"]) == 18
    h2 = next(h for h in out["holes"] if h["hole_number"] == 2)
    assert h2["par"] == 3
    assert "166" in h2["plan"] or "PW" in h2["plan"].upper()
    assert out["game_profile"]["headline"]


def test_prep_api(client: TestClient) -> None:
    r = client.get("/api/v1/on-course/prep/courses")
    assert r.status_code == 200
    slugs = [c["course_slug"] for c in r.json()["courses"]]
    assert "woldingham-white" in slugs

    r2 = client.get("/api/v1/on-course/prep/woldingham-white?year=2026")
    assert r2.status_code == 200
    j = r2.json()
    assert j["holes"][11]["hole_number"] == 12
    assert j["holes"][11]["yardage_yards"] == 410
    assert "plan" in j["holes"][0]
    assert "swing" not in j["summary_line"].lower()

    r404 = client.get("/api/v1/on-course/prep/unknown-course")
    assert r404.status_code == 404
