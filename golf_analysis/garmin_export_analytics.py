"""Garmin Golf Community export analytics for dashboard (strategy / performance)."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def _parse_year_from_scorecard(sc: dict[str, Any]) -> int | None:
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


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def load_garmin_export(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def iter_scorecards(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Flatten scorecards from ``details`` with hole-level rollups."""

    details = data.get("details")
    if not isinstance(details, list):
        return []
    out: list[dict[str, Any]] = []
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
            y = _parse_year_from_scorecard(sc)
            if calendar_year is not None and y is not None and y != calendar_year:
                continue
            sc_id = sc.get("id")
            holes_raw = sc.get("holes")
            holes = holes_raw if isinstance(holes_raw, list) else []

            total_putts = 0
            putt_holes = 0
            fairway_decided = 0
            fairway_hit = 0
            penalty_holes = 0
            blowup_holes = 0
            holes_with_strokes = 0
            strokes_list: list[int] = []

            for h in holes:
                if not isinstance(h, dict):
                    continue
                st = _as_int(h.get("strokes") if h.get("strokes") is not None else h.get("score"))
                if st is not None:
                    strokes_list.append(st)
                    holes_with_strokes += 1
                    if st >= 7:
                        blowup_holes += 1
                pt = _as_int(h.get("putts"))
                if pt is not None:
                    total_putts += pt
                    putt_holes += 1
                pen = _as_int(h.get("penalties"))
                if pen is not None and pen > 0:
                    penalty_holes += 1
                fo = h.get("fairwayShotOutcome")
                if isinstance(fo, str) and fo.strip():
                    u = fo.strip().upper()
                    if u in ("HIT", "LEFT", "RIGHT"):
                        fairway_decided += 1
                        if u == "HIT":
                            fairway_hit += 1

            course = sc.get("courseName") or sc.get("course_name")
            start = sc.get("startTime") or sc.get("formattedStartTime")
            holes_completed = _as_int(sc.get("holesCompleted")) or len(holes)

            out.append(
                {
                    "scorecard_id": str(sc_id) if sc_id is not None else None,
                    "course_name": str(course) if course else None,
                    "started_at": str(start) if start else None,
                    "calendar_year": y,
                    "strokes": _as_int(sc.get("strokes") or sc.get("totalScore")),
                    "holes_completed": holes_completed,
                    "score_type": sc.get("scoreType"),
                    "stableford_points": _as_int(sc.get("typeScore")),
                    "player_handicap": sc.get("playerHandicap") or sc.get("courseHandicapStr"),
                    "total_putts_holes": total_putts,
                    "holes_with_putts": putt_holes,
                    "fairway_decided": fairway_decided,
                    "fairway_hit": fairway_hit,
                    "penalty_holes": penalty_holes,
                    "blowup_holes_ge7": blowup_holes,
                    "holes_with_strokes": holes_with_strokes,
                    "mean_strokes_per_hole": statistics.fmean(strokes_list) if strokes_list else None,
                }
            )

    def sort_key(row: dict[str, Any]) -> str:
        return row.get("started_at") or ""

    out.sort(key=sort_key, reverse=True)
    return out[:limit]


def scoring_method_proxy_metrics(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Scorecard-level proxies aligned with *Scoring Method* themes (ESZ/DSZ need shot geometry).

    - **Avoid big numbers**: blow-up holes (strokes >= 7) rate.
    - **Avoid penalties**: holes with penalty > 0.
    - **Fairway / start line** (tee game proxy): fairway HIT among decided outcomes.
    - **Putting load**: putts per hole when putts recorded.
    """

    if not scorecards:
        return {
            "rounds": 0,
            "caveat": "No scorecards in filter. Ingest Garmin Golf JSON or widen year.",
            "esz_dsz_note": (
                "True ESZ (inside 100 yd in regulation) and DSZ (down in three inside 100) require "
                "normalized shot rows vs pin; see docs/on-course-analysis-methodology.md."
            ),
        }

    n = len(scorecards)
    sf_points = [r["stableford_points"] for r in scorecards if r.get("stableford_points") is not None]
    fh = sum(r["fairway_hit"] for r in scorecards)
    fd = sum(r["fairway_decided"] for r in scorecards)
    pen = sum(r["penalty_holes"] for r in scorecards)
    blow = sum(r["blowup_holes_ge7"] for r in scorecards)
    holes_st = sum(r["holes_with_strokes"] for r in scorecards)
    putt_holes = sum(r["holes_with_putts"] for r in scorecards)
    putts = sum(r["total_putts_holes"] for r in scorecards)

    return {
        "rounds": n,
        "esz_dsz_note": (
            "ESZ/DSZ percentages need per-shot distance to pin (not in scorecard rows alone). "
            "Below are **round-management proxies** from the same scorecard Garmin uses for practice cards."
        ),
        "proxy_avoid_big_numbers": {
            "label": "Blow-up holes (strokes ≥ 7, no par on hole)",
            "holes_ge7": blow,
            "holes_tracked": holes_st,
            "pct_holes": (100.0 * blow / holes_st) if holes_st else None,
        },
        "proxy_penalties": {
            "label": "Penalty holes (hole penalties > 0)",
            "penalty_holes": pen,
            "holes_tracked": holes_st,
            "pct_holes": (100.0 * pen / holes_st) if holes_st else None,
        },
        "proxy_fairway": {
            "label": "Fairway outcomes (HIT / LEFT / RIGHT only)",
            "fairway_hit": fh,
            "fairway_decided": fd,
            "pct_hit": (100.0 * fh / fd) if fd else None,
        },
        "proxy_putting_load": {
            "label": "Putting load (sum putts / holes with putt count)",
            "total_putts": putts,
            "holes_with_putts": putt_holes,
            "putts_per_hole": (putts / putt_holes) if putt_holes else None,
        },
        "stableford": {
            "rounds_with_points": len(sf_points),
            "mean_points": statistics.fmean(sf_points) if sf_points else None,
        },
    }


def performance_round_rollups(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    """High-level Garmin performance slice for Performance tab."""

    if not scorecards:
        return {"rounds": 0}
    strokes = [r["strokes"] for r in scorecards if r.get("strokes") is not None]
    holes_c = [r["holes_completed"] for r in scorecards if r.get("holes_completed")]
    st_types: dict[str, int] = {}
    for r in scorecards:
        t = r.get("score_type")
        if t:
            st_types[str(t)] = st_types.get(str(t), 0) + 1
    return {
        "rounds": len(scorecards),
        "mean_strokes_per_round": statistics.fmean(strokes) if strokes else None,
        "mean_holes_completed": statistics.fmean(holes_c) if holes_c else None,
        "best_strokes_round": min(strokes) if strokes else None,
        "score_types": st_types,
    }
