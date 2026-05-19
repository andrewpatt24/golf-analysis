"""Tests for training takeaways and club-pair helpers."""

from __future__ import annotations

from golf_analysis.range_shot_analytics import (
    build_training_takeaways,
    club_pair_landing_compare,
)
from golf_analysis.repository import connect, init_schema


def test_build_training_takeaways_landing_bias() -> None:
    landing = [
        {
            "club": "driver",
            "n": 20,
            "pct_left": 55,
            "pct_right": 20,
            "pct_straight": 25,
            "straight_band_yards": 5,
        }
    ]
    lines = build_training_takeaways(
        landing_side=landing,
        gapping=[],
        shot_shape={"five_way_spin_axis": None},
        carry_distribution=[],
    )
    assert len(lines) >= 1
    assert "driver" in lines[0]
    assert "left" in lines[0].lower()


def test_build_training_takeaways_shape_slice() -> None:
    fw = {"usable": True, "n": 20, "pct_slice": 35, "pct_hook": 5}
    lines = build_training_takeaways(
        landing_side=[],
        gapping=[],
        shot_shape={"five_way_spin_axis": fw},
        carry_distribution=[],
    )
    assert any("slice" in x.lower() for x in lines)


def test_club_pair_compare_empty_db(tmp_path) -> None:
    db = tmp_path / "t.db"
    conn = connect(db)
    init_schema(conn)
    try:
        out = club_pair_landing_compare(
            conn, db_path=db, calendar_year=None, club_a="driver", club_b="3w"
        )
    finally:
        conn.close()
    assert "error" not in out
    assert out["club_a"] is None
    assert out["club_b"] is None
