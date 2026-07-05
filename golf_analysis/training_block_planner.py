"""Build drill-linked training blocks from Garmin, Rapsodo, and drill history."""

from __future__ import annotations

from typing import Any

from golf_analysis.drills.catalog import (
    apply_drill_overrides,
    drill_session_stats,
    enrich_drill,
    find_base_drill,
    load_drill_overrides,
    load_effective_all_catalog,
)
from golf_analysis.training_block_store import block_all_complete, new_block_id, utc_now_iso

# Drill pools by training focus (IDs must exist in catalog).
_DRILL_POOLS: dict[str, list[str]] = {
    "range_dispersion": [
        "range_dispersion",
        "range_direction_window",
        "range_lm_distance",
    ],
    "range_target": [
        "range_target_irons",
        "range_closest_to_pin",
    ],
    "range_combine": [
        "range_combine",
    ],
    "direction": [
        "range_dispersion",
        "range_direction_window",
        "putt_6_foot_compass",
        "putt_3_foot_compass",
        "gate_drill",
    ],
    "putting_short": [
        "putt_25_in_a_row_3ft",
        "gate_drill",
        "clock_drill_circle_8",
        "six_foot_test",
        "streak_builder",
    ],
    "putting_lag": [
        "lag_putting_knockout",
        "lag_it_drill",
        "putt_20_in_a_row_20ft_lag",
        "putt_20_in_a_row_30ft_lag",
        "putt_killer",
    ],
    "short_game": [
        "chip_8_of_10_30ft",
        "chip_nsew_compass",
        "chip_par_18_challenge",
        "chip_general_practice",
    ],
    "maintenance": [
        "drill_3_6_9",
        "speed_ladder",
        "chip_general_practice",
        "gate_drill",
    ],
    "combine": [
        "range_combine",
        "putt_20_tee_game",
        "putt_10_foot_game",
        "ladder_drill",
    ],
}

_SESSION_BLUEPRINTS: list[dict[str, str]] = [
    {"focus": "range_dispersion", "priority_tag": "P1", "title_prefix": "Range — dispersion"},
    {"focus": "range_target", "priority_tag": "P1", "title_prefix": "Range — approach targets"},
    {"focus": "short_game", "priority_tag": "P2", "title_prefix": "Short game touch"},
    {"focus": "range_combine", "priority_tag": "P3", "title_prefix": "Combine & scoring"},
]


def _is_wood_club(club: str) -> bool:
    c = club.lower().strip().replace(" ", "")
    if c in {"driver", "dr", "1w", "d"}:
        return True
    if len(c) >= 2 and c[-1] == "w" and c[:-1].replace(".", "").isdigit():
        return True
    if len(c) >= 2 and c[-1] == "h" and c[0].isdigit():
        return True
    if "hybrid" in c or (len(c) >= 3 and c.endswith("hy")):
        return True
    return False


def _flagged_has_woods(flagged_clubs: list[str]) -> bool:
    return any(_is_wood_club(c) for c in flagged_clubs)


def _primary_flagged_club(flagged_clubs: list[str]) -> str | None:
    if not flagged_clubs:
        return None
    woods = [c for c in flagged_clubs if _is_wood_club(c)]
    return woods[0] if woods else flagged_clubs[0]


def _known_drill_ids() -> set[str]:
    ids: set[str] = set()
    for drills in load_effective_all_catalog().values():
        for d in drills:
            raw = d.get("id")
            if raw:
                ids.add(str(raw))
    return ids


def _pick_drill(
    focus: str,
    *,
    used: set[str],
    stats: dict[str, dict[str, Any]],
    known: set[str],
) -> dict[str, Any] | None:
    pool = [did for did in _DRILL_POOLS.get(focus, []) if did in known and did not in used]
    if not pool:
        return None

    def sort_key(did: str) -> tuple[int, int]:
        row = stats.get(did) or {}
        days = row.get("days_since_last_played")
        if days is None:
            return (0, 9999)
        return (1, -int(days))

    pool.sort(key=sort_key)
    did = pool[0]
    found = find_base_drill(did)
    if found is None:
        return None
    _, base = found
    drill = apply_drill_overrides(base, load_drill_overrides())
    return enrich_drill(drill, stats=stats)


def _flatten_garmin_scoring(scoring: dict[str, Any]) -> dict[str, Any]:
    out = dict(scoring)
    putting = scoring.get("proxy_putting_load")
    if isinstance(putting, dict) and putting.get("putts_per_hole") is not None:
        out["putts_per_hole"] = putting["putts_per_hole"]
    fairway = scoring.get("proxy_fairway")
    if isinstance(fairway, dict) and fairway.get("pct_hit") is not None:
        out["fairway_hit_pct"] = fairway["pct_hit"]
    penalties = scoring.get("proxy_penalties")
    if isinstance(penalties, dict) and penalties.get("pct_holes") is not None:
        out["penalty_hole_rate"] = float(penalties["pct_holes"]) / 100.0
    blow = scoring.get("proxy_avoid_big_numbers")
    if isinstance(blow, dict) and blow.get("pct_holes") is not None:
        out["stableford_zero_point_rate"] = float(blow["pct_holes"]) / 100.0
    return out


def _garmin_coach_lines(scoring: dict[str, Any]) -> list[str]:
    scoring = _flatten_garmin_scoring(scoring)
    lines: list[str] = []
    rounds = int(scoring.get("rounds") or 0)
    if rounds <= 0:
        lines.append("No on-course rounds in this window yet — range and drill work builds the foundation.")
        return lines

    putts = scoring.get("putts_per_hole")
    if putts is not None and float(putts) >= 1.95:
        lines.append(
            f"On-course putting load is high ({float(putts):.2f} putts/hole over {rounds} rounds) — "
            "prioritise lag and short-make drills."
        )
    elif putts is not None:
        lines.append(f"Putting averages {float(putts):.2f} per hole — maintain with structured drills.")

    pen_rate = scoring.get("penalty_hole_rate")
    if pen_rate is not None and float(pen_rate) >= 0.08:
        lines.append(
            f"Penalty holes show up on {100 * float(pen_rate):.0f}% of holes — "
            "direction and start-line work should support safer tee targets."
        )

    fw = scoring.get("fairway_hit_pct")
    if fw is not None and float(fw) < 45:
        lines.append(
            f"Fairway hit rate is {float(fw):.0f}% — combine range awareness with compass-style putting for aim."
        )

    blow = scoring.get("stableford_zero_point_rate")
    if blow is not None and float(blow) >= 0.12:
        lines.append(
            f"Big-number holes (0 Stableford points) on {100 * float(blow):.0f}% of tracked holes — "
            "short game and lag putting reduce damage."
        )

    proxy_esz = scoring.get("proxy_esz")
    if isinstance(proxy_esz, dict):
        rate = proxy_esz.get("rate")
        if rate is not None and float(rate) < 0.35:
            lines.append(
                f"Scoring-zone proxy (inside 100 yd in regulation) is {100 * float(rate):.0f}% — "
                "chipping and wedge-touch drills are in the mix."
            )

    if not lines:
        lines.append(
            f"Solid baseline across {rounds} on-course round(s) — this block rotates drills you have not hit recently."
        )
    return lines


def build_coach_summary(
    *,
    garmin_scoring: dict[str, Any] | None,
    rapsodo_insights: list[str],
    flagged_clubs: list[str],
) -> str:
    parts: list[str] = []
    if garmin_scoring:
        parts.extend(_garmin_coach_lines(garmin_scoring))
    if flagged_clubs:
        clubs = ", ".join(flagged_clubs[:3])
        if _flagged_has_woods(flagged_clubs):
            parts.append(
                f"Range dispersion flags on {clubs} — Range simulation and direction-window drills are scheduled."
            )
        else:
            parts.append(f"Range dispersion flags: {clubs} — target and direction drills are scheduled first.")
    elif rapsodo_insights:
        parts.append(rapsodo_insights[0])
    if not parts:
        parts.append(
            "Your training block uses trackable drills tied to putting, short game, and combine-style scoring."
        )
    return " ".join(parts[:4])


def _focus_for_blueprint(
    blueprint: dict[str, str],
    *,
    garmin_scoring: dict[str, Any] | None,
    flagged_clubs: list[str],
    rapsodo_insights: list[str],
) -> str:
    focus = blueprint["focus"]
    text = " ".join(rapsodo_insights).lower()
    flat = _flatten_garmin_scoring(garmin_scoring) if garmin_scoring else {}
    putts = flat.get("putts_per_hole")

    if focus == "range_dispersion":
        if flagged_clubs and _flagged_has_woods(flagged_clubs):
            return "range_dispersion"
        if flagged_clubs:
            return "range_target"
        return "range_dispersion"
    if focus == "range_target":
        if flagged_clubs and not _flagged_has_woods(flagged_clubs):
            return "range_target"
        if flagged_clubs:
            return "range_dispersion"
        return "range_target"
    if focus == "range_combine":
        if "gapping" in text or "gap" in text or "combine" in text:
            return "range_combine"
        return "range_combine"
    if focus == "direction" and flagged_clubs:
        return "range_dispersion" if _flagged_has_woods(flagged_clubs) else "range_target"
    if focus == "putting_short" and putts is not None and float(putts) >= 1.9:
        return "putting_short"
    if focus == "putting_short" and ("putt" in text or "lag" in text):
        return "putting_lag" if "lag" in text else "putting_short"
    if focus == "short_game" and garmin_scoring:
        proxy_esz = garmin_scoring.get("proxy_esz")
        if isinstance(proxy_esz, dict):
            rate = proxy_esz.get("rate")
            if rate is not None and float(rate) < 0.4:
                return "short_game"
    if focus == "combine" and ("gapping" in text or "gap" in text):
        return "combine"
    return focus


def _session_rationale(
    focus: str,
    drill: dict[str, Any],
    *,
    flagged_clubs: list[str],
    garmin_scoring: dict[str, Any] | None,
) -> str:
    title = str(drill.get("title", "Drill"))
    mins = drill.get("expected_duration_minutes")
    dur = f" (~{mins} min)" if mins else ""
    if focus in {"range_dispersion", "range_target", "range_combine", "direction"} and flagged_clubs:
        club = _primary_flagged_club(flagged_clubs) or "your focus club"
        mode = str(drill.get("rapsodo_mode_label") or "Rapsodo")
        return (
            f"{title}{dur} — use {mode}; log session with **{club}** as club focus "
            f"(dispersion flagged on range data)."
        )
    if focus in {"putting_short", "putting_lag"} and garmin_scoring:
        putts = _flatten_garmin_scoring(garmin_scoring).get("putts_per_hole")
        if putts is not None:
            return f"{title}{dur} — supports on-course putting ({float(putts):.2f} putts/hole in window)."
    if focus == "short_game":
        return f"{title}{dur} — builds touch around the green for up-and-down opportunities."
    if focus == "combine":
        return f"{title}{dur} — scored combine format to track improvement session to session."
    return f"{title}{dur} — log your result when finished so progress stays tracked."


def build_training_block(
    *,
    calendar_year: int,
    n_sessions: int,
    garmin_scoring: dict[str, Any] | None,
    rapsodo_insights: list[str],
    flagged_clubs: list[str],
) -> dict[str, Any]:
    stats = drill_session_stats()
    known = _known_drill_ids()
    used: set[str] = set()
    sessions: list[dict[str, Any]] = []

    blueprints = list(_SESSION_BLUEPRINTS)
    while len(blueprints) < n_sessions:
        blueprints.append(
            {"focus": "maintenance", "priority_tag": "P1", "title_prefix": "Maintenance rotation"}
        )

    for i in range(n_sessions):
        bp = blueprints[i]
        focus = _focus_for_blueprint(
            bp,
            garmin_scoring=garmin_scoring,
            flagged_clubs=flagged_clubs,
            rapsodo_insights=rapsodo_insights,
        )
        drill = _pick_drill(focus, used=used, stats=stats, known=known)
        if drill is None:
            drill = _pick_drill("maintenance", used=used, stats=stats, known=known)
        if drill is None:
            continue
        did = str(drill["id"])
        used.add(did)
        sessions.append(
            {
                "index": i + 1,
                "title": f"{bp['title_prefix']} — {drill['title']}",
                "description": _session_rationale(
                    focus,
                    drill,
                    flagged_clubs=flagged_clubs,
                    garmin_scoring=garmin_scoring,
                ),
                "priority_tag": bp["priority_tag"],
                "focus": focus,
                "drill_id": did,
                "drill_title": drill["title"],
                "drill_category": drill.get("category"),
                "expected_duration_minutes": drill.get("expected_duration_minutes"),
                "success_target": drill.get("success_target"),
                "rapsodo_mode_label": drill.get("rapsodo_mode_label"),
                "default_aim": drill.get("default_aim"),
                "suggested_club": _primary_flagged_club(flagged_clubs)
                if focus.startswith("range") and flagged_clubs
                else None,
                "completed_at": None,
                "linked_session_id": None,
            }
        )

    coach_summary = build_coach_summary(
        garmin_scoring=garmin_scoring,
        rapsodo_insights=rapsodo_insights,
        flagged_clubs=flagged_clubs,
    )

    return {
        "block_id": new_block_id(),
        "generated_at": utc_now_iso(),
        "calendar_year": calendar_year,
        "sessions_planned": len(sessions),
        "coach_summary": coach_summary,
        "insights": rapsodo_insights,
        "flagged_clubs": flagged_clubs,
        "sessions": sessions,
        "all_complete": False,
    }


def enrich_block_completion(block: dict[str, Any]) -> dict[str, Any]:
    out = dict(block)
    out["all_complete"] = block_all_complete(out)
    return out
