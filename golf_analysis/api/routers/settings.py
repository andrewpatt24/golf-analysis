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


@router.get("/settings")
def get_settings() -> dict[str, object]:
    return load_settings()


@router.put("/settings")
def put_settings(body: SettingsUpdate) -> dict[str, object]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return save_settings(updates)
