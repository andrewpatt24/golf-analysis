"""Rapsodo / range_shots analytics for dashboard (training tab)."""

from __future__ import annotations

import sqlite3
import statistics
from pathlib import Path
from typing import Any

from golf_analysis.range_analysis import lm_shot_cohort_sql
from golf_analysis.rapsodo_list_kinds import load_session_ids_for_calendar_year


def _repo_root(db_path: Path) -> Path | None:
    from golf_analysis.rapsodo_list_kinds import find_repo_root

    return find_repo_root(db_path.parent)


def _year_clause(calendar_year: int | None, db_path: Path) -> tuple[str, list[Any]]:
    if calendar_year is None:
        return "", []
    repo = _repo_root(db_path)
    session_ids = load_session_ids_for_calendar_year(repo, calendar_year) if repo else set()
    y0 = f"{calendar_year}-01-01"
    y1 = f"{calendar_year + 1}-01-01"
    if session_ids:
        ph = ",".join("?" * len(session_ids))
        sql = (
            f" AND substr(s.title, 17) IN ({ph}) "
            "AND length(s.title) >= 17 "
            "AND lower(substr(s.title, 1, 16)) = 'rapsodo_session_'"
        )
        return sql, sorted(session_ids)
    return " AND s.started_at >= ? AND s.started_at < ? ", [y0, y1]


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def club_carry_distribution(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
) -> list[dict[str, Any]]:
    """Per club: n, mean carry, p10/p90 carry (linear interpolation), mean |offline|."""

    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    sql = f"""
        SELECT lower(trim(rs.club)) AS club, rs.carry_yards, rs.offline_yards
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.club IS NOT NULL AND TRIM(rs.club) != ''
          AND rs.carry_yards IS NOT NULL
          {ysql}
    """
    rows = conn.execute(sql, yparams).fetchall()
    by_club: dict[str, dict[str, list[float]]] = {}
    for club, carry, off in rows:
        if not club or club in ("average", "median", "std. dev.", "club type"):
            continue
        by_club.setdefault(club, {"carry": [], "abs_off": []})
        by_club[club]["carry"].append(float(carry))
        if off is not None:
            by_club[club]["abs_off"].append(abs(float(off)))

    out: list[dict[str, Any]] = []
    for club, d in sorted(by_club.items(), key=lambda x: -len(x[1]["carry"])):
        carries = sorted(d["carry"])
        n = len(carries)
        if n < 3:
            continue
        mean_c = statistics.fmean(carries)
        p10 = _percentile(carries, 0.10)
        p90 = _percentile(carries, 0.90)
        mean_abs = statistics.fmean(d["abs_off"]) if d["abs_off"] else None
        disp_idx = (mean_abs / mean_c) if mean_abs is not None and mean_c else None
        out.append(
            {
                "club": club,
                "n": n,
                "mean_carry_yards": mean_c,
                "p10_carry_yards": p10,
                "p90_carry_yards": p90,
                "mean_abs_offline_yards": mean_abs,
                "dispersion_index_mean_abs_per_carry": disp_idx,
            }
        )
    return out


def landing_side_by_club(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    straight_yards: float = 5.0,
) -> list[dict[str, Any]]:
    """Classify offline sign into left / right / straight (|offline| < threshold)."""

    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    sql = f"""
        SELECT lower(trim(rs.club)) AS club, rs.offline_yards
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.club IS NOT NULL AND TRIM(rs.club) != ''
          AND rs.offline_yards IS NOT NULL
          {ysql}
    """
    rows = conn.execute(sql, yparams).fetchall()
    by_club: dict[str, dict[str, int]] = {}
    for club, off in rows:
        if not club or club in ("average", "median", "std. dev.", "club type"):
            continue
        b = by_club.setdefault(club, {"left": 0, "right": 0, "straight": 0, "n": 0})
        o = float(off)
        b["n"] += 1
        if abs(o) < straight_yards:
            b["straight"] += 1
        elif o < 0:
            b["left"] += 1
        else:
            b["right"] += 1

    out: list[dict[str, Any]] = []
    for club, b in sorted(by_club.items(), key=lambda x: -x[1]["n"]):
        n = b["n"]
        if n < 5:
            continue
        out.append(
            {
                "club": club,
                "n": n,
                "pct_left": 100.0 * b["left"] / n,
                "pct_right": 100.0 * b["right"] / n,
                "pct_straight": 100.0 * b["straight"] / n,
                "straight_band_yards": straight_yards,
            }
        )
    return out


def club_gapping(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    min_shots: int = 8,
) -> list[dict[str, Any]]:
    """Clubs sorted by median carry (longest first); gap = shorter carry vs the club above."""

    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    sql = f"""
        SELECT lower(trim(rs.club)) AS club, rs.carry_yards
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.club IS NOT NULL AND TRIM(rs.club) != ''
          AND rs.carry_yards IS NOT NULL
          {ysql}
    """
    rows = conn.execute(sql, yparams).fetchall()
    by_club: dict[str, list[float]] = {}
    for club, carry in rows:
        if not club or club in ("average", "median", "std. dev.", "club type"):
            continue
        by_club.setdefault(club, []).append(float(carry))
    medians: list[tuple[str, float, int]] = []
    for club, carries in by_club.items():
        if len(carries) < min_shots:
            continue
        med = statistics.median(carries)
        medians.append((club, med, len(carries)))
    # Longest carry first (typical bag view); gap = yards shorter than the club above (longer).
    medians.sort(key=lambda x: x[1], reverse=True)
    out: list[dict[str, Any]] = []
    prev_med: float | None = None
    prev_club: str | None = None
    for club, med, n in medians:
        gap = (prev_med - med) if prev_med is not None else None
        out.append(
            {
                "club": club,
                "median_carry_yards": med,
                "n": n,
                "gap_from_previous_club_yards": gap,
                "previous_club_in_order": prev_club,
            }
        )
        prev_med = med
        prev_club = club
    return out


def list_range_shots(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    club: str | None = None,
    session_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    params: list[Any] = list(yparams)
    extra = ""
    if club and club.strip():
        extra += " AND lower(trim(rs.club)) = ? "
        params.append(club.strip().lower())
    if session_id is not None:
        extra += " AND s.id = ? "
        params.append(session_id)
    params.append(limit)
    sql = f"""
        SELECT rs.id, rs.shot_index, lower(trim(rs.club)), rs.carry_yards, rs.offline_yards,
               rs.ball_speed_mph, rs.smash_factor, rs.launch_angle_deg, rs.spin_rpm, rs.spin_axis_deg,
               s.id, s.title, s.started_at
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          {ysql}
          {extra}
        ORDER BY s.started_at DESC NULLS LAST, rs.id DESC
        LIMIT ?
    """
    cur = conn.execute(sql, params)
    out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        out.append(
            {
                "shot_id": int(r[0]),
                "shot_index": r[1],
                "club": r[2],
                "carry_yards": r[3],
                "offline_yards": r[4],
                "ball_speed_mph": r[5],
                "smash_factor": r[6],
                "launch_angle_deg": r[7],
                "spin_rpm": r[8],
                "spin_axis_deg": r[9],
                "session_id": int(r[10]),
                "session_title": r[11],
                "session_started_at": r[12],
            }
        )
    return out


def _spin_axis_shape_category(axis: float) -> str:
    """
    RH-oriented coarse bins on spin-axis degrees (Rapsodo / LM convention).

    Negative → draw/hook tendency, positive → fade/slice; thresholds are a first
    pass — tune vs vendor UI once you have enough tagged sessions.
    """

    if axis <= -12:
        return "hook"
    if axis <= -4:
        return "draw"
    if axis < 4:
        return "straight"
    if axis < 12:
        return "fade"
    return "slice"


def shot_shape_bins(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
) -> dict[str, Any]:
    """Offline sign proxy (3-way) + optional Rapsodo-style five-way from spin axis."""

    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    sql_off = f"""
        SELECT rs.offline_yards
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.offline_yards IS NOT NULL
          {ysql}
    """
    off_rows = conn.execute(sql_off, yparams).fetchall()
    hook = slice_bias = straight = 0
    for (off,) in off_rows:
        o = float(off)
        if abs(o) < 8:
            straight += 1
        elif o > 0:
            slice_bias += 1
        else:
            hook += 1
    n_off = len(off_rows)

    sql_axis = f"""
        SELECT rs.spin_axis_deg
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND rs.spin_axis_deg IS NOT NULL
          {ysql}
    """
    axis_rows = conn.execute(sql_axis, yparams).fetchall()
    bins = {"hook": 0, "draw": 0, "straight": 0, "fade": 0, "slice": 0}
    for (axis,) in axis_rows:
        cat = _spin_axis_shape_category(float(axis))
        bins[cat] += 1
    n_spin = len(axis_rows)
    min_spin = 15
    usable = n_spin >= min_spin
    five_way: dict[str, Any] | None = None
    if n_spin:
        five_way = {
            "n": n_spin,
            "usable": usable,
            "pct_hook": 100.0 * bins["hook"] / n_spin,
            "pct_draw": 100.0 * bins["draw"] / n_spin,
            "pct_straight": 100.0 * bins["straight"] / n_spin,
            "pct_fade": 100.0 * bins["fade"] / n_spin,
            "pct_slice": 100.0 * bins["slice"] / n_spin,
            "bins_deg": "<= -12 hook, (-12,-4] draw, (-4,4) straight, [4,12) fade, >=12 slice (RH)",
        }
        if not usable:
            five_way["note"] = f"Need at least {min_spin} shots with spin axis for stable five-way %."

    return {
        "n_shots": n_off,
        "n_shots_spin_axis": n_spin,
        "note": (
            "Offline: |offline|<8 yd = straight band, else hook vs slice *side* from sign. "
            "Five-way hook/draw/straight/fade/slice uses spin-axis bins when present (Session Insights style)."
        ),
        "pct_hook_side": (100.0 * hook / n_off) if n_off else None,
        "pct_slice_side": (100.0 * slice_bias / n_off) if n_off else None,
        "pct_straight_band": (100.0 * straight / n_off) if n_off else None,
        "five_way_spin_axis": five_way,
    }


def _club_compare_one(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    club: str,
    straight_yards: float,
) -> dict[str, Any] | None:
    """Landing % + mean carry by lateral band + mean launch/smash for one club."""

    cohort = lm_shot_cohort_sql()
    ysql, yparams = _year_clause(calendar_year, db_path)
    sql = f"""
        SELECT rs.offline_yards, rs.carry_yards, rs.launch_angle_deg, rs.smash_factor
        FROM range_shots rs
        JOIN range_sessions s ON s.id = rs.session_id
        JOIN imports i ON i.id = s.import_id
        WHERE {cohort}
          AND lower(trim(rs.club)) = ?
          AND rs.offline_yards IS NOT NULL
          AND rs.carry_yards IS NOT NULL
          {ysql}
    """
    params: list[Any] = [club, *yparams]
    rows = conn.execute(sql, params).fetchall()
    if len(rows) < 5:
        return None
    left_c: list[float] = []
    right_c: list[float] = []
    str_c: list[float] = []
    launches: list[float] = []
    smashes: list[float] = []
    n_left = n_right = n_str = 0
    for off, carry, la, sm in rows:
        o = float(off)
        c = float(carry)
        if la is not None:
            launches.append(float(la))
        if sm is not None:
            smashes.append(float(sm))
        if abs(o) < straight_yards:
            n_str += 1
            str_c.append(c)
        elif o < 0:
            n_left += 1
            left_c.append(c)
        else:
            n_right += 1
            right_c.append(c)
    n = len(rows)
    return {
        "club": club,
        "n": n,
        "pct_left": 100.0 * n_left / n,
        "pct_straight": 100.0 * n_str / n,
        "pct_right": 100.0 * n_right / n,
        "mean_carry_yards_left": statistics.fmean(left_c) if left_c else None,
        "mean_carry_yards_straight": statistics.fmean(str_c) if str_c else None,
        "mean_carry_yards_right": statistics.fmean(right_c) if right_c else None,
        "mean_launch_angle_deg": statistics.fmean(launches) if launches else None,
        "mean_smash_factor": statistics.fmean(smashes) if smashes else None,
        "straight_band_yards": straight_yards,
    }


def club_pair_landing_compare(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    club_a: str,
    club_b: str,
    straight_yards: float = 5.0,
) -> dict[str, Any]:
    """
    Session Insights–style two-club comparison: lateral mix + mean carry when missing left/right.
    """

    ca = club_a.strip().lower()
    cb = club_b.strip().lower()
    if not ca or not cb:
        return {"error": "club_a and club_b must be non-empty"}
    if ca == cb:
        return {"error": "Pick two different clubs"}
    sa = _club_compare_one(
        conn, db_path=db_path, calendar_year=calendar_year, club=ca, straight_yards=straight_yards
    )
    sb = _club_compare_one(
        conn, db_path=db_path, calendar_year=calendar_year, club=cb, straight_yards=straight_yards
    )
    return {
        "club_a": sa,
        "club_b": sb,
        "straight_band_yards": straight_yards,
        "calendar_year": calendar_year,
    }


def build_training_takeaways(
    *,
    landing_side: list[dict[str, Any]],
    gapping: list[dict[str, Any]],
    shot_shape: dict[str, Any],
    carry_distribution: list[dict[str, Any]] | None = None,
    max_items: int = 6,
) -> list[str]:
    """Short deterministic lines (feature list: key takeaways)."""

    lines: list[str] = []
    for row in landing_side:
        n = int(row["n"])
        if n < 12:
            continue
        pl, pr = float(row["pct_left"]), float(row["pct_right"])
        if pl >= 48 and pl >= pr + 12:
            lines.append(
                f"{row['club']}: {pl:.0f}% left vs {pr:.0f}% right ({n} shots) — bias left; "
                "plan start line and aim away from left trouble."
            )
        elif pr >= 48 and pr >= pl + 12:
            lines.append(
                f"{row['club']}: {pr:.0f}% right vs {pl:.0f}% left ({n} shots) — bias right; "
                "check face-to-path and alignment."
            )
    for row in gapping[1:]:
        gapv = row.get("gap_from_previous_club_yards")
        prev = row.get("previous_club_in_order")
        if gapv is None or prev is None:
            continue
        if float(gapv) < 6 and int(row["n"]) >= 8:
            lines.append(
                f"Gapping: {row['club']} is only {float(gapv):.0f} yd beyond {prev} on median carry — "
                "verify separation or dial loft/length."
            )
            break
    fw = shot_shape.get("five_way_spin_axis")
    if isinstance(fw, dict) and fw.get("usable"):
        ps = float(fw.get("pct_slice") or 0)
        ph = float(fw.get("pct_hook") or 0)
        nspin = int(fw.get("n") or 0)
        if ps >= 28:
            lines.append(
                f"Shape (spin axis): {ps:.0f}% slice bin over {nspin} shots — work face control / path match."
            )
        elif ph >= 22:
            lines.append(
                f"Shape (spin axis): {ph:.0f}% hook bin over {nspin} shots — watch path in-to-out vs face."
            )
    if carry_distribution:
        worst = max(
            (c for c in carry_distribution if c.get("dispersion_index_mean_abs_per_carry") is not None),
            key=lambda c: float(c["dispersion_index_mean_abs_per_carry"]),
            default=None,
        )
        if worst is not None and int(worst["n"]) >= 10:
            di = float(worst["dispersion_index_mean_abs_per_carry"])
            if di >= 0.22:
                lines.append(
                    f"{worst['club']}: dispersion index {di:.3f} (|offline|/carry) on {worst['n']} shots — "
                    "priority direction game."
                )
    return lines[:max_items]


def training_takeaways_for_window(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    calendar_year: int | None,
    max_items: int = 6,
) -> list[str]:
    landing = landing_side_by_club(conn, db_path=db_path, calendar_year=calendar_year)
    gapping = club_gapping(conn, db_path=db_path, calendar_year=calendar_year)
    shape = shot_shape_bins(conn, db_path=db_path, calendar_year=calendar_year)
    carry = club_carry_distribution(conn, db_path=db_path, calendar_year=calendar_year)
    return build_training_takeaways(
        landing_side=landing,
        gapping=gapping,
        shot_shape=shape,
        carry_distribution=carry,
        max_items=max_items,
    )
