from __future__ import annotations

import json
from datetime import date, datetime, time
from enum import Enum
from typing import Any


def json_safe(obj: Any) -> Any:
    """Recursively convert values for JSON / SQLite TEXT columns."""

    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return str(obj)


def dumps_json(obj: Any) -> str:
    return json.dumps(json_safe(obj), separators=(",", ":"), ensure_ascii=False)
