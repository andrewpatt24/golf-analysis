"""Find credentials from dashboard_secrets, repo secrets.json, or Garth login dir."""

from __future__ import annotations

import os
from pathlib import Path

from golf_analysis.api.dashboard_secrets_store import (
    garth_configured,
    load_secrets,
    rapsodo_bearer_from_secrets,
    save_secrets,
)
from golf_analysis.rapsodo_list_kinds import find_repo_root


def default_garth_home() -> Path:
    """Same search order as ``golf-ingest`` CLI."""

    env = os.environ.get("GARTH_HOME")
    if env:
        return Path(env).expanduser()
    home = Path("~/.garth").expanduser()
    if home.is_dir() and garth_configured(home):
        return home
    local = (Path.cwd() / ".garth").resolve()
    if local.is_dir() and garth_configured(local):
        return local
    return home


def repo_secrets_json_path() -> Path | None:
    root = find_repo_root(Path.cwd())
    if root is None:
        return None
    path = root / "secrets.json"
    return path if path.is_file() else None


def rapsodo_bearer_from_repo_secrets() -> str | None:
    path = repo_secrets_json_path()
    if path is None:
        return None
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("rapsodo_bearer")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def discover_rapsodo_bearer() -> tuple[str | None, str | None]:
    """Return (token, source_label). Dashboard secrets win over repo secrets.json."""

    secrets = load_secrets()
    raw = (secrets.get("rapsodo") or {}).get("bearer")
    if raw and str(raw).strip():
        return str(raw).strip(), "dashboard_secrets"
    token = rapsodo_bearer_from_repo_secrets()
    if token:
        return token, "secrets.json"
    return None, None


def discover_garth_home(*, data_dir: Path | None = None) -> tuple[Path | None, str | None]:
    """Return (garth_dir, source_label)."""

    secrets = load_secrets()
    raw = (secrets.get("garmin") or {}).get("garth_dir")
    if raw:
        p = Path(str(raw)).expanduser().resolve()
        if garth_configured(p):
            return p, "dashboard_secrets"

    if data_dir is not None:
        p = (data_dir / "garth").resolve()
        if garth_configured(p):
            return p, "data/garth"

    for label, candidate in (
        ("GARTH_HOME", Path(os.environ.get("GARTH_HOME", "")).expanduser() if os.environ.get("GARTH_HOME") else None),
        ("~/.garth", Path("~/.garth").expanduser()),
        ("./.garth", (Path.cwd() / ".garth").resolve()),
    ):
        if candidate is None:
            continue
        if garth_configured(candidate):
            return candidate.resolve(), label

    return None, None


def import_local_credentials_into_dashboard(*, data_dir: Path | None = None) -> dict[str, object]:
    """
    Persist locally discovered credentials into dashboard_secrets.json.

    Does not overwrite values already saved in dashboard secrets.
  """

    updates: dict[str, object] = {}
    imported: list[str] = []

    current = load_secrets()
    bearer, src = discover_rapsodo_bearer()
    if bearer and not current["rapsodo"].get("bearer"):
        updates["rapsodo"] = {
            "bearer": bearer,
            "authorization_scheme": current["rapsodo"].get("authorization_scheme") or "JWT",
        }
        imported.append(src or "rapsodo")

    garth, garth_src = discover_garth_home(data_dir=data_dir)
    if garth and not current["garmin"].get("garth_dir"):
        updates["garmin"] = {"garth_dir": str(garth)}
        imported.append(garth_src or "garmin")

    if updates:
        save_secrets(updates)

    return {"imported": imported, "skipped": not bool(updates)}
