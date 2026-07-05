"""Drill catalog and session logging API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from golf_analysis.drills.catalog import (
    append_session,
    delete_session,
    drill_session_stats,
    enrich_drill,
    find_drill,
    format_session_summary,
    list_sessions,
    load_drill_sessions_doc,
    load_effective_all_catalog,
    load_effective_category_catalog,
    reset_drill_overrides,
    set_favorites,
    toggle_favorite,
    update_drill,
    update_session,
)

router = APIRouter(tags=["drills"])


class SessionResultBody(BaseModel):
    score: int | None = None
    total: int | None = None
    completed: bool | None = None
    points: int | None = None
    streak: int | None = None
    attempts: int | None = None
    club: str | None = None
    aim: str | None = None
    combine_score: int | None = None


class LogSessionBody(BaseModel):
    drill_id: str
    result: SessionResultBody
    notes: str | None = None


class FavoritesBody(BaseModel):
    favorites: list[str] = Field(default_factory=list)


class DrillPatchBody(BaseModel):
    title: str | None = None
    description: str | None = None
    equipment_needed: list[str] | str | None = None
    distances: list[str] | str | None = None
    attempts_per_distance: int | None = None
    is_timed: bool | None = None
    penalty_reset_rule: str | None = None
    success_target: str | None = None
    expected_duration_minutes: int | None = None


class SessionPatchBody(BaseModel):
    result: SessionResultBody | None = None
    notes: str | None = None
    logged_at: str | None = None


def _enrich_all(drills: list[dict[str, Any]], stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_drill(d, stats=stats) for d in drills]


@router.get("/drills/catalog")
def get_catalog(category: str | None = None) -> dict[str, Any]:
    stats = drill_session_stats()
    if category:
        drills = _enrich_all(load_effective_category_catalog(category), stats)
        return {"category": category, "drills": drills}
    all_cat = load_effective_all_catalog()
    return {
        "categories": {
            cat: _enrich_all(drills, stats)
            for cat, drills in all_cat.items()
        }
    }


@router.get("/drills/state")
def get_drill_state() -> dict[str, Any]:
    doc = load_drill_sessions_doc()
    return {"favorites": doc.get("favorites") or [], "session_count": len(doc.get("sessions") or [])}


@router.get("/drills/favorites")
def get_favorites() -> dict[str, Any]:
    doc = load_drill_sessions_doc()
    stats = drill_session_stats()
    fav_ids = doc.get("favorites") or []
    drills: list[dict[str, Any]] = []
    for fid in fav_ids:
        found = find_drill(str(fid))
        if found:
            cat, drill = found
            enriched = enrich_drill(drill, stats=stats)
            enriched["category"] = cat
            drills.append(enriched)
    return {"favorites": fav_ids, "drills": drills}


@router.put("/drills/favorites")
def put_favorites(body: FavoritesBody) -> dict[str, Any]:
    favorites = set_favorites(body.favorites)
    return {"favorites": favorites}


@router.post("/drills/favorites/{drill_id}/toggle")
def post_toggle_favorite(drill_id: str) -> dict[str, Any]:
    if find_drill(drill_id) is None:
        raise HTTPException(status_code=404, detail="Drill not found")
    favorites = toggle_favorite(drill_id)
    return {"favorites": favorites, "drill_id": drill_id, "is_favorite": drill_id in favorites}


@router.get("/drills/sessions")
def get_sessions(drill_id: str | None = None, category: str | None = None) -> dict[str, Any]:
    rows = list_sessions(drill_id=drill_id, category=category)
    out: list[dict[str, Any]] = []
    for row in rows:
        found = find_drill(str(row.get("drill_id", "")))
        drill = found[1] if found else None
        item = dict(row)
        item["summary"] = format_session_summary(row, drill)
        out.append(item)
    return {"sessions": out}


@router.post("/drills/sessions")
def post_session(body: LogSessionBody) -> dict[str, Any]:
    try:
        row = append_session(
            drill_id=body.drill_id,
            result=body.result.model_dump(exclude_none=True),
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    found = find_drill(body.drill_id)
    drill = found[1] if found else None
    row["summary"] = format_session_summary(row, drill)
    return row


@router.patch("/drills/{drill_id}")
def patch_drill(drill_id: str, body: DrillPatchBody) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    try:
        drill = update_drill(drill_id, patch)
    except ValueError as e:
        raise HTTPException(status_code=404 if "Unknown drill" in str(e) else 400, detail=str(e)) from e
    stats = drill_session_stats()
    return enrich_drill(drill, stats=stats)


@router.delete("/drills/{drill_id}/overrides")
def delete_drill_overrides(drill_id: str) -> dict[str, Any]:
    try:
        drill = reset_drill_overrides(drill_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    stats = drill_session_stats()
    return enrich_drill(drill, stats=stats)


@router.patch("/drills/sessions/{session_id}")
def patch_session(session_id: str, body: SessionPatchBody) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    kwargs: dict[str, Any] = {}
    if "result" in patch and patch["result"] is not None:
        kwargs["result"] = SessionResultBody(**patch["result"]).model_dump(exclude_none=True)
    if "notes" in patch:
        kwargs["notes"] = patch["notes"]
    if "logged_at" in patch:
        kwargs["logged_at"] = patch["logged_at"]
    try:
        row = update_session(session_id, **kwargs)
    except ValueError as e:
        status = 404 if "Unknown" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e
    found = find_drill(str(row.get("drill_id", "")))
    drill = found[1] if found else None
    row = dict(row)
    row["summary"] = format_session_summary(row, drill)
    return row


@router.delete("/drills/sessions/{session_id}")
def delete_session_route(session_id: str) -> dict[str, Any]:
    try:
        delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"deleted": True, "session_id": session_id}
