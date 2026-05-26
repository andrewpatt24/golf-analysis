"""Pre-round hole plans for courses without Garmin history (layout + your numbers)."""

from __future__ import annotations

from typing import Any

from golf_analysis.course_layout.manual_courses import get_manual_course
from golf_analysis.garmin_export_analytics import scoring_method_proxy_metrics_from_export


def build_game_profile_from_export(data: dict[str, Any] | None, *, calendar_year: int) -> dict[str, Any]:
    """Compact WHERE tendencies from recent scorecards (not swing coaching)."""

    if not data:
        return {
            "rounds": 0,
            "penalty_pct": None,
            "fairway_hit_pct": None,
            "putts_per_hole": None,
            "headline": "No Garmin export — plans use yardages only.",
        }

    metrics = scoring_method_proxy_metrics_from_export(data, calendar_year=calendar_year)
    rounds = int(metrics.get("rounds") or 0)
    pen = metrics.get("proxy_penalties") or {}
    fw = metrics.get("proxy_fairway") or {}
    putt = metrics.get("proxy_putting_load") or {}

    penalty_pct = pen.get("pct_holes")
    fairway_hit_pct = fw.get("pct_hit")
    putts_per_hole = putt.get("putts_per_hole")

    headlines: list[str] = []
    if penalty_pct is not None and float(penalty_pct) >= 12:
        headlines.append(f"Penalties on {penalty_pct:.0f}% of holes — favour fairways over distance.")
    elif penalty_pct is not None:
        headlines.append(f"Penalty rate {penalty_pct:.0f}% — normal tee aggression OK when wide open.")

    if fairway_hit_pct is not None and float(fairway_hit_pct) < 45:
        headlines.append(f"Fairways {fairway_hit_pct:.0f}% — club down when trouble is in play.")
    elif fairway_hit_pct is not None:
        headlines.append(f"Fairways {fairway_hit_pct:.0f}%.")

    if putts_per_hole is not None and float(putts_per_hole) >= 2.0:
        headlines.append(f"Putting load {putts_per_hole:.2f}/hole — lag for tap-ins inside 100 yd.")

    if not headlines:
        headlines.append(
            f"{rounds} round(s) in {calendar_year} — no dominant leak; match clubs to yardage book."
        )

    return {
        "rounds": rounds,
        "penalty_pct": penalty_pct,
        "fairway_hit_pct": fairway_hit_pct,
        "putts_per_hole": putts_per_hole,
        "headline": " ".join(headlines),
    }


def _clubs_by_carry(clubs: list[dict[str, Any]]) -> list[tuple[str, float, bool]]:
    rows: list[tuple[str, float, bool]] = []
    for c in clubs:
        carry = c.get("mean_carry_yards")
        if carry is None:
            continue
        rows.append((str(c["club"]), float(carry), bool(c.get("needs_work"))))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows


def pick_club_for_carry(
    target_yards: float,
    clubs: list[dict[str, Any]],
    *,
    max_overshoot: float = 12.0,
) -> tuple[str | None, int | None]:
    """Club whose mean carry is closest to target without large overshoot."""

    ranked = _clubs_by_carry(clubs)
    if not ranked:
        return None, None

    best: tuple[str, float] | None = None
    best_gap = float("inf")
    for club, carry, _ in ranked:
        gap = abs(carry - target_yards)
        overshoot = carry - target_yards
        if overshoot > max_overshoot:
            continue
        if gap < best_gap:
            best_gap = gap
            best = (club, carry)

    if best is None:
        club, carry, _ = ranked[-1]
        return club, round(carry)

    return best[0], round(best[1])


def _trusted_tee_club(clubs: list[dict[str, Any]], penalty_pct: float | None) -> tuple[str | None, float | None]:
    ranked = _clubs_by_carry(clubs)
    if not ranked:
        return None, None

    high_pen = penalty_pct is not None and float(penalty_pct) >= 12.0
    if high_pen and len(ranked) >= 2:
        club, carry, needs = ranked[1]
        if not needs:
            return club, carry

    for club, carry, needs in ranked:
        if not needs:
            return club, carry
    club, carry, _ = ranked[0]
    return club, carry


def _target_for_hole(*, par: int, stroke_index: int | None, yardage: int) -> str:
    si = stroke_index or 10
    hard = si <= 6
    easy = si >= 14

    if par == 3:
        if hard:
            return "par (stroke hole)"
        if easy:
            return "par — good chance"
        return "par"

    if par == 5:
        if yardage >= 530 or hard:
            return f"bogey ({par + 1})"
        if easy and yardage < 500:
            return "par with two good strikes"
        return f"bogey ({par + 1})"

    # par 4
    if yardage >= 420 or hard:
        return f"bogey ({par + 1})"
    if easy and yardage <= 360:
        return "par"
    return "par"


def _classify_holes(holes: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    attack: list[int] = []
    caution: list[int] = []
    for h in holes:
        hnum = int(h["hole_number"])
        si = int(h.get("stroke_index") or 10)
        par = int(h.get("par") or 4)
        yds = int(h.get("yardage_yards") or 0)
        if si >= 14:
            attack.append(hnum)
        if si <= 6 or (par >= 4 and yds >= 410) or (par == 5 and yds >= 530):
            caution.append(hnum)
    return attack, caution


def _tee_and_approach_notes(
    *,
    par: int,
    yardage: int,
    clubs: list[dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[str, str | None]:
    penalty_pct = profile.get("penalty_pct")
    tee_club, tee_carry = _trusted_tee_club(clubs, penalty_pct if isinstance(penalty_pct, (int, float)) else None)

    if par == 3:
        club, carry = pick_club_for_carry(float(yardage), clubs)
        if club:
            return f"{club.upper()} — charted {carry} yd carry for {yardage} yd", None
        return f"Match a full swing to {yardage} yd (check Yards tab)", None

    if not tee_club or tee_carry is None:
        return "Set up from your Yards tab — no carry data loaded.", None

    if par == 5:
        remain = max(0, yardage - int(tee_carry))
        approach_club, approach_carry = pick_club_for_carry(float(remain), clubs)
        layup_yards = max(80, remain - 100) if remain > 220 else remain
        layup_club, layup_carry = pick_club_for_carry(float(layup_yards), clubs)
        tee_line = f"Tee: {tee_club.upper()} (~{int(tee_carry)} yd)"
        if remain > 230 and layup_club:
            second = f"Lay up with {layup_club.upper()} (~{layup_carry} yd) to ~100 yd scoring zone"
            third = (
                f"Approach ~{remain} yd remaining — plan {approach_club.upper()} if going for green in 3"
                if approach_club
                else f"Approach ~{remain} yd — pick wedge from Pitch tab"
            )
            return tee_line, f"{second}; {third}"
        if approach_club:
            return tee_line, f"Into green: ~{remain} yd — {approach_club.upper()} ({approach_carry} yd chart)"
        return tee_line, f"Into green: ~{remain} yd — use Pitch tab"

    # par 4
    if yardage <= int(tee_carry) + 15:
        return f"{tee_club.upper()} can reach green territory ({yardage} yd) — still pick a fairway target.", None

    remain = yardage - int(tee_carry)
    approach_club, approach_carry = pick_club_for_carry(float(remain), clubs)
    tee_line = f"Tee: {tee_club.upper()} (~{int(tee_carry)} yd)"
    if penalty_pct is not None and float(penalty_pct) >= 12 and yardage >= 380:
        tee_line = f"Tee: one club less than max — fairway first ({tee_club.upper()} or 3-wood)"
    if approach_club:
        return tee_line, f"Approach ~{remain} yd — {approach_club.upper()} ({approach_carry} yd chart)"
    return tee_line, f"Approach ~{remain} yd — check Yards / Pitch tabs"


def _hole_plan_line(
    *,
    par: int,
    yardage: int,
    stroke_index: int | None,
    clubs: list[dict[str, Any]],
    profile: dict[str, Any],
) -> str:
    tee, approach = _tee_and_approach_notes(
        par=par, yardage=yardage, clubs=clubs, profile=profile
    )
    parts = [tee]
    if approach:
        parts.append(approach)
    si = stroke_index or 10
    if si <= 6:
        parts.append("Hardest stroke index — play to your target score, not the card.")
    return " · ".join(parts)


def build_on_course_prep(
    *,
    course_slug: str,
    calendar_year: int,
    clubs: list[dict[str, Any]],
    garmin_export: dict[str, Any] | None,
) -> dict[str, Any]:
    """Full pre-round pack for a manually catalogued course."""

    layout = get_manual_course(course_slug)
    if layout is None:
        raise KeyError(course_slug)

    profile = build_game_profile_from_export(garmin_export, calendar_year=calendar_year)
    holes_in = list(layout.get("holes") or [])
    attack, caution = _classify_holes(holes_in)

    hole_cards: list[dict[str, Any]] = []
    for h in sorted(holes_in, key=lambda x: int(x.get("hole_number") or 0)):
        hnum = int(h["hole_number"])
        par = int(h.get("par") or 4)
        yds = int(h.get("yardage_yards") or 0)
        si = h.get("stroke_index")
        target = _target_for_hole(par=par, stroke_index=int(si) if si is not None else None, yardage=yds)
        plan = _hole_plan_line(
            par=par,
            yardage=yds,
            stroke_index=int(si) if si is not None else None,
            clubs=clubs,
            profile=profile,
        )
        hole_cards.append(
            {
                "hole_number": hnum,
                "par": par,
                "stroke_index": si,
                "yardage_yards": yds,
                "target": target,
                "plan": plan,
                "press": hnum in attack and hnum not in caution,
                "respect": hnum in caution,
            }
        )

    summary_parts: list[str] = []
    if attack:
        summary_parts.append(f"Press (easy SI): {', '.join(str(x) for x in attack[:5])}")
    if caution:
        summary_parts.append(f"Respect: {', '.join(str(x) for x in caution[:5])}")
    if not summary_parts:
        summary_parts.append("Even card — execute your yardage book.")

    return {
        "course_slug": course_slug,
        "course_name": layout["course_name"],
        "tee_name": layout.get("tee_name"),
        "par_total": layout.get("par_total"),
        "yardage_total": layout.get("yardage_total"),
        "course_rating": layout.get("course_rating"),
        "slope_rating": layout.get("slope_rating"),
        "calendar_year": calendar_year,
        "game_profile": profile,
        "attack_holes": attack,
        "caution_holes": caution,
        "summary_line": " · ".join(summary_parts),
        "holes": hole_cards,
        "note": (
            "Pre-round plan from scorecard yardages and your practice carries — "
            "WHERE to play, not swing changes (see Playbook)."
        ),
    }
