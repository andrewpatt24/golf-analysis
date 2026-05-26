from __future__ import annotations

import json

from fastapi import APIRouter, Query

from golf_analysis.analysis_plan_report import (
    scorecard_ids_for_calendar_year,
    strokes_gained_ratings_from_export,
    summarize_last10_strokes_gained,
)
from golf_analysis.api.deps import garmin_export_path
from golf_analysis.api.settings_store import load_settings
from golf_analysis.garmin_export_analytics import (
    iter_scorecards,
    load_garmin_export,
    performance_round_rollups,
)

router = APIRouter(tags=["performance"])


@router.get("/performance/garmin-samples")
def garmin_last10_samples(
    year: int | None = Query(None),
) -> dict[str, object]:
    """Last-10 SG sample aggregates from Garmin JSON file (if present)."""

    path = garmin_export_path()
    if path is None:
        return {"available": False, "reason": "GOLF_GARMIN_JSON not set or file missing", "summary": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"available": False, "reason": str(e), "summary": {}}
    if not isinstance(data, dict):
        return {"available": False, "reason": "invalid JSON root", "summary": {}}
    sc_ids = None
    if year is not None:
        sc_ids = scorecard_ids_for_calendar_year(data, year)
    summary = summarize_last10_strokes_gained(data, scorecard_ids=sc_ids)
    return {
        "available": True,
        "source": str(path),
        "year_filter": year,
        "summary": summary,
        "sg_ratings": strokes_gained_ratings_from_export(data),
    }


@router.get("/performance/garmin-bundle")
def garmin_performance_bundle(
    year: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    """Round rollups from export + last-10 SG samples (same year filter when set)."""

    settings = load_settings()
    y = int(year) if year is not None else int(settings.get("calendarYear", 2026))
    path = garmin_export_path()
    data = load_garmin_export(path)
    if data is None:
        return {
            "available": False,
            "year": y,
            "round_rollups": performance_round_rollups([]),
            "last10": {},
            "sg_ratings": [],
        }
    cards = iter_scorecards(data, calendar_year=y, limit=limit)
    sc_ids = scorecard_ids_for_calendar_year(data, y)
    last10 = summarize_last10_strokes_gained(data, scorecard_ids=sc_ids)
    return {
        "available": True,
        "source": str(path),
        "year": y,
        "round_rollups": performance_round_rollups(cards),
        "last10": last10,
        "sg_ratings": strokes_gained_ratings_from_export(data),
        "rounds_in_bundle": len(cards),
    }
