"""ESZ / DSZ from Garmin ``shotDetails`` (geometry, orientation distances, or par-based heuristics)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

# Scoring Method: ~100 yd ring to pin (use meters for haversine, convert to yards).
SCORING_ZONE_YARDS = 100.0
YARDS_PER_METER = 1.0936132983377

# When only cumulative ``meters`` per shot exist: assume a straight “hole length” by par (yards).
_ASSUMED_HOLE_YARDS_BY_PAR: dict[int, float] = {3: 185.0, 4: 405.0, 5: 525.0}

# Documented for API consumers (Garmin JSON — not SQLite).
ESZ_DSZ_DATA_MODEL: dict[str, Any] = {
    "source": "Garmin Golf Community export JSON (e.g. golf-export.json).",
    "round_key": "scorecard id string — matches shotDetails[].scorecardId.",
    "scorecard_metadata": (
        "Prefer details[].scorecardDetails[].scorecard (rich). "
        "If missing, summary.scorecardSummaries[] is merged for holePars / courseName / startTime."
    ),
    "hole_par": "scorecard.holePars[hole-1] digit, else scorecard.holes[] where number matches hole.",
    "shot_sequences": "shotDetails[].response.holeShots[] with holeNumber, optional pinPosition, shots[].",
    "distance_to_pin_per_shot_end": [
        "1) Haversine yards: shots[].endLoc lat/lon vs pinPosition (Garmin semicircles).",
        "2) Else remainingDistance (yards) keyed by shots[].id from any shotId object in the file.",
        "3) Else startingDistanceToHole minus this shot meters (yards).",
        "4) Else cumulative shot meters vs hole yardage (holes[]) or par-default straight length.",
    ],
    "esz_hole": "entered ≤100 yd zone by end of stroke on or before stroke index (par − 2) (GIR-style regulation).",
    "dsz_hole": (
        "Among holes that entered the zone: ≤3 strokes from first in-zone through holed out. "
        "Prefer scorecard gross strokes S on the hole and entry stroke E (1-based) from the shot trace: "
        "S − E + 1 ≤ 3; if holes[].strokes/score is missing or S < E, fall back to shot-count in trace."
    ),
    "aggregation": (
        "hole_level: one row per holeShots entry with evaluable shots. "
        "totals: sum across those holes. by_round: same holes grouped by scorecard id."
    ),
}


def _assumed_hole_length_yards(par: int) -> float:
    return _ASSUMED_HOLE_YARDS_BY_PAR.get(par, 400.0)


def _semicircles_to_degrees(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x * (180.0 / 2.0**31)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters (WGS84 sphere)."""

    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(h)))
    return 6371000.0 * c


def _yards_to_pin(loc: dict[str, Any] | None, pin: dict[str, Any] | None) -> float | None:
    if not isinstance(loc, dict) or not isinstance(pin, dict):
        return None
    la1 = _semicircles_to_degrees(loc.get("lat"))
    lo1 = _semicircles_to_degrees(loc.get("lon"))
    la2 = _semicircles_to_degrees(pin.get("lat"))
    lo2 = _semicircles_to_degrees(pin.get("lon"))
    if la1 is None or lo1 is None or la2 is None or lo2 is None:
        return None
    m = _haversine_m(la1, lo1, la2, lo2)
    return m * YARDS_PER_METER


def _index_shot_orientation_yards(data: dict[str, Any]) -> tuple[dict[int, float], dict[int, float]]:
    """
    Walk the export for ``shotId`` + distance fields (Garmin last-10 / ``shotOrientationDetail``).

    Returns:
        (remaining_after_shot_yards, starting_distance_to_hole_yards) keyed by ``shotId``.
    """

    remaining: dict[int, float] = {}
    starting: dict[int, float] = {}

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "shotId" in obj:
                try:
                    sid = int(obj["shotId"])
                except (TypeError, ValueError):
                    sid = -1
                if sid >= 0:
                    if "remainingDistance" in obj:
                        try:
                            remaining[sid] = float(obj["remainingDistance"])
                        except (TypeError, ValueError):
                            pass
                    if "startingDistanceToHole" in obj:
                        try:
                            starting[sid] = float(obj["startingDistanceToHole"])
                        except (TypeError, ValueError):
                            pass
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(data)
    return remaining, starting


def _hole_play_length_yards(scorecard: dict[str, Any], hole_number: int) -> float | None:
    """Hole length from scorecard ``holes[]`` when Garmin includes it (yards or short holes in meters)."""

    holes = scorecard.get("holes")
    if not isinstance(holes, list):
        return None
    for h in holes:
        if not isinstance(h, dict):
            continue
        try:
            hn = int(h.get("number") or h.get("holeNumber") or 0)
        except (TypeError, ValueError):
            continue
        if hn != hole_number:
            continue
        for key in (
            "length",
            "holeLength",
            "yardage",
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
            # Typical scorecard hole length: 55–700 yd. Very small values are often meters (e.g. 72).
            if x < 95:
                return x * YARDS_PER_METER
            if x <= 750:
                return x
        return None
    return None


def _first_scoring_zone_shot_index(
    shots: list[dict[str, Any]],
    pin: Any,
    par: int,
    shot_remaining_yards: dict[int, float],
    shot_starting_yards: dict[int, float],
    hole_play_yards: float | None,
) -> tuple[int | None, str]:
    """
    First shot index whose end-of-shot distance-to-pin (best available estimate) is ≤ zone.

    Priority per shot: (1) haversine ``endLoc`` vs ``pin``, (2) ``remainingDistance`` by ``shot.id``,
    (3) ``startingDistanceToHole - shot meters`` (yards) by ``shot.id``,
    (4) heuristic ``max(0, hole_length_or_par_default - cumulative shot meters as yards)``.
    """

    assumed = (
        hole_play_yards
        if hole_play_yards is not None and hole_play_yards >= 60.0
        else _assumed_hole_length_yards(par)
    )
    cum_h = 0.0
    pin_d = pin if isinstance(pin, dict) else None

    for i, shot in enumerate(shots):
        yd: float | None = None
        tier = "geometry"
        if pin_d is not None:
            end = shot.get("endLoc")
            yd = _yards_to_pin(end if isinstance(end, dict) else None, pin_d)
        if yd is None:
            tier = "orientation"
            sidv = shot.get("id")
            if sidv is not None:
                try:
                    k = int(sidv)
                    if k in shot_remaining_yards:
                        yd = shot_remaining_yards[k]
                except (TypeError, ValueError):
                    pass
        if yd is None:
            tier = "orientation_starting_minus_shot"
            sidv = shot.get("id")
            m = shot.get("meters")
            if sidv is not None:
                try:
                    k = int(sidv)
                    if k in shot_starting_yards:
                        try:
                            seg = float(m) * YARDS_PER_METER if m is not None else 0.0
                        except (TypeError, ValueError):
                            seg = 0.0
                        yd = max(0.0, shot_starting_yards[k] - seg)
                except (TypeError, ValueError):
                    pass
        if yd is None:
            tier = "heuristic_straight_hole"
            m = shot.get("meters")
            try:
                seg = float(m) * YARDS_PER_METER if m is not None else 0.0
            except (TypeError, ValueError):
                seg = 0.0
            cum_h += seg
            yd = max(0.0, assumed - cum_h)
        if yd is not None and yd <= SCORING_ZONE_YARDS:
            return i, tier
    return None, "none"


def _scorecard_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map scorecard id string -> scorecard dict from ``details`` only."""

    out: dict[str, dict[str, Any]] = {}
    details = data.get("details")
    if not isinstance(details, list):
        return out
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
            sid = sc.get("id")
            if sid is None:
                continue
            out[str(sid).strip()] = sc
    return out


def _merge_summary_scorecards_into_index(data: dict[str, Any], out: dict[str, dict[str, Any]]) -> None:
    """Fill gaps using ``summary.scorecardSummaries`` (same ids as ``shotDetails``)."""

    summary = data.get("summary")
    if not isinstance(summary, dict):
        return
    scs = summary.get("scorecardSummaries")
    if not isinstance(scs, list):
        return
    for raw in scs:
        if not isinstance(raw, dict):
            continue
        sid = raw.get("id")
        if sid is None:
            continue
        key = str(sid).strip()
        if key not in out:
            out[key] = dict(raw)
            continue
        tgt = out[key]
        for fld in ("holePars", "courseName", "startTime", "formattedStartTime", "endTime"):
            if fld not in tgt or tgt.get(fld) in (None, ""):
                v = raw.get(fld)
                if v is not None and v != "":
                    tgt[fld] = v


def _build_scorecard_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = _scorecard_index(data)
    _merge_summary_scorecards_into_index(data, out)
    return out


def _course_started_meta(sc: dict[str, Any]) -> tuple[str | None, str | None]:
    course = sc.get("courseName") or sc.get("course_name")
    start = sc.get("startTime") or sc.get("formattedStartTime")
    return (str(course) if course else None, str(start) if start else None)


def _rollup_esz_dsz_by_round(hole_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per scorecard_id rollups for dashboard round table."""

    g: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in hole_rows:
        g[str(r["scorecard_id"]).strip()].append(r)

    out: list[dict[str, Any]] = []
    for sid, rows in sorted(g.items(), key=lambda kv: (kv[1][0].get("started_at") or "", kv[0])):
        hev = len(rows)
        esz_ok = sum(1 for x in rows if x["esz_success"])
        dsz_elig = sum(1 for x in rows if x["entered_scoring_zone"])
        dsz_ok = sum(1 for x in rows if x["dsz_success"])
        mm: dict[str, int] = {
            "geometry": 0,
            "orientation": 0,
            "orientation_starting_minus_shot": 0,
            "heuristic_straight_hole": 0,
        }
        for x in rows:
            if not x["entered_scoring_zone"]:
                continue
            t = x.get("first_zone_method")
            if isinstance(t, str) and t in mm:
                mm[t] += 1
        course = rows[0].get("course_name")
        started = rows[0].get("started_at")
        out.append(
            {
                "scorecard_id": sid,
                "course_name": course,
                "started_at": started,
                "holes_evaluated": hev,
                "esz_success_holes": esz_ok,
                "esz_pct": (100.0 * esz_ok / hev) if hev else None,
                "dsz_holes_with_zone_entry": dsz_elig,
                "dsz_success_holes": dsz_ok,
                "dsz_pct": (100.0 * dsz_ok / dsz_elig) if dsz_elig else None,
                "distance_to_pin_methods": mm,
            }
        )
    return out


def _strokes_recorded_for_hole(scorecard: dict[str, Any], hole_number: int) -> int | None:
    """Gross strokes on a hole from ``holes[]`` when Garmin includes them (``strokes``, ``score``, …)."""

    holes = scorecard.get("holes")
    if not isinstance(holes, list):
        return None
    for h in holes:
        if not isinstance(h, dict):
            continue
        try:
            hn = int(h.get("number") or h.get("holeNumber") or 0)
        except (TypeError, ValueError):
            continue
        if hn != hole_number:
            continue
        for key in ("strokes", "score", "holeStrokes", "grossStrokes", "grossScore"):
            v = h.get(key)
            if v is None:
                continue
            try:
                n = int(round(float(v)))
            except (TypeError, ValueError):
                continue
            if n >= 1:
                return n
        return None
    return None


def _dsz_success_and_basis(
    hole_strokes: int | None,
    entry_stroke_1based: int,
    shots_in_trace_from_zone: int,
) -> tuple[bool, int, str]:
    """
    DSZ: ≤3 strokes from first in-zone through holed out (inclusive of the entry stroke).

    Prefer scorecard gross ``S`` and entry index ``E`` from the trace: ``S - E + 1``.
    If ``S`` is missing or ``S < E`` (inconsistent vs trace), use ``shots_in_trace_from_zone``.
    """

    if hole_strokes is not None and hole_strokes >= entry_stroke_1based:
        n = hole_strokes - entry_stroke_1based + 1
        return (n <= 3, n, "scorecard")
    if hole_strokes is not None:
        return (
            shots_in_trace_from_zone <= 3,
            shots_in_trace_from_zone,
            "shot_trace_score_lt_entry",
        )
    return (shots_in_trace_from_zone <= 3, shots_in_trace_from_zone, "shot_trace")


def _par_for_hole(scorecard: dict[str, Any], hole_number: int) -> int | None:
    hp = scorecard.get("holePars")
    if isinstance(hp, str) and hole_number >= 1:
        idx = hole_number - 1
        if idx < len(hp) and hp[idx].isdigit():
            return int(hp[idx])
    holes = scorecard.get("holes")
    if isinstance(holes, list):
        for h in holes:
            if not isinstance(h, dict):
                continue
            try:
                hn = int(h.get("number") or h.get("holeNumber") or 0)
            except (TypeError, ValueError):
                continue
            if hn == hole_number:
                p = h.get("par")
                if p is not None:
                    try:
                        return int(round(float(p)))
                    except (TypeError, ValueError):
                        return None
    return None


def _scorecard_year(sc: dict[str, Any]) -> int | None:
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


def compute_esz_dsz_from_shot_details(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
    scorecard_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    ESZ: first shot whose **end** lies within ``SCORING_ZONE_YARDS`` of the pin occurs on or before
    stroke ``par − 2`` (GIR-style regulation: e.g. par 4 by end of stroke 2).

    DSZ: **≤ 3** strokes from first in-zone through holed out. When the scorecard lists gross strokes
    ``S`` for the hole, use ``S - E + 1`` with ``E`` = 1-based stroke index of first in-zone from the
    trace; otherwise use the number of shots in the trace from first in-zone through the last shot.

    Distance-to-pin per shot (first that succeeds): **geometry** (``endLoc`` vs ``pin``),
    else **remainingDistance** by ``shot.id``, else **startingDistanceToHole − shot meters**,
    else **cumulative heuristic** (scorecard hole length when present, else par template).
    """

    sc_index = _build_scorecard_index(data)
    shot_details = data.get("shotDetails")
    if not isinstance(shot_details, list):
        return {
            "holes_evaluated": 0,
            "shot_detail_blocks": 0,
            "note": "No shotDetails array in export.",
            "availability_hint": "Garmin export has no top-level shotDetails list.",
            "diagnostics": {},
            "by_round": [],
            "data_model": ESZ_DSZ_DATA_MODEL,
        }

    shot_remaining_yards, shot_starting_yards = _index_shot_orientation_yards(data)
    n_blocks = sum(1 for b in shot_details if isinstance(b, dict))
    hole_rows: list[dict[str, Any]] = []
    dbg: dict[str, int] = {
        "blocks_missing_scorecard_id": 0,
        "blocks_excluded_by_scorecard_id_filter": 0,
        "blocks_scorecard_not_in_details_index": 0,
        "blocks_excluded_by_calendar_year": 0,
        "blocks_missing_response": 0,
        "blocks_missing_hole_shots_list": 0,
        "hole_rows_bad_hole_number": 0,
        "hole_rows_missing_par": 0,
        "hole_rows_missing_shots_list": 0,
        "hole_rows_no_shots_after_exclude": 0,
        "dsz_basis_scorecard": 0,
        "dsz_basis_shot_trace": 0,
        "dsz_basis_shot_trace_score_lt_entry": 0,
    }

    for block in shot_details:
        if not isinstance(block, dict):
            continue
        sid_raw = block.get("scorecardId")
        if sid_raw is None:
            dbg["blocks_missing_scorecard_id"] += 1
            continue
        sid = str(sid_raw).strip()
        # Empty set must not filter: ``sid not in set()`` is always true and would drop every hole.
        if scorecard_ids is not None and len(scorecard_ids) > 0 and sid not in scorecard_ids:
            dbg["blocks_excluded_by_scorecard_id_filter"] += 1
            continue
        sc = sc_index.get(sid)
        if not isinstance(sc, dict):
            dbg["blocks_scorecard_not_in_details_index"] += 1
            continue
        if calendar_year is not None:
            y = _scorecard_year(sc)
            if y is not None and y != calendar_year:
                dbg["blocks_excluded_by_calendar_year"] += 1
                continue
        resp = block.get("response")
        if not isinstance(resp, dict):
            dbg["blocks_missing_response"] += 1
            continue
        hole_shots = resp.get("holeShots")
        if not isinstance(hole_shots, list):
            dbg["blocks_missing_hole_shots_list"] += 1
            continue
        for hs in hole_shots:
            if not isinstance(hs, dict):
                continue
            try:
                hole_num = int(hs.get("holeNumber") or block.get("holeNumber") or 0)
            except (TypeError, ValueError):
                dbg["hole_rows_bad_hole_number"] += 1
                continue
            if hole_num < 1:
                dbg["hole_rows_bad_hole_number"] += 1
                continue
            par = _par_for_hole(sc, hole_num)
            if par is None:
                dbg["hole_rows_missing_par"] += 1
                continue
            pin = hs.get("pinPosition")
            shots_raw = hs.get("shots")
            if not isinstance(shots_raw, list):
                dbg["hole_rows_missing_shots_list"] += 1
                continue
            shots = [s for s in shots_raw if isinstance(s, dict) and not s.get("excludeFromStats")]
            if not shots:
                dbg["hole_rows_no_shots_after_exclude"] += 1
                continue
            shots.sort(key=lambda s: int(s.get("shotOrder") or s.get("shot_order") or 0) or 0)

            hole_play = _hole_play_length_yards(sc, hole_num)
            first_in_idx, tier = _first_scoring_zone_shot_index(
                shots,
                pin,
                par,
                shot_remaining_yards,
                shot_starting_yards,
                hole_play,
            )

            course_name, started_at = _course_started_meta(sc)

            if first_in_idx is None:
                hole_rows.append(
                    {
                        "scorecard_id": sid,
                        "hole_number": hole_num,
                        "par": par,
                        "course_name": course_name,
                        "started_at": started_at,
                        "entered_scoring_zone": False,
                        "esz_success": False,
                        "dsz_success": False,
                        "first_zone_method": "none",
                    }
                )
                continue

            stroke_at_entry = first_in_idx + 1
            esz_cap = par - 2
            esz_success = stroke_at_entry <= esz_cap
            hole_strokes = _strokes_recorded_for_hole(sc, hole_num)
            shots_from_zone = len(shots) - first_in_idx
            dsz_success, _, dsz_basis = _dsz_success_and_basis(
                hole_strokes,
                stroke_at_entry,
                shots_from_zone,
            )
            if dsz_basis == "scorecard":
                dbg["dsz_basis_scorecard"] += 1
            elif dsz_basis == "shot_trace_score_lt_entry":
                dbg["dsz_basis_shot_trace_score_lt_entry"] += 1
            else:
                dbg["dsz_basis_shot_trace"] += 1
            hole_rows.append(
                {
                    "scorecard_id": sid,
                    "hole_number": hole_num,
                    "par": par,
                    "course_name": course_name,
                    "started_at": started_at,
                    "entered_scoring_zone": True,
                    "esz_success": esz_success,
                    "dsz_success": dsz_success,
                    "first_zone_method": tier,
                }
            )

    holes_used = len(hole_rows)
    esz_ok = sum(1 for r in hole_rows if r["esz_success"])
    esz_fail = holes_used - esz_ok
    dsz_eligible = sum(1 for r in hole_rows if r["entered_scoring_zone"])
    dsz_ok = sum(1 for r in hole_rows if r["entered_scoring_zone"] and r["dsz_success"])
    method_first_zone: dict[str, int] = {
        "geometry": 0,
        "orientation": 0,
        "orientation_starting_minus_shot": 0,
        "heuristic_straight_hole": 0,
    }
    for r in hole_rows:
        if not r["entered_scoring_zone"]:
            continue
        t = r.get("first_zone_method")
        if isinstance(t, str) and t in method_first_zone:
            method_first_zone[t] += 1

    by_round = _rollup_esz_dsz_by_round(hole_rows)

    heuristic_note = (
        "Heuristic tier: subtracts cumulative shot ``meters`` (as yards) from scorecard hole length "
        "when ``holes[].yardage``/length fields exist; otherwise uses typical length by par. "
        "Ignores dog-legs and lateral misses. ``startingDistanceToHole - shot`` is a coarse end-of-shot proxy."
    )

    return {
        "holes_evaluated": holes_used,
        "shot_detail_blocks": n_blocks,
        "dsz_holes_with_zone_entry": dsz_eligible,
        "scoring_zone_yards": SCORING_ZONE_YARDS,
        "esz_pct": (100.0 * esz_ok / holes_used) if holes_used else None,
        "dsz_pct": (100.0 * dsz_ok / dsz_eligible) if dsz_eligible else None,
        "esz_success_holes": esz_ok,
        "esz_fail_holes": esz_fail,
        "dsz_success_holes": dsz_ok,
        "dsz_fail_holes": dsz_eligible - dsz_ok,
        "distance_to_pin_methods": method_first_zone,
        "heuristic_note": heuristic_note,
        "note": (
            "ESZ/DSZ use ≤100 yd to pin by end of stroke (ESZ regulation: first zone entry by end of stroke par−2). "
            "DSZ prefers scorecard gross strokes on the hole vs entry stroke from the trace (see data_model). "
            "Per shot: (1) haversine endLoc vs pin, (2) remainingDistance by shot id, "
            "(3) startingDistanceToHole minus shot meters, "
            "(4) straight-line cumulative meters vs hole length or par default."
        ),
        "availability_hint": (
            None
            if holes_used > 0
            else (
                f"No holes matched filters (shotDetails blocks in file: {n_blocks}). "
                "Filtering is by calendar year and scorecard id (not by course name or single date). "
                "Need par (holePars / holes), a shots list, then geometry, remainingDistance, "
                "startingDistanceToHole−shot, or cumulative meters vs hole length/par default. "
                "See diagnostics on this payload."
            )
        ),
        "diagnostics": dbg,
        "by_round": by_round,
        "rounds_with_hole_analysis": len(by_round),
        "data_model": ESZ_DSZ_DATA_MODEL,
    }
