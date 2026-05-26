from __future__ import annotations

from fastapi import APIRouter, Query

from golf_analysis.analysis_plan_report import scorecard_ids_for_calendar_year
from golf_analysis.api.deps import garmin_export_path
from golf_analysis.api.settings_store import load_settings
from golf_analysis.garmin_esz_dsz import compute_esz_dsz_from_shot_details
from golf_analysis.garmin_export_analytics import load_garmin_export
from golf_analysis.metrics_reference import build_metrics_reference

router = APIRouter(tags=["reference"])


@router.get("/reference")
def metrics_reference(
    year: int | None = Query(None, description="Optional calendar year for live ESZ/DSZ engine counts"),
) -> dict[str, object]:
    """
    Canonical metric definitions and formulas (same rules as Strategy / Performance).

    Optional ``year`` adds ``engine_snapshot`` from the Garmin export when available.
    """

    payload: dict[str, object] = build_metrics_reference()
    settings = load_settings()
    y = int(year) if year is not None else int(settings.get("calendarYear", 2026))
    payload["year"] = y

    path = garmin_export_path()
    data = load_garmin_export(path)
    if data is None:
        payload["engine_snapshot"] = {
            "source_available": False,
            "reason": "GOLF_GARMIN_JSON not set or file missing",
        }
        return payload

    sc_ids = scorecard_ids_for_calendar_year(data, y)
    sc_filter = sc_ids if len(sc_ids) > 0 else None
    geom = compute_esz_dsz_from_shot_details(data, calendar_year=y, scorecard_ids=sc_filter)
    methods = geom.get("distance_to_pin_methods")
    payload["engine_snapshot"] = {
        "source_available": True,
        "source": str(path),
        "year": y,
        "holes_evaluated": geom.get("holes_evaluated"),
        "esz_pct": geom.get("esz_pct"),
        "dsz_pct": geom.get("dsz_pct"),
        "distance_to_pin_methods": methods if isinstance(methods, dict) else None,
        "note": geom.get("note"),
        "heuristic_note": geom.get("heuristic_note"),
        "data_model": geom.get("data_model"),
    }
    return payload
