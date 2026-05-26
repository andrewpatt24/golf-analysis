"""On-course course summaries: WHERE to improve, not swing technique."""

from __future__ import annotations

from typing import Any

from golf_analysis.api.settings_store import load_settings
from golf_analysis.garmin_course_holes import trouble_min_avg_stableford_points


def _target_label(avg_vs_par: float | None, par: int | None) -> str:
    if avg_vs_par is None:
        return "par"
    if avg_vs_par >= 2.0:
        return f"max {(par or 0) + 2}" if par else "damage control"
    if avg_vs_par >= 1.0:
        return f"bogey ({(par or 0) + 1})" if par else "bogey"
    return "par"


def build_hole_top_improvement(agg: dict[str, Any]) -> str:
    """
    Single highest-impact strategic change for a hole (course management, not swing).
    """

    pen_rate = float(agg.get("penalty_rate") or 0.0)
    esz_miss = agg.get("esz_miss_rate")
    esz_eval = int(agg.get("esz_evaluated_count") or 0)
    dsz_rate = agg.get("dsz_success_rate")
    dsz_elig = int(agg.get("dsz_eligible_count") or 0)
    fw_dec = int(agg.get("fairway_decided") or 0)
    fw_hit = int(agg.get("fairway_hit") or 0)
    fw_left = int(agg.get("fairway_left") or 0)
    fw_right = int(agg.get("fairway_right") or 0)
    avg_putts = agg.get("avg_putts")
    blow_n = int(agg.get("blowup_count") or 0)

    candidates: list[tuple[float, str]] = []

    if pen_rate >= 0.25:
        club = (
            "Lay up — 3-wood or long iron you trust"
            if pen_rate >= 0.3
            else "Club for the fairway, not max distance"
        )
        aim = "centre of fairway"
        if fw_dec >= 2 and fw_right > fw_left and fw_right >= fw_hit:
            aim = "left centre (trouble tends right)"
        elif fw_dec >= 2 and fw_left > fw_right and fw_left >= fw_hit:
            aim = "right centre (trouble tends left)"
        weight = pen_rate * 10.0 + (2.0 if pen_rate >= 0.3 else 0.0)
        candidates.append(
            (weight, f"{club}; aim {aim}. Skip driver unless it's wide open.")
        )

    if fw_dec >= 2 and fw_hit / fw_dec < 0.4:
        candidates.append(
            (3.5, "Prioritize fairway position — one club less off the tee if needed.")
        )

    if esz_miss is not None and float(esz_miss) >= 0.4 and esz_eval >= 1:
        candidates.append(
            (
                float(esz_miss) * 5.0,
                "Plan lay-up distance before the tee shot — leave a confident approach yardage.",
            )
        )

    if dsz_elig >= 1 and dsz_rate is not None and float(dsz_rate) < 0.5:
        candidates.append(
            (
                (1.0 - float(dsz_rate)) * 4.0,
                "Inside 100 yd: commit to wedge distance and two-putt — don't force at the pin.",
            )
        )

    if avg_putts is not None and float(avg_putts) >= 2.2:
        candidates.append(
            (float(avg_putts), "On the green: lag to tap-in range — two-putt is a good result.")
        )

    if blow_n > 0:
        candidates.append(
            (2.0 + float(blow_n), "Damage-control hole — take bogey when out of position; no hero recoveries.")
        )

    if not candidates:
        if agg.get("trouble_hole"):
            return "Play conservative targets — your history shows this hole costs shots."
        return "No dominant leak — execute your usual plan."

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def build_on_course_course_summary(
    *,
    course_name: str,
    course_slug: str,
    rounds_count: int,
    holes: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compact strategy for playing a course you've seen before.

    Focuses on holes to press, holes to respect, and where shots leak — not swing fixes.
    """

    settings = load_settings()
    green_min = float(settings.get("stablefordColorGreenMin", 2.0))

    attack: list[int] = []
    caution: list[int] = []
    hole_cards: list[dict[str, Any]] = []

    for h in sorted(holes, key=lambda x: int(x.get("hole_number") or 0)):
        hnum = int(h["hole_number"])
        sf = h.get("avg_stableford_points")
        plays = int(h.get("plays_count") or 0)
        if sf is not None and sf >= green_min and plays >= 1:
            attack.append(hnum)
        if h.get("trouble_hole"):
            caution.append(hnum)

        reasons = [str(r) for r in (h.get("trouble_reasons") or []) if str(r).strip()]
        where = "; ".join(reasons[:2]) if reasons else "No dominant leak in your history"
        top_improvement = build_hole_top_improvement(h)

        hole_cards.append(
            {
                "hole_number": hnum,
                "par": h.get("par"),
                "stroke_index": h.get("stroke_index"),
                "yardage_yards": h.get("yardage_yards"),
                "plays_count": plays,
                "target": _target_label(
                    float(h["avg_vs_par"]) if h.get("avg_vs_par") is not None else None,
                    h.get("par"),
                ),
                "where_to_improve": where,
                "top_improvement": top_improvement,
                "avg_stableford_points": sf,
                "trouble_hole": bool(h.get("trouble_hole")),
            }
        )

    summary_parts: list[str] = []
    if attack:
        summary_parts.append(f"Press: holes {', '.join(str(x) for x in attack[:4])}")
    if caution:
        summary_parts.append(f"Respect: holes {', '.join(str(x) for x in caution[:4])}")
    if not summary_parts:
        summary_parts.append(
            f"{rounds_count} round(s) logged — no strong attack/caution split yet; play your numbers."
        )

    return {
        "course_slug": course_slug,
        "course_name": course_name,
        "rounds_count": rounds_count,
        "attack_holes": attack,
        "caution_holes": caution,
        "trouble_threshold_stableford": trouble_min_avg_stableford_points(),
        "summary_line": " · ".join(summary_parts),
        "holes": hole_cards,
        "note": "Strategy from your round history — where shots leak, not swing changes.",
    }
