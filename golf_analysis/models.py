from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RangeShot(BaseModel):
    """One launch-monitor shot, normalized for analysis."""

    shot_index: int | None = None
    club: str | None = None
    ball_speed_mph: float | None = None
    club_speed_mph: float | None = None
    smash_factor: float | None = None
    launch_angle_deg: float | None = None
    launch_direction_deg: float | None = None
    spin_rpm: float | None = None
    spin_axis_deg: float | None = None
    carry_yards: float | None = None
    total_yards: float | None = None
    apex_yards: float | None = None
    descent_angle_deg: float | None = None
    offline_yards: float | None = None
    attack_angle_deg: float | None = None
    club_path_deg: float | None = None
    face_to_path_deg: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RangeSession(BaseModel):
    """A range / simulator session (e.g. MLM2Pro)."""

    title: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    venue: str | None = None
    notes: str | None = None
    practice_kind: str | None = Field(
        default=None,
        description="Optional session label (e.g. from future connectors); Rapsodo CSV uses list_source_kind only.",
    )
    list_source_kind: str | None = Field(
        default=None,
        description="Rapsodo list endpoint bucket (e.g. practice, combine, courses) from rapsodo_session_list.json.",
    )
    shots: list[RangeShot] = Field(default_factory=list)
    raw_headers: list[str] | None = None


class RoundHole(BaseModel):
    hole_number: int | None = None
    par: int | None = None
    stroke_index: int | None = None
    score: int | None = None
    putts: int | None = None
    fairway_hit: bool | None = None
    green_in_regulation: bool | None = None
    penalty_strokes: int | None = None
    distance_meters: float | None = None
    duration_s: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RoundTrackPoint(BaseModel):
    """Sparse GPS / track sample if present in source file."""

    time: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    altitude_m: float | None = None
    distance_m: float | None = None
    heart_rate: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class GolfRound(BaseModel):
    """An on-course round (e.g. Garmin)."""

    title: str | None = None
    course_name: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    holes: list[RoundHole] = Field(default_factory=list)
    track: list[RoundTrackPoint] = Field(default_factory=list)
    total_strokes: int | None = None
    total_putts: int | None = None
    score_relative_to_par: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class IngestPayload(BaseModel):
    """What a connector produced from one file."""

    range_sessions: list[RangeSession] = Field(default_factory=list)
    rounds: list[GolfRound] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
