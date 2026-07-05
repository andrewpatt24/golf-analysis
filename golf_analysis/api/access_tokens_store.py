"""Guest dashboard access tokens (revocable; synced via GCS on Cloud Run)."""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def access_tokens_path() -> Path:
    raw = os.environ.get("GOLF_ACCESS_TOKENS_FILE", "data/access_tokens.json")
    return Path(raw).expanduser().resolve()


def _empty_doc() -> dict[str, Any]:
    return {"guests": []}


def load_access_tokens_doc() -> dict[str, Any]:
    path = access_tokens_path()
    if not path.is_file():
        return _empty_doc()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_doc()
    if not isinstance(data, dict):
        return _empty_doc()
    guests = data.get("guests")
    if not isinstance(guests, list):
        data["guests"] = []
    return data


def save_access_tokens_doc(doc: dict[str, Any]) -> Path:
    path = access_tokens_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def guest_token_values() -> frozenset[str]:
    doc = load_access_tokens_doc()
    out: set[str] = set()
    for row in doc.get("guests") or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("token")
        if raw and str(raw).strip():
            out.add(str(raw).strip())
    return frozenset(out)


def list_guests() -> list[dict[str, Any]]:
    doc = load_access_tokens_doc()
    rows = doc.get("guests") or []
    return [r for r in rows if isinstance(r, dict)]


def create_guest_token(*, label: str) -> dict[str, Any]:
    label = label.strip() or "guest"
    token = secrets.token_hex(24)
    row = {
        "id": uuid4().hex[:12],
        "label": label,
        "token": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc = load_access_tokens_doc()
    guests = list(doc.get("guests") or [])
    guests.append(row)
    doc["guests"] = guests
    save_access_tokens_doc(doc)
    return row


def revoke_guest(*, guest_id: str) -> bool:
    guest_id = guest_id.strip()
    doc = load_access_tokens_doc()
    guests = [g for g in doc.get("guests") or [] if isinstance(g, dict)]
    kept = [g for g in guests if str(g.get("id", "")) != guest_id]
    if len(kept) == len(guests):
        return False
    doc["guests"] = kept
    save_access_tokens_doc(doc)
    return True
