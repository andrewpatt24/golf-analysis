from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from golf_analysis.api.deps import repo_root_from_db, require_db_exists
from golf_analysis.api.training_data import (
    club_training_rows,
    list_training_clubs_catalog,
    training_dispersion_settings,
    training_scatter_points,
)
from golf_analysis.range_analysis import lm_shot_cohort_sql
from golf_analysis.range_shot_analytics import (
    build_training_takeaways,
    club_carry_distribution,
    club_gapping,
    club_pair_landing_compare,
    landing_side_by_club,
    list_range_shots,
    shot_shape_bins,
)
from golf_analysis.repository import connect, init_schema
from golf_analysis.rapsodo_list_kinds import load_session_ids_for_calendar_year

router = APIRouter(tags=["range"])


def _year_param(year: int | None) -> int | None:
    return year


@router.get("/range/clubs-catalog")
@router.get("/training/clubs-catalog")
def range_clubs_catalog(db: Path = Depends(require_db_exists)) -> dict[str, object]:
    """All clubs in the library (for Settings exclusions and compare pickers)."""

    conn = connect(db)
    init_schema(conn)
    try:
        clubs = list_training_clubs_catalog(conn)
        _, excluded = training_dispersion_settings()
        return {"clubs": clubs, "excluded": sorted(excluded)}
    finally:
        conn.close()


@router.get("/range/clubs")
@router.get("/training/clubs")
def range_clubs(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None, description="Calendar year filter; omit for all years"),
) -> list[dict[str, object]]:
    conn = connect(db)
    init_schema(conn)
    try:
        return club_training_rows(conn, db_path=db, calendar_year=_year_param(year))
    finally:
        conn.close()


@router.get("/range/scatter")
@router.get("/training/scatter")
def range_scatter(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None),
    club: Annotated[list[str] | None, Query()] = None,
    session_id: Annotated[list[int] | None, Query()] = None,
) -> list[dict[str, object]]:
    conn = connect(db)
    init_schema(conn)
    try:
        clubs = [c for c in (club or []) if c.strip()] or None
        sids = [int(x) for x in (session_id or [])] if session_id else None
        return training_scatter_points(
            conn,
            db_path=db,
            calendar_year=_year_param(year),
            clubs=clubs,
            session_ids=sids,
        )
    finally:
        conn.close()


@router.get("/range/sessions")
@router.get("/training/sessions")
def range_sessions(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
) -> list[dict[str, object]]:
    conn = connect(db)
    init_schema(conn)
    cohort = lm_shot_cohort_sql()
    params: list[object] = []
    year_sql = ""
    if year is not None:
        repo = repo_root_from_db(db)
        sids = load_session_ids_for_calendar_year(repo, year) if repo else set()
        y0 = f"{year}-01-01"
        y1 = f"{year + 1}-01-01"
        if sids:
            ph = ",".join("?" * len(sids))
            year_sql = (
                f" AND substr(s.title, 17) IN ({ph}) "
                "AND length(s.title) >= 17 "
                "AND lower(substr(s.title, 1, 16)) = 'rapsodo_session_'"
            )
            params.extend(sorted(sids))
        else:
            year_sql = " AND s.started_at >= ? AND s.started_at < ? "
            params.extend([y0, y1])
    params.append(limit)
    sql = f"""
        SELECT s.id, s.title, s.started_at, COUNT(rs.id) AS n_shots
        FROM range_sessions s
        JOIN imports i ON i.id = s.import_id
        LEFT JOIN range_shots rs ON rs.session_id = s.id
        WHERE {cohort}
          {year_sql}
        GROUP BY s.id
        ORDER BY (s.started_at IS NULL) ASC, s.started_at DESC
        LIMIT ?
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {"session_id": int(r[0]), "title": r[1], "started_at": r[2], "shot_count": int(r[3] or 0)}
        for r in rows
    ]


@router.get("/range/analytics")
@router.get("/training/analytics")
def range_analytics(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None),
) -> dict[str, object]:
    """Carry distribution (p10/p90), landing-side %, gapping, shot-shape proxy."""

    conn = connect(db)
    init_schema(conn)
    try:
        y = _year_param(year)
        landing = landing_side_by_club(conn, db_path=db, calendar_year=y)
        gapping = club_gapping(conn, db_path=db, calendar_year=y)
        shape = shot_shape_bins(conn, db_path=db, calendar_year=y)
        carry = club_carry_distribution(conn, db_path=db, calendar_year=y)
        takeaways = build_training_takeaways(
            landing_side=landing,
            gapping=gapping,
            shot_shape=shape,
            carry_distribution=carry,
        )
        return {
            "carry_distribution": carry,
            "landing_side": landing,
            "gapping": gapping,
            "shot_shape": shape,
            "takeaways": takeaways,
        }
    finally:
        conn.close()


@router.get("/range/club-compare")
@router.get("/training/club-compare")
def range_club_compare(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None),
    club_a: str = Query(..., min_length=1, description="First club (matches lower(trim) in DB)"),
    club_b: str = Query(..., min_length=1, description="Second club"),
) -> dict[str, object]:
    """Two-club landing + carry-by-band + mean launch/smash (Session Insights style)."""

    conn = connect(db)
    init_schema(conn)
    try:
        return club_pair_landing_compare(
            conn,
            db_path=db,
            calendar_year=_year_param(year),
            club_a=club_a,
            club_b=club_b,
        )
    finally:
        conn.close()


@router.get("/range/shots")
@router.get("/training/shots")
def range_shots(
    db: Path = Depends(require_db_exists),
    year: int | None = Query(None),
    club: str | None = Query(None),
    session_id: int | None = Query(None),
    limit: int = Query(80, ge=1, le=500),
) -> list[dict[str, object]]:
    """Recent shots for drill-down (feature list: list of shots with stats)."""

    conn = connect(db)
    init_schema(conn)
    try:
        return list_range_shots(
            conn,
            db_path=db,
            calendar_year=_year_param(year),
            club=club,
            session_id=session_id,
            limit=limit,
        )
    finally:
        conn.close()
