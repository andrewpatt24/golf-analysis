"""Manually entered course scorecards (offline prep until catalog ingest)."""

from __future__ import annotations

from typing import Any

# Woldingham Golf Club — White tees (from club app scorecard, May 2026).
_WOLDINGHAM_WHITE_HOLES: tuple[dict[str, int], ...] = (
    {"hole_number": 1, "yardage_yards": 383, "par": 4, "stroke_index": 8},
    {"hole_number": 2, "yardage_yards": 166, "par": 3, "stroke_index": 16},
    {"hole_number": 3, "yardage_yards": 392, "par": 4, "stroke_index": 4},
    {"hole_number": 4, "yardage_yards": 349, "par": 4, "stroke_index": 18},
    {"hole_number": 5, "yardage_yards": 504, "par": 5, "stroke_index": 14},
    {"hole_number": 6, "yardage_yards": 389, "par": 4, "stroke_index": 12},
    {"hole_number": 7, "yardage_yards": 196, "par": 3, "stroke_index": 2},
    {"hole_number": 8, "yardage_yards": 334, "par": 4, "stroke_index": 6},
    {"hole_number": 9, "yardage_yards": 546, "par": 5, "stroke_index": 10},
    {"hole_number": 10, "yardage_yards": 397, "par": 4, "stroke_index": 5},
    {"hole_number": 11, "yardage_yards": 167, "par": 3, "stroke_index": 13},
    {"hole_number": 12, "yardage_yards": 410, "par": 4, "stroke_index": 1},
    {"hole_number": 13, "yardage_yards": 382, "par": 4, "stroke_index": 11},
    {"hole_number": 14, "yardage_yards": 385, "par": 4, "stroke_index": 3},
    {"hole_number": 15, "yardage_yards": 164, "par": 3, "stroke_index": 17},
    {"hole_number": 16, "yardage_yards": 547, "par": 5, "stroke_index": 7},
    {"hole_number": 17, "yardage_yards": 174, "par": 3, "stroke_index": 15},
    {"hole_number": 18, "yardage_yards": 491, "par": 5, "stroke_index": 9},
)

MANUAL_COURSES: dict[str, dict[str, Any]] = {
    "woldingham-white": {
        "course_slug": "woldingham-white",
        "course_name": "Woldingham Golf Club",
        "tee_name": "White",
        "hole_count": 18,
        "par_total": 71,
        "yardage_total": 6376,
        "course_rating": 71.2,
        "slope_rating": 130,
        "holes": [dict(h) for h in _WOLDINGHAM_WHITE_HOLES],
    },
}


def list_manual_courses() -> list[dict[str, Any]]:
    """Summary rows for course pickers."""

    out: list[dict[str, Any]] = []
    for slug, course in sorted(MANUAL_COURSES.items(), key=lambda item: item[1]["course_name"]):
        out.append(
            {
                "course_slug": slug,
                "course_name": course["course_name"],
                "tee_name": course.get("tee_name"),
                "hole_count": course.get("hole_count"),
                "par_total": course.get("par_total"),
                "yardage_total": course.get("yardage_total"),
            }
        )
    return out


def get_manual_course(course_slug: str) -> dict[str, Any] | None:
    course = MANUAL_COURSES.get(course_slug)
    if not course:
        return None
    return dict(course)
