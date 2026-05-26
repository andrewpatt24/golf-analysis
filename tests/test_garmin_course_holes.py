"""Tests for per-course hole coach analytics."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.main import create_app
from golf_analysis.garmin_course_holes import (
    attach_hole_compare,
    build_course_scoring_stats,
    build_hole_coach,
    course_detail_from_export,
    course_slug,
    iter_hole_plays,
    list_courses_from_export,
)
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


def test_course_slug() -> None:
    assert course_slug("Fixture Links") == "fixture-links"


def test_stroke_index_on_course_detail() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "si-sc",
                            "startTime": "2026-07-01T12:00:00Z",
                            "courseName": "Index Course",
                            "holePars": "44",
                            "courseHandicapStr": "071706131408151001040218111605120309",
                            "holes": [
                                {"number": 1, "strokes": 5, "typeScore": 2},
                                {"number": 2, "strokes": 4, "typeScore": 2},
                            ],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [],
    }
    detail = course_detail_from_export(data, "index-course", calendar_year=2026)
    assert detail is not None
    h1 = next(h for h in detail["holes"] if h["hole_number"] == 1)
    h2 = next(h for h in detail["holes"] if h["hole_number"] == 2)
    assert h1["stroke_index"] == 7
    assert h2["stroke_index"] == 17


def test_par_from_hole_pars_string() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc-par",
                            "startTime": "2026-06-01T12:00:00Z",
                            "courseName": "Par Test",
                            "holePars": "434",
                            "holes": [
                                {"number": 1, "strokes": 5, "putts": 2},
                                {"number": 2, "strokes": 4, "putts": 2},
                                {"number": 3, "strokes": 6, "putts": 2},
                            ],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [],
    }
    plays = iter_hole_plays(data, calendar_year=2026)
    assert len(plays) == 3
    assert plays[0]["par"] == 4
    assert plays[0]["score_vs_par"] == 1
    detail = course_detail_from_export(data, "par-test", calendar_year=2026)
    assert detail is not None
    h1 = next(h for h in detail["holes"] if h["hole_number"] == 1)
    assert h1["avg_score"] == 5.0
    assert h1["avg_vs_par"] == 1.0


def test_list_and_detail_from_minimal_fixture() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    import json

    data = json.loads(fixture.read_text(encoding="utf-8"))
    listed = list_courses_from_export(data, calendar_year=2026, min_rounds=1)
    assert len(listed["courses"]) == 1
    c0 = listed["courses"][0]
    assert c0["course_name"] == "Fixture Links"
    slug = c0["course_slug"]
    detail = course_detail_from_export(data, slug, calendar_year=2026)
    assert detail is not None
    assert detail["course_name"] == "Fixture Links"
    assert len(detail["holes"]) == 2
    h1 = next(h for h in detail["holes"] if h["hole_number"] == 1)
    assert h1["plays_count"] == 1
    assert "coach" in h1
    assert h1["coach"]["headline"]
    assert len(h1["coach"]["sections"]) >= 1


def test_trouble_hole_avg_stableford_below_threshold() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sf1",
                            "startTime": "2026-03-01T12:00:00Z",
                            "courseName": "Stableford Test",
                            "holePars": "44",
                            "holes": [
                                {"number": 1, "strokes": 7, "typeScore": 0},
                                {"number": 2, "strokes": 6, "typeScore": 0},
                            ],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [],
    }
    detail = course_detail_from_export(
        data, "stableford-test", calendar_year=2026, trouble_min_avg_stableford=1.0
    )
    assert detail is not None
    h1 = next(h for h in detail["holes"] if h["hole_number"] == 1)
    assert h1["avg_stableford_points"] == 0.0
    assert h1["trouble_hole"] is True
    assert "Stableford" in h1["trouble_reasons"][0]

    data_ok = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sf2",
                            "startTime": "2026-04-01T12:00:00Z",
                            "courseName": "Stableford OK",
                            "holePars": "4",
                            "holes": [
                                {"number": 1, "strokes": 4, "typeScore": 2},
                                {"number": 1, "strokes": 5, "typeScore": 1},
                            ],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [],
    }
    detail_ok = course_detail_from_export(
        data_ok, "stableford-ok", calendar_year=2026, trouble_min_avg_stableford=1.0
    )
    assert detail_ok is not None
    h1_ok = next(h for h in detail_ok["holes"] if h["hole_number"] == 1)
    assert h1_ok["avg_stableford_points"] == 1.5
    assert h1_ok["trouble_hole"] is False


def test_build_hole_coach_penalty_pattern() -> None:
    agg = {
        "plays_count": 4,
        "par": 4,
        "avg_vs_par": 1.8,
        "penalty_rate": 0.5,
        "penalty_count": 2,
        "esz_evaluated_count": 2,
        "esz_miss_rate": 0.75,
        "esz_success_rate": 0.25,
        "dsz_eligible_count": 1,
        "dsz_success_rate": 0.0,
        "fairway_decided": 4,
        "fairway_hit": 1,
        "fairway_left": 0,
        "fairway_right": 3,
        "blowup_count": 0,
        "avg_putts": 2.0,
    }
    coach = build_hole_coach(agg, hole_number=7)
    assert "penalt" in coach["headline"].lower() or "penalt" in coach["sections"][0]["body"].lower()
    titles = [s["title"] for s in coach["sections"]]
    assert "Tee shot plan" in titles


def test_strategy_courses_api(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(fixture))
    r = client.get("/api/v1/strategy/courses?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["source_available"] is True
    assert len(j["courses"]) == 1


def test_course_scoring_stats_by_par_and_compare() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc-par-stats",
                            "startTime": "2026-06-01T12:00:00Z",
                            "courseName": "Par Stats",
                            "holePars": "434",
                            "holes": [
                                {"number": 1, "strokes": 4, "putts": 2, "typeScore": 2},
                                {"number": 2, "strokes": 5, "putts": 2, "typeScore": 1},
                                {"number": 3, "strokes": 6, "putts": 3, "typeScore": 0},
                            ],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [],
    }
    plays = iter_hole_plays(data, calendar_year=2026)
    stats = build_course_scoring_stats(plays)
    assert stats["overall"]["avg_stableford_points"] == 1.0
    assert stats["by_par"]["3"]["avg_stableford_points"] == 1.0
    assert stats["by_par"]["4"]["avg_stableford_points"] == 1.0
    assert stats["by_par"]["4"]["diff_vs_course_overall_pct"]["avg_stableford_points"] == 0.0

    detail = course_detail_from_export(data, "par-stats", calendar_year=2026)
    assert detail is not None
    assert "scoring_stats" in detail
    h3 = next(h for h in detail["holes"] if h["hole_number"] == 3)
    assert h3["compare"] is not None
    sf = h3["compare"]["metrics"]["avg_stableford_points"]
    assert sf["value"] == 0.0
    assert sf["diff_vs_course_overall_pct"] == -100.0
    assert sf["diff_vs_par_on_course_pct"] == -100.0

    cmp = attach_hole_compare({"par": 4, "esz_success_rate": 0.5, "esz_evaluated_count": 2}, stats)
    assert cmp is not None
    assert cmp["metrics"]["esz_pct"]["value"] == 50.0

    assert attach_hole_compare({"par": 4, "esz_evaluated_count": 0}, stats) is None


def test_strategy_course_detail_api(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(fixture))
    r = client.get("/api/v1/strategy/courses/fixture-links?year=2026")
    assert r.status_code == 200
    j = r.json()
    assert j["found"] is True
    assert len(j["holes"]) == 2
    assert j["holes"][0]["coach"]["sections"]
    assert "scoring_stats" in j
    assert "overall" in j["scoring_stats"]
