from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ACTIVITY_LIST = "/activitylist-service/activities/search/activities"
_DOWNLOAD_ORIGINAL = "/download-service/files/activity"


def _require_garth() -> Any:
    try:
        import garth
    except ImportError as e:  # pragma: no cover - exercised when sync extra missing
        raise ImportError(
            "Garmin community sync needs garth-ng. Install sync extras: uv sync --group sync"
        ) from e
    return garth


def resume_garth_session(garth_home: Path) -> None:
    """Load tokens from a directory previously created with `garth login` or `garth.save`."""

    garth = _require_garth()
    home = garth_home.expanduser().resolve()
    if not home.is_dir():
        raise FileNotFoundError(
            f"Garth session directory not found: {home}\n"
            "Run: uv run --group sync garth login\n"
            "Or set GARTH_HOME and use garth CLI to save tokens there."
        )
    garth.resume(str(home))


def _normalize_activity_list(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("activities", "activityList", "data", "items"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
    return []


def _activity_type_key(activity: dict[str, Any]) -> str | None:
    at = activity.get("activityType")
    if isinstance(at, dict):
        tk = at.get("typeKey")
        if isinstance(tk, str):
            return tk.lower()
    if isinstance(at, str):
        return at.lower()
    return None


def _is_golf(activity: dict[str, Any]) -> bool:
    tk = _activity_type_key(activity)
    if tk == "golf":
        return True
    name = (activity.get("activityName") or activity.get("name") or "").lower()
    return "golf" in name


def _activity_id(activity: dict[str, Any]) -> str | None:
    for key in ("activityId", "activityID", "summaryId"):
        v = activity.get(key)
        if v is not None:
            return str(v)
    return None


def _safe_filename(activity: dict[str, Any], activity_id: str) -> str:
    ts = activity.get("startTimeLocal") or activity.get("startGMT") or ""
    raw = f"{ts}_{activity_id}".strip("_")
    raw = re.sub(r"[^\w.\-]+", "_", str(raw), flags=re.UNICODE)
    return raw[:180] or f"activity_{activity_id}"


def download_golf_activities(
    *,
    garth_home: Path,
    out_dir: Path,
    limit: int = 30,
    start: int = 0,
    include_non_golf: bool = False,
    backfill: bool = False,
    max_pages: int | None = 200,
) -> list[Path]:
    """
    List recent activities from Garmin Connect (community API) and download
    original files (often a .zip containing .fit) for golf rounds.

    ``limit`` is how many activities Garmin returns **per request** (mixed sports).
    Only activities passing ``_is_golf`` are downloaded unless ``include_non_golf``.

    With ``backfill=True``, repeats the list request with increasing ``start`` until
    a page returns fewer than ``limit`` activities (end of history), so you can pull
    all golf rounds (subject to dedupe on re-ingest). ``max_pages`` caps pages when
    backfilling (default 200) to avoid infinite loops.
    """

    garth = _require_garth()
    resume_garth_session(garth_home)
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    offset = start
    pages = 0

    while True:
        pages += 1
        if backfill and max_pages is not None and pages > max_pages:
            break
        payload = garth.client.connectapi(
            _ACTIVITY_LIST,
            params={"start": str(offset), "limit": str(limit)},
        )
        activities = _normalize_activity_list(payload)
        if not activities:
            break
        for act in activities:
            if not include_non_golf and not _is_golf(act):
                continue
            aid = _activity_id(act)
            if not aid:
                continue
            data = garth.client.download(f"{_DOWNLOAD_ORIGINAL}/{aid}")
            if not data:
                continue
            name = _safe_filename(act, aid)
            suffix = ".zip" if data[:2] == b"PK" else ".fit"
            path = out_dir / f"{name}{suffix}"
            path.write_bytes(data)
            written.append(path)

        if not backfill:
            break
        if len(activities) < limit:
            break
        offset += limit

    return written
