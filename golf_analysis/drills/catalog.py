"""Putting / chipping / range drill catalog and logged session persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DRILL_CATEGORIES = ("putting", "chipping", "range")

_CATALOG_FILES: dict[str, str] = {
    "putting": "putting_drills.json",
    "chipping": "chipping_drills.json",
    "range": "range_drills.json",
}


def _package_drills_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "drills"


def drill_sessions_path() -> Path:
    raw = os.environ.get("GOLF_DRILL_SESSIONS", "data/drill_sessions.json")
    return Path(raw).expanduser().resolve()


def _empty_sessions_doc() -> dict[str, Any]:
    return {"favorites": [], "sessions": [], "overrides": {}}


def load_drill_sessions_doc() -> dict[str, Any]:
    path = drill_sessions_path()
    if not path.is_file():
        return _empty_sessions_doc()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_sessions_doc()
    if not isinstance(data, dict):
        return _empty_sessions_doc()
    favorites = data.get("favorites")
    sessions = data.get("sessions")
    overrides = data.get("overrides")
    return {
        "favorites": [str(x) for x in favorites if x] if isinstance(favorites, list) else [],
        "sessions": [s for s in sessions if isinstance(s, dict)] if isinstance(sessions, list) else [],
        "overrides": overrides if isinstance(overrides, dict) else {},
    }


def save_drill_sessions_doc(doc: dict[str, Any]) -> dict[str, Any]:
    path = drill_sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_category_catalog(category: str) -> list[dict[str, Any]]:
    if category not in DRILL_CATEGORIES:
        return []
    filename = _CATALOG_FILES.get(category)
    if not filename:
        return []
    path = _package_drills_dir() / filename
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item.setdefault("category", category)
        out.append(item)
    return out


def load_all_catalog() -> dict[str, list[dict[str, Any]]]:
    return {cat: load_category_catalog(cat) for cat in DRILL_CATEGORIES}


def all_drill_ids() -> list[str]:
    ids: list[str] = []
    for drills in load_all_catalog().values():
        for d in drills:
            raw = d.get("id")
            if raw:
                ids.append(str(raw))
    return ids


def validate_catalog_no_duplicate_ids() -> None:
    seen: dict[str, str] = {}
    for cat, drills in load_all_catalog().items():
        for d in drills:
            did = str(d.get("id", "")).strip()
            if not did:
                raise ValueError(f"Drill missing id in category {cat!r}")
            if did in seen:
                raise ValueError(f"Duplicate drill id {did!r} in {seen[did]} and {cat}")
            seen[did] = cat
            if expected_duration_minutes(d) is None:
                raise ValueError(f"Drill {did!r} missing expected_duration_minutes")


DRILL_EDITABLE_FIELDS = frozenset({
    "title",
    "description",
    "equipment_needed",
    "distances",
    "attempts_per_distance",
    "is_timed",
    "penalty_reset_rule",
    "success_target",
    "expected_duration_minutes",
})


def load_drill_overrides(doc: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    raw_doc = doc if doc is not None else load_drill_sessions_doc()
    raw = raw_doc.get("overrides")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            out[str(key)] = dict(val)
    return out


def apply_drill_overrides(drill: dict[str, Any], overrides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    did = str(drill.get("id", ""))
    patch = overrides.get(did)
    if not patch:
        return dict(drill)
    out = dict(drill)
    for key in DRILL_EDITABLE_FIELDS:
        if key in patch:
            out[key] = patch[key]
    return out


def find_base_drill(drill_id: str) -> tuple[str, dict[str, Any]] | None:
    for cat in DRILL_CATEGORIES:
        for drill in load_category_catalog(cat):
            if str(drill.get("id")) == drill_id:
                return cat, dict(drill)
    return None


def find_drill(drill_id: str) -> tuple[str, dict[str, Any]] | None:
    found = find_base_drill(drill_id)
    if found is None:
        return None
    cat, drill = found
    overrides = load_drill_overrides()
    return cat, apply_drill_overrides(drill, overrides)


def load_effective_category_catalog(category: str) -> list[dict[str, Any]]:
    overrides = load_drill_overrides()
    return [apply_drill_overrides(d, overrides) for d in load_category_catalog(category)]


def load_effective_all_catalog() -> dict[str, list[dict[str, Any]]]:
    return {cat: load_effective_category_catalog(cat) for cat in DRILL_CATEGORIES}


def _clean_drill_patch(patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in patch.items():
        if key not in DRILL_EDITABLE_FIELDS:
            continue
        if key == "equipment_needed":
            if isinstance(val, list):
                out[key] = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str):
                out[key] = [x.strip() for x in val.replace("\n", ",").split(",") if x.strip()]
        elif key == "distances":
            if isinstance(val, list):
                out[key] = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str):
                out[key] = [x.strip() for x in val.replace("\n", ",").split(",") if x.strip()]
        elif key == "attempts_per_distance":
            if val is None or val == "":
                out[key] = None
            else:
                out[key] = int(val)
        elif key == "expected_duration_minutes":
            if val is None or val == "":
                continue
            mins = int(val)
            if mins > 0:
                out[key] = mins
        elif key == "is_timed":
            out[key] = bool(val)
        elif key in {"title", "description", "penalty_reset_rule", "success_target"}:
            text = str(val).strip()
            if key == "penalty_reset_rule":
                out[key] = text or None
            else:
                out[key] = text
    return out


def update_drill(drill_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    found = find_base_drill(drill_id)
    if found is None:
        raise ValueError(f"Unknown drill id: {drill_id}")
    _, base = found
    cleaned = _clean_drill_patch(patch)
    if not cleaned:
        raise ValueError("No editable fields provided")

    doc = load_drill_sessions_doc()
    overrides = load_drill_overrides(doc)
    current = dict(overrides.get(drill_id, {}))
    current.update(cleaned)
    overrides[drill_id] = current
    doc["overrides"] = overrides
    save_drill_sessions_doc(doc)
    return apply_drill_overrides(base, overrides)


def reset_drill_overrides(drill_id: str) -> dict[str, Any]:
    found = find_base_drill(drill_id)
    if found is None:
        raise ValueError(f"Unknown drill id: {drill_id}")
    _, base = found
    doc = load_drill_sessions_doc()
    overrides = load_drill_overrides(doc)
    overrides.pop(drill_id, None)
    doc["overrides"] = overrides
    save_drill_sessions_doc(doc)
    return base


def expected_total_attempts(drill: dict[str, Any]) -> int | None:
    """Best-effort denominator for score_out_of_total drills."""

    tracking = str(drill.get("tracking_type", ""))
    apd = drill.get("attempts_per_distance")
    distances = drill.get("distances") or []
    n_dist = len(distances) if isinstance(distances, list) else 0

    if tracking == "score_out_of_total" and apd is not None and n_dist:
        try:
            return int(apd) * n_dist
        except (TypeError, ValueError):
            pass
    if tracking == "score_out_of_total" and apd is not None:
        try:
            return int(apd)
        except (TypeError, ValueError):
            pass
    if tracking == "points_based":
        if drill.get("id") == "lag_putting_knockout":
            return 9
        if drill.get("id") == "lag_it_drill":
            return 10
    return None


def max_points(drill: dict[str, Any]) -> int | None:
    if drill.get("tracking_type") != "points_based":
        return None
    if drill.get("id") == "lag_putting_knockout":
        return 9
    if drill.get("id") == "lag_it_drill":
        return 10
    if drill.get("id") == "putt_overtake_game":
        return 10
    return None


def expected_duration_minutes(drill: dict[str, Any]) -> int | None:
    raw = drill.get("expected_duration_minutes")
    if raw is None:
        return None
    try:
        mins = int(raw)
    except (TypeError, ValueError):
        return None
    return mins if mins > 0 else None


def _parse_logged_at(iso: str) -> datetime | None:
    if not iso or not str(iso).strip():
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def days_since_last_played(last_played_at: str | None, *, now: datetime | None = None) -> int | None:
    dt = _parse_logged_at(last_played_at or "")
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    return max(0, (ref - dt).days)


def drill_session_stats() -> dict[str, dict[str, Any]]:
    """Per drill_id: last_played_at, days_since_last_played, session_count."""

    doc = load_drill_sessions_doc()
    stats: dict[str, dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    for row in doc.get("sessions") or []:
        if not isinstance(row, dict):
            continue
        did = str(row.get("drill_id", "")).strip()
        if not did:
            continue
        logged_at = str(row.get("logged_at", "")).strip()
        rec = stats.setdefault(
            did,
            {"last_played_at": logged_at, "session_count": 0},
        )
        rec["session_count"] += 1
        if logged_at and logged_at > rec["last_played_at"]:
            rec["last_played_at"] = logged_at
    for rec in stats.values():
        rec["days_since_last_played"] = days_since_last_played(rec["last_played_at"], now=now)
    return stats


def enrich_drill(drill: dict[str, Any], *, stats: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    out = dict(drill)
    out["expected_total_attempts"] = expected_total_attempts(drill)
    out["max_points"] = max_points(drill)
    out["expected_duration_minutes"] = expected_duration_minutes(drill)
    for key in ("rapsodo_mode", "rapsodo_mode_label", "default_aim", "suggested_clubs"):
        if key in drill:
            out[key] = drill[key]
    did = str(drill.get("id", ""))
    if stats is not None:
        row = stats.get(did)
        if row:
            out["last_played_at"] = row.get("last_played_at")
            out["days_since_last_played"] = row.get("days_since_last_played")
            out["session_count"] = row.get("session_count", 0)
        else:
            out["last_played_at"] = None
            out["days_since_last_played"] = None
            out["session_count"] = 0
    base = find_base_drill(did)
    if base is not None:
        overrides = load_drill_overrides()
        out["is_customized"] = did in overrides
    return out


def set_favorites(favorite_ids: list[str]) -> list[str]:
    doc = load_drill_sessions_doc()
    known = {str(d.get("id")) for drills in load_all_catalog().values() for d in drills}
    cleaned = []
    seen: set[str] = set()
    for raw in favorite_ids:
        fid = str(raw).strip()
        if fid and fid in known and fid not in seen:
            cleaned.append(fid)
            seen.add(fid)
    doc["favorites"] = cleaned
    save_drill_sessions_doc(doc)
    return cleaned


def toggle_favorite(drill_id: str) -> list[str]:
    doc = load_drill_sessions_doc()
    favorites = list(doc.get("favorites") or [])
    if drill_id in favorites:
        favorites = [f for f in favorites if f != drill_id]
    else:
        if find_drill(drill_id):
            favorites.append(drill_id)
    doc["favorites"] = favorites
    save_drill_sessions_doc(doc)
    return favorites


def list_sessions(*, drill_id: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    doc = load_drill_sessions_doc()
    rows = list(doc.get("sessions") or [])
    if drill_id:
        rows = [r for r in rows if str(r.get("drill_id")) == drill_id]
    if category:
        rows = [r for r in rows if str(r.get("category")) == category]
    rows.sort(key=lambda r: str(r.get("logged_at", "")), reverse=True)
    return rows


def append_session(
    *,
    drill_id: str,
    result: dict[str, Any],
    notes: str | None = None,
) -> dict[str, Any]:
    found = find_drill(drill_id)
    if found is None:
        raise ValueError(f"Unknown drill id: {drill_id}")
    category, drill = found
    row = {
        "id": uuid4().hex[:16],
        "drill_id": drill_id,
        "category": category,
        "tracking_type": drill.get("tracking_type"),
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "result": _normalize_result(drill, result),
        "notes": (notes or "").strip() or None,
    }
    doc = load_drill_sessions_doc()
    sessions = list(doc.get("sessions") or [])
    sessions.append(row)
    doc["sessions"] = sessions
    save_drill_sessions_doc(doc)
    return row


def _find_session_index(sessions: list[dict[str, Any]], session_id: str) -> int | None:
    for i, row in enumerate(sessions):
        if str(row.get("id")) == session_id:
            return i
    return None


_MISSING = object()


def update_session(
    session_id: str,
    *,
    result: dict[str, Any] | None = None,
    notes: Any = _MISSING,
    logged_at: str | None = None,
) -> dict[str, Any]:
    doc = load_drill_sessions_doc()
    sessions = list(doc.get("sessions") or [])
    idx = _find_session_index(sessions, session_id)
    if idx is None:
        raise ValueError(f"Unknown session id: {session_id}")
    row = dict(sessions[idx])
    drill_id = str(row.get("drill_id", ""))
    found = find_drill(drill_id)
    if found is None:
        raise ValueError(f"Unknown drill id: {drill_id}")
    _, drill = found

    if result is not None:
        row["result"] = _normalize_result(drill, result)
    if notes is not _MISSING:
        row["notes"] = (str(notes).strip() or None) if notes is not None else None
    if logged_at is not None:
        dt = _parse_logged_at(logged_at)
        if dt is None:
            raise ValueError("Invalid logged_at timestamp")
        row["logged_at"] = dt.isoformat()

    sessions[idx] = row
    doc["sessions"] = sessions
    save_drill_sessions_doc(doc)
    return row


def delete_session(session_id: str) -> None:
    doc = load_drill_sessions_doc()
    sessions = list(doc.get("sessions") or [])
    idx = _find_session_index(sessions, session_id)
    if idx is None:
        raise ValueError(f"Unknown session id: {session_id}")
    sessions.pop(idx)
    doc["sessions"] = sessions
    save_drill_sessions_doc(doc)


def _normalize_result(drill: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    tracking = str(drill.get("tracking_type", ""))
    out: dict[str, Any] = {}

    if tracking == "score_out_of_total":
        score = _int_or_none(raw.get("score"))
        total = _int_or_none(raw.get("total")) or expected_total_attempts(drill)
        out["score"] = score
        out["total"] = total
    elif tracking == "boolean_completion":
        out["completed"] = bool(raw.get("completed"))
    elif tracking == "points_based":
        out["points"] = _int_or_none(raw.get("points"))
        out["max_points"] = max_points(drill)
    elif tracking == "streak":
        out["streak"] = _int_or_none(raw.get("streak"))
    elif tracking == "total_attempts":
        out["attempts"] = _int_or_none(raw.get("attempts"))
    elif tracking == "club_focus_session":
        club = str(raw.get("club", "")).strip().lower()
        aim = str(raw.get("aim", "")).strip()
        out["club"] = club or None
        out["aim"] = aim or None
        out["completed"] = bool(raw.get("completed"))
        score = _int_or_none(raw.get("combine_score"))
        if score is not None:
            out["combine_score"] = score
    else:
        out.update(raw)

    return out


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_session_summary(session: dict[str, Any], drill: dict[str, Any] | None = None) -> str:
    result = session.get("result") or {}
    tracking = str(session.get("tracking_type") or (drill or {}).get("tracking_type", ""))

    if tracking == "score_out_of_total":
        s, t = result.get("score"), result.get("total")
        if s is not None and t is not None:
            return f"{s}/{t}"
        if s is not None:
            return str(s)
    if tracking == "boolean_completion":
        return "Completed" if result.get("completed") else "Not completed"
    if tracking == "points_based":
        pts = result.get("points")
        mx = result.get("max_points")
        if pts is not None and mx is not None:
            return f"{pts}/{mx} pts"
        if pts is not None:
            return f"{pts} pts"
    if tracking == "streak":
        streak = result.get("streak")
        return f"Streak {streak}" if streak is not None else "—"
    if tracking == "total_attempts":
        att = result.get("attempts")
        return f"{att} attempts" if att is not None else "—"
    if tracking == "club_focus_session":
        club = result.get("club") or "—"
        aim = result.get("aim")
        bits = [str(club)]
        if aim:
            short = str(aim)
            if len(short) > 40:
                short = short[:37] + "…"
            bits.append(short)
        score = result.get("combine_score")
        if score is not None:
            bits.append(f"score {score}")
        status = "✓" if result.get("completed") else "—"
        return f"{' · '.join(bits)} {status}"
    return "—"
