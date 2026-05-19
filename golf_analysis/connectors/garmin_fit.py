from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fitparse import FitFile
from fitparse.utils import FitParseError

from golf_analysis.connectors.base import Connector
from golf_analysis.models import GolfRound, IngestPayload, RoundHole, RoundTrackPoint
from golf_analysis.serialization import json_safe


def _fit_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return None


def _semicircles_to_deg(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw) * (180.0 / 2**31)
    except (TypeError, ValueError):
        return None


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sport_name(sport: Any) -> str | None:
    if sport is None:
        return None
    if isinstance(sport, str):
        return sport.lower()
    return str(sport).lower()


def _lap_dict_safe(lap: dict[str, Any]) -> dict[str, Any]:
    return {k: json_safe(v) for k, v in lap.items() if v is not None}


def _infer_hole_number(lap: dict[str, Any], lap_index: int) -> int:
    """Prefer explicit hole fields; otherwise lap order (1-based)."""

    for key, val in lap.items():
        lk = str(key).lower()
        if ("hole" in lk and "num" in lk) or lk in ("hole_number", "hole"):
            n = _as_int(val)
            if n is not None and 1 <= n <= 18:
                return n
    idx = _as_int(lap.get("message_index"))
    if idx is not None and 1 <= idx <= 18:
        return idx
    return lap_index + 1


def _infer_hole_score(lap: dict[str, Any], sport_is_golf: bool) -> int | None:
    """
    For golf, per-hole stroke counts often appear as `total_cycles` on each lap.
    Only trust this when sport is golf and the value looks like a hole score.
    """

    if not sport_is_golf:
        return None
    n = _as_int(lap.get("total_cycles"))
    if n is not None and 1 <= n <= 20:
        return n
    return None


def _infer_putts(lap: dict[str, Any]) -> int | None:
    """Garmin sometimes encodes putts in developer fields; standard lap fields vary by model."""

    for key in lap:
        lk = str(key).lower()
        if "putt" in lk:
            n = _as_int(lap.get(key))
            if n is not None and 0 <= n <= 15:
                return n
    return None


def _infer_par(lap: dict[str, Any]) -> int | None:
    for key in lap:
        lk = str(key).lower()
        if lk == "par" or lk.endswith("_par"):
            n = _as_int(lap.get(key))
            if n is not None and 3 <= n <= 6:
                return n
    return None


def laps_to_holes(laps: list[dict[str, Any]], sport_is_golf: bool) -> list[RoundHole]:
    holes: list[RoundHole] = []
    for i, lap in enumerate(laps):
        hole_num = _infer_hole_number(lap, i)
        score = _infer_hole_score(lap, sport_is_golf)
        putts = _infer_putts(lap)
        par = _infer_par(lap)
        holes.append(
            RoundHole(
                hole_number=hole_num,
                par=par,
                stroke_index=None,
                score=score,
                putts=putts,
                fairway_hit=None,
                green_in_regulation=None,
                penalty_strokes=None,
                distance_meters=_as_float(lap.get("total_distance")),
                duration_s=_as_float(lap.get("total_timer_time") or lap.get("total_elapsed_time")),
                extra=_lap_dict_safe(lap),
            )
        )
    return holes


def records_to_track(records: list[dict[str, Any]], max_points: int = 25_000) -> tuple[list[RoundTrackPoint], bool]:
    out: list[RoundTrackPoint] = []
    truncated = False
    for r in records:
        if len(out) >= max_points:
            truncated = True
            break
        lat = _semicircles_to_deg(r.get("position_lat"))
        lon = _semicircles_to_deg(r.get("position_long"))
        if lat is None and lon is None and r.get("timestamp") is None:
            continue
        out.append(
            RoundTrackPoint(
                time=_fit_ts(r.get("timestamp")),
                lat=lat,
                lon=lon,
                altitude_m=_as_float(r.get("altitude")),
                distance_m=_as_float(r.get("distance")),
                heart_rate=_as_int(r.get("heart_rate")),
                extra={k: json_safe(v) for k, v in r.items() if k not in ("position_lat", "position_long")},
            )
        )
    return out, truncated


def parse_fit_bytes(data: bytes, logical_name: str) -> IngestPayload:
    """Parse a single .fit payload; used by the connector and tests."""

    try:
        fit = FitFile(io.BytesIO(data))
        warnings: list[str] = []
        sport: Any = None
        sub_sport: Any = None
        session_meta: dict[str, Any] = {}
        laps: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []

        for msg in fit.messages:
            if msg.name == "file_id":
                continue
            if msg.name == "sport":
                vals = msg.get_values()
                if vals:
                    sport = vals.get("sport") or sport
                    sub_sport = vals.get("sub_sport") or sub_sport
            elif msg.name == "session":
                session_meta.update(msg.get_values() or {})
            elif msg.name == "lap":
                laps.append(msg.get_values() or {})
            elif msg.name == "record":
                records.append(msg.get_values() or {})

        sport_name = _sport_name(sport)
        sport_is_golf = sport_name == "golf"
        if sport is not None and not sport_is_golf:
            warnings.append(
                f"FIT sport is {sport!r}, not golf — hole strokes inferred only where "
                f"fields are unambiguous; prefer golf activity exports."
            )

        holes = laps_to_holes(laps, sport_is_golf=sport_is_golf)
        track, truncated = records_to_track(records)
        if truncated:
            warnings.append(f"Track truncated to {len(track)} points for storage.")

        started = _fit_ts(session_meta.get("start_time"))
        ended = _fit_ts(session_meta.get("timestamp"))

        total_timer = session_meta.get("total_timer_time")
        total_dist = session_meta.get("total_distance")

        session_total_cycles = _as_int(session_meta.get("total_cycles"))
        total_strokes = session_total_cycles if sport_is_golf and session_total_cycles else None
        if total_strokes is not None and not (18 <= total_strokes <= 200):
            total_strokes = None

        hole_scores = [h.score for h in holes if h.score is not None]
        if hole_scores and len(hole_scores) >= 9:
            summed = sum(hole_scores)
            if total_strokes is None or abs(total_strokes - summed) > 4:
                total_strokes = summed

        total_putts = None
        hole_putts = [h.putts for h in holes if h.putts is not None]
        if hole_putts and len(hole_putts) >= 9:
            total_putts = sum(hole_putts)

        rnd = GolfRound(
            title=logical_name,
            course_name=session_meta.get("name") or session_meta.get("sport_profile_name"),
            started_at=started,
            ended_at=ended,
            holes=holes,
            track=track,
            total_strokes=total_strokes,
            total_putts=total_putts,
            score_relative_to_par=None,
            extra={
                "source_name": logical_name,
                "sport": str(sport) if sport is not None else None,
                "sub_sport": str(sub_sport) if sub_sport is not None else None,
                "total_timer_time_s": float(total_timer) if total_timer is not None else None,
                "total_distance_m": float(total_dist) if total_dist is not None else None,
                "session_fields": json_safe({k: v for k, v in session_meta.items() if v is not None}),
            },
        )
        return IngestPayload(rounds=[rnd], warnings=warnings)
    except FitParseError as e:
        return IngestPayload(warnings=[f"Could not read FIT file {logical_name!r}: {e}"])


class GarminFitConnector(Connector):
    """Golf activities exported from Garmin Connect as `.fit` (often inside a `.zip`)."""

    id = "garmin_fit"

    def can_handle(self, path: Path) -> bool:
        suf = path.suffix.lower()
        return suf in (".fit", ".zip")

    def ingest(self, path: Path) -> IngestPayload:
        payloads: list[IngestPayload] = []
        for name, data in iter_fit_bytes_from_path(path):
            payloads.append(parse_fit_bytes(data, logical_name=Path(name).stem))
        if not payloads:
            return IngestPayload(warnings=[f"No .fit payload found in {path}"])
        return _merge_payloads(payloads, [])


def _merge_payloads(payloads: list[IngestPayload], warnings: list[str]) -> IngestPayload:
    rs: list = []
    rr: list = []
    w = list(warnings)
    for p in payloads:
        rs.extend(p.range_sessions)
        rr.extend(p.rounds)
        w.extend(p.warnings)
    return IngestPayload(range_sessions=rs, rounds=rr, warnings=w)


def _iter_fit_payloads(path: Path) -> list[tuple[str, bytes]]:
    suf = path.suffix.lower()
    if suf == ".fit":
        return [(path.name, path.read_bytes())]
    if suf == ".zip":
        out: list[tuple[str, bytes]] = []
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".fit") and not name.endswith("/"):
                    out.append((Path(name).name, zf.read(name)))
        return out
    return []


def iter_fit_bytes_from_path(path: Path) -> list[tuple[str, bytes]]:
    """Return ``(logical_name, raw_bytes)`` for each ``.fit`` inside ``path`` (``.fit`` or ``.zip``)."""

    return _iter_fit_payloads(path)
