"""Estimate 18-hole gross from Garmin scorecards (net double bogey caps + partial imputation)."""

from __future__ import annotations

from typing import Any

from golf_analysis.garmin_esz_dsz import _par_for_hole
from golf_analysis.garmin_export_analytics import _as_int


def parse_course_stroke_indexes(scorecard: dict[str, Any]) -> list[int] | None:
    """``courseHandicapStr``: 18 × two-digit stroke index values."""

    raw = scorecard.get("courseHandicapStr")
    if not isinstance(raw, str) or len(raw) != 36:
        return None
    out: list[int] = []
    for i in range(0, 36, 2):
        pair = raw[i : i + 2]
        if not pair.isdigit():
            return None
        out.append(int(pair))
    return out if len(out) == 18 else None


def course_handicap_strokes(scorecard: dict[str, Any]) -> int | None:
    """Playing handicap for the round (``playerHandicap``)."""

    return _as_int(scorecard.get("playerHandicap") or scorecard.get("courseHandicap"))


def strokes_received_on_hole(course_handicap: int, stroke_index: int | None) -> int:
    """
    Strokes allocated on a hole from course handicap and stroke index (1–18).

    ``base = CH // 18`` on every hole; holes with SI ≤ ``CH % 18`` get one extra stroke.
    """

    if course_handicap <= 0 or stroke_index is None or stroke_index < 1:
        return 0
    base = course_handicap // 18
    remainder = course_handicap % 18
    return base + (1 if stroke_index <= remainder else 0)


def net_double_bogey_gross(
    par: int,
    course_handicap: int,
    stroke_index: int | None,
) -> int:
    """
    Gross score for net double bogey on a hole (WHS-style max when posting).

    ``par + 2 + strokes_received`` — not plain par, and not net par (``par + strokes``).
    """

    return par + 2 + strokes_received_on_hole(course_handicap, stroke_index)


def capped_hole_gross(
    actual_gross: int,
    par: int | None,
    course_handicap: int,
    stroke_index: int | None,
) -> tuple[int, bool]:
    """Return ``min(actual, net double bogey)`` when par is known; else actual unchanged."""

    if par is None:
        return actual_gross, False
    cap = net_double_bogey_gross(par, course_handicap, stroke_index)
    if actual_gross > cap:
        return cap, True
    return actual_gross, False


def _hole_gross(h: dict[str, Any]) -> int | None:
    return _as_int(h.get("strokes") if h.get("strokes") is not None else h.get("score"))


def _holes_scored(scorecard: dict[str, Any]) -> list[tuple[int, int]]:
    """(hole_number, gross_strokes) for holes with a recorded score."""

    holes_raw = scorecard.get("holes")
    if not isinstance(holes_raw, list):
        return []
    out: list[tuple[int, int]] = []
    for h in holes_raw:
        if not isinstance(h, dict):
            continue
        try:
            hn = int(h.get("number") or h.get("holeNumber") or 0)
        except (TypeError, ValueError):
            continue
        if hn < 1:
            continue
        g = _hole_gross(h)
        if g is not None:
            out.append((hn, g))
    return out


def course_par_total(scorecard: dict[str, Any]) -> int | None:
    total = 0
    n = 0
    for hn in range(1, 19):
        p = _par_for_hole(scorecard, hn)
        if p is not None:
            total += p
            n += 1
    return total if n >= 9 else None


def _handicap_net_gross_18(
    scorecard: dict[str, Any],
    scored: list[tuple[int, int]],
    *,
    course_handicap: int,
    stroke_indexes: list[int],
) -> dict[str, Any]:
    """Cap blow-up played holes at net double bogey; impute unplayed holes the same way."""

    scored_set = {hn for hn, _ in scored}
    gross_raw = sum(g for _, g in scored)
    played_net = 0
    holes_capped = 0
    blowup_reduction = 0
    for hn, g in scored:
        p = _par_for_hole(scorecard, hn)
        adj, capped = capped_hole_gross(g, p, course_handicap, stroke_indexes[hn - 1])
        played_net += adj
        if capped:
            holes_capped += 1
            blowup_reduction += g - adj

    unplayed_imputed = 0
    for hn in range(1, 19):
        if hn in scored_set:
            continue
        p = _par_for_hole(scorecard, hn)
        if p is None:
            continue
        unplayed_imputed += net_double_bogey_gross(p, course_handicap, stroke_indexes[hn - 1])

    gross_net_18 = played_net + unplayed_imputed
    holes_scored = len(scored)
    is_partial = holes_scored < 18 or unplayed_imputed > 0
    return {
        "gross_raw": gross_raw,
        "gross_net_18": gross_net_18,
        "gross_actual": gross_raw,
        "gross_estimated_18": gross_net_18,
        "played_net": played_net,
        "unplayed_imputed": unplayed_imputed,
        "holes_capped": holes_capped,
        "blowup_reduction": blowup_reduction,
        "is_partial": is_partial,
        "method": "handicap_net_double_bogey",
    }


def estimated_round_gross_18(scorecard: dict[str, Any]) -> dict[str, Any]:
    """
    Return raw and net 18-hole gross totals.

    With ``playerHandicap`` + ``courseHandicapStr``:

    - **gross_raw** — sum of scorecard strokes on played holes (uncapped).
    - **gross_net_18** — each played hole capped at net double bogey; unplayed holes imputed
      at net double bogey (partial rounds). Full 18-hole rounds can still differ when blow-ups
      were capped.

    Without handicap data, partial rounds use par-ratio / linear scale; full rounds use raw only.
    """

    scored = _holes_scored(scorecard)
    holes_scored = len(scored)
    played_gross = sum(g for _, g in scored)
    holes_completed = _as_int(scorecard.get("holesCompleted")) or holes_scored
    listed = _as_int(scorecard.get("strokes") or scorecard.get("totalScore"))
    if played_gross <= 0 and listed is not None:
        played_gross = listed
        if holes_scored == 0:
            holes_scored = holes_completed

    if holes_scored <= 0:
        return {
            "gross_raw": listed,
            "gross_net_18": listed,
            "gross_actual": listed,
            "gross_estimated_18": listed,
            "method": "none",
            "holes_scored": 0,
            "holes_completed": holes_completed,
            "is_partial": False,
            "holes_capped": 0,
            "blowup_reduction": 0,
        }

    ch = course_handicap_strokes(scorecard)
    sis = parse_course_stroke_indexes(scorecard)
    if ch is not None and ch >= 0 and sis is not None:
        adj = _handicap_net_gross_18(
            scorecard,
            scored,
            course_handicap=ch,
            stroke_indexes=sis,
        )
        return {
            **adj,
            "holes_scored": holes_scored,
            "holes_completed": holes_completed,
            "course_handicap": ch,
        }

    gross_raw = played_gross
    if holes_scored >= 18:
        return {
            "gross_raw": gross_raw,
            "gross_net_18": gross_raw,
            "gross_actual": gross_raw,
            "gross_estimated_18": gross_raw,
            "method": "full_18",
            "holes_scored": holes_scored,
            "holes_completed": holes_completed,
            "is_partial": False,
            "holes_capped": 0,
            "blowup_reduction": 0,
        }

    total_par = course_par_total(scorecard)
    played_par = sum(_par_for_hole(scorecard, hn) or 0 for hn, _ in scored)
    if total_par and played_par > 0:
        est = round(played_gross * (total_par / played_par))
        method = "par_ratio_scale"
    else:
        est = round(played_gross * (18 / holes_scored))
        method = "linear_holes_scale"
    return {
        "gross_raw": gross_raw,
        "gross_net_18": est,
        "gross_actual": gross_raw,
        "gross_estimated_18": est,
        "method": method,
        "holes_scored": holes_scored,
        "holes_completed": holes_completed,
        "is_partial": True,
        "holes_capped": 0,
        "blowup_reduction": 0,
    }
