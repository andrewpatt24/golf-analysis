"""First-pass text report for docs/frameworks/analysis-plan.md (WHERE + WHY skeleton)."""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from golf_analysis.range_analysis import lm_shot_cohort_sql
from golf_analysis.rapsodo_list_kinds import find_repo_root, load_session_ids_for_calendar_year

# First-pass defaults (see docs/frameworks/analysis-plan.md).
MIN_SHOTS_PER_CLUB = 8
LATERAL_TO_LENGTH_RATIO_CAP = 0.10  # std(|offline|)/std(carry) — "lateral dispersion vs length dispersion"
LATERAL_TO_DISTANCE_CAP = 0.10  # std(offline) <= 10% of mean carry (nominal distance)


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _stdev(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    return statistics.stdev(xs)


def iter_last10_shots_with_sg(
    data: dict[str, Any],
    *,
    scorecard_ids: set[str] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """
    Garmin Golf JSON often puts ``strokesGained`` on **sample** rows inside ``last10Data*`` blocks,
    not on every ``shotDetails`` nested shot. Yield (category, row) for aggregation.

    When ``scorecard_ids`` is set, only rows whose ``scorecardId`` maps to that set are included
    (rows without ``scorecardId`` are excluded).
    """

    out: list[tuple[str, dict[str, Any]]] = []
    mapping = (
        ("last10DataApproach", "approach"),
        ("last10DataChip", "around_the_green"),
        ("last10DataPutt", "putting"),
        ("last10DataDrive", "tee"),
    )
    for top_key, cat in mapping:
        block = data.get(top_key)
        if not isinstance(block, dict):
            continue
        for arr in block.values():
            if not isinstance(arr, list):
                continue
            for row in arr:
                if not isinstance(row, dict) or row.get("strokesGained") is None:
                    continue
                if scorecard_ids is not None:
                    sid = row.get("scorecardId")
                    if sid is None:
                        continue
                    if str(sid).strip() not in scorecard_ids:
                        continue
                out.append((cat, row))
    return out


def summarize_last10_strokes_gained(
    data: dict[str, Any],
    *,
    scorecard_ids: set[str] | None = None,
) -> dict[str, dict[str, float]]:
    """Per category: sum SG, count, mean; plus overall."""

    by_cat: dict[str, list[float]] = defaultdict(list)
    for cat, row in iter_last10_shots_with_sg(data, scorecard_ids=scorecard_ids):
        try:
            sg = float(row["strokesGained"])
        except (TypeError, ValueError):
            continue
        by_cat[cat].append(sg)
    summary: dict[str, dict[str, float]] = {}
    all_vals: list[float] = []
    for cat, vals in sorted(by_cat.items()):
        all_vals.extend(vals)
        summary[cat] = {
            "count": float(len(vals)),
            "sum_sg": float(sum(vals)),
            "mean_sg": float(sum(vals) / len(vals)) if vals else 0.0,
        }
    summary["_overall"] = {
        "count": float(len(all_vals)),
        "sum_sg": float(sum(all_vals)),
        "mean_sg": float(sum(all_vals) / len(all_vals)) if all_vals else 0.0,
    }
    return summary


def _scorecard_start_year(sc: dict[str, Any]) -> int | None:
    for key in ("startTime", "formattedStartTime", "startTimestamp"):
        v = sc.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if len(s) >= 4 and s[:4].isdigit():
            try:
                return int(s[:4])
            except ValueError:
                continue
    return None


def scorecard_ids_for_calendar_year(data: dict[str, Any], year: int) -> set[str]:
    """
    Scorecard ids whose recorded start time is in ``year``.

    Uses ``details`` and ``summary.scorecardSummaries`` so the id set matches exports where one
    surface has a clearer ``startTime`` than the other (same approach as merging scorecards for ESZ).
    """

    out: set[str] = set()

    def add_from_scorecard(sc: dict[str, Any]) -> None:
        if _scorecard_start_year(sc) != year:
            return
        cid = sc.get("id")
        if cid is not None:
            out.add(str(cid).strip())

    details = data.get("details")
    if isinstance(details, list):
        for entry in details:
            if not isinstance(entry, dict):
                continue
            scd = entry.get("scorecardDetails")
            if not isinstance(scd, list):
                continue
            for el in scd:
                if not isinstance(el, dict):
                    continue
                sc = el.get("scorecard")
                if isinstance(sc, dict):
                    add_from_scorecard(sc)

    summary = data.get("summary")
    if isinstance(summary, dict):
        scs = summary.get("scorecardSummaries")
        if isinstance(scs, list):
            for raw in scs:
                if isinstance(raw, dict):
                    add_from_scorecard(raw)

    return out


def scorecard_round_stats(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
) -> tuple[int, float | None]:
    """Count scorecards in ``details`` and mean score vs par when present.

    When ``calendar_year`` is set, only scorecards whose start time falls in that year are counted.
    """

    details = data.get("details")
    if not isinstance(details, list):
        return 0, None
    rels: list[float] = []
    n = 0
    for entry in details:
        if not isinstance(entry, dict):
            continue
        scd = entry.get("scorecardDetails")
        if not isinstance(scd, list):
            continue
        for el in scd:
            if not isinstance(el, dict):
                continue
            sc = el.get("scorecard")
            if not isinstance(sc, dict):
                continue
            if calendar_year is not None and _scorecard_start_year(sc) != calendar_year:
                continue
            n += 1
            v = sc.get("scoreRelativeToPar")
            if v is None:
                v = sc.get("relativeScore")
            if v is not None:
                try:
                    rels.append(float(v))
                except (TypeError, ValueError):
                    pass
    mean_rel = statistics.fmean(rels) if rels else None
    return n, mean_rel


def range_shot_rows_for_dispersion(
    conn: sqlite3.Connection,
    *,
    calendar_year: int | None = None,
    repo_root: Path | None = None,
) -> list[sqlite3.Row]:
    cohort = lm_shot_cohort_sql()
    year_sql = ""
    params: list[Any] = []
    if calendar_year is not None:
        y0 = f"{calendar_year}-01-01"
        y1 = f"{calendar_year + 1}-01-01"
        session_ids: set[str] = set()
        if repo_root is not None:
            session_ids = load_session_ids_for_calendar_year(repo_root, calendar_year)
        if session_ids:
            placeholders = ",".join("?" * len(session_ids))
            year_sql = (
                f" AND substr(s.title, 17) IN ({placeholders}) "
                "AND length(s.title) >= 17 "
                "AND lower(substr(s.title, 1, 16)) = 'rapsodo_session_'"
            )
            params.extend(sorted(session_ids))
        else:
            year_sql = " AND s.started_at >= ? AND s.started_at < ? "
            params.extend([y0, y1])
    sql = f"""
            SELECT rs.club, rs.carry_yards, rs.offline_yards,
                   rs.club_path_deg, rs.launch_direction_deg, rs.smash_factor
            FROM range_shots rs
            JOIN range_sessions s ON s.id = rs.session_id
            JOIN imports i ON i.id = s.import_id
            WHERE {cohort}
              AND rs.club IS NOT NULL AND TRIM(rs.club) != ''
              AND rs.carry_yards IS NOT NULL
              {year_sql}
            """
    return list(conn.execute(sql, params).fetchall())


def dispersion_by_club(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Group by normalized club label; apply first-pass dispersion rules."""

    by_club: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"carry": [], "offline": [], "path": [], "ldir": [], "smash": []}
    )

    def norm_club(c: str) -> str:
        return c.strip().lower()

    for r in rows:
        club = norm_club(str(r["club"]))
        if not club or club in ("average", "median", "std. dev.", "club type"):
            continue
        carry = r["carry_yards"]
        off = r["offline_yards"]
        if carry is None:
            continue
        by_club[club]["carry"].append(float(carry))
        if off is not None:
            by_club[club]["offline"].append(float(off))
        if r["club_path_deg"] is not None:
            by_club[club]["path"].append(float(r["club_path_deg"]))
        if r["launch_direction_deg"] is not None:
            by_club[club]["ldir"].append(float(r["launch_direction_deg"]))
        if r["smash_factor"] is not None:
            by_club[club]["smash"].append(float(r["smash_factor"]))

    out: list[dict[str, Any]] = []
    for club, d in sorted(by_club.items(), key=lambda x: -len(x[1]["carry"])):
        carries = d["carry"]
        offs = d["offline"]
        if len(carries) < MIN_SHOTS_PER_CLUB:
            continue
        mean_c = _mean(carries)
        std_c = _stdev(carries)
        std_o = _stdev(offs) if len(offs) >= 2 else None
        ratio = (std_o / std_c) if std_o is not None and std_c and std_c >= 1.0 else None
        fail_ratio = ratio is not None and ratio > LATERAL_TO_LENGTH_RATIO_CAP
        fail_dist = std_o is not None and mean_c is not None and std_o > LATERAL_TO_DISTANCE_CAP * mean_c
        bad = fail_ratio or fail_dist
        out.append(
            {
                "club": club,
                "n": len(carries),
                "mean_carry_yards": mean_c,
                "std_carry_yards": std_c,
                "std_offline_yards": std_o,
                "lateral_to_length_ratio": ratio,
                "fail_ratio_rule": fail_ratio,
                "fail_10pct_mean_carry_rule": fail_dist,
                "needs_work": bad,
                "median_path_deg": statistics.median(d["path"]) if d["path"] else None,
                "median_launch_dir_deg": statistics.median(d["ldir"]) if d["ldir"] else None,
                "median_smash": statistics.median(d["smash"]) if d["smash"] else None,
            }
        )
    out.sort(key=lambda x: (not x["needs_work"], -x["n"]))
    return out


def build_analysis_plan_report(
    *,
    garmin_json: Path | None,
    db_path: Path,
    calendar_year: int | None = 2026,
) -> str:
    repo_root = find_repo_root(db_path.parent)
    if calendar_year is not None:
        lines: list[str] = [
            "Analysis plan report (first pass)",
            f"Scope: calendar year {calendar_year} — Garmin rounds + range training only.",
            "",
        ]
    else:
        lines = [
            "Analysis plan report (first pass)",
            "Scope: all calendar years.",
            "WHERE: Garmin (JSON) + last-10 SG samples | WHY: Rapsodo dispersion (library DB)",
            "",
        ]

    # --- Garmin ---
    if garmin_json and garmin_json.is_file():
        try:
            data = json.loads(garmin_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            lines.append(f"Garmin JSON: failed to read {garmin_json}: {e}")
            data = None
    else:
        lines.append(
            f"Garmin JSON: not found at {garmin_json!r} — skipping rounds section "
            "(pass --garmin-json or place data/raw/garmin/golf-export.json)."
        )
        data = None

    if isinstance(data, dict):
        n_sc, mean_rel = scorecard_round_stats(data, calendar_year=calendar_year)
        year_note = f" ({calendar_year})" if calendar_year is not None else ""
        lines.append(f"## Rounds — Garmin{year_note}")
        lines.append(f"- Scorecards in `details`{year_note}: {n_sc}")
        if mean_rel is not None:
            lines.append(f"- Mean score vs par (where recorded): {mean_rel:+.2f}")
        sc_ids: set[str] | None = None
        if calendar_year is not None:
            sc_ids = scorecard_ids_for_calendar_year(data, calendar_year)
            lines.append(
                f"- Scorecard ids with `startTime` in {calendar_year}: **{len(sc_ids)}** "
                "(used to filter last-10 SG sample rows by `scorecardId`)."
            )
        sg_rows = iter_last10_shots_with_sg(data, scorecard_ids=sc_ids)
        lines.append(
            f"- Per-shot `strokesGained` on **each** `shotDetails` tree shot: **not present** in this export "
            f"(nested shots checked). Garmin does supply SG on **last-10 sample** rows instead."
        )
        lines.append(f"- `last10Data*` sample shots carrying `strokesGained` (after filters): **{len(sg_rows)}** rows")
        sg_sum = summarize_last10_strokes_gained(data, scorecard_ids=sc_ids)
        for key in sorted(k for k in sg_sum if not str(k).startswith("_")):
            s = sg_sum[key]
            lines.append(
                f"  - {key}: n={int(s['count'])}, sum SG={s['sum_sg']:.3f}, mean SG={s['mean_sg']:.3f}"
            )
        ov = sg_sum.get("_overall", {})
        lines.append(
            f"  - **Combined (approach + ATG samples):** n={int(ov.get('count', 0))}, "
            f"sum SG={ov.get('sum_sg', 0):.3f}, mean SG={ov.get('mean_sg', 0):.3f}"
        )
        if calendar_year is not None:
            lines.append(
                f"- **Caveat:** last-10 blocks are still Garmin’s **recent-window** lists; only rows with "
                f"`scorecardId` tied to a {calendar_year} scorecard in `details` are counted here."
            )
        else:
            lines.append(
                "- **Caveat:** these are Garmin’s **recent-window** samples, not an exhaustive sum over "
                "every historical shot. Full per-shot SG for all rounds would still require either "
                "vendor fields on every shot (not in your `shotDetails` tree) or a baseline table "
                "(see on-course methodology)."
            )
        stats = data.get("last10DataStats")
        if calendar_year is None and isinstance(stats, dict) and isinstance(stats.get("strokesGainedRatings"), list):
            lines.append("- `last10DataStats.strokesGainedRatings` (headline buckets):")
            for row in stats["strokesGainedRatings"][:8]:
                if isinstance(row, dict):
                    lines.append(f"  - {json.dumps(row, default=str)}")
        elif calendar_year is not None:
            lines.append(
                "- `last10DataStats.strokesGainedRatings`: omitted in year scope (Garmin aggregate, not per-year)."
            )
        if calendar_year is None:
            lines.append("")
            lines.append("### Scoring-method / geography (not in this pass)")
            lines.append(
                "- ESZ (≤100 yd) / DSZ (down in three) and ring logic need haversine on `shotDetails`; "
                "not implemented here — see docs/on-course-analysis-methodology.md."
            )
    lines.append("")

    # --- Rapsodo ---
    r_year = f" ({calendar_year})" if calendar_year is not None else ""
    lines.append(f"## Training — Rapsodo{r_year}")
    lines.append(
        f"Cohort: `range_analysis.lm_shot_cohort_sql()` — practice/combine (or legacy NULL list kind)."
    )
    if calendar_year is not None:
        snap = (
            "session ids from `data/raw/rapsodo/rapsodo_session_list.json` `sessions_merged[].startdate` "
            f"in {calendar_year}, matched to `range_sessions.title` (`rapsodo_session_<id>`); "
            "if the snapshot is missing or empty for that year, `range_sessions.started_at` "
            f"falls back to [{calendar_year}-01-01, {calendar_year + 1}-01-01)."
        )
        lines.append(f"- **Year filter:** {snap}")
    lines.append(
        f"Rules: fail if std(offline_yards)/std(carry_yards) > {LATERAL_TO_LENGTH_RATIO_CAP} "
        f"when std(carry)≥1 yd, OR std(offline) > {LATERAL_TO_DISTANCE_CAP:.0%} of mean carry. "
        f"Min {MIN_SHOTS_PER_CLUB} shots per club."
    )
    if not db_path.is_file():
        lines.append(f"Library DB missing: {db_path}")
        return "\n".join(lines) + "\n"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = range_shot_rows_for_dispersion(
            conn,
            calendar_year=calendar_year,
            repo_root=repo_root,
        )
        if not rows:
            lines.append("No range shots in cohort — ingest Rapsodo CSVs or widen cohort.")
        else:
            lines.append(f"Shots considered: {len(rows)}")
            for row in dispersion_by_club(rows):
                flag = " **FLAG**" if row["needs_work"] else ""
                rto = row["lateral_to_length_ratio"]
                rto_s = f"{rto:.3f}" if rto is not None else "—"
                std_o = row["std_offline_yards"]
                std_o_s = f"{std_o:.2f}" if std_o is not None else "—"
                mp, ml = row["median_path_deg"], row["median_launch_dir_deg"]
                extra = ""
                if mp is not None and ml is not None:
                    extra = f", median path {mp:.2f}°, launch dir {ml:.2f}°"
                lines.append(
                    f"- **{row['club']}** (n={row['n']}){flag}: mean carry {row['mean_carry_yards']:.1f} yd, "
                    f"std carry {row['std_carry_yards']:.2f}, std offline {std_o_s}, lat/len {rto_s}{extra}"
                )
    finally:
        conn.close()

    lines.append("")
    lines.append("## Resolved defaults (open questions, v1)")
    lines.append("- **SG source:** use Garmin `last10DataApproach` / `last10DataChip` sample `strokesGained`; not full history.")
    lines.append("- **Dispersion stats:** sample **stdev** for carry and offline (signed offline).")
    lines.append("- **Length dispersion:** `std(carry_yards)` vs mean carry for the 10% cap.")
    lines.append("- **Combine in cohort:** yes (practice + combine per `range_analysis`).")
    lines.append("- **Garmin↔Rapsodo club join:** not automated in this pass; compare failing clubs to on-course manually.")
    return "\n".join(lines) + "\n"


def run_analysis_plan_report(
    *,
    garmin_json: Path | None,
    db_path: Path,
    calendar_year: int | None = 2026,
) -> str:
    return build_analysis_plan_report(
        garmin_json=garmin_json,
        db_path=db_path,
        calendar_year=calendar_year,
    )
