"""Individual range-shot cohort filters and summary stats (Rapsodo + library SQLite)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Included in v1 individual-shot LM analytics (see project discussion).
LM_SHOT_LIST_SOURCE_KINDS = frozenset({"practice", "combine"})

# Explicitly excluded from that cohort when list_source_kind is set (sim / games).
EXCLUDED_LIST_SOURCE_KINDS = frozenset(
    {"courses", "range", "closest_to_pin", "target_range", "unknown", "list"}
)


def lm_shot_cohort_sql() -> str:
    """
    SQL snippet: true when a range_shots row belongs to the v1 LM shot analysis cohort.

    - Rapsodo CSV imports only.
    - ``list_source_kind`` must be practice or combine, OR NULL (legacy ingest before snapshot).
    """

    kinds = ", ".join(f"'{k}'" for k in sorted(LM_SHOT_LIST_SOURCE_KINDS))
    return f"""(
  i.connector_id = 'rapsodo_csv'
  AND (s.list_source_kind IN ({kinds}) OR s.list_source_kind IS NULL)
)"""


@dataclass
class RangeShotsReport:
    text: str


def build_range_shots_report(conn: sqlite3.Connection) -> RangeShotsReport:
    cohort = lm_shot_cohort_sql()
    cur = conn.cursor()

    n_sessions = cur.execute(
        f"SELECT COUNT(DISTINCT s.id) FROM range_sessions s "
        f"JOIN imports i ON i.id = s.import_id WHERE {cohort}",
    ).fetchone()[0]
    n_shots = cur.execute(
        f"SELECT COUNT(*) FROM range_shots rs "
        f"JOIN range_sessions s ON s.id = rs.session_id "
        f"JOIN imports i ON i.id = s.import_id WHERE {cohort}",
    ).fetchone()[0]

    by_kind = cur.execute(
        f"SELECT COALESCE(s.list_source_kind, '(null)'), COUNT(DISTINCT s.id), COUNT(rs.id) "
        f"FROM range_sessions s "
        f"JOIN imports i ON i.id = s.import_id "
        f"LEFT JOIN range_shots rs ON rs.session_id = s.id "
        f"WHERE {cohort} "
        f"GROUP BY 1 ORDER BY 1",
    ).fetchall()

    excluded_sessions = cur.execute(
        "SELECT COUNT(DISTINCT s.id) FROM range_sessions s "
        "JOIN imports i ON i.id = s.import_id WHERE i.connector_id = 'rapsodo_csv' "
        "AND s.list_source_kind IS NOT NULL AND "
        f"s.list_source_kind IN ({', '.join(repr(k) for k in sorted(EXCLUDED_LIST_SOURCE_KINDS))})",
    ).fetchone()[0]

    club_rows = cur.execute(
        f"SELECT rs.club, COUNT(*), AVG(rs.ball_speed_mph), AVG(rs.carry_yards) "
        f"FROM range_shots rs "
        f"JOIN range_sessions s ON s.id = rs.session_id "
        f"JOIN imports i ON i.id = s.import_id "
        f"WHERE {cohort} AND rs.club IS NOT NULL AND TRIM(rs.club) != '' "
        f"GROUP BY rs.club ORDER BY COUNT(*) DESC LIMIT 15",
    ).fetchall()

    lines: list[str] = [
        "Range shots report (v1 LM cohort)",
        "",
        "Cohort: Rapsodo CSV, list_source_kind in {practice, combine} OR NULL (legacy).",
        "",
        f"Sessions in cohort: {int(n_sessions)}",
        f"Shots in cohort: {int(n_shots)}",
        f"Rapsodo sessions excluded by list kind (courses/range/…): {int(excluded_sessions)}",
        "",
        "By list_source_kind (sessions / shots):",
    ]
    for kind, ns, nshot in by_kind:
        lines.append(f"  {kind}: sessions={int(ns)}, shots={int(nshot)}")
    lines.append("")
    lines.append("Top clubs by shot count (mean ball speed mph, mean carry yd):")
    for club, cnt, mb, mc in club_rows:
        if club is None:
            continue
        bs = f"{mb:.1f}" if mb is not None else "—"
        cy = f"{mc:.1f}" if mc is not None else "—"
        lines.append(f"  {club}: n={int(cnt)}, ball_speed={bs}, carry={cy}")
    if not club_rows:
        lines.append("  (no club-labelled shots in cohort)")

    return RangeShotsReport(text="\n".join(lines) + "\n")


def run_range_shots_report(db_path: Path) -> str:
    from golf_analysis.repository import connect, init_schema

    conn = connect(db_path)
    init_schema(conn)
    try:
        return build_range_shots_report(conn).text
    finally:
        conn.close()
