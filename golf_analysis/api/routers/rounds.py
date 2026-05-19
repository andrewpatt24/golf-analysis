from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from golf_analysis.api.deps import require_db_exists
from golf_analysis.api.settings_store import load_settings
from golf_analysis.repository import connect, init_schema

router = APIRouter(tags=["rounds"])


@router.get("/rounds")
def list_rounds(
    db: Path = Depends(require_db_exists),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, object | None]]:
    settings = load_settings()
    max_age = int(settings.get("maxAgeDays", 365))
    max_n = int(settings.get("maxRounds", 10))
    lim = min(limit, max_n)
    conn = connect(db)
    init_schema(conn)
    try:
        rows = conn.execute(
            """
            SELECT r.id, r.course_name, r.title, r.started_at, r.ended_at,
                   r.total_strokes, r.total_putts, r.score_relative_to_par,
                   (SELECT COUNT(*) FROM round_holes h WHERE h.round_id = r.id)
            FROM golf_rounds r
            WHERE r.started_at IS NOT NULL
              AND date(r.started_at) >= date('now', ?)
            ORDER BY r.started_at DESC
            LIMIT ?
            """,
            (f"-{max_age} days", lim),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict[str, object | None]] = []
    for r in rows:
        out.append(
            {
                "id": int(r[0]),
                "course_name": r[1],
                "title": r[2],
                "started_at": r[3],
                "ended_at": r[4],
                "total_strokes": r[5],
                "total_putts": r[6],
                "score_relative_to_par": r[7],
                "round_hole_count": int(r[8] or 0),
            }
        )
    return out


@router.get("/rounds/summary")
def rounds_summary(db: Path = Depends(require_db_exists)) -> dict[str, object]:
    settings = load_settings()
    max_age = int(settings.get("maxAgeDays", 365))
    conn = connect(db)
    init_schema(conn)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*),
                   AVG(CAST(score_relative_to_par AS REAL)),
                   SUM(CAST(total_putts AS INTEGER))
            FROM golf_rounds
            WHERE started_at IS NOT NULL
              AND date(started_at) >= date('now', ?)
            """,
            (f"-{max_age} days",),
        ).fetchone()
        n = int(row[0] or 0)
        avg_vs_par = float(row[1]) if row[1] is not None else None
        putts_sum = int(row[2] or 0) if row[2] is not None else None
    finally:
        conn.close()
    return {
        "rounds_in_window": n,
        "mean_score_relative_to_par": avg_vs_par,
        "sum_putts": putts_sum,
        "window_days": max_age,
    }
