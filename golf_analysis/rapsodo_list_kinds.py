"""Map Rapsodo session id → ``_list_source_kind`` from ``data/raw/rapsodo/rapsodo_session_list.json``."""

from __future__ import annotations

import json
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    """First directory upward from ``start`` that contains ``pyproject.toml``."""

    p = start.resolve()
    for d in [p, *p.parents]:
        if (d / "pyproject.toml").is_file():
            return d
    return None


def load_list_source_kind_map(repo_root: Path) -> dict[str, str]:
    """
    Build ``session_id_str -> list_source_kind`` from the merged session snapshot (schema v2).

    Multiple keys per row (``sessionid``, ``simulationid``, ``id``) may map to the same kind so
    CSV filenames like ``rapsodo_session_<id>.csv`` resolve consistently.
    """

    path = repo_root / "data" / "raw" / "rapsodo" / "rapsodo_session_list.json"
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(doc, dict):
        return {}
    merged = doc.get("sessions_merged")
    if not isinstance(merged, list):
        return {}
    out: dict[str, str] = {}
    for row in merged:
        if not isinstance(row, dict):
            continue
        kind = row.get("_list_source_kind")
        if not isinstance(kind, str) or not kind.strip():
            continue
        kind = kind.strip()
        for key in ("sessionid", "simulationid", "id", "_id"):
            v = row.get(key)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                out[s] = kind
    return out


def load_session_ids_for_calendar_year(repo_root: Path, year: int) -> set[str]:
    """
    Session ids whose ``startdate`` / ``startDate`` in ``sessions_merged`` falls in ``year``.

    Used to scope range shots to true session calendar time (DB ``started_at`` is often CSV mtime).
    """

    path = repo_root / "data" / "raw" / "rapsodo" / "rapsodo_session_list.json"
    if not path.is_file():
        return set()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(doc, dict):
        return set()
    merged = doc.get("sessions_merged")
    if not isinstance(merged, list):
        return set()
    out: set[str] = set()
    for row in merged:
        if not isinstance(row, dict):
            continue
        raw = row.get("startdate") or row.get("startDate")
        if raw is None:
            continue
        s = str(raw).strip()
        if len(s) < 4 or not s[:4].isdigit():
            continue
        try:
            row_year = int(s[:4])
        except ValueError:
            continue
        if row_year != year:
            continue
        for key in ("sessionid", "simulationid", "id", "_id"):
            v = row.get(key)
            if v is None:
                continue
            sid = str(v).strip()
            if sid:
                out.add(sid)
    return out
