"""ESZ / DSZ from Garmin ``shotDetails`` (geometry, orientation distances, or par-based heuristics)."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from golf_analysis.metrics_reference import ENTRY_DISTANCE_NOTE, PROXY_DSZ, PROXY_ESZ

from golf_analysis.scoring_zone_constants import (
    DSZ_ENTRY_BAND_STEP_YARDS,
    DSZ_ENTRY_CLOSE_MAX_YARDS,
    SCORING_ZONE_YARDS,
)

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
        "Among holes that entered the zone with scorecard gross S and a shot trace: "
        "strokes inside zone = S − (tracked shots before first ≤100 yd end). "
        "DSZ success when that count is ≤ 3. Holes without score on the card are excluded from DSZ %."
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


GEOMETRY_DISTANCE_TIERS = frozenset(
    {"geometry", "orientation", "orientation_starting_minus_shot"},
)



def _build_dsz_entry_band_defs() -> tuple[tuple[str, str, float, float], ...]:
    """0–30 yd, then 10 yd steps to 100 (30–40, 40–50, …)."""

    bands: list[tuple[str, str, float, float]] = [
        ("0_30", "0–30 yd", 0.0, DSZ_ENTRY_CLOSE_MAX_YARDS),
    ]
    start = int(DSZ_ENTRY_CLOSE_MAX_YARDS)
    while start < int(SCORING_ZONE_YARDS):
        end = float(start + DSZ_ENTRY_BAND_STEP_YARDS)
        bands.append((f"{start}_{int(end)}", f"{start}–{int(end)} yd", float(start), end))
        start = int(end)
    return tuple(bands)


DSZ_ENTRY_BANDS: tuple[tuple[str, str, float, float], ...] = _build_dsz_entry_band_defs()


def _first_scoring_zone_shot_index(
    shots: list[dict[str, Any]],
    pin: Any,
    par: int,
    shot_remaining_yards: dict[int, float],
    shot_starting_yards: dict[int, float],
    hole_play_yards: float | None,
) -> tuple[int | None, str, float | None]:
    """
    First shot index whose end-of-shot distance-to-pin (best available estimate) is ≤ zone.

    Returns ``(index, distance_tier, yards_at_entry)``.

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
            return i, tier, yd
    return None, "none", None


def _dsz_entry_band_id(yards: float) -> str | None:
    if yards < 0 or yards > SCORING_ZONE_YARDS:
        return None
    if yards <= DSZ_ENTRY_CLOSE_MAX_YARDS:
        return "0_30"
    for bid, _, ymin, ymax in DSZ_ENTRY_BANDS:
        if bid == "0_30":
            continue
        if ymin < yards <= ymax:
            return bid
    return None


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
        dsz_elig = sum(1 for x in rows if _hole_dsz_evaluable(x))
        dsz_ok = sum(1 for x in rows if _hole_dsz_evaluable(x) and x.get("dsz_success"))
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


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _hole_dict_for_number(scorecard: dict[str, Any], hole_number: int) -> dict[str, Any] | None:
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
        if hn == hole_number:
            return h
    return None


def _strokes_recorded_for_hole(scorecard: dict[str, Any], hole_number: int) -> int | None:
    """Gross strokes on a hole from ``holes[]`` when Garmin includes them (``strokes``, ``score``, …)."""

    h = _hole_dict_for_number(scorecard, hole_number)
    if not h:
        return None
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


def _putts_for_hole(scorecard: dict[str, Any], hole_number: int) -> int | None:
    h = _hole_dict_for_number(scorecard, hole_number)
    if not h:
        return None
    return _as_int(h.get("putts"))


def _shot_end_on_green(shot: dict[str, Any]) -> bool | None:
    """Whether a shot ended on the putting surface (``endLoc.lie`` = Green)."""

    end = shot.get("endLoc")
    if not isinstance(end, dict):
        return None
    lie = end.get("lie")
    if not isinstance(lie, str) or not lie.strip():
        return None
    u = lie.strip().upper().replace(" ", "")
    if u == "GREEN":
        return True
    if u in ("FAIRWAY", "ROUGH", "BUNKER", "TEEBOX", "UNKNOWN", "FRINGE"):
        return False
    return None


def _entry_shot_on_green(entry_shot: dict[str, Any]) -> bool | None:
    """Whether the first in-zone shot ended on the green (``endLoc.lie``)."""

    return _shot_end_on_green(entry_shot)


def _traced_strokes_from_zone_entry(
    shots: list[dict[str, Any]],
    first_in_zone_index: int,
) -> int:
    """Shot-trace count from first in-zone shot through the last traced shot on the hole."""

    return max(0, len(shots) - first_in_zone_index)


def _strokes_to_green_from_entry(
    shots: list[dict[str, Any]],
    pin: Any,
    first_in_zone_index: int,
) -> int | None:
    """
    Traced shots from zone entry through the first shot that ends on the green (inclusive).

    None when lie is never Green inside the zone.
    """

    pin_d = pin if isinstance(pin, dict) else None
    if pin_d is None:
        return None
    in_zone = False
    count = 0
    for sh in shots[first_in_zone_index:]:
        end = sh.get("endLoc")
        yd = _yards_to_pin(end if isinstance(end, dict) else None, pin_d)
        if yd is not None and yd <= SCORING_ZONE_YARDS:
            in_zone = True
            count += 1
            if _shot_end_on_green(sh) is True:
                return count
        elif in_zone:
            break
    return None


def _scorecard_shots_before_putts(
    hole_strokes: int | None,
    tracked_shots_outside_zone: int,
    hole_putts: int | None,
) -> int | None:
    """Scorecard strokes from zone entry through on-green (gross − putts − traced shots before zone)."""

    if hole_strokes is None or hole_putts is None:
        return None
    if hole_strokes < tracked_shots_outside_zone + hole_putts:
        return None
    return hole_strokes - hole_putts - tracked_shots_outside_zone


def _dsz_success_for_entry_band(*, scorecard_inside: int | None) -> tuple[bool, int | None, str]:
    """
    DSZ for entry-distance bands: scorecard gross − traced shots before 100 yd ≤ 3.

    Uses scorecard + trace index only (no lie-based stroke counts). ``shots before putts`` on
    the band table is the pitching/chipping split (also scorecard-derived).
    """

    if scorecard_inside is None:
        return (False, None, "none")
    return (scorecard_inside <= 3, scorecard_inside, "scorecard_minus_outside")


def _reached_green_in_zone(
    shots: list[dict[str, Any]],
    pin: Any,
    first_in_zone_index: int,
) -> bool | None:
    """
    Whether any traced shot while inside the scoring zone ended on the green.

    Used for DSZ entry-distance bands: from 30+ yd the first in-zone shot is almost
    never lie=Green (ball is still that many yards from the pin); pitching vs putting
    needs “did you get on the green before holing out from this entry distance”.
    """

    pin_d = pin if isinstance(pin, dict) else None
    if pin_d is None:
        return None
    saw_lie = False
    in_zone = False
    for sh in shots[first_in_zone_index:]:
        end = sh.get("endLoc")
        yd = _yards_to_pin(end if isinstance(end, dict) else None, pin_d)
        if yd is not None and yd <= SCORING_ZONE_YARDS:
            in_zone = True
            on_green = _shot_end_on_green(sh)
            if on_green is None:
                continue
            saw_lie = True
            if on_green:
                return True
        elif in_zone:
            break
    if not saw_lie:
        return None
    return False


def _tracked_shots_outside_zone(first_in_zone_shot_index: int) -> int:
    """Count of shots in the trace before the first end position inside 100 yd."""

    return first_in_zone_shot_index


def _strokes_inside_scoring_zone(
    hole_strokes: int | None,
    tracked_shots_outside_zone: int,
) -> int | None:
    """Scorecard gross minus traced pre-zone shots (strokes used from zone entry through holing out)."""

    if hole_strokes is None:
        return None
    if hole_strokes < tracked_shots_outside_zone:
        return None
    return hole_strokes - tracked_shots_outside_zone


def _hole_dsz_evaluable(row: dict[str, Any]) -> bool:
    return bool(row.get("entered_scoring_zone")) and row.get("strokes_inside_zone") is not None


def _dsz_success_from_score_and_trace(
    hole_strokes: int | None,
    tracked_shots_outside_zone: int,
) -> tuple[bool, int | None, bool]:
    """
    DSZ: strokes inside zone (score − tracked shots outside 100 yd) ≤ 3.

    Returns ``(dsz_success, strokes_inside_zone, evaluable)``.
    """

    inside = _strokes_inside_scoring_zone(hole_strokes, tracked_shots_outside_zone)
    if inside is None:
        return (False, None, False)
    return (inside <= 3, inside, True)


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


def build_esz_dsz_hole_rows(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
    scorecard_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    """
    Per-hole ESZ/DSZ rows from ``shotDetails``.

    Returns ``(hole_rows, diagnostics, shot_detail_block_count)``.
    """

    sc_index = _build_scorecard_index(data)
    shot_details = data.get("shotDetails")
    if not isinstance(shot_details, list):
        return [], {}, 0

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
        "dsz_basis_score_minus_tracked_outside": 0,
        "dsz_skipped_no_scorecard": 0,
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
            first_in_idx, tier, entry_yards = _first_scoring_zone_shot_index(
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
            tracked_outside_zone = _tracked_shots_outside_zone(first_in_idx)
            dsz_success, strokes_inside_zone, dsz_evaluable = _dsz_success_from_score_and_trace(
                hole_strokes,
                tracked_outside_zone,
            )
            if dsz_evaluable:
                dbg["dsz_basis_score_minus_tracked_outside"] += 1
            else:
                dbg["dsz_skipped_no_scorecard"] += 1
            entry_shot = shots[first_in_idx]
            entry_on_green = _entry_shot_on_green(entry_shot)
            reached_green = _reached_green_in_zone(shots, pin, first_in_idx)
            hole_putts = _putts_for_hole(sc, hole_num)
            shots_before_putts = _scorecard_shots_before_putts(
                hole_strokes,
                tracked_outside_zone,
                hole_putts,
            )
            dsz_entry_ok, dsz_entry_strokes, dsz_entry_basis = _dsz_success_for_entry_band(
                scorecard_inside=strokes_inside_zone,
            )
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
                    "dsz_success_entry_band": dsz_entry_ok,
                    "dsz_entry_strokes": dsz_entry_strokes,
                    "dsz_entry_basis": dsz_entry_basis,
                    "first_zone_method": tier,
                    "first_zone_yards": round(entry_yards, 1) if entry_yards is not None else None,
                    "hole_strokes": hole_strokes,
                    "tracked_shots_outside_zone": tracked_outside_zone,
                    "strokes_inside_zone": strokes_inside_zone,
                    "scorecard_shots_before_putts": shots_before_putts,
                    "entry_on_green": entry_on_green,
                    "reached_green_in_zone": reached_green,
                    "hole_putts": hole_putts,
                }
            )

    return hole_rows, dbg, n_blocks


PAR_BUCKETS_ESZ_DSZ = (3, 4, 5)


def _rel_diff_pct(par_value: float, avg_value: float) -> float | None:
    if avg_value == 0:
        return 0.0 if par_value == 0 else None
    return 100.0 * (par_value - avg_value) / avg_value


def _esz_dsz_by_par_splits(
    by_par: dict[int, tuple[int, int]],
    *,
    avg_value: float | None,
) -> dict[str, Any]:
    """``by_par[par]`` = ``(numerator, denominator)`` for the metric (e.g. esz_ok, esz_eval)."""

    out: dict[str, Any] = {}
    if avg_value is None:
        return out
    for par in PAR_BUCKETS_ESZ_DSZ:
        num, den = by_par.get(par, (0, 0))
        if not den:
            continue
        val = 100.0 * num / den
        out[str(par)] = {
            "par": par,
            "value": val,
            "sample_holes": den,
            "diff_vs_avg_pct": _rel_diff_pct(val, avg_value),
        }
    return out


@dataclass
class _EntryBandCounters:
    entry_holes: int = 0
    dsz_ok: int = 0
    dsz_tot: int = 0
    green_ok: int = 0
    green_lie_known: int = 0
    putts_sum: int = 0
    putts_n: int = 0
    before_putts_sum: int = 0
    before_putts_n: int = 0
    inside_sum: int = 0
    inside_n: int = 0


def _dsz_entry_band_rows(
    hole_rows: list[dict[str, Any]],
    *,
    geometry_only: bool,
    overall_dsz_pct: float | None,
    overall_green_pct: float | None = None,
    overall_mean_putts: float | None = None,
) -> list[dict[str, Any]]:
    counters: dict[str, _EntryBandCounters] = {bid: _EntryBandCounters() for bid, _, _, _ in DSZ_ENTRY_BANDS}

    for r in hole_rows:
        if not r.get("entered_scoring_zone"):
            continue
        tier = r.get("first_zone_method")
        if geometry_only and tier not in GEOMETRY_DISTANCE_TIERS:
            continue
        y = r.get("first_zone_yards")
        if y is None:
            continue
        try:
            yf = float(y)
        except (TypeError, ValueError):
            continue
        bid = _dsz_entry_band_id(yf)
        if bid is None:
            continue
        c = counters[bid]
        c.entry_holes += 1
        inside = r.get("strokes_inside_zone")
        if inside is not None:
            c.inside_sum += int(inside)
            c.inside_n += 1
        if r.get("dsz_entry_strokes") is not None:
            c.dsz_tot += 1
            if r.get("dsz_success_entry_band"):
                c.dsz_ok += 1
        sbp = r.get("scorecard_shots_before_putts")
        if sbp is not None:
            try:
                c.before_putts_sum += int(sbp)
                c.before_putts_n += 1
            except (TypeError, ValueError):
                pass
        on_green = r.get("reached_green_in_zone")
        if on_green is None:
            on_green = r.get("entry_on_green")
        if on_green is not None:
            c.green_lie_known += 1
            if on_green:
                c.green_ok += 1
        pt = r.get("hole_putts")
        if pt is not None:
            try:
                c.putts_sum += int(pt)
                c.putts_n += 1
            except (TypeError, ValueError):
                pass

    rows: list[dict[str, Any]] = []
    for bid, label, ymin, ymax in DSZ_ENTRY_BANDS:
        c = counters[bid]
        if not c.entry_holes:
            continue
        pct_dsz = (100.0 * c.dsz_ok / c.dsz_tot) if c.dsz_tot else None
        pct_green = (100.0 * c.green_ok / c.green_lie_known) if c.green_lie_known else None
        mean_putts = (c.putts_sum / c.putts_n) if c.putts_n else None
        mean_shots_before_putts = (
            (c.before_putts_sum / c.before_putts_n) if c.before_putts_n else None
        )
        mean_strokes_inside = (c.inside_sum / c.inside_n) if c.inside_n else None
        rows.append(
            {
                "band_id": bid,
                "label": label,
                "min_yards": ymin,
                "max_yards": ymax,
                "close_entry_band": bid == "0_30",
                "zone_entry_holes": c.entry_holes,
                "dsz_eval_holes": c.dsz_tot,
                "dsz_success_holes": c.dsz_ok,
                "pct_success": pct_dsz,
                "mean_strokes_inside_zone": round(mean_strokes_inside, 2)
                if mean_strokes_inside is not None
                else None,
                "mean_shots_before_putts": round(mean_shots_before_putts, 2)
                if mean_shots_before_putts is not None
                else None,
                "shots_before_putts_holes": c.before_putts_n,
                "diff_vs_avg_pct": _rel_diff_pct(pct_dsz, overall_dsz_pct)
                if pct_dsz is not None and overall_dsz_pct is not None
                else None,
                "green_hit_holes": c.green_ok,
                "green_lie_known_holes": c.green_lie_known,
                "pct_green": pct_green,
                "diff_green_vs_avg_pct": _rel_diff_pct(pct_green, overall_green_pct)
                if pct_green is not None and overall_green_pct is not None
                else None,
                "putts_holes": c.putts_n,
                "mean_putts": round(mean_putts, 2) if mean_putts is not None else None,
                "diff_putts_vs_avg_pct": _rel_diff_pct(mean_putts, overall_mean_putts)
                if mean_putts is not None and overall_mean_putts is not None
                else None,
            }
        )
    return rows


def _overall_green_and_putts(
    hole_rows: list[dict[str, Any]],
    *,
    geometry_only: bool,
) -> tuple[float | None, float | None]:
    green_ok = green_known = putts_sum = putts_n = 0
    for r in hole_rows:
        if not r.get("entered_scoring_zone"):
            continue
        if geometry_only and r.get("first_zone_method") not in GEOMETRY_DISTANCE_TIERS:
            continue
        if r.get("first_zone_yards") is None:
            continue
        og = r.get("reached_green_in_zone")
        if og is None:
            og = r.get("entry_on_green")
        if og is not None:
            green_known += 1
            if og:
                green_ok += 1
        pt = r.get("hole_putts")
        if pt is not None:
            putts_sum += int(pt)
            putts_n += 1
    pct_green = (100.0 * green_ok / green_known) if green_known else None
    mean_putts = (putts_sum / putts_n) if putts_n else None
    return pct_green, mean_putts


def _dsz_entry_distance_block(hole_rows: list[dict[str, Any]], *, overall_dsz_pct: float | None) -> dict[str, Any]:
    in_zone = [r for r in hole_rows if r.get("entered_scoring_zone")]
    with_yards = [r for r in in_zone if r.get("first_zone_yards") is not None]
    geometry_n = sum(1 for r in with_yards if r.get("first_zone_method") in GEOMETRY_DISTANCE_TIERS)
    heuristic_n = len(with_yards) - geometry_n
    yards_vals = [float(r["first_zone_yards"]) for r in with_yards]
    mean_y = sum(yards_vals) / len(yards_vals) if yards_vals else None
    inside_vals = [
        int(r["strokes_inside_zone"])
        for r in with_yards
        if r.get("strokes_inside_zone") is not None
    ]
    mean_inside = sum(inside_vals) / len(inside_vals) if inside_vals else None

    green_all, putts_all = _overall_green_and_putts(hole_rows, geometry_only=False)
    green_geom, putts_geom = _overall_green_and_putts(hole_rows, geometry_only=True)
    bands_all = _dsz_entry_band_rows(
        hole_rows,
        geometry_only=False,
        overall_dsz_pct=overall_dsz_pct,
        overall_green_pct=green_all,
        overall_mean_putts=putts_all,
    )
    bands_geometry = _dsz_entry_band_rows(
        hole_rows,
        geometry_only=True,
        overall_dsz_pct=overall_dsz_pct,
        overall_green_pct=green_geom,
        overall_mean_putts=putts_geom,
    )
    return {
        "label": "DSZ by yards to pin when entering the scoring zone (≤100 yd)",
        "mean_entry_yards": round(mean_y, 1) if mean_y is not None else None,
        "mean_strokes_inside_zone": round(mean_inside, 2) if mean_inside is not None else None,
        "holes_with_inside_zone_strokes": len(inside_vals),
        "overall_pct_green_geometry": round(green_geom, 1) if green_geom is not None else None,
        "overall_mean_putts_geometry": round(putts_geom, 2) if putts_geom is not None else None,
        "holes_in_zone": len(in_zone),
        "holes_with_entry_yards": len(with_yards),
        "holes_geometry_distance": geometry_n,
        "holes_heuristic_distance": heuristic_n,
        "band_step_yards": DSZ_ENTRY_BAND_STEP_YARDS,
        "bands": bands_all,
        "bands_geometry": bands_geometry,
        "note": ENTRY_DISTANCE_NOTE,
        "data_quality": {
            "shots_before_putts": "scorecard",
            "mean_putts": "scorecard",
            "pct_green": "shot_trace_lie",
            "pct_success": "scorecard_minus_traced_outside",
        },
    }


def esz_dsz_scoring_proxy_blocks(hole_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline-style ESZ / DSZ blocks (overall + par 3/4/5) for Strategy overview chips."""

    if not hole_rows:
        return {}

    esz_eval = len(hole_rows)
    esz_ok = sum(1 for r in hole_rows if r.get("esz_success"))
    dsz_zone = sum(1 for r in hole_rows if _hole_dsz_evaluable(r))
    dsz_ok = sum(1 for r in hole_rows if _hole_dsz_evaluable(r) and r.get("dsz_success"))

    esz_by_par: dict[int, tuple[int, int]] = {p: (0, 0) for p in PAR_BUCKETS_ESZ_DSZ}
    dsz_by_par: dict[int, tuple[int, int]] = {p: (0, 0) for p in PAR_BUCKETS_ESZ_DSZ}

    for r in hole_rows:
        par = r.get("par")
        if par not in PAR_BUCKETS_ESZ_DSZ:
            continue
        eo, ee = esz_by_par[par]
        esz_by_par[par] = (eo + (1 if r.get("esz_success") else 0), ee + 1)
        if _hole_dsz_evaluable(r):
            do, dz = dsz_by_par[par]
            dsz_by_par[par] = (do + (1 if r.get("dsz_success") else 0), dz + 1)

    esz_pct = (100.0 * esz_ok / esz_eval) if esz_eval else None
    dsz_pct = (100.0 * dsz_ok / dsz_zone) if dsz_zone else None

    return {
        "proxy_esz": {
            "title": PROXY_ESZ["title"],
            "label": PROXY_ESZ["label"],
            "direction": "higher_is_better",
            "metric": "pct_success",
            "holes_evaluated": esz_eval,
            "success_holes": esz_ok,
            "pct_success": esz_pct,
            "by_par": _esz_dsz_by_par_splits(esz_by_par, avg_value=esz_pct),
        },
        "proxy_dsz": {
            "title": PROXY_DSZ["title"],
            "label": PROXY_DSZ["label"],
            "direction": "higher_is_better",
            "metric": "pct_success",
            "zone_entry_holes": dsz_zone,
            "success_holes": dsz_ok,
            "pct_success": dsz_pct,
            "by_par": _esz_dsz_by_par_splits(dsz_by_par, avg_value=dsz_pct),
            "entry_distance": _dsz_entry_distance_block(hole_rows, overall_dsz_pct=dsz_pct),
        },
    }


def compute_esz_dsz_from_shot_details(
    data: dict[str, Any],
    *,
    calendar_year: int | None = None,
    scorecard_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    ESZ: first shot whose **end** lies within ``SCORING_ZONE_YARDS`` of the pin occurs on or before
    stroke ``par − 2`` (GIR-style regulation: e.g. par 4 by end of stroke 2).

    DSZ: **≤ 3** strokes inside the scoring zone: scorecard gross ``S`` minus traced shots before the
    first ≤100 yd end. Holes without ``S`` are excluded from DSZ aggregates.

    Distance-to-pin per shot (first that succeeds): **geometry** (``endLoc`` vs ``pin``),
    else **remainingDistance** by ``shot.id``, else **startingDistanceToHole − shot meters**,
    else **cumulative heuristic** (scorecard hole length when present, else par template).
    """

    hole_rows, dbg, n_blocks = build_esz_dsz_hole_rows(
        data, calendar_year=calendar_year, scorecard_ids=scorecard_ids
    )
    if not isinstance(data.get("shotDetails"), list):
        return {
            "holes_evaluated": 0,
            "shot_detail_blocks": 0,
            "note": "No shotDetails array in export.",
            "availability_hint": "Garmin export has no top-level shotDetails list.",
            "diagnostics": {},
            "by_round": [],
            "data_model": ESZ_DSZ_DATA_MODEL,
        }

    holes_used = len(hole_rows)
    esz_ok = sum(1 for r in hole_rows if r["esz_success"])
    esz_fail = holes_used - esz_ok
    dsz_eligible = sum(1 for r in hole_rows if _hole_dsz_evaluable(r))
    dsz_ok = sum(1 for r in hole_rows if _hole_dsz_evaluable(r) and r.get("dsz_success"))
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

    payload: dict[str, Any] = {
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
            "DSZ uses scorecard gross minus traced shots before 100 yd (see data_model). "
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
    if holes_used > 0:
        payload.update(esz_dsz_scoring_proxy_blocks(hole_rows))
    return payload
