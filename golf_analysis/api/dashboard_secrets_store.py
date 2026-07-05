"""Dashboard-managed credentials (Rapsodo JWT, Garmin Garth dir) — separate from analytics settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from golf_analysis.local_auth.sanitize import sanitize_secrets_document

_DEFAULTS: dict[str, Any] = {
    "rapsodo": {
        "bearer": None,
        "authorization_scheme": "JWT",
    },
    "garmin": {
        "garth_dir": None,
    },
}


def secrets_path() -> Path:
    raw = os.environ.get("GOLF_DASHBOARD_SECRETS", "data/dashboard_secrets.json")
    return Path(raw).expanduser().resolve()


def load_secrets() -> dict[str, Any]:
    path = secrets_path()
    if not path.is_file():
        return _deep_copy_defaults()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _deep_copy_defaults()
    if not isinstance(data, dict):
        return _deep_copy_defaults()
    merged = _deep_copy_defaults()
    r = data.get("rapsodo")
    if isinstance(r, dict):
        merged["rapsodo"].update({k: r[k] for k in merged["rapsodo"] if k in r})
    g = data.get("garmin")
    if isinstance(g, dict):
        merged["garmin"].update({k: g[k] for k in merged["garmin"] if k in g})
    return merged


def save_secrets(updates: dict[str, Any]) -> dict[str, Any]:
    updates = sanitize_secrets_document(updates)
    current = load_secrets()
    if "rapsodo" in updates and isinstance(updates["rapsodo"], dict):
        for k, v in updates["rapsodo"].items():
            if k in current["rapsodo"]:
                current["rapsodo"][k] = v
    if "garmin" in updates and isinstance(updates["garmin"], dict):
        for k, v in updates["garmin"].items():
            if k in current["garmin"]:
                current["garmin"][k] = v
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = sanitize_secrets_document(current)
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return current


def mask_secret(value: str | None, *, visible_tail: int = 6) -> str | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    if len(s) <= visible_tail + 3:
        return "••••••"
    return f"{s[:3]}…{s[-visible_tail:]}"


def secrets_for_api(*, data_dir: Path | None = None) -> dict[str, Any]:
    """Masked view for GET /data-sources/credentials (includes local discovery)."""

    from golf_analysis.api.credential_discovery import discover_garth_home, discover_rapsodo_bearer

    s = load_secrets()
    r = s.get("rapsodo") or {}
    bearer, rapsodo_source = discover_rapsodo_bearer()
    garth_path, garth_source = discover_garth_home(data_dir=data_dir)
    g = s.get("garmin") or {}
    stored_garth = g.get("garth_dir")

    return {
        "rapsodo": {
            "configured": bool(bearer),
            "bearer_masked": mask_secret(bearer),
            "authorization_scheme": r.get("authorization_scheme") or "JWT",
            "stored_in_dashboard": bool(r.get("bearer")),
            "source": rapsodo_source,
        },
        "garmin": {
            "configured": garth_path is not None,
            "garth_dir": str(garth_path) if garth_path else None,
            "stored_in_dashboard": bool(stored_garth),
            "source": garth_source,
        },
    }


def rapsodo_bearer_from_secrets() -> str | None:
    from golf_analysis.api.credential_discovery import discover_rapsodo_bearer

    bearer, _ = discover_rapsodo_bearer()
    return bearer


def garth_home_from_secrets(*, fallback: Path | None = None) -> Path | None:
    from golf_analysis.api.credential_discovery import discover_garth_home

    data_dir = fallback.parent if fallback and fallback.name == "garth" else fallback
    if fallback and fallback.name != "garth":
        data_dir = fallback
    garth, _ = discover_garth_home(data_dir=data_dir if data_dir and data_dir.is_dir() else None)
    if garth:
        return garth
    if fallback and garth_configured(fallback):
        return fallback.resolve()
    return None


def garth_configured(garth_dir: Path | None) -> bool:
    if garth_dir is None or not garth_dir.is_dir():
        return False
    return any(garth_dir.glob("*.json"))


def _deep_copy_defaults() -> dict[str, Any]:
    return {
        "rapsodo": dict(_DEFAULTS["rapsodo"]),
        "garmin": dict(_DEFAULTS["garmin"]),
    }
