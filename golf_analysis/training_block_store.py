"""Persist active training block and session completion state."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def training_block_path() -> Path:
    raw = os.environ.get("GOLF_TRAINING_BLOCK", "data/training_block.json")
    return Path(raw).expanduser().resolve()


def _empty_doc() -> dict[str, Any]:
    return {"active_block": None}


def load_training_block_doc() -> dict[str, Any]:
    path = training_block_path()
    if not path.is_file():
        return _empty_doc()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_doc()
    if not isinstance(data, dict):
        return _empty_doc()
    block = data.get("active_block")
    return {"active_block": block if isinstance(block, dict) else None}


def save_training_block_doc(doc: dict[str, Any]) -> dict[str, Any]:
    path = training_block_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def get_active_block() -> dict[str, Any] | None:
    block = load_training_block_doc().get("active_block")
    return dict(block) if isinstance(block, dict) else None


def save_active_block(block: dict[str, Any]) -> dict[str, Any]:
    doc = load_training_block_doc()
    doc["active_block"] = block
    save_training_block_doc(doc)
    return block


def clear_active_block() -> None:
    save_training_block_doc(_empty_doc())


def block_all_complete(block: dict[str, Any]) -> bool:
    sessions = block.get("sessions") or []
    if not sessions:
        return False
    return all(bool(s.get("completed_at")) for s in sessions if isinstance(s, dict))


def mark_session_complete(
    block: dict[str, Any],
    session_index: int,
    *,
    linked_session_id: str | None = None,
) -> dict[str, Any]:
    sessions = list(block.get("sessions") or [])
    for row in sessions:
        if not isinstance(row, dict):
            continue
        if int(row.get("index", -1)) == session_index:
            row["completed_at"] = datetime.now(timezone.utc).isoformat()
            if linked_session_id:
                row["linked_session_id"] = linked_session_id
            break
    else:
        raise ValueError(f"Unknown session index: {session_index}")
    out = dict(block)
    out["sessions"] = sessions
    out["all_complete"] = block_all_complete(out)
    return out


def new_block_id() -> str:
    return uuid4().hex[:12]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
