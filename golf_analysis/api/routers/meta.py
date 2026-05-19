from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from golf_analysis.api.deps import require_db_exists
from golf_analysis.repository import connect, init_schema

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta(db: Path = Depends(require_db_exists)) -> dict[str, object]:
    conn = connect(db)
    init_schema(conn)
    try:
        n_rounds = conn.execute("SELECT COUNT(*) FROM golf_rounds").fetchone()[0]
        n_range_shots = conn.execute("SELECT COUNT(*) FROM range_shots").fetchone()[0]
        n_sessions = conn.execute("SELECT COUNT(*) FROM range_sessions").fetchone()[0]
    finally:
        conn.close()
    return {
        "library_db": str(db),
        "golf_rounds": int(n_rounds),
        "range_sessions": int(n_sessions),
        "range_shots": int(n_range_shots),
    }
