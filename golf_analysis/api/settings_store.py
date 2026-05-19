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
}


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
            merged[k] = v
    return merged


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    for k, v in updates.items():
        if k in _DEFAULTS:
            current[k] = v
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
