"""Tests for Garmin ESZ/DSZ from shotDetails."""

from __future__ import annotations

import pytest

from golf_analysis.garmin_esz_dsz import (
    DSZ_ENTRY_BANDS,
    _dsz_success_for_entry_band,
    _dsz_success_from_score_and_trace,
    _strokes_inside_scoring_zone,
    compute_esz_dsz_from_shot_details,
)


def test_dsz_band_pct_is_per_hole_not_sum_of_means() -> None:
    """DSZ % counts holes with inside<=3, not whether mean(before putts)+mean(putts)<=3."""

    hole_rows = [
        {
            "entered_scoring_zone": True,
            "first_zone_method": "geometry",
            "first_zone_yards": 55.0,
            "strokes_inside_zone": 4,
            "dsz_entry_strokes": 4,
            "dsz_success_entry_band": False,
            "scorecard_shots_before_putts": 2,
            "hole_putts": 2,
        },
        {
            "entered_scoring_zone": True,
            "first_zone_method": "geometry",
            "first_zone_yards": 58.0,
            "strokes_inside_zone": 3,
            "dsz_entry_strokes": 3,
            "dsz_success_entry_band": True,
            "scorecard_shots_before_putts": 1,
            "hole_putts": 2,
        },
    ]
    from golf_analysis.garmin_esz_dsz import _dsz_entry_band_rows

    bands = _dsz_entry_band_rows(hole_rows, geometry_only=True, overall_dsz_pct=50.0)
    b = next(x for x in bands if x["band_id"] == "50_60")
    assert b["pct_success"] == 50.0
    assert b["dsz_success_holes"] == 1
    assert b["mean_shots_before_putts"] == 1.5
    assert b["mean_putts"] == 2.0
    assert b["mean_strokes_inside_zone"] == 3.5
    # Mean before putts + mean putts = 3.5 but DSZ is 50% because one hole has 4 strokes inside


def test_dsz_entry_band_scorecard_inside() -> None:
    ok, total, basis = _dsz_success_for_entry_band(scorecard_inside=3)
    assert ok and total == 3 and basis == "scorecard_minus_outside"
    fail, total2, _ = _dsz_success_for_entry_band(scorecard_inside=4)
    assert not fail and total2 == 4


def test_entry_band_green_and_putts_breakdown() -> None:
    hole_rows = [
        {
            "entered_scoring_zone": True,
            "first_zone_method": "geometry",
            "first_zone_yards": 25.0,
            "dsz_success": True,
            "strokes_inside_zone": 2,
            "entry_on_green": True,
            "reached_green_in_zone": True,
            "scorecard_shots_before_putts": 1,
            "hole_putts": 2,
            "dsz_entry_strokes": 3,
            "dsz_success_entry_band": True,
        },
        {
            "entered_scoring_zone": True,
            "first_zone_method": "geometry",
            "first_zone_yards": 25.0,
            "dsz_success": False,
            "strokes_inside_zone": 4,
            "entry_on_green": False,
            "reached_green_in_zone": True,
            "scorecard_shots_before_putts": 1,
            "hole_putts": 3,
            "dsz_entry_strokes": 4,
            "dsz_success_entry_band": False,
        },
        {
            "entered_scoring_zone": True,
            "first_zone_method": "geometry",
            "first_zone_yards": 55.0,
            "dsz_success": False,
            "strokes_inside_zone": 4,
            "entry_on_green": False,
            "reached_green_in_zone": True,
            "scorecard_shots_before_putts": 2,
            "hole_putts": 2,
            "dsz_entry_strokes": 4,
            "dsz_success_entry_band": False,
        },
    ]
    from golf_analysis.garmin_esz_dsz import _dsz_entry_band_rows

    bands = _dsz_entry_band_rows(hole_rows, geometry_only=True, overall_dsz_pct=33.3)
    b30 = next(b for b in bands if b["band_id"] == "0_30")
    assert b30["green_hit_holes"] == 2
    assert b30["green_lie_known_holes"] == 2
    assert b30["pct_green"] == 100.0
    assert b30["mean_putts"] == 2.5
    assert b30["putts_holes"] == 2
    assert b30["pct_success"] == 50.0
    b50 = next(b for b in bands if b["band_id"] == "50_60")
    assert b50["pct_green"] == 100.0
    assert b50["pct_success"] == 0.0
    assert b50["mean_shots_before_putts"] == 2.0


def test_strokes_inside_zone_score_minus_tracked_outside() -> None:
    assert _strokes_inside_scoring_zone(5, 2) == 3
    assert _strokes_inside_scoring_zone(5, 0) == 5
    assert _strokes_inside_scoring_zone(None, 1) is None
    assert _strokes_inside_scoring_zone(4, 5) is None
    ok, inside, ev = _dsz_success_from_score_and_trace(5, 2)
    assert ev and inside == 3 and ok
    fail, inside2, ev2 = _dsz_success_from_score_and_trace(6, 2)
    assert ev2 and inside2 == 4 and not fail


def _pin() -> dict:
    return {"lat": 606601458, "lon": -4615121, "x": 379, "y": 103}


def test_esz_dsz_par4_two_shots_in_zone() -> None:
    """Par 4: reach ≤100 yd by stroke 2 (≤ par−2) → ESZ; two strokes from first in-zone to hole out → DSZ."""

    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 3}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "pinPosition": _pin(),
                            "shots": [
                                {
                                    "shotOrder": 1,
                                    "endLoc": {
                                        "lat": 606585573,
                                        "lon": -4622913,
                                        "lie": "Unknown",
                                        "lieSource": "CARTOGRAPHY",
                                    },
                                    "excludeFromStats": False,
                                },
                                {
                                    "shotOrder": 2,
                                    "endLoc": {
                                        "lat": 606599017,
                                        "lon": -4615801,
                                        "lie": "Rough",
                                        "lieSource": "CARTOGRAPHY",
                                    },
                                    "excludeFromStats": False,
                                },
                                {
                                    "shotOrder": 3,
                                    "endLoc": _pin(),
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 1
    assert r["dsz_success_holes"] == 1
    methods = r["distance_to_pin_methods"]
    assert isinstance(methods, dict) and methods.get("geometry") == 1
    assert r["proxy_esz"]["pct_success"] == 100.0
    assert r["proxy_dsz"]["pct_success"] == 100.0
    assert r["proxy_esz"]["direction"] == "higher_is_better"
    entry = r["proxy_dsz"]["entry_distance"]
    assert entry["mean_entry_yards"] is not None
    geom_bands = entry["bands_geometry"]
    assert len(geom_bands) >= 1
    assert geom_bands[0]["pct_success"] == 100.0
    assert len(DSZ_ENTRY_BANDS) == 8  # 0–30 + seven 10 yd bands


def test_esz_par4_zone_on_stroke_three_is_not_esz() -> None:
    """Par 4: first ≤100 yd on stroke 3 → not ESZ (cap par−2 = 2); still DSZ if holed in ≤3 from there."""

    far = {"lat": 606585573, "lon": -4622913, "lie": "Unknown", "lieSource": "CARTOGRAPHY"}
    in_zone = {"lat": 606599017, "lon": -4615801, "lie": "Rough", "lieSource": "CARTOGRAPHY"}
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 5}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "pinPosition": _pin(),
                            "shots": [
                                {"shotOrder": 1, "endLoc": far, "excludeFromStats": False},
                                {"shotOrder": 2, "endLoc": far, "excludeFromStats": False},
                                {"shotOrder": 3, "endLoc": in_zone, "excludeFromStats": False},
                                {"shotOrder": 4, "endLoc": _pin(), "excludeFromStats": False},
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 0
    assert r["dsz_success_holes"] == 1


def test_esz_dsz_empty_scorecard_id_filter_does_not_drop_all() -> None:
    """Regression: empty scorecard_ids set must not exclude every sid."""

    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 3}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "pinPosition": {"lat": 606601458, "lon": -4615121},
                            "shots": [
                                {
                                    "shotOrder": 1,
                                    "endLoc": {
                                        "lat": 606585573,
                                        "lon": -4622913,
                                        "lie": "Unknown",
                                        "lieSource": "CARTOGRAPHY",
                                    },
                                    "excludeFromStats": False,
                                },
                                {
                                    "shotOrder": 2,
                                    "endLoc": {
                                        "lat": 606599017,
                                        "lon": -4615801,
                                        "lie": "Rough",
                                        "lieSource": "CARTOGRAPHY",
                                    },
                                    "excludeFromStats": False,
                                },
                                {
                                    "shotOrder": 3,
                                    "endLoc": {"lat": 606601458, "lon": -4615121},
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids=set())
    assert r["holes_evaluated"] == 1


def test_esz_dsz_heuristic_when_no_geometry() -> None:
    """Par 4 with only ``meters`` (no pin / endLoc): straight-hole cumulative heuristic."""

    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 3}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "shots": [
                                {
                                    "shotOrder": 1,
                                    "meters": 300.0,
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 1
    methods = r["distance_to_pin_methods"]
    assert isinstance(methods, dict) and methods.get("heuristic_straight_hole") == 1


def test_esz_dsz_orientation_remaining_distance() -> None:
    """Use ``remainingDistance`` by ``shot.id`` when geometry is absent."""

    data = {
        "last10DataApproach": {
            "shotOrientationDetail": [
                {"shotId": 4242, "remainingDistance": 55.0},
            ]
        },
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 3}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "shots": [
                                {
                                    "id": 4242,
                                    "shotOrder": 1,
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 1
    methods = r["distance_to_pin_methods"]
    assert isinstance(methods, dict) and methods.get("orientation") == 1


def test_esz_dsz_orientation_starting_minus_shot() -> None:
    """When ``remainingDistance`` is absent, use ``startingDistanceToHole - shot meters``."""

    data = {
        "last10DataApproach": {
            "shotOrientationDetail": [
                {"shotId": 9001, "startingDistanceToHole": 118.0},
            ]
        },
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "score": 3}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "shots": [
                                {
                                    "id": 9001,
                                    "shotOrder": 1,
                                    "meters": 25.0,
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 1
    methods = r["distance_to_pin_methods"]
    assert isinstance(methods, dict) and methods.get("orientation_starting_minus_shot") == 1


def test_esz_dsz_heuristic_prefers_scorecard_hole_yardage() -> None:
    """Cumulative heuristic uses ``holes[].yardage`` when present (vs par default)."""

    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "yardage": 430}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "shots": [
                                {
                                    "shotOrder": 1,
                                    "meters": 400.0,
                                    "excludeFromStats": False,
                                },
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["esz_success_holes"] == 1
    methods = r["distance_to_pin_methods"]
    assert isinstance(methods, dict) and methods.get("heuristic_straight_hole") == 1


def test_dsz_uses_scorecard_gross_when_putts_missing_from_trace() -> None:
    """Two GPS strokes ending in zone then pin; scorecard gross 6 ⇒ DSZ uses S−E+1, not trace length."""

    far = {"lat": 606585573, "lon": -4622913, "lie": "Unknown", "lieSource": "CARTOGRAPHY"}
    data = {
        "details": [
            {
                "scorecardDetails": [
                    {
                        "scorecard": {
                            "id": "sc1",
                            "startTime": "2026-05-01T12:00:00Z",
                            "holePars": "4",
                            "holes": [{"number": 1, "par": 4, "strokes": 6}],
                        }
                    }
                ]
            }
        ],
        "shotDetails": [
            {
                "scorecardId": "sc1",
                "holeNumber": 1,
                "response": {
                    "holeShots": [
                        {
                            "holeNumber": 1,
                            "pinPosition": _pin(),
                            "shots": [
                                {"shotOrder": 1, "endLoc": far, "excludeFromStats": False},
                                {"shotOrder": 2, "endLoc": _pin(), "excludeFromStats": False},
                            ],
                        }
                    ]
                },
            }
        ],
    }
    r = compute_esz_dsz_from_shot_details(data, calendar_year=2026, scorecard_ids={"sc1"})
    assert r["holes_evaluated"] == 1
    assert r["dsz_success_holes"] == 0
    assert (r.get("diagnostics") or {}).get("dsz_basis_score_minus_tracked_outside") == 1
