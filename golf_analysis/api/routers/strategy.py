from __future__ import annotations

from fastapi import APIRouter, Query

from golf_analysis.analysis_plan_report import scorecard_ids_for_calendar_year
from golf_analysis.api.deps import garmin_export_path
from golf_analysis.api.settings_store import load_settings
from golf_analysis.garmin_esz_dsz import ESZ_DSZ_DATA_MODEL, compute_esz_dsz_from_shot_details
from golf_analysis.garmin_export_analytics import (
    iter_scorecards,
    load_garmin_export,
    performance_round_rollups,
    scoring_method_proxy_metrics,
)

router = APIRouter(tags=["strategy"])


@router.get("/strategy/status")
def strategy_status() -> dict[str, object]:
    """Lightweight flag; full payload is ``/strategy/overview``."""

    return {
        "esz_dsz_in_sql": False,
        "note": "Use GET /api/v1/strategy/overview for Garmin + Scoring Method proxies.",
    }


@router.get("/strategy/overview")
def strategy_overview(
    year: int | None = Query(None, description="Calendar year; defaults to settings.calendarYear"),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    """
    Garmin export: scorecard list + **Scoring Method** proxies (see docs/frameworks/scoring-method.md).
    ESZ/DSZ from ``shotDetails`` geometry when present (``esz_dsz_from_shots``).
    """

    settings = load_settings()
    y = int(year) if year is not None else int(settings.get("calendarYear", 2026))
    path = garmin_export_path()
    data = load_garmin_export(path)
    if data is None:
        return {
            "source_available": False,
            "year": y,
            "reason": "GOLF_GARMIN_JSON not set or file missing",
            "scoring_method": scoring_method_proxy_metrics([]),
            "performance": performance_round_rollups([]),
            "scorecards": [],
            "esz_dsz_in_sql": False,
            "esz_dsz_from_shots": {
                "holes_evaluated": 0,
                "note": "No Garmin JSON.",
                "by_round": [],
                "data_model": ESZ_DSZ_DATA_MODEL,
            },
        }
    cards = iter_scorecards(data, calendar_year=y, limit=limit)
    sc_ids = scorecard_ids_for_calendar_year(data, y)
    # Empty year set must not be passed as a filter (would exclude every scorecard id).
    sc_filter = sc_ids if len(sc_ids) > 0 else None
    geom = compute_esz_dsz_from_shot_details(data, calendar_year=y, scorecard_ids=sc_filter)
    return {
        "source_available": True,
        "source": str(path),
        "year": y,
        "scoring_method": scoring_method_proxy_metrics(cards),
        "performance": performance_round_rollups(cards),
        "scorecards": cards,
        "esz_dsz_in_sql": False,
        "esz_dsz_from_shots": geom,
    }
