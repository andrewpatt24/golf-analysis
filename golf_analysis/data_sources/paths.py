"""Resolve data paths from environment (local dev vs Cloud Run /data)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from golf_analysis.api.credential_discovery import discover_garth_home
from golf_analysis.rapsodo_list_kinds import find_repo_root


@dataclass(frozen=True)
class DataPaths:
    data_dir: Path
    library_db: Path
    garmin_json: Path
    rapsodo_out: Path
    garmin_raw: Path
    garth_home: Path | None
    rapsodo_config: Path
    secrets_path: Path
    refresh_jobs_dir: Path


def resolve_data_paths() -> DataPaths:
    repo = find_repo_root(Path.cwd())
    data_dir = Path(os.environ.get("GOLF_DATA_DIR", "data")).expanduser().resolve()

    library_raw = os.environ.get("GOLF_LIBRARY_DB", str(data_dir / "library.db"))
    garmin_json_raw = os.environ.get("GOLF_GARMIN_JSON", str(data_dir / "raw" / "garmin" / "golf-export.json"))
    secrets_raw = os.environ.get("GOLF_DASHBOARD_SECRETS", str(data_dir / "dashboard_secrets.json"))

    garth, _ = discover_garth_home(data_dir=data_dir)

    return DataPaths(
        data_dir=data_dir,
        library_db=Path(library_raw).expanduser().resolve(),
        garmin_json=Path(garmin_json_raw).expanduser().resolve(),
        rapsodo_out=(data_dir / "raw" / "rapsodo").resolve(),
        garmin_raw=(data_dir / "raw" / "garmin").resolve(),
        garth_home=garth,
        rapsodo_config=_resolve_rapsodo_config(repo),
        secrets_path=Path(secrets_raw).expanduser().resolve(),
        refresh_jobs_dir=(data_dir / "refresh_jobs").resolve(),
    )


def _resolve_rapsodo_config(repo: Path | None) -> Path:
    env = os.environ.get("GOLF_RAPSODO_CONFIG", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p.resolve()
    candidates: list[Path] = []
    if repo:
        candidates.append(repo / "config" / "rapsodo-endpoints.json")
    candidates.append(Path("/app/config/rapsodo-endpoints.json"))
    candidates.append(Path("config/rapsodo-endpoints.json"))
    for c in candidates:
        if c.is_file():
            return c.resolve()
    example = (repo / "config" / "rapsodo-endpoints.example.json") if repo else None
    if example and example.is_file():
        return example.resolve()
    return Path("config/rapsodo-endpoints.example.json")
