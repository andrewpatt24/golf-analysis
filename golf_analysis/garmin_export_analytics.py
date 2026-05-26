"""Garmin Golf Community export analytics for dashboard (strategy / performance)."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from golf_analysis.garmin_esz_dsz import _build_scorecard_index, _course_started_meta, _par_for_hole
from golf_analysis.metrics_reference import proxy_tile_spec

ProxyDirection = Literal["lower_is_better", "higher_is_better"]
PAR_BUCKETS = (3, 4, 5)


def _course_name_from_entry(entry: dict[str, Any]) -> str | None:
    """Garmin often puts the course label on ``details[].courseSnapshots[]``, not on ``scorecard``."""

    snaps = entry.get("courseSnapshots")
    if isinstance(snaps, list) and snaps:
        first = snaps[0]
        if isinstance(first, dict):
            name = first.get("name")
            if name is not None and str(name).strip():
                return str(name).strip()
    for key in ("courseName", "course_name"):
        v = entry.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _resolve_course_and_started(
    sc: dict[str, Any],
    entry: dict[str, Any],
    sc_index: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    """Merge ``summary.scorecardSummaries`` + entry snapshots (same as ESZ/DSZ indexing)."""

    sid = sc.get("id")
    merged = sc_index.get(str(sid).strip(), sc) if sid is not None else sc
    course, start = _course_started_meta(merged)
    if not course:
        course = _course_name_from_entry(entry)
    if not start:
        for key in ("startTime", "formattedStartTime"):
            v = entry.get(key)
            if v is not None and str(v).strip():
                start = str(v).strip()
                break
    return course, start


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


@dataclass
class _ProxyHoleAccum:
    stableford_zero: int = 0
    stableford_tracked: int = 0
    penalty_holes: int = 0
    holes_with_strokes: int = 0
    fairway_hit: int = 0
    fairway_decided: int = 0
    putts: int = 0
    putt_holes: int = 0


def _rel_diff_pct(par_value: float, avg_value: float) -> float | None:
    if avg_value == 0:
        return 0.0 if par_value == 0 else None
    return 100.0 * (par_value - avg_value) / avg_value


def _by_par_splits(
    by_par: dict[int, _ProxyHoleAccum],
    *,
    value_fn: Any,
    sample_fn: Any,
    avg_value: float | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if avg_value is None:
        return out
    for par in PAR_BUCKETS:
        acc = by_par.get(par) or _ProxyHoleAccum()
        sample = sample_fn(acc)
        if not sample:
            continue
        val = value_fn(acc)
        if val is None:
            continue
        out[str(par)] = {
            "par": par,
            "value": val,
            "sample_holes": sample,
            "diff_vs_avg_pct": _rel_diff_pct(val, avg_value),
        }
    return out


def _accumulate_hole(acc: _ProxyHoleAccum, h: dict[str, Any], sc: dict[str, Any]) -> None:
    st = _as_int(h.get("strokes") if h.get("strokes") is not None else h.get("score"))
    if st is not None:
        acc.holes_with_strokes += 1
    ts = _as_int(h.get("typeScore"))
    if st is not None and ts is not None:
        acc.stableford_tracked += 1
        if ts <= 0:
            acc.stableford_zero += 1
    pt = _as_int(h.get("putts"))
    if pt is not None:
        acc.putts += pt
        acc.putt_holes += 1
    pen = _as_int(h.get("penalties"))
    if pen is not None and pen > 0:
        acc.penalty_holes += 1
    fo = h.get("fairwayShotOutcome")
    if isinstance(fo, str) and fo.strip():
        u = fo.strip().upper()
        if u in ("HIT", "LEFT", "RIGHT"):
            acc.fairway_decided += 1
            if u == "HIT":
                acc.fairway_hit += 1


def _hole_par(h: dict[str, Any], sc: dict[str, Any]) -> int | None:
    par = _as_int(h.get("par"))
    if par is not None:
        return par
    hn = _as_int(h.get("number") if h.get("number") is not None else h.get("holeNumber"))
    if hn is not None:
        return _par_for_hole(sc, hn)
    return None


def accumulate_proxy_holes_by_par(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
) -> tuple[_ProxyHoleAccum, dict[int, _ProxyHoleAccum], int]:
    """Roll up strategy proxy counters overall and by par 3 / 4 / 5."""

    details = data.get("details")
    if not isinstance(details, list):
        empty = _ProxyHoleAccum()
        return empty, {p: _ProxyHoleAccum() for p in PAR_BUCKETS}, 0

    sc_index = _build_scorecard_index(data)
    overall = _ProxyHoleAccum()
    by_par = {p: _ProxyHoleAccum() for p in PAR_BUCKETS}
    rounds = 0

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
            sid = sc.get("id")
            merged = sc_index.get(str(sid).strip(), sc) if sid is not None else sc
            holes_raw = merged.get("holes")
            holes = holes_raw if isinstance(holes_raw, list) else []
            if not holes:
                continue
            rounds += 1
            for h in holes:
                if not isinstance(h, dict):
                    continue
                _accumulate_hole(overall, h, merged)
                par = _hole_par(h, merged)
                if par in PAR_BUCKETS:
                    _accumulate_hole(by_par[par], h, merged)

    return overall, by_par, rounds


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
    sc_index = _build_scorecard_index(data)
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
            stableford_zero_holes = 0
            stableford_holes_tracked = 0
            holes_with_strokes = 0
            strokes_list: list[int] = []

            for h in holes:
                if not isinstance(h, dict):
                    continue
                st = _as_int(h.get("strokes") if h.get("strokes") is not None else h.get("score"))
                if st is not None:
                    strokes_list.append(st)
                    holes_with_strokes += 1
                ts = _as_int(h.get("typeScore"))
                if st is not None and ts is not None:
                    stableford_holes_tracked += 1
                    if ts <= 0:
                        stableford_zero_holes += 1
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

            course, start = _resolve_course_and_started(sc, entry, sc_index)
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
                    "stableford_zero_point_holes": stableford_zero_holes,
                    "stableford_holes_tracked": stableford_holes_tracked,
                    "holes_with_strokes": holes_with_strokes,
                    "mean_strokes_per_hole": statistics.fmean(strokes_list) if strokes_list else None,
                }
            )

    def sort_key(row: dict[str, Any]) -> str:
        return row.get("started_at") or ""

    out.sort(key=sort_key, reverse=True)
    return out[:limit]


def _metrics_from_accum(
    overall: _ProxyHoleAccum,
    by_par: dict[int, _ProxyHoleAccum],
    *,
    rounds: int,
    sf_round_points: list[int] | None = None,
) -> dict[str, Any]:
    zero_sf = overall.stableford_zero
    sf_tracked = overall.stableford_tracked
    holes_st = overall.holes_with_strokes
    pen = overall.penalty_holes
    fh = overall.fairway_hit
    fd = overall.fairway_decided
    putts = overall.putts
    putt_holes = overall.putt_holes

    pct_zero = (100.0 * zero_sf / sf_tracked) if sf_tracked else None
    pct_pen = (100.0 * pen / holes_st) if holes_st else None
    pct_fw = (100.0 * fh / fd) if fd else None
    putts_ph = (putts / putt_holes) if putt_holes else None

    return {
        "rounds": rounds,
        "esz_dsz_note": (
            "ESZ/DSZ percentages need per-shot distance to pin (not in scorecard rows alone). "
            "Below are **round-management proxies** from the same scorecard Garmin uses for practice cards."
        ),
        "proxy_avoid_big_numbers": {
            "title": proxy_tile_spec("proxy_avoid_big_numbers")["title"],
            "label": proxy_tile_spec("proxy_avoid_big_numbers")["label"],
            "direction": "lower_is_better",
            "metric": "pct_holes",
            "stableford_zero_point_holes": zero_sf,
            "stableford_holes_tracked": sf_tracked,
            "pct_holes": pct_zero,
            "by_par": _by_par_splits(
                by_par,
                value_fn=lambda a: (100.0 * a.stableford_zero / a.stableford_tracked)
                if a.stableford_tracked
                else None,
                sample_fn=lambda a: a.stableford_tracked,
                avg_value=pct_zero,
            ),
        },
        "proxy_penalties": {
            "title": proxy_tile_spec("proxy_penalties")["title"],
            "label": proxy_tile_spec("proxy_penalties")["label"],
            "direction": "lower_is_better",
            "metric": "pct_holes",
            "penalty_holes": pen,
            "holes_tracked": holes_st,
            "pct_holes": pct_pen,
            "by_par": _by_par_splits(
                by_par,
                value_fn=lambda a: (100.0 * a.penalty_holes / a.holes_with_strokes)
                if a.holes_with_strokes
                else None,
                sample_fn=lambda a: a.holes_with_strokes,
                avg_value=pct_pen,
            ),
        },
        "proxy_fairway": {
            "title": proxy_tile_spec("proxy_fairway")["title"],
            "label": proxy_tile_spec("proxy_fairway")["label"],
            "direction": "higher_is_better",
            "metric": "pct_hit",
            "fairway_hit": fh,
            "fairway_decided": fd,
            "pct_hit": pct_fw,
            "by_par": _by_par_splits(
                by_par,
                value_fn=lambda a: (100.0 * a.fairway_hit / a.fairway_decided) if a.fairway_decided else None,
                sample_fn=lambda a: a.fairway_decided,
                avg_value=pct_fw,
            ),
        },
        "proxy_putting_load": {
            "title": proxy_tile_spec("proxy_putting_load")["title"],
            "label": proxy_tile_spec("proxy_putting_load")["label"],
            "direction": "lower_is_better",
            "metric": "putts_per_hole",
            "total_putts": putts,
            "holes_with_putts": putt_holes,
            "putts_per_hole": putts_ph,
            "by_par": _by_par_splits(
                by_par,
                value_fn=lambda a: (a.putts / a.putt_holes) if a.putt_holes else None,
                sample_fn=lambda a: a.putt_holes,
                avg_value=putts_ph,
            ),
        },
        "stableford": {
            "rounds_with_points": len(sf_round_points) if sf_round_points is not None else 0,
            "mean_points": statistics.fmean(sf_round_points) if sf_round_points else None,
        },
    }


def scoring_method_proxy_metrics_from_export(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
) -> dict[str, Any]:
    """Strategy proxies from hole-level export data, including par 3 / 4 / 5 splits."""

    overall, by_par, rounds = accumulate_proxy_holes_by_par(data, calendar_year=calendar_year)
    if rounds == 0:
        return {
            "rounds": 0,
            "caveat": "No scorecards in filter. Ingest Garmin Golf JSON or widen year.",
            "esz_dsz_note": (
                "True ESZ (inside 100 yd in regulation) and DSZ (down in three inside 100) require "
                "normalized shot rows vs pin; see docs/on-course-analysis-methodology.md."
            ),
        }
    cards = iter_scorecards(data, calendar_year=calendar_year, limit=10_000)
    sf_points = [r["stableford_points"] for r in cards if r.get("stableford_points") is not None]
    return _metrics_from_accum(overall, by_par, rounds=rounds, sf_round_points=sf_points)


def scoring_method_proxy_metrics(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Scorecard-level proxies aligned with *Scoring Method* themes (ESZ/DSZ need shot geometry).

    - **Avoid big numbers**: holes with 0 Stableford points (``typeScore``).
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

    overall = _ProxyHoleAccum(
        stableford_zero=sum(r["stableford_zero_point_holes"] for r in scorecards),
        stableford_tracked=sum(r["stableford_holes_tracked"] for r in scorecards),
        penalty_holes=sum(r["penalty_holes"] for r in scorecards),
        holes_with_strokes=sum(r["holes_with_strokes"] for r in scorecards),
        fairway_hit=sum(r["fairway_hit"] for r in scorecards),
        fairway_decided=sum(r["fairway_decided"] for r in scorecards),
        putts=sum(r["total_putts_holes"] for r in scorecards),
        putt_holes=sum(r["holes_with_putts"] for r in scorecards),
    )
    sf_points = [r["stableford_points"] for r in scorecards if r.get("stableford_points") is not None]
    return _metrics_from_accum(
        overall,
        {p: _ProxyHoleAccum() for p in PAR_BUCKETS},
        rounds=len(scorecards),
        sf_round_points=sf_points,
    )


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
