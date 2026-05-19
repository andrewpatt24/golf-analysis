"""Tests for Garmin ESZ/DSZ from shotDetails."""

from __future__ import annotations

from golf_analysis.garmin_esz_dsz import compute_esz_dsz_from_shot_details


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
                            "holes": [],
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
                            "holes": [],
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
                            "holes": [],
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
                            "holes": [],
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
                            "holes": [],
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
                            "holes": [],
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
    assert (r.get("diagnostics") or {}).get("dsz_basis_scorecard") == 1
