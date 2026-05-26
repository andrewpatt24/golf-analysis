"""User-editable on-course crib sheet (swing thoughts, chip notes, etc.)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

_DEFAULT_PITCH_ROWS: list[dict[str, str]] = [
    {"dist": "90–100y", "club": "AW", "stance": "2-Head", "gripSwing": "Full Choke / 10-2"},
    {"dist": "75–85y", "club": "54°", "stance": "2-Head", "gripSwing": "Half Choke / 10-2"},
    {"dist": "65–75y", "club": "54°", "stance": "1-Head", "gripSwing": "Half Choke / 10-2"},
    {"dist": "50–60y", "club": "54°", "stance": "1-Head", "gripSwing": "Half Choke / 9-3"},
    {"dist": "40–50y", "club": "54°", "stance": "1-Head", "gripSwing": "Full Choke / 9-3"},
    {"dist": "30–40y", "club": "54°", "stance": "1-Head", "gripSwing": "Full Choke / 8-4"},
    {"dist": "<30y", "club": "54°", "stance": "1-Head", "gripSwing": "Soft Hands / 7-5"},
]

_DEFAULTS: dict[str, Any] = {
    "swingCue": "TEMPO",
    "swingThoughts": (
        "Setup: Grip, distance vs knee, shoulder-width stance. Engage core and glutes.\n"
        "Backswing: Thumbs to the Sky — stop hands at chest height.\n"
        "Downswing: TEMPO — lag arms, force through the ball not at the top. Clear hips, no sway.\n"
        "Finish: Chest to the Sky — rotate hard through the ball.\n"
        "Feel: Logo to Target — flat lead wrist at impact."
    ),
    "chipNotes": (
        "Can I putt it? Can I putt it with loft?\n"
        "Soft Hands | Stick the Finish\n\n"
        "Release 1 — Chip & Run\n"
        "Setup: 1-Head stance | flat lead wrist | shaft lean to front hip\n"
        "Execution: Stiff-arm V | no hinge | hands/chest as one\n"
        "Finish: Grip points at front hip\n\n"
        "Release 2 — Soft Landing\n"
        "Setup: 2-Head stance (flared) | lower hands | 2/10 grip\n"
        "Execution: Gravity drop | toe up backswing | chest rotation\n"
        "Finish: Club face looks at lead shoulder"
    ),
    "fixNotes": (
        "Pulling / tired? Back to Target downswing. Clear hips. Don't be Army.\n"
        "Fat / thin? Pivot line check. Stack lead shoulder over lead foot.\n"
        "Slicing? Logo to Target (flatten wrist)."
    ),
    "windNotes": (
        "Into: Club up +2 | choke down | swing 70%.\n"
        "With: Club down -1 | land short (Release 1).\n"
        "Side: Aim at the upwind edge — let it drift to centre.\n"
        "Army warning: wind hates arm swings. If pulling left, rotate the buckle."
    ),
    "puttingRoutine": (
        "Read: Low side, uphill — left or right higher?\n"
        "Align: Dominant eye over the line; close other eye; shaft check.\n"
        "Visualize: 3–4 sec at real speed — ball on track into the hole.\n"
        "Rehearse: Stroke parallel to line (not at hole); hold finish, see it in.\n"
        "Putt: One cue — rock torso, stick the finish."
    ),
    "pitchRows": deepcopy(_DEFAULT_PITCH_ROWS),
}


def playbook_path() -> Path:
    raw = os.environ.get("GOLF_ON_COURSE_PLAYBOOK", "data/on_course_playbook.json")
    return Path(raw).expanduser().resolve()


def load_playbook() -> dict[str, Any]:
    path = playbook_path()
    if not path.is_file():
        return deepcopy(_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(_DEFAULTS)
    if not isinstance(data, dict):
        return deepcopy(_DEFAULTS)
    merged = deepcopy(_DEFAULTS)
    for key in _DEFAULTS:
        if key not in data:
            continue
        if key == "pitchRows":
            rows = data[key]
            if isinstance(rows, list) and rows:
                merged[key] = [_normalize_pitch_row(r) for r in rows if isinstance(r, dict)]
            continue
        merged[key] = str(data[key]) if data[key] is not None else merged[key]
    return merged


def _normalize_pitch_row(row: dict[str, Any]) -> dict[str, str]:
    return {
        "dist": str(row.get("dist", "")).strip(),
        "club": str(row.get("club", "")).strip(),
        "stance": str(row.get("stance", "")).strip(),
        "gripSwing": str(row.get("gripSwing", "")).strip(),
    }


def save_playbook(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_playbook()
    for key in _DEFAULTS:
        if key not in updates:
            continue
        val = updates[key]
        if key == "pitchRows":
            if isinstance(val, list):
                current[key] = [_normalize_pitch_row(r) for r in val if isinstance(r, dict)]
            continue
        if val is not None:
            current[key] = str(val)
    path = playbook_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
