from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from golf_analysis.analysis_plan_report import dispersion_by_club, range_shot_rows_for_dispersion
from golf_analysis.api.deps import repo_root_from_db


def club_training_rows(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
) -> list[dict[str, Any]]:
    repo = repo_root_from_db(db_path)
    rows = range_shot_rows_for_dispersion(conn, calendar_year=calendar_year, repo_root=repo)
    from golf_analysis.range_analysis import lm_shot_cohort_sql

    cohort = lm_shot_cohort_sql()
    year_sql = ""
    params: list[Any] = []
    if calendar_year is not None:
        from golf_analysis.rapsodo_list_kinds import load_session_ids_for_calendar_year

        sids = load_session_ids_for_calendar_year(repo, calendar_year) if repo else set()
        y0 = f"{calendar_year}-01-01"
        y1 = f"{calendar_year + 1}-01-01"
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
    abs_sql = f"""
        SELECT lower(trim(rs.club)) AS c, AVG(ABS(rs.offline_yards)) AS mean_abs_off
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.club IS NOT NULL AND TRIM(rs.club) != ''
          AND rs.carry_yards IS NOT NULL AND rs.offline_yards IS NOT NULL
          {year_sql}
        GROUP BY 1
    """
    mean_abs_by_club = {r[0]: float(r[1]) for r in conn.execute(abs_sql, params).fetchall() if r[0]}

    out: list[dict[str, Any]] = []
    for row in dispersion_by_club(rows):
        mean_c = row["mean_carry_yards"]
        mean_abs = mean_abs_by_club.get(row["club"])
        ratio_mean = None
        if mean_c and mean_abs is not None:
            ratio_mean = mean_abs / float(mean_c)
        out.append(
            {
                "club": row["club"],
                "n": row["n"],
                "mean_carry_yards": mean_c,
                "mean_total_yards": None,
                "mean_abs_offline_yards": mean_abs,
                "std_carry_yards": row["std_carry_yards"],
                "std_offline_yards": row["std_offline_yards"],
                "lateral_to_length_ratio_sd": row["lateral_to_length_ratio"],
                "dispersion_ratio_mean_abs_offline_per_carry": ratio_mean,
                "median_path_deg": row["median_path_deg"],
                "median_launch_dir_deg": row["median_launch_dir_deg"],
                "median_smash": row["median_smash"],
                "needs_work": row["needs_work"],
            }
        )
    return out


def training_scatter_points(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    clubs: list[str] | None,
    session_ids: list[int] | None,
) -> list[dict[str, Any]]:
    """Shot-level points for scatter (x/y chosen client-side from keys on each point)."""

    from golf_analysis.range_analysis import lm_shot_cohort_sql
    from golf_analysis.rapsodo_list_kinds import load_session_ids_for_calendar_year

    cohort = lm_shot_cohort_sql()
    params: list[Any] = []
    year_sql = ""
    if calendar_year is not None:
        repo = repo_root_from_db(db_path)
        sids = load_session_ids_for_calendar_year(repo, calendar_year) if repo else set()
        y0 = f"{calendar_year}-01-01"
        y1 = f"{calendar_year + 1}-01-01"
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

    club_sql = ""
    if clubs:
        norms = [c.strip().lower() for c in clubs if c.strip()]
        if norms:
            club_sql = " AND lower(trim(rs.club)) IN (" + ",".join("?" * len(norms)) + ") "
            params.extend(norms)

    sess_sql = ""
    if session_ids:
        sess_sql = " AND s.id IN (" + ",".join("?" * len(session_ids)) + ") "
        params.extend(session_ids)

    sql = f"""
        SELECT rs.carry_yards, rs.offline_yards, rs.ball_speed_mph, rs.smash_factor,
               lower(trim(rs.club)) AS club, s.id AS session_id, s.title AS session_title,
               s.started_at AS session_started_at
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.carry_yards IS NOT NULL
          {year_sql}
          {club_sql}
          {sess_sql}
        LIMIT 5000
    """
    cur = conn.execute(sql, params)
    points: list[dict[str, Any]] = []
    for r in cur.fetchall():
        points.append(
            {
                "carry_yards": r[0],
                "offline_yards": r[1],
                "ball_speed_mph": r[2],
                "smash_factor": r[3],
                "club": r[4],
                "session_id": r[5],
                "session_title": r[6],
                "session_started_at": r[7],
            }
        )
    return points
