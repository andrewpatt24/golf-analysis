from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from golf_analysis.api.settings_store import load_settings, save_settings

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    maxRounds: int | None = Field(None, ge=1, le=200)
    maxPracticeSessions: int | None = Field(None, ge=1, le=200)
    maxAgeDays: int | None = Field(None, ge=1, le=3650)
    calendarYear: int | None = Field(None, ge=2000, le=2100)
    trainingBlockSessions: int | None = Field(None, ge=2, le=12)
    troubleMinAvgStablefordPoints: float | None = Field(None, ge=0, le=4)
    stablefordColorGreenMin: float | None = Field(None, ge=0, le=4)
    stablefordColorYellowMin: float | None = Field(None, ge=0, le=4)
    avgPuttsHighThreshold: float | None = Field(None, ge=0, le=6)
    trainingDispersionRatioFlag: float | None = Field(
        None, ge=0.01, le=1.0, description="FLAG when mean |offline|/mean carry exceeds this (default 0.1)"
    )
    excludedTrainingClubs: list[str] | None = None


@router.get("/settings")
def get_settings() -> dict[str, object]:
    return load_settings()


@router.put("/settings")
def put_settings(body: SettingsUpdate) -> dict[str, object]:
    return save_settings(body.model_dump(exclude_none=True))
