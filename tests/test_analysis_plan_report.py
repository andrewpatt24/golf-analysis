"""Tests for analysis_plan_report."""

from __future__ import annotations

import json
from pathlib import Path

from golf_analysis.analysis_plan_report import (
    iter_last10_shots_with_sg,
    scorecard_ids_for_calendar_year,
    scorecard_round_stats,
    strokes_gained_ratings_from_export,
    summarize_last10_strokes_gained,
)


def test_iter_last10_shots_with_sg_finds_orientation_rows() -> None:
    data = {
        "last10DataApproach": {
            "shotOrientationDetail": [
                {"strokesGained": 0.1, "holeNumber": 1},
                {"strokesGained": -0.2, "holeNumber": 2},
            ],
            "numberOfRounds": 10,
        },
        "last10DataChip": {
            "shotOrientationDetail": [{"strokesGained": 0.05}],
        },
    }
    rows = iter_last10_shots_with_sg(data)
    assert len(rows) == 3
    cats = {r[0] for r in rows}
    assert cats == {"approach", "around_the_green"}


def test_strokes_gained_ratings_from_export() -> None:
    data = {
        "last10DataStats": {
            "strokesGainedRatings": [
                {"statShotType": "DRIVE", "playerStrokesGained": -0.18, "groupStrokesGained": -0.35},
                {"statShotType": "PUTT", "playerStrokesGained": None, "groupStrokesGained": -0.01},
            ]
        }
    }
    rows = strokes_gained_ratings_from_export(data)
    assert len(rows) == 2
    assert rows[0]["stat_shot_type"] == "DRIVE"
    assert rows[0]["player_strokes_gained"] == -0.18


def test_summarize_last10_strokes_gained() -> None:
    data = {
        "last10DataApproach": {
            "shotOrientationDetail": [
                {"strokesGained": 0.5},
                {"strokesGained": -0.5},
            ]
        },
        "last10DataChip": {"shotOrientationDetail": [{"strokesGained": 1.0}]},
    }
    s = summarize_last10_strokes_gained(data)
    assert s["approach"]["count"] == 2.0
    assert s["approach"]["sum_sg"] == 0.0
    assert s["around_the_green"]["sum_sg"] == 1.0
    assert s["_overall"]["count"] == 3.0


def test_scorecard_round_stats() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "1",
                            "scoreRelativeToPar": 5,
                            "holes": [],
                        }
                    }
                ]
            },
            {
                "scorecardDetails": [
                    {"scorecard": {"id": "2", "scoreRelativeToPar": 3, "holes": []}},
                ]
            },
        ]
    }
    n, m = scorecard_round_stats(data)
    assert n == 2
    assert m == 4.0


def test_scorecard_round_stats_calendar_year_filters_start_time() -> None:
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "a",
                            "startTime": "2025-06-01T12:00:00.000Z",
                            "scoreRelativeToPar": 10,
                            "holes": [],
                        }
                    },
                    {
                        "scorecard": {
                            "id": "b",
                            "startTime": "2026-03-01T12:00:00.000Z",
                            "scoreRelativeToPar": 2,
                            "holes": [],
                        }
                    },
                ]
            },
        ]
    }
    n, m = scorecard_round_stats(data, calendar_year=2026)
    assert n == 1
    assert m == 2.0
    assert scorecard_ids_for_calendar_year(data, 2026) == {"b"}


def test_scorecard_ids_includes_summary_scorecard_summaries() -> None:
    """Year filter ids must include summary rows (not only details)."""

    data = {
        "details": [],
        "summary": {
            "scorecardSummaries": [
                {"id": "x1", "startTime": "2026-01-01T12:00:00.000Z"},
                {"id": "x2", "startTime": "2025-01-01T12:00:00.000Z"},
            ]
        },
    }
    assert scorecard_ids_for_calendar_year(data, 2026) == {"x1"}
    data = {
        "last10DataApproach": {
            "shotOrientationDetail": [
                {"strokesGained": 0.1, "scorecardId": 100},
                {"strokesGained": 0.2, "scorecardId": 200},
            ],
        },
    }
    all_rows = iter_last10_shots_with_sg(data)
    assert len(all_rows) == 2
    filtered = iter_last10_shots_with_sg(data, scorecard_ids={"100"})
    assert len(filtered) == 1
    assert filtered[0][1]["strokesGained"] == 0.1
