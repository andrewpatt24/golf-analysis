"""Read/write repo-root ``secrets.json`` (local only — never uploaded to Cloud Run)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from golf_analysis.rapsodo_list_kinds import find_repo_root


class LocalAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class RapsodoLoginCredentials:
    email: str
    password: str


@dataclass(frozen=True)
class GarminLoginCredentials:
    email: str
    password: str
    totp_secret: str | None = None


def repo_secrets_path(*, start: Path | None = None) -> Path | None:
    root = find_repo_root(start or Path.cwd())
    if root is None:
        return None
    return root / "secrets.json"


def load_repo_secrets(*, start: Path | None = None) -> dict[str, Any]:
    path = repo_secrets_path(start=start)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise LocalAuthError(f"Could not read {path}: {e}") from e
    return data if isinstance(data, dict) else {}


def save_repo_secrets(updates: dict[str, Any], *, start: Path | None = None) -> Path:
    path = repo_secrets_path(start=start)
    if path is None:
        raise LocalAuthError("Could not find repo root (pyproject.toml) for secrets.json")
    current = load_repo_secrets(start=start) if path.is_file() else {}
    current.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return path


def _block_str(data: dict[str, Any], block: str, key: str) -> str | None:
    section = data.get(block)
    if not isinstance(section, dict):
        return None
    raw = section.get(key)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def rapsodo_login_credentials(*, start: Path | None = None) -> RapsodoLoginCredentials | None:
    data = load_repo_secrets(start=start)
    email = str(data.get("rapsodo_email") or _block_str(data, "rapsodo", "email") or "").strip()
    password = str(data.get("rapsodo_password") or _block_str(data, "rapsodo", "password") or "").strip()
    if not email or not password:
        return None
    return RapsodoLoginCredentials(email=email, password=password)


def garmin_login_credentials(*, start: Path | None = None) -> GarminLoginCredentials | None:
    data = load_repo_secrets(start=start)
    email = str(data.get("garmin_email") or _block_str(data, "garmin", "email") or "").strip()
    password = str(data.get("garmin_password") or _block_str(data, "garmin", "password") or "").strip()
    totp = str(data.get("garmin_totp_secret") or _block_str(data, "garmin", "totp_secret") or "").strip() or None
    if not email or not password:
        return None
    return GarminLoginCredentials(email=email, password=password, totp_secret=totp)


def normalize_bearer_token(raw: str) -> str:
    s = raw.strip()
    if s.upper().startswith("JWT "):
        return s[4:].strip()
    if s.lower().startswith("bearer "):
        return s[7:].strip()
    return s


def write_rapsodo_bearer(token: str, *, start: Path | None = None) -> Path:
    bearer = normalize_bearer_token(token)
    if not bearer:
        raise LocalAuthError("Empty Rapsodo bearer token")
    return save_repo_secrets({"rapsodo_bearer": bearer}, start=start)


def read_rapsodo_bearer(*, start: Path | None = None) -> str | None:
    data = load_repo_secrets(start=start)
    raw = data.get("rapsodo_bearer")
    if raw is None:
        return None
    s = normalize_bearer_token(str(raw))
    return s or None
