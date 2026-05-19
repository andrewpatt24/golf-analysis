from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from golf_analysis.api.deps import require_db_exists
from golf_analysis.api.settings_store import load_settings
from golf_analysis.api.training_data import club_training_rows
from golf_analysis.range_shot_analytics import training_takeaways_for_window
from golf_analysis.repository import connect, init_schema

router = APIRouter(tags=["plans"])


@router.get("/plans/training-block")
def training_block_plan(
    db: Path = Depends(require_db_exists),
) -> dict[str, object]:
    """Insights + N-session block from settings (NBLM-style placeholders + real LM flags)."""

    settings = load_settings()
    n_sessions = int(settings.get("trainingBlockSessions", 4))
    year = int(settings.get("calendarYear", 2026))
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

    sessions: list[dict[str, object]] = []
    templates = [
        ("Priority 1 — Distance game", "Random targets, change clubs; ~45 min / 50 balls.", "P1"),
        ("Priority 1 — Direction game", "10-yard accuracy window; check spin axis if curving.", "P1"),
        ("Priority 2 — Maintenance", "Short game touch; fewer balls, quality tempo.", "P2"),
        ("Priority 3 — Combine / gapping", "Rapsodo Combine or wedge ladder when available.", "P3"),
    ]
    for i in range(min(n_sessions, len(templates))):
        title, desc, tag = templates[i]
        sessions.append(
            {
                "index": i + 1,
                "title": title,
                "description": desc,
                "priority_tag": tag,
            }
        )
    if n_sessions > len(templates):
        for j in range(len(templates), n_sessions):
            sessions.append(
                {
                    "index": j + 1,
                    "title": f"Extra session {j + 1}",
                    "description": "Repeat weakest pillar drill or on-course rehearsal.",
                    "priority_tag": "P1",
                }
            )

    return {
        "calendar_year": year,
        "sessions_planned": n_sessions,
        "insights": insights,
        "flagged_clubs": [c["club"] for c in flagged],
        "sessions": sessions,
    }
