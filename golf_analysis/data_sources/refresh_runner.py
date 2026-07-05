"""Run sync + ingest per dashboard data source."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from golf_analysis.api.credential_discovery import discover_garth_home
from golf_analysis.api.dashboard_secrets_store import rapsodo_bearer_from_secrets
from golf_analysis.data_sources.paths import DataPaths, resolve_data_paths
from golf_analysis.ingest import expand_paths, ingest_paths
from golf_analysis.local_auth.runtime import local_auth_enabled

SOURCE_IDS = ("rapsodo", "garmin_golf", "garmin_fit", "local_ingest")
REFRESH_ALL_ORDER = SOURCE_IDS


@dataclass
class SourceRefreshResult:
    source_id: str
    ok: bool
    message: str = ""
    files_written: int = 0
    ingest_ok: int = 0
    ingest_skip: int = 0
    ingest_error: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ok": self.ok,
            "message": self.message,
            "files_written": self.files_written,
            "ingest_ok": self.ingest_ok,
            "ingest_skip": self.ingest_skip,
            "ingest_error": self.ingest_error,
            "warnings": self.warnings,
            "error": self.error,
        }


def source_status(paths: DataPaths | None = None) -> list[dict[str, Any]]:
    p = paths or resolve_data_paths()
    last = _load_last_runs(p)
    out: list[dict[str, Any]] = []
    for sid in SOURCE_IDS:
        meta = _source_meta(sid)
        rec = last.get(sid) or {}
        configured = _is_configured(sid, p)
        out.append(
            {
                "id": sid,
                "label": meta["label"],
                "description": meta["description"],
                "configured": configured,
                "last_run_at": rec.get("last_run_at"),
                "last_ok": rec.get("last_ok"),
                "last_message": rec.get("last_message"),
                "last_error": rec.get("last_error"),
            }
        )
    return out


def refresh_source(source_id: str, paths: DataPaths | None = None) -> SourceRefreshResult:
    p = paths or resolve_data_paths()
    if source_id not in SOURCE_IDS:
        return SourceRefreshResult(source_id=source_id, ok=False, error=f"Unknown source: {source_id}")

    try:
        if source_id == "rapsodo":
            result = _refresh_rapsodo(p)
        elif source_id == "garmin_golf":
            result = _refresh_garmin_golf(p)
        elif source_id == "garmin_fit":
            result = _refresh_garmin_fit(p)
        else:
            result = _refresh_local_ingest(p)
    except Exception as e:  # noqa: BLE001
        result = SourceRefreshResult(
            source_id=source_id,
            ok=False,
            error=str(e),
            message=str(e),
        )

    _record_last_run(p, result)
    return result


def refresh_all(paths: DataPaths | None = None) -> list[SourceRefreshResult]:
    p = paths or resolve_data_paths()
    results: list[SourceRefreshResult] = []
    for sid in REFRESH_ALL_ORDER:
        r = refresh_source(sid, p)
        results.append(r)
    return results


def _garth_dir(p: DataPaths) -> Path | None:
    garth, _ = discover_garth_home(data_dir=p.data_dir)
    return garth


def _is_configured(source_id: str, p: DataPaths) -> bool:
    if source_id == "rapsodo":
        return bool(rapsodo_bearer_from_secrets()) and p.rapsodo_config.is_file()
    if source_id in ("garmin_golf", "garmin_fit"):
        return _garth_dir(p) is not None
    return True


def _source_meta(source_id: str) -> dict[str, str]:
    meta = {
        "rapsodo": {
            "label": "Rapsodo",
            "description": "Range tab, training yardages, On Course carries",
        },
        "garmin_golf": {
            "label": "Garmin Golf",
            "description": "Strategy, Performance, On Course history",
        },
        "garmin_fit": {
            "label": "Garmin activities (FIT)",
            "description": "Activity files and shot traces in library",
        },
        "local_ingest": {
            "label": "Re-import local files",
            "description": "Re-scan data/raw into library.db",
        },
    }
    return meta[source_id]


def _try_local_rapsodo_login(*, force: bool = False) -> str | None:
    if not local_auth_enabled():
        return None
    try:
        from golf_analysis.local_auth import ensure_rapsodo_bearer

        return ensure_rapsodo_bearer(force=force)
    except Exception:
        return None


def _refresh_rapsodo(p: DataPaths) -> SourceRefreshResult:
    if not p.rapsodo_config.is_file():
        return SourceRefreshResult(
            source_id="rapsodo",
            ok=False,
            error="Rapsodo endpoints config missing",
            message="Missing config/rapsodo-endpoints.json",
        )
    bearer = rapsodo_bearer_from_secrets()
    if not bearer:
        bearer = _try_local_rapsodo_login()
    if not bearer:
        return SourceRefreshResult(
            source_id="rapsodo",
            ok=False,
            error="Rapsodo JWT not configured",
            message="Add JWT in Settings or rapsodo_email/password in secrets.json and run local-auth-login",
        )

    from golf_analysis.local_auth import rapsodo_auth_failed
    from golf_analysis.sync.rapsodo_cloud import download_sessions_via_http, load_rapsodo_config

    cfg = load_rapsodo_config(p.rapsodo_config)
    cfg = cfg.model_copy(update={"bearer_token": bearer})
    written, warnings, _snap = download_sessions_via_http(
        cfg, out_dir=p.rapsodo_out, config_path=p.rapsodo_config
    )
    if rapsodo_auth_failed(warnings):
        refreshed = _try_local_rapsodo_login(force=True)
        if refreshed:
            cfg = cfg.model_copy(update={"bearer_token": refreshed})
            written, warnings, _snap = download_sessions_via_http(
                cfg, out_dir=p.rapsodo_out, config_path=p.rapsodo_config
            )
    ingest = _ingest_paths(written, p.library_db)
    ok = not rapsodo_auth_failed(warnings)
    return SourceRefreshResult(
        source_id="rapsodo",
        ok=ok,
        message=f"Synced {len(written)} CSV(s); ingest {ingest['ok']} new",
        files_written=len(written),
        ingest_ok=ingest["ok"],
        ingest_skip=ingest["skip"],
        ingest_error=ingest["error"],
        warnings=warnings,
        error="Rapsodo API rejected credentials (401/403)" if not ok else None,
    )


def _try_local_garmin_login(p: DataPaths, *, force: bool = False) -> Path | None:
    if not local_auth_enabled():
        return None
    try:
        from golf_analysis.local_auth import ensure_garth_session

        garth_dir = p.data_dir / "garth"
        return ensure_garth_session(garth_dir, force=force)
    except Exception:
        return None


def _refresh_garmin_golf(p: DataPaths) -> SourceRefreshResult:
    garth_home = _garth_dir(p)
    if garth_home is None:
        garth_home = _try_local_garmin_login(p)

    from golf_analysis.sync.garmin_golf_community import download_garmin_golf_export

    if garth_home is None:
        return SourceRefreshResult(
            source_id="garmin_golf",
            ok=False,
            error="Garmin Connect not configured",
            message="Paste Garth token JSON in Settings or add garmin_email/password to secrets.json",
        )

    p.garmin_json.parent.mkdir(parents=True, exist_ok=True)
    try:
        export = download_garmin_golf_export(
            garth_home=garth_home,
            out_path=p.garmin_json,
        )
    except Exception:
        _try_local_garmin_login(p, force=True)
        garth_home = _garth_dir(p) or garth_home
        export = download_garmin_golf_export(
            garth_home=garth_home,
            out_path=p.garmin_json,
        )
    warnings = list(export.get("warnings") or [])
    summaries = (export.get("summary") or {}).get("scorecardSummaries") or []
    ingest = _ingest_paths([p.garmin_json], p.library_db)
    return SourceRefreshResult(
        source_id="garmin_golf",
        ok=True,
        message=f"Exported {len(summaries)} scorecards; ingest {ingest['ok']} new",
        files_written=1,
        ingest_ok=ingest["ok"],
        ingest_skip=ingest["skip"],
        ingest_error=ingest["error"],
        warnings=warnings,
    )


def _refresh_garmin_fit(p: DataPaths) -> SourceRefreshResult:
    garth_home = _garth_dir(p)
    if garth_home is None:
        garth_home = _try_local_garmin_login(p)
    if garth_home is None:
        return SourceRefreshResult(
            source_id="garmin_fit",
            ok=False,
            error="Garmin Connect not configured",
            message="Paste Garth token JSON in Settings or add garmin_email/password to secrets.json",
        )

    from golf_analysis.sync.garmin_community import download_golf_activities

    try:
        written = download_golf_activities(
            garth_home=garth_home,
            out_dir=p.garmin_raw,
            limit=50,
            backfill=False,
            max_pages=5,
        )
    except Exception:
        _try_local_garmin_login(p, force=True)
        garth_home = _garth_dir(p) or garth_home
        written = download_golf_activities(
            garth_home=garth_home,
            out_dir=p.garmin_raw,
            limit=50,
            backfill=False,
            max_pages=5,
        )
    ingest = _ingest_paths(written, p.library_db)
    return SourceRefreshResult(
        source_id="garmin_fit",
        ok=True,
        message=f"Downloaded {len(written)} file(s); ingest {ingest['ok']} new",
        files_written=len(written),
        ingest_ok=ingest["ok"],
        ingest_skip=ingest["skip"],
        ingest_error=ingest["error"],
    )


def _refresh_local_ingest(p: DataPaths) -> SourceRefreshResult:
    raw_root = p.data_dir / "raw"
    paths: list[Path] = []
    if raw_root.is_dir():
        paths = expand_paths([raw_root])
    if p.garmin_json.is_file() and p.garmin_json not in paths:
        paths.append(p.garmin_json)
    paths = sorted(set(paths))
    if not paths:
        return SourceRefreshResult(
            source_id="local_ingest",
            ok=True,
            message="No files under data/raw to import",
        )
    ingest = _ingest_paths(paths, p.library_db)
    return SourceRefreshResult(
        source_id="local_ingest",
        ok=True,
        message=f"Imported {ingest['ok']} file(s), skipped {ingest['skip']} duplicate(s)",
        files_written=len(paths),
        ingest_ok=ingest["ok"],
        ingest_skip=ingest["skip"],
        ingest_error=ingest["error"],
    )


def _ingest_paths(paths: list[Path], db_path: Path) -> dict[str, int]:
    if not paths:
        return {"ok": 0, "skip": 0, "error": 0}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    results = ingest_paths(paths, db_path=db_path)
    ok = sum(1 for r in results if not r.error and not r.skipped_duplicate)
    skip = sum(1 for r in results if r.skipped_duplicate)
    err = sum(1 for r in results if r.error)
    return {"ok": ok, "skip": skip, "error": err}


def _last_runs_path(p: DataPaths) -> Path:
    return p.data_dir / "data_source_last_runs.json"


def _load_last_runs(p: DataPaths) -> dict[str, dict[str, Any]]:
    path = _last_runs_path(p)
    if not path.is_file():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _record_last_run(p: DataPaths, result: SourceRefreshResult) -> None:
    import json
    from datetime import datetime, timezone

    path = _last_runs_path(p)
    all_runs = _load_last_runs(p)
    all_runs[result.source_id] = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "last_ok": result.ok,
        "last_message": result.message,
        "last_error": result.error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(all_runs, indent=2), encoding="utf-8")
