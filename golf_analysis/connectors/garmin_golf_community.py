from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golf_analysis.connectors.base import Connector
from golf_analysis.models import GolfRound, IngestPayload, RoundHole
from golf_analysis.serialization import json_safe


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(round(float(val)))
    except (TypeError, ValueError):
        return None


def _as_bool(val: Any) -> bool | None:
    if val is True or val is False:
        return val
    if isinstance(val, str):
        lo = val.lower()
        if lo in ("true", "1", "yes", "hit"):
            return True
        if lo in ("false", "0", "no", "miss"):
            return False
    return None


def _extract_scorecard(card_details: dict[str, Any]) -> dict[str, Any] | None:
    details = card_details.get("scorecardDetails")
    if not isinstance(details, list):
        return None
    for el in details:
        if not isinstance(el, dict):
            continue
        sc = el.get("scorecard")
        if isinstance(sc, dict):
            return sc
    return None


def _as_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _yards_to_meters(yards: Any) -> float | None:
    yf = _as_float(yards)
    return yf * 0.9144 if yf is not None else None


def _hole_from_golf_api(h: dict[str, Any]) -> RoundHole:
    hn = _as_int(h.get("number") if h.get("number") is not None else h.get("holeNumber"))
    return RoundHole(
        hole_number=hn,
        par=_as_int(h.get("par")),
        stroke_index=_as_int(h.get("strokeIndex") or h.get("handicapStrokeIndex")),
        score=_as_int(h.get("score") if h.get("score") is not None else h.get("strokes")),
        putts=_as_int(h.get("putts")),
        fairway_hit=_as_bool(h.get("fairwayHit") or h.get("fairway_hit")),
        green_in_regulation=_as_bool(h.get("greenInRegulation") or h.get("green_in_regulation")),
        penalty_strokes=_as_int(h.get("penaltyStrokes") or h.get("penalties")),
        distance_meters=_yards_to_meters(h.get("yardage") or h.get("yardageYards")),
        duration_s=None,
        extra={k: json_safe(v) for k, v in h.items() if v is not None},
    )


def parse_garmin_golf_export(data: dict[str, Any]) -> IngestPayload:
    """
    Parse ``garmin_golf``-style export dict (summary, details, shotDetails, clubs, …)
    into ``GolfRound`` rows.
    """

    warnings: list[str] = list(data.get("warnings") or []) if isinstance(data.get("warnings"), list) else []
    details = data.get("details")
    if not isinstance(details, list):
        return IngestPayload(warnings=warnings + ["Missing or invalid 'details' array."])

    shot_index: dict[str, list[dict[str, Any]]] = {}
    raw_shots = data.get("shotDetails")
    if isinstance(raw_shots, list):
        for row in raw_shots:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("scorecardId") or "")
            if sid:
                shot_index.setdefault(sid, []).append(row)

    rounds: list[GolfRound] = []
    for entry in details:
        if not isinstance(entry, dict):
            continue
        sc = _extract_scorecard(entry)
        if not sc:
            warnings.append("Skipped a details entry with no scorecard payload.")
            continue

        sc_id = sc.get("id")
        sc_id_str = str(sc_id) if sc_id is not None else ""

        course = sc.get("courseName") or sc.get("course_name")
        title = course or str(sc.get("formattedStartTime") or sc.get("startTime") or "golf_round")

        holes_raw = sc.get("holes")
        holes: list[RoundHole] = []
        if isinstance(holes_raw, list):
            for h in holes_raw:
                if isinstance(h, dict):
                    holes.append(_hole_from_golf_api(h))

        total_strokes = _as_int(sc.get("totalScore") or sc.get("total_strokes"))
        if total_strokes is None and holes:
            scores = [h.score for h in holes if h.score is not None]
            if scores:
                total_strokes = sum(scores)

        total_putts = _as_int(sc.get("totalPutts"))
        if total_putts is None and holes:
            putts = [h.putts for h in holes if h.putts is not None]
            if putts:
                total_putts = sum(putts)

        score_vs_par = _as_int(sc.get("scoreRelativeToPar") or sc.get("relativeScore"))

        extra: dict[str, Any] = {
            "source": "garmin_golf_community",
            "scorecard_id": sc_id,
            "garmin_golf_shot_details": json_safe(shot_index.get(sc_id_str, [])),
            "clubs_summary": json_safe(data.get("clubs")) if data.get("clubs") else None,
            "scorecard": json_safe(sc),
        }

        rounds.append(
            GolfRound(
                title=str(title)[:500],
                course_name=str(course)[:500] if course else None,
                started_at=_parse_dt(sc.get("startTime")),
                ended_at=_parse_dt(sc.get("endTime")),
                holes=holes,
                track=[],
                total_strokes=total_strokes,
                total_putts=total_putts,
                score_relative_to_par=score_vs_par,
                extra=extra,
            )
        )

    if not rounds:
        warnings.append("No scorecard rounds parsed from export.")
    return IngestPayload(rounds=rounds, warnings=warnings)


def _looks_like_garmin_golf_export(data: dict[str, Any]) -> bool:
    sm = data.get("summary")
    if not isinstance(sm, dict):
        return False
    if not isinstance(sm.get("scorecardSummaries"), list):
        return False
    return isinstance(data.get("details"), list)


class GarminGolfCommunityConnector(Connector):
    """``garmin_golf``-style JSON (scorecard summary + details + optional shot rows)."""

    id = "garmin_golf_community"

    def can_handle(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        return isinstance(raw, dict) and _looks_like_garmin_golf_export(raw)

    def ingest(self, path: Path) -> IngestPayload:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return IngestPayload(warnings=[f"Expected JSON object in {path}"])
        if not _looks_like_garmin_golf_export(data):
            return IngestPayload(warnings=[f"JSON in {path} is not a Garmin golf community export."])
        return parse_garmin_golf_export(data)
