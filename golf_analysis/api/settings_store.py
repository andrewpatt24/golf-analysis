from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "maxRounds": 10,
    "maxPracticeSessions": 10,
    "maxAgeDays": 365,
    "calendarYear": 2026,
    "trainingBlockSessions": 4,
    "troubleMinAvgStablefordPoints": 1.0,
    "stablefordColorGreenMin": 2.0,
    "stablefordColorYellowMin": 1.0,
    "avgPuttsHighThreshold": 2.25,
    "trainingDispersionRatioFlag": 0.1,
    "excludedTrainingClubs": [],
}

_LIST_SETTING_KEYS = frozenset({"excludedTrainingClubs"})


def settings_path() -> Path:
    raw = os.environ.get("GOLF_DASHBOARD_SETTINGS", "data/dashboard_settings.json")
    return Path(raw).expanduser().resolve()


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.is_file():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULTS)
    if not isinstance(data, dict):
        return dict(_DEFAULTS)
    merged = dict(_DEFAULTS)
    for k, v in data.items():
        if k in _DEFAULTS:
            merged[k] = _normalize_setting_value(k, v)
    return merged


def _normalize_setting_value(key: str, value: Any) -> Any:
    if key in _LIST_SETTING_KEYS:
        if not isinstance(value, list):
            return []
        return sorted({str(x).strip().lower() for x in value if str(x).strip()})
    return value


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    for k, v in updates.items():
        if k in _DEFAULTS:
            current[k] = _normalize_setting_value(k, v)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
