"""Per-course hole aggregates and rule-based coach play plans from Garmin export."""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from typing import Any

from golf_analysis.garmin_esz_dsz import (
    _build_scorecard_index,
    _par_for_hole,
    _scorecard_year,
    build_esz_dsz_hole_rows,
)
from golf_analysis.garmin_export_analytics import _as_int, _parse_year_from_scorecard
from golf_analysis.api.settings_store import load_settings
from golf_analysis.garmin_handicap_gross import estimated_round_gross_18, parse_course_stroke_indexes

PAR_BUCKETS = (3, 4, 5)


def _rel_diff_pct(value: float, baseline: float) -> float | None:
    if baseline == 0:
        return 0.0 if value == 0 else None
    return 100.0 * (value - baseline) / baseline


def _plays_scoring_rates(plays: list[dict[str, Any]]) -> dict[str, Any]:
    """ESZ %, DSZ %, mean putts, mean Stableford points for a play list."""

    esz_eval = [p for p in plays if p.get("esz_evaluated")]
    esz_ok = sum(1 for p in esz_eval if p.get("esz_success"))
    dsz_elig = sum(1 for p in esz_eval if p.get("entered_scoring_zone"))
    dsz_ok = sum(
        1
        for p in esz_eval
        if p.get("entered_scoring_zone") and p.get("dsz_success")
    )
    putts = [p["putts"] for p in plays if p.get("putts") is not None]
    sf_pts = [p["stableford_points"] for p in plays if p.get("stableford_points") is not None]
    return {
        "sample_plays": len(plays),
        "esz_evaluated": len(esz_eval),
        "dsz_eligible": dsz_elig,
        "putts_tracked": len(putts),
        "stableford_tracked": len(sf_pts),
        "esz_pct": (100.0 * esz_ok / len(esz_eval)) if esz_eval else None,
        "dsz_pct": (100.0 * dsz_ok / dsz_elig) if dsz_elig else None,
        "avg_putts": statistics.fmean(putts) if putts else None,
        "avg_stableford_points": statistics.fmean(sf_pts) if sf_pts else None,
    }


def build_course_scoring_stats(plays: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Course-level Scoring Method stats with par 3/4/5 splits.

    Each par bucket includes ``diff_vs_course_overall_pct`` (relative % vs all holes
    played on this course in the filter window — the "round average" on course).
    """

    overall = _plays_scoring_rates(plays)
    by_par: dict[str, Any] = {}
    for par in PAR_BUCKETS:
        par_plays = [p for p in plays if p.get("par") == par]
        if not par_plays:
            continue
        rates = _plays_scoring_rates(par_plays)
        diffs: dict[str, float | None] = {}
        for key in ("esz_pct", "dsz_pct", "avg_putts", "avg_stableford_points"):
            val = rates.get(key)
            base = overall.get(key)
            if val is not None and base is not None:
                diffs[key] = _rel_diff_pct(val, base)
        by_par[str(par)] = {
            "par": par,
            **rates,
            "diff_vs_course_overall_pct": diffs,
        }
    return {"overall": overall, "by_par": by_par}


def attach_hole_compare(
    agg: dict[str, Any],
    scoring_stats: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Per-hole ESZ/DSZ/putts/points vs course overall and vs same-par average on course.
    """

    overall = scoring_stats.get("overall") or {}
    par = agg.get("par")
    if par is None:
        return None
    par_row = (scoring_stats.get("by_par") or {}).get(str(int(par))) or {}

    def _metric(hole_val: float | None, overall_key: str) -> dict[str, Any] | None:
        if hole_val is None:
            return None
        base_course = overall.get(overall_key)
        base_par = par_row.get(overall_key)
        out: dict[str, Any] = {"value": hole_val}
        if base_course is not None:
            out["diff_vs_course_overall_pct"] = _rel_diff_pct(hole_val, base_course)
        if base_par is not None:
            out["diff_vs_par_on_course_pct"] = _rel_diff_pct(hole_val, base_par)
        return out

    metrics: dict[str, Any] = {}
    if agg.get("esz_success_rate") is not None and int(agg.get("esz_evaluated_count") or 0) > 0:
        esz_pct = 100.0 * float(agg["esz_success_rate"])
        m = _metric(esz_pct, "esz_pct")
        if m:
            metrics["esz_pct"] = m
    if agg.get("dsz_success_rate") is not None and int(agg.get("dsz_eligible_count") or 0) > 0:
        dsz_pct = 100.0 * float(agg["dsz_success_rate"])
        m = _metric(dsz_pct, "dsz_pct")
        if m:
            metrics["dsz_pct"] = m
    if agg.get("avg_putts") is not None:
        m = _metric(float(agg["avg_putts"]), "avg_putts")
        if m:
            metrics["avg_putts"] = m
    if agg.get("avg_stableford_points") is not None:
        m = _metric(float(agg["avg_stableford_points"]), "avg_stableford_points")
        if m:
            metrics["avg_stableford_points"] = m

    if not metrics:
        return None
    return {
        "metrics": metrics,
        "lower_is_better": ["avg_putts"],
    }


def trouble_min_avg_stableford_points() -> float:
    """Threshold from dashboard settings (default 1.0). Trouble if hole avg ``typeScore`` is below."""

    raw = load_settings().get("troubleMinAvgStablefordPoints", 1.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0


def stroke_index_for_hole(scorecard: dict[str, Any], hole_number: int) -> int | None:
    """Stroke index 1–18 from ``courseHandicapStr`` or hole-level fields."""

    sis = parse_course_stroke_indexes(scorecard)
    if sis is not None and 1 <= hole_number <= 18:
        return sis[hole_number - 1]
    holes_raw = scorecard.get("holes")
    if isinstance(holes_raw, list):
        for h in holes_raw:
            if not isinstance(h, dict):
                continue
            try:
                hn = int(h.get("number") or h.get("holeNumber") or 0)
            except (TypeError, ValueError):
                continue
            if hn == hole_number:
                return _as_int(h.get("strokeIndex") or h.get("handicapStrokeIndex"))
    return None


def stroke_index_for_course_hole(
    sc_index: dict[str, dict[str, Any]],
    scorecard_ids: list[str],
    hole_number: int,
) -> int | None:
    """First resolvable stroke index across scorecards for this course."""

    for sid in scorecard_ids:
        sc = sc_index.get(sid)
        if isinstance(sc, dict):
            si = stroke_index_for_hole(sc, hole_number)
            if si is not None:
                return si
    return None


def course_slug(course_name: str) -> str:
    s = course_name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "course"


def _hole_yardage_yards(h: dict[str, Any]) -> float | None:
    for key in (
        "yardage",
        "yardageYards",
        "length",
        "holeLength",
        "holeYardage",
        "distance",
        "totalDistance",
        "holeDistance",
        "measurementValue",
        "holeLengthYards",
    ):
        v = h.get(key)
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x <= 0:
            continue
        if x < 95:
            return x * 1.0936132983377
        if x <= 750:
            return x
    return None


def _fairway_outcome(h: dict[str, Any]) -> str | None:
    fo = h.get("fairwayShotOutcome")
    if isinstance(fo, str) and fo.strip():
        u = fo.strip().upper()
        if u in ("HIT", "LEFT", "RIGHT"):
            return u
    fh = h.get("fairwayHit") if h.get("fairwayHit") is not None else h.get("fairway_hit")
    if fh is True:
        return "HIT"
    if fh is False:
        return None
    return None


def iter_hole_plays(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
) -> list[dict[str, Any]]:
    """One row per scorecard hole with scorecard stats + optional ESZ/DSZ merge."""

    sc_index = _build_scorecard_index(data)
    esz_rows, _, _ = build_esz_dsz_hole_rows(data, calendar_year=calendar_year, scorecard_ids=None)
    esz_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for r in esz_rows:
        sid = str(r.get("scorecard_id") or "").strip()
        try:
            hn = int(r.get("hole_number") or 0)
        except (TypeError, ValueError):
            continue
        if sid and hn >= 1:
            esz_by_key[(sid, hn)] = r

    plays: list[dict[str, Any]] = []
    for sid, sc in sc_index.items():
        y = _scorecard_year(sc) or _parse_year_from_scorecard(sc)
        if calendar_year is not None and y is not None and y != calendar_year:
            continue
        course = sc.get("courseName") or sc.get("course_name")
        if not course:
            continue
        course_name = str(course).strip()
        if not course_name:
            continue
        slug = course_slug(course_name)
        start = sc.get("startTime") or sc.get("formattedStartTime")
        holes_raw = sc.get("holes")
        if not isinstance(holes_raw, list):
            continue
        for h in holes_raw:
            if not isinstance(h, dict):
                continue
            try:
                hn = int(h.get("number") or h.get("holeNumber") or 0)
            except (TypeError, ValueError):
                continue
            if hn < 1:
                continue
            par = _as_int(h.get("par")) or _par_for_hole(sc, hn)
            score = _as_int(h.get("strokes") if h.get("strokes") is not None else h.get("score"))
            putts = _as_int(h.get("putts"))
            pen_n = _as_int(h.get("penalties") if h.get("penalties") is not None else h.get("penaltyStrokes"))
            penalty = pen_n is not None and pen_n > 0
            fw = _fairway_outcome(h)
            vs_par = (score - par) if score is not None and par is not None else None
            blowup = score is not None and score >= 7
            sf_pts = _as_int(h.get("typeScore"))
            er = esz_by_key.get((sid, hn))
            play: dict[str, Any] = {
                "course_slug": slug,
                "course_name": course_name,
                "scorecard_id": sid,
                "started_at": str(start) if start else None,
                "hole_number": hn,
                "par": par,
                "yardage_yards": _hole_yardage_yards(h),
                "score": score,
                "score_vs_par": vs_par,
                "putts": putts,
                "penalty": penalty,
                "fairway_outcome": fw,
                "blowup": blowup,
                "stableford_points": sf_pts,
                "esz_evaluated": er is not None,
                "entered_scoring_zone": er.get("entered_scoring_zone") if er else None,
                "esz_success": er.get("esz_success") if er else None,
                "dsz_success": er.get("dsz_success") if er else None,
            }
            plays.append(play)
    return plays


def _aggregate_hole(
    plays: list[dict[str, Any]],
    *,
    trouble_min_avg_stableford: float,
) -> dict[str, Any]:
    n = len(plays)
    pars = [p["par"] for p in plays if p.get("par") is not None]
    par = int(statistics.mode(pars)) if pars else None
    yardages = [p["yardage_yards"] for p in plays if p.get("yardage_yards") is not None]
    scores = [p["score"] for p in plays if p.get("score") is not None]
    vs_pars = [p["score_vs_par"] for p in plays if p.get("score_vs_par") is not None]
    putts = [p["putts"] for p in plays if p.get("putts") is not None]
    pen_n = sum(1 for p in plays if p.get("penalty"))
    blow_n = sum(1 for p in plays if p.get("blowup"))
    fw_hit = sum(1 for p in plays if p.get("fairway_outcome") == "HIT")
    fw_left = sum(1 for p in plays if p.get("fairway_outcome") == "LEFT")
    fw_right = sum(1 for p in plays if p.get("fairway_outcome") == "RIGHT")
    fw_dec = fw_hit + fw_left + fw_right
    esz_eval = [p for p in plays if p.get("esz_evaluated")]
    esz_ok = sum(1 for p in esz_eval if p.get("esz_success"))
    dsz_elig = sum(1 for p in esz_eval if p.get("entered_scoring_zone"))
    dsz_ok = sum(1 for p in esz_eval if p.get("entered_scoring_zone") and p.get("dsz_success"))

    avg_score = statistics.fmean(scores) if scores else None
    avg_vs_par = statistics.fmean(vs_pars) if vs_pars else None
    penalty_rate = pen_n / n if n else None
    esz_success_rate = esz_ok / len(esz_eval) if esz_eval else None
    esz_miss_rate = (1.0 - esz_success_rate) if esz_success_rate is not None else None
    dsz_success_rate = dsz_ok / dsz_elig if dsz_elig else None

    sf_pts_list = [
        int(p["stableford_points"])
        for p in plays
        if p.get("stableford_points") is not None
    ]
    sf_tracked = len(sf_pts_list)
    avg_stableford = statistics.fmean(sf_pts_list) if sf_pts_list else None

    trouble = False
    trouble_reasons: list[str] = []
    if sf_tracked > 0 and avg_stableford is not None and avg_stableford < trouble_min_avg_stableford:
        trouble = True
        trouble_reasons.append(
            f"avg {avg_stableford:.2f} Stableford pts ({sf_tracked} plays) "
            f"— below {trouble_min_avg_stableford:g} pt threshold"
        )

    return {
        "plays_count": n,
        "par": par,
        "yardage_yards": statistics.fmean(yardages) if yardages else None,
        "avg_score": avg_score,
        "avg_vs_par": avg_vs_par,
        "scores": scores,
        "avg_putts": statistics.fmean(putts) if putts else None,
        "putts_tracked_plays": len(putts),
        "penalty_count": pen_n,
        "penalty_rate": penalty_rate,
        "blowup_count": blow_n,
        "fairway_hit": fw_hit,
        "fairway_left": fw_left,
        "fairway_right": fw_right,
        "fairway_decided": fw_dec,
        "fairway_hit_pct": (100.0 * fw_hit / fw_dec) if fw_dec else None,
        "esz_evaluated_count": len(esz_eval),
        "esz_success_count": esz_ok,
        "esz_success_rate": esz_success_rate,
        "esz_miss_rate": esz_miss_rate,
        "dsz_eligible_count": dsz_elig,
        "dsz_success_count": dsz_ok,
        "dsz_success_rate": dsz_success_rate,
        "stableford_tracked_plays": sf_tracked,
        "avg_stableford_points": avg_stableford,
        "stableford_points_list": sf_pts_list,
        "trouble_min_avg_stableford": trouble_min_avg_stableford,
        "trouble_hole": trouble,
        "trouble_reasons": trouble_reasons,
    }


def build_hole_coach(agg: dict[str, Any], *, hole_number: int) -> dict[str, Any]:
    """Rule-based play plan from aggregated hole stats."""

    n = int(agg.get("plays_count") or 0)
    par = agg.get("par")
    avg_vs = agg.get("avg_vs_par")
    pen_rate = agg.get("penalty_rate") or 0.0
    esz_miss = agg.get("esz_miss_rate")
    esz_rate = agg.get("esz_success_rate")
    dsz_rate = agg.get("dsz_success_rate")
    dsz_elig = int(agg.get("dsz_eligible_count") or 0)
    fw_dec = int(agg.get("fairway_decided") or 0)
    fw_hit = int(agg.get("fairway_hit") or 0)
    fw_left = int(agg.get("fairway_left") or 0)
    fw_right = int(agg.get("fairway_right") or 0)
    avg_putts = agg.get("avg_putts")
    blow_n = int(agg.get("blowup_count") or 0)

    primary_parts: list[str] = []
    if pen_rate >= 0.3:
        primary_parts.append("penalties off the tee or in play")
    if esz_miss is not None and esz_miss >= 0.5 and int(agg.get("esz_evaluated_count") or 0) >= 1:
        primary_parts.append("rarely reaching the scoring zone in regulation")
    if fw_dec >= 2 and fw_right >= fw_hit and fw_right >= fw_left:
        primary_parts.append("misses right off the tee")
    elif fw_dec >= 2 and fw_left > fw_hit and fw_left >= fw_right:
        primary_parts.append("misses left off the tee")
    if avg_vs is not None and avg_vs >= 1.0 and not primary_parts:
        primary_parts.append("scores well above par on average")
    if not primary_parts:
        primary_parts.append("no single dominant leak — stay with your game plan")

    primary = (
        f"Hole {hole_number}"
        + (f" (par {par})" if par else "")
        + f": across {n} round(s) you mainly lose shots because "
        + ", and ".join(primary_parts)
        + "."
    )

    sections: list[dict[str, str]] = []

    if pen_rate >= 0.25 or (fw_dec >= 2 and fw_hit / fw_dec < 0.4):
        aim = "centre of the fairway"
        if fw_right > fw_left and fw_dec >= 2:
            aim = "left centre of the fairway (trouble tends to be right)"
        elif fw_left > fw_right and fw_dec >= 2:
            aim = "right centre of the fairway (trouble tends to be left)"
        club_hint = "3-wood or long iron" if pen_rate >= 0.3 else "club you trust for fairway"
        sections.append(
            {
                "title": "Tee shot plan",
                "body": (
                    f"Prioritize position over distance: {club_hint} to {aim}. "
                    f"Driver only when conditions are ideal and you have not had a penalty here recently."
                ),
            }
        )
    elif par and par >= 4:
        sections.append(
            {
                "title": "Tee shot plan",
                "body": "Start line and fairway width matter more than extra yards — pick a consistent start line.",
            }
        )

    if pen_rate >= 0.2 or blow_n > 0:
        sections.append(
            {
                "title": "If you miss the fairway",
                "body": (
                    "No hero shots: get back to short grass on the first attempt. "
                    "Treat bogey as a good outcome when out of position."
                ),
            }
        )

    if esz_miss is not None and esz_miss >= 0.4:
        sections.append(
            {
                "title": "Scoring zone (≤100 yd)",
                "body": (
                    "Plan your approach yardage before the tee shot — expect wedge from "
                    "120–150 yd rather than a short pitch unless you reach ESZ in regulation."
                ),
            }
        )
    if dsz_elig >= 1 and dsz_rate is not None and dsz_rate < 0.5:
        sections.append(
            {
                "title": "Inside 100 yards",
                "body": (
                    "When you reach the zone, focus on getting down in three: committed wedge distance, "
                    "two-putt mindset on the green."
                ),
            }
        )

    if avg_putts is not None and avg_putts >= 2.2:
        sections.append(
            {
                "title": "On the green",
                "body": "Lag putting to tap-in range; two-putt is a win when long.",
            }
        )

    target = "par"
    if avg_vs is not None:
        if avg_vs >= 2.0 or blow_n > 0:
            target = f"bogey ({(par or 0) + 1})" if par else "bogey"
        elif avg_vs >= 1.0:
            target = f"bogey ({(par or 0) + 1})" if par else "bogey"
    sections.append(
        {
            "title": "Target score / mindset",
            "body": f"Play for {target} with conservative targets; execute the tee and recovery rules above.",
        }
    )

    confidence = f"Based on {n} round(s) on this course"
    if int(agg.get("esz_evaluated_count") or 0) < n:
        confidence += f" · ESZ/DSZ from shot trace on {agg.get('esz_evaluated_count')} of {n} play(s)"

    return {
        "headline": primary,
        "sections": sections,
        "confidence_note": confidence,
    }


def _course_summary_from_holes(
    course_name: str,
    course_slug_val: str,
    holes: list[dict[str, Any]],
    round_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    n_rounds = len(round_rows)
    gross_est = [
        r.get("gross_net_18") or r.get("gross_estimated_18")
        for r in round_rows
        if (r.get("gross_net_18") or r.get("gross_estimated_18")) is not None
    ]
    partial_n = sum(1 for r in round_rows if r.get("is_partial"))
    trouble = sorted(
        [h for h in holes if h.get("trouble_hole")],
        key=lambda h: h.get("avg_stableford_points") if h.get("avg_stableford_points") is not None else 99,
    )
    worst = [h["hole_number"] for h in trouble[:3]]
    esz_eval_total = sum(h.get("esz_evaluated_count") or 0 for h in holes)
    esz_ok_total = sum(h.get("esz_success_count") or 0 for h in holes)
    pen_total = sum(h.get("penalty_count") or 0 for h in holes)
    play_total = sum(h.get("plays_count") or 0 for h in holes)

    coach_lines: list[str] = []
    if trouble:
        nums = ", ".join(str(h["hole_number"]) for h in trouble[:3])
        coach_lines.append(f"Most cost comes on hole(s) {nums} — see play plans for tee and recovery choices.")
    if pen_total > 0 and play_total > 0 and pen_total / play_total >= 0.15:
        coach_lines.append("Penalties are a recurring theme — club down and widen your fairway target.")
    if not coach_lines:
        coach_lines.append("No dominant trouble pattern; keep tracking ESZ and penalties round to round.")

    return {
        "course_slug": course_slug_val,
        "course_name": course_name,
        "rounds_count": n_rounds,
        "avg_gross": statistics.fmean(gross_est) if gross_est else None,
        "partial_rounds_count": partial_n,
        "avg_gross_note": (
            "18h net gross: blow-up holes capped at net double bogey; partial rounds impute unplayed holes the same way. "
            "Raw card total shown when it differs."
            if partial_n > 0
            else None
        ),
        "worst_hole_numbers": worst,
        "esz_pct": (100.0 * esz_ok_total / esz_eval_total) if esz_eval_total else None,
        "penalty_hole_pct": (100.0 * pen_total / play_total) if play_total else None,
        "course_coach_summary": " ".join(coach_lines),
    }


def list_courses_from_export(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
    min_rounds: int = 1,
    trouble_min_avg_stableford: float | None = None,
) -> dict[str, Any]:
    trouble_thr = (
        trouble_min_avg_stableford
        if trouble_min_avg_stableford is not None
        else trouble_min_avg_stableford_points()
    )
    plays = iter_hole_plays(data, calendar_year=calendar_year)
    by_course: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rounds_by_course: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    for p in plays:
        slug = p["course_slug"]
        by_course[slug].append(p)
        sid = p["scorecard_id"]
        if sid not in rounds_by_course[slug]:
            rounds_by_course[slug][sid] = {
                "scorecard_id": sid,
                "started_at": p.get("started_at"),
            }

    sc_index = _build_scorecard_index(data)
    for slug, rmap in rounds_by_course.items():
        for sid, row in rmap.items():
            sc = sc_index.get(sid)
            if sc:
                gross = estimated_round_gross_18(sc)
                row.update(gross)
                row["strokes"] = gross.get("gross_net_18") or gross.get("gross_estimated_18")

    courses_out: list[dict[str, Any]] = []
    for slug, cplays in sorted(by_course.items(), key=lambda kv: kv[1][0]["course_name"]):
        course_name = cplays[0]["course_name"]
        rrows = list(rounds_by_course[slug].values())
        if len(rrows) < min_rounds:
            continue
        by_hole: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for p in cplays:
            by_hole[int(p["hole_number"])].append(p)
        holes_agg = []
        for hn in sorted(by_hole):
            agg = _aggregate_hole(by_hole[hn], trouble_min_avg_stableford=trouble_thr)
            agg["hole_number"] = hn
            holes_agg.append(agg)
        summary = _course_summary_from_holes(course_name, slug, holes_agg, rrows)
        courses_out.append(summary)

    return {
        "calendar_year": calendar_year,
        "courses": courses_out,
        "min_rounds": min_rounds,
        "trouble_min_avg_stableford_points": trouble_thr,
    }


def course_detail_from_export(
    data: dict[str, Any],
    course_slug_param: str,
    *,
    calendar_year: int | None = None,
    trouble_min_avg_stableford: float | None = None,
) -> dict[str, Any] | None:
    trouble_thr = (
        trouble_min_avg_stableford
        if trouble_min_avg_stableford is not None
        else trouble_min_avg_stableford_points()
    )
    plays = iter_hole_plays(data, calendar_year=calendar_year)
    cplays = [p for p in plays if p["course_slug"] == course_slug_param]
    if not cplays:
        return None

    course_name = cplays[0]["course_name"]
    sc_index = _build_scorecard_index(data)
    scorecard_ids = list({str(p["scorecard_id"]) for p in cplays if p.get("scorecard_id")})
    by_hole: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in cplays:
        by_hole[int(p["hole_number"])].append(p)

    holes_out: list[dict[str, Any]] = []
    for hn in sorted(by_hole):
        hole_plays = by_hole[hn]
        agg = _aggregate_hole(hole_plays, trouble_min_avg_stableford=trouble_thr)
        agg["hole_number"] = hn
        agg["stroke_index"] = stroke_index_for_course_hole(sc_index, scorecard_ids, hn)
        agg["coach"] = build_hole_coach(agg, hole_number=hn)
        agg["recent_plays"] = sorted(
            hole_plays,
            key=lambda x: x.get("started_at") or "",
            reverse=True,
        )[:8]
        holes_out.append(agg)

    rounds_map: dict[str, dict[str, Any]] = {}
    for p in cplays:
        sid = p["scorecard_id"]
        if sid not in rounds_map:
            rounds_map[sid] = {
                "scorecard_id": sid,
                "started_at": p.get("started_at"),
                "leak_holes": [],
            }
    for sid, row in rounds_map.items():
        sc = sc_index.get(sid)
        if sc:
            gross = estimated_round_gross_18(sc)
            row.update(gross)
            row["strokes"] = gross.get("gross_estimated_18")

    for h in holes_out:
        if not h.get("trouble_hole"):
            continue
        hn = int(h["hole_number"])
        for p in by_hole[hn]:
            sid = p["scorecard_id"]
            if sid in rounds_map:
                leaks = rounds_map[sid]["leak_holes"]
                if hn not in leaks:
                    leaks.append(hn)

    round_history = sorted(rounds_map.values(), key=lambda r: r.get("started_at") or "", reverse=True)
    summary = _course_summary_from_holes(course_name, course_slug_param, holes_out, list(rounds_map.values()))
    scoring_stats = build_course_scoring_stats(cplays)
    for h in holes_out:
        cmp = attach_hole_compare(h, scoring_stats)
        if cmp:
            h["compare"] = cmp

    return {
        "calendar_year": calendar_year,
        "course_slug": course_slug_param,
        "course_name": course_name,
        "trouble_min_avg_stableford_points": trouble_thr,
        **summary,
        "scoring_stats": scoring_stats,
        "holes": holes_out,
        "round_history": round_history,
    }
