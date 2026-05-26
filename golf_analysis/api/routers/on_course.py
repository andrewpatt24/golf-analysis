"""On-course mode: playbook, yardages, course strategy (WHERE to improve)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from golf_analysis.api.deps import require_db_exists
from golf_analysis.api.on_course_playbook_store import load_playbook, save_playbook
from golf_analysis.api.settings_store import load_settings
from golf_analysis.api.training_data import club_training_rows
from golf_analysis.garmin_course_holes import course_detail_from_export, list_courses_from_export
from golf_analysis.course_layout.manual_courses import list_manual_courses
from golf_analysis.on_course_prep import build_on_course_prep
from golf_analysis.on_course_strategy import build_on_course_course_summary
from golf_analysis.repository import connect, init_schema

router = APIRouter(tags=["on-course"])


class PitchRow(BaseModel):
    dist: str = ""
    club: str = ""
    stance: str = ""
    gripSwing: str = ""


class PlaybookUpdate(BaseModel):
    swingCue: str | None = None
    swingThoughts: str | None = None
    chipNotes: str | None = None
    fixNotes: str | None = None
    windNotes: str | None = None
    puttingRoutine: str | None = None
    pitchRows: list[PitchRow] | None = None


def _garmin_export_path() -> Path:
    raw = os.environ.get("GOLF_GARMIN_JSON", "data/raw/garmin/golf-export.json")
    return Path(raw).expanduser().resolve()


def _load_garmin() -> dict[str, Any] | None:
    path = _garmin_export_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@router.get("/on-course/playbook")
def get_playbook() -> dict[str, object]:
    return load_playbook()


@router.put("/on-course/playbook")
def put_playbook(body: PlaybookUpdate) -> dict[str, object]:
    payload = body.model_dump(exclude_none=True)
    if "pitchRows" in payload and payload["pitchRows"] is not None:
        payload["pitchRows"] = [
            r.model_dump() if hasattr(r, "model_dump") else r for r in payload["pitchRows"]
        ]
    return save_playbook(payload)


@router.get("/on-course/yardages")
def on_course_yardages(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None, description="Calendar year; defaults to settings calendarYear"),
    min_carry: float = Query(100, ge=50, le=300, description="Minimum mean carry yards"),
) -> dict[str, object]:
    """Full-swing yardages from recent range/practice (carry ≥ min_carry)."""

    y = year if year is not None else int(load_settings().get("calendarYear", 2026))
    conn = connect(db)
    init_schema(conn)
    try:
        rows = club_training_rows(conn, db_path=db, calendar_year=y)
    finally:
        conn.close()

    clubs: list[dict[str, object]] = []
    for row in rows:
        carry = row.get("mean_carry_yards")
        if carry is None or float(carry) < min_carry:
            continue
        clubs.append(
            {
                "club": row["club"],
                "mean_carry_yards": round(float(carry)),
                "n": row.get("n", 0),
                "needs_work": bool(row.get("needs_work")),
            }
        )
    clubs.sort(key=lambda r: float(r["mean_carry_yards"]), reverse=True)
    return {"calendar_year": y, "min_carry_yards": min_carry, "clubs": clubs}


@router.get("/on-course/courses")
def on_course_courses(
    year: int | None = Query(None),
    min_rounds: int = Query(1, ge=1),
) -> dict[str, object]:
    data = _load_garmin()
    y = year if year is not None else int(load_settings().get("calendarYear", 2026))
    if not data:
        return {"source_available": False, "calendar_year": y, "courses": []}
    payload = list_courses_from_export(data, calendar_year=y, min_rounds=min_rounds)
    courses = payload.get("courses") or []
    slim = [
        {
            "course_slug": c.get("course_slug"),
            "course_name": c.get("course_name"),
            "rounds_count": c.get("rounds_count"),
            "worst_hole_numbers": c.get("worst_hole_numbers") or [],
        }
        for c in courses
        if isinstance(c, dict)
    ]
    return {"source_available": True, "calendar_year": y, "courses": slim}


@router.get("/on-course/course-strategy/{course_slug}")
def on_course_course_strategy(
    course_slug: str,
    year: int | None = Query(None),
) -> dict[str, object]:
    data = _load_garmin()
    y = year if year is not None else int(load_settings().get("calendarYear", 2026))
    if not data:
        raise HTTPException(status_code=503, detail="Garmin export not available")
    detail = course_detail_from_export(data, course_slug, calendar_year=y)
    if detail is None:
        raise HTTPException(status_code=404, detail="Course not found in your history")
    return build_on_course_course_summary(
        course_name=str(detail.get("course_name") or course_slug),
        course_slug=course_slug,
        rounds_count=int(detail.get("rounds_count") or 0),
        holes=list(detail.get("holes") or []),
    )


@router.get("/on-course/prep/courses")
def on_course_prep_courses() -> dict[str, object]:
    """Manually catalogued courses for pre-round planning (no live API)."""

    return {"courses": list_manual_courses()}


@router.get("/on-course/prep/{course_slug}")
def on_course_prep_plan(
    course_slug: str,
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None, description="Calendar year for yardages and Garmin profile"),
) -> dict[str, object]:
    """Hole-by-hole plan: scorecard + your carry yardages + WHERE tendencies."""

    y = year if year is not None else int(load_settings().get("calendarYear", 2026))
    conn = connect(db)
    init_schema(conn)
    try:
        rows = club_training_rows(conn, db_path=db, calendar_year=y)
    finally:
        conn.close()

    clubs: list[dict[str, object]] = []
    for row in rows:
        carry = row.get("mean_carry_yards")
        if carry is None:
            continue
        clubs.append(
            {
                "club": row["club"],
                "mean_carry_yards": round(float(carry)),
                "n": row.get("n", 0),
                "needs_work": bool(row.get("needs_work")),
            }
        )
    clubs.sort(key=lambda r: float(r["mean_carry_yards"]), reverse=True)

    try:
        return build_on_course_prep(
            course_slug=course_slug,
            calendar_year=y,
            clubs=clubs,
            garmin_export=_load_garmin(),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Course not in manual catalog") from None
