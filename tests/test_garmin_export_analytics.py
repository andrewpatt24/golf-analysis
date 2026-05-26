"""Unit tests for Garmin export analytics helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from golf_analysis.garmin_export_analytics import (
    iter_scorecards,
    load_garmin_export,
    performance_round_rollups,
    scoring_method_proxy_metrics,
    scoring_method_proxy_metrics_from_export,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"


def test_load_garmin_export_missing() -> None:
    assert load_garmin_export(None) is None
    assert load_garmin_export(Path("/nonexistent/no.json")) is None


def test_iter_scorecards_fixture_year_filter() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    rows_2026 = iter_scorecards(data, calendar_year=2026, limit=10)
    assert len(rows_2026) == 1
    assert rows_2026[0]["course_name"] == "Fixture Links"
    assert rows_2026[0]["strokes"] == 8
    assert rows_2026[0]["stableford_zero_point_holes"] == 1
    assert rows_2026[0]["stableford_holes_tracked"] == 2
    rows_2025 = iter_scorecards(data, calendar_year=2025, limit=10)
    assert rows_2025 == []


def test_iter_scorecards_course_from_summary_when_missing_on_scorecard() -> None:
    data = {
        "summary": {
            "scorecardSummaries": [
                {
                    "id": "888",
                    "courseName": "Summary Only Club",
                    "startTime": "2026-02-01T09:00:00Z",
                }
            ]
        },
        "details": [
            {
                "startTime": "2026-02-01T09:00:00Z",
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "888",
                            "startTime": "2026-02-01T09:00:00Z",
                            "totalScore": 72,
                            "holes": [{"number": 1, "par": 4, "score": 4, "typeScore": 2}],
                        }
                    }
                ],
            }
        ],
    }
    rows = iter_scorecards(data, calendar_year=2026, limit=5)
    assert len(rows) == 1
    assert rows[0]["course_name"] == "Summary Only Club"


def test_iter_scorecards_course_from_entry_snapshots() -> None:
    data = {
        "summary": {"scorecardSummaries": []},
        "details": [
            {
                "startTime": "2026-03-01T10:00:00Z",
                "courseSnapshots": [{"name": "Snap Nine"}],
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "777",
                            "startTime": "2026-03-01T10:00:00Z",
                            "totalScore": 36,
                            "holes": [{"number": 1, "par": 4, "score": 4}],
                        }
                    }
                ],
            }
        ],
    }
    rows = iter_scorecards(data, calendar_year=2026, limit=5)
    assert rows[0]["course_name"] == "Snap Nine"


def test_scoring_method_proxies_fixture() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    cards = iter_scorecards(data, calendar_year=2026, limit=10)
    sm = scoring_method_proxy_metrics(cards)
    assert sm["rounds"] == 1
    assert "esz_dsz_note" in sm
    abn = sm["proxy_avoid_big_numbers"]
    assert abn["stableford_zero_point_holes"] == 1
    assert abn["stableford_holes_tracked"] == 2
    assert abn["pct_holes"] == 50.0
    pr = performance_round_rollups(cards)
    assert pr["rounds"] == 1
    assert pr["mean_strokes_per_round"] == 8.0


def test_scoring_method_par_splits() -> None:
    data = {
        "summary": {"scorecardSummaries": []},
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "1",
                            "startTime": "2026-06-01T10:00:00Z",
                            "holes": [
                                {"number": 1, "par": 3, "score": 5, "typeScore": 0, "putts": 2},
                                {"number": 2, "par": 4, "score": 4, "typeScore": 2, "putts": 2},
                                {"number": 3, "par": 5, "score": 5, "typeScore": 2, "putts": 2},
                            ],
                        }
                    }
                ],
            }
        ],
    }
    sm = scoring_method_proxy_metrics_from_export(data, calendar_year=2026)
    by_par = sm["proxy_avoid_big_numbers"]["by_par"]
    assert by_par["3"]["value"] == 100.0
    assert by_par["4"]["value"] == 0.0
    assert by_par["3"]["diff_vs_avg_pct"] == pytest.approx(200.0)
    assert by_par["4"]["diff_vs_avg_pct"] == pytest.approx(-100.0)
    assert sm["proxy_putting_load"]["by_par"]["3"]["value"] == 2.0
