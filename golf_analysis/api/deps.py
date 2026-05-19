from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, HTTPException


def library_db_path() -> Path:
    raw = os.environ.get("GOLF_LIBRARY_DB", "data/library.db")
    return Path(raw).expanduser().resolve()


def garmin_export_path() -> Path | None:
    """
    Resolve Garmin export JSON.

    Relative paths are resolved against the **repo root** (directory containing ``pyproject.toml``)
    inferred from ``GOLF_LIBRARY_DB``'s parent chain, then ``Path.cwd()``, so the API finds
    ``data/raw/garmin/golf-export.json`` even when the process cwd is not the repo root.
    """

    from golf_analysis.rapsodo_list_kinds import find_repo_root

    raw = os.environ.get("GOLF_GARMIN_JSON", "data/raw/garmin/golf-export.json")
    p = Path(raw).expanduser()
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p.resolve())
    else:
        db_parent = Path(os.environ.get("GOLF_LIBRARY_DB", "data/library.db")).expanduser().resolve().parent
        for start in (db_parent, Path.cwd().resolve()):
            root = find_repo_root(start)
            if root is not None:
                candidates.append((root / p).resolve())
        candidates.append((Path.cwd() / p).resolve())
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file():
            return cand
    return None


def repo_root_from_db(db: Path) -> Path | None:
    from golf_analysis.rapsodo_list_kinds import find_repo_root

    return find_repo_root(db.parent)


def require_db_exists(db: Path = Depends(library_db_path)) -> Path:
    if not db.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Library database not found: {db}. Set GOLF_LIBRARY_DB or run golf-ingest ingest.",
        )
    return db
