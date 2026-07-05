from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from golf_analysis.api.deps import garmin_export_path, require_db_exists
from golf_analysis.api.settings_store import load_settings
from golf_analysis.api.training_data import club_training_rows
from golf_analysis.garmin_export_analytics import load_garmin_export, scoring_method_proxy_metrics_from_export
from golf_analysis.range_shot_analytics import training_takeaways_for_window
from golf_analysis.repository import connect, init_schema
from golf_analysis.training_block_planner import build_training_block, enrich_block_completion
from golf_analysis.training_block_store import (
    block_all_complete,
    clear_active_block,
    get_active_block,
    mark_session_complete,
    save_active_block,
)

router = APIRouter(tags=["plans"])


class CompleteSessionBody(BaseModel):
    linked_session_id: str | None = None


def _garmin_scoring_for_year(year: int) -> dict[str, Any] | None:
    path = garmin_export_path()
    data = load_garmin_export(path)
    if data is None:
        return None
    return scoring_method_proxy_metrics_from_export(data, calendar_year=year)


def _collect_plan_inputs(db: Path, year: int) -> tuple[list[str], list[str], list[str]]:
    conn = connect(db)
    init_schema(conn)
    try:
        clubs = club_training_rows(conn, db_path=db, calendar_year=year)
        take_lines = training_takeaways_for_window(conn, db_path=db, calendar_year=year, max_items=4)
    finally:
        conn.close()

    flagged = [c for c in clubs if c.get("needs_work")]
    insights: list[str] = []
    insights.extend(take_lines)
    if flagged:
        top = sorted(flagged, key=lambda x: -int(x["n"]))[:3]
        for c in top:
            mabs = c.get("mean_abs_offline_yards")
            mabs_s = f"{float(mabs):.1f}" if mabs is not None else "—"
            insights.append(
                f"{c['club']}: dispersion focus — mean carry {float(c['mean_carry_yards']):.0f} yd, "
                f"mean |offline| {mabs_s} yd "
                f"({c['n']} shots in {year})."
            )
    else:
        insights.append("No clubs flagged in dispersion rules for this window — keep baseline tracking.")

    flagged_ids = [str(c["club"]) for c in flagged]
    return insights, flagged_ids, take_lines


def _generate_block(db: Path, *, year: int, n_sessions: int) -> dict[str, Any]:
    insights, flagged_ids, _ = _collect_plan_inputs(db, year)
    garmin_scoring = _garmin_scoring_for_year(year)
    block = build_training_block(
        calendar_year=year,
        n_sessions=n_sessions,
        garmin_scoring=garmin_scoring,
        rapsodo_insights=insights,
        flagged_clubs=flagged_ids,
    )
    save_active_block(block)
    return block


def _ensure_active_block(db: Path) -> dict[str, Any]:
    settings = load_settings()
    year = int(settings.get("calendarYear", 2026))
    n_sessions = int(settings.get("trainingBlockSessions", 4))

    active = get_active_block()
    if active and int(active.get("calendar_year", year)) == year:
        return enrich_block_completion(active)

    return _generate_block(db, year=year, n_sessions=n_sessions)


@router.get("/plans/training-block")
def training_block_plan(
    db: Path = Depends(require_db_exists),
) -> dict[str, object]:
    """Active drill-linked training block; generates on first visit or new year."""

    block = _ensure_active_block(db)
    return block


@router.post("/plans/training-block/regenerate")
def regenerate_training_block(
    db: Path = Depends(require_db_exists),
) -> dict[str, object]:
    """Start a fresh block after the current one is fully complete."""

    active = get_active_block()
    if active and not block_all_complete(active):
        raise HTTPException(
            status_code=400,
            detail="Complete all sessions in the current block before regenerating.",
        )

    settings = load_settings()
    year = int(settings.get("calendarYear", 2026))
    n_sessions = int(settings.get("trainingBlockSessions", 4))
    clear_active_block()
    block = _generate_block(db, year=year, n_sessions=n_sessions)
    return block


@router.patch("/plans/training-block/sessions/{session_index}/complete")
def complete_training_session(
    session_index: int,
    body: CompleteSessionBody | None = None,
    db: Path = Depends(require_db_exists),
) -> dict[str, object]:
    payload = body or CompleteSessionBody()
    active = _ensure_active_block(db)
    try:
        updated = mark_session_complete(
            active,
            session_index,
            linked_session_id=payload.linked_session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    save_active_block(updated)
    return enrich_block_completion(updated)
