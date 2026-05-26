"""Tests for 18-hole gross estimation on partial scorecards."""

from __future__ import annotations

from golf_analysis.garmin_esz_dsz import _par_for_hole
from golf_analysis.garmin_handicap_gross import (
    capped_hole_gross,
    estimated_round_gross_18,
    net_double_bogey_gross,
    parse_course_stroke_indexes,
    strokes_received_on_hole,
)


def test_strokes_received_allocation() -> None:
    assert strokes_received_on_hole(25, 1) == 2
    assert strokes_received_on_hole(25, 7) == 2
    assert strokes_received_on_hole(25, 8) == 1
    assert sum(strokes_received_on_hole(25, si) for si in range(1, 19)) == 25


def test_net_double_bogey_gross() -> None:
    assert net_double_bogey_gross(4, 25, 7) == 8
    assert net_double_bogey_gross(4, 25, 8) == 7


def test_capped_hole_gross_blowup() -> None:
    adj, capped = capped_hole_gross(12, 4, 10, 1)
    assert capped is True
    assert adj == net_double_bogey_gross(4, 10, 1)


def test_full_round_unchanged_when_under_cap() -> None:
    holes = [{"number": i, "strokes": 5, "par": 4} for i in range(1, 19)]
    sc = {
        "playerHandicap": 10,
        "courseHandicapStr": "010203040506070809101112131415161718",
        "holes": holes,
        "holesCompleted": 18,
    }
    r = estimated_round_gross_18(sc)
    assert r["method"] == "handicap_net_double_bogey"
    assert r["gross_raw"] == 90
    assert r["gross_net_18"] == 90
    assert r["gross_estimated_18"] == 90
    assert r["is_partial"] is False
    assert r["holes_capped"] == 0


def test_full_round_caps_blowup_hole() -> None:
    holes = [{"number": i, "strokes": 5, "par": 4} for i in range(1, 19)]
    holes[0] = {"number": 1, "strokes": 12, "par": 4}
    sc = {
        "playerHandicap": 10,
        "courseHandicapStr": "010203040506070809101112131415161718",
        "holePars": "4" * 18,
        "holes": holes,
        "holesCompleted": 18,
    }
    r = estimated_round_gross_18(sc)
    assert r["gross_raw"] == 90 + 7
    assert r["gross_net_18"] < r["gross_raw"]
    assert r["holes_capped"] == 1
    assert r["blowup_reduction"] == 12 - net_double_bogey_gross(4, 10, 1)
    assert r["is_partial"] is False


def test_partial_handicap_gross_up() -> None:
    sc = {
        "playerHandicap": 25,
        "courseHandicapStr": "071706131408151001040218111605120309",
        "holePars": "434334344443434444",
        "holes": [
            {"number": 1, "strokes": 7, "handicapScore": 5},
            {"number": 2, "strokes": 3, "handicapScore": 2},
            {"number": 3, "strokes": 6, "handicapScore": 4},
        ],
        "holesCompleted": 3,
        "strokes": 16,
    }
    r = estimated_round_gross_18(sc)
    assert r["is_partial"] is True
    assert r["method"] == "handicap_net_double_bogey"
    assert r["gross_raw"] == 16
    assert r["gross_net_18"] > 16
    assert r["gross_net_18"] == r["played_net"] + r["unplayed_imputed"]

    ch = sc["playerHandicap"]
    sis = parse_course_stroke_indexes(sc)
    assert sis is not None
    par_only = 16
    for hn in range(1, 19):
        if hn in (1, 2, 3):
            continue
        p = _par_for_hole(sc, hn)
        assert p is not None
        par_only += p
    assert r["gross_net_18"] > par_only


def test_partial_caps_played_blowup() -> None:
    sc = {
        "playerHandicap": 10,
        "courseHandicapStr": "010203040506070809101112131415161718",
        "holePars": "444",
        "holes": [{"number": 1, "strokes": 12, "par": 4}],
        "holesCompleted": 1,
    }
    r = estimated_round_gross_18(sc)
    assert r["gross_raw"] == 12
    assert r["played_net"] == net_double_bogey_gross(4, 10, 1)
    assert r["holes_capped"] == 1
    assert r["gross_net_18"] > r["played_net"]
