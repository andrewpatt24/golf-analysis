"""Refresh job tracking (async sync on Cloud Run)."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from golf_analysis.data_sources.paths import resolve_data_paths
from golf_analysis.data_sources.refresh_runner import REFRESH_ALL_ORDER, refresh_all, refresh_source


@dataclass
class RefreshJob:
    job_id: str
    status: str  # queued | running | succeeded | failed
    source_ids: list[str]
    created_at: str
    updated_at: str
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    gcs_uploaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "source_ids": self.source_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "results": self.results,
            "error": self.error,
            "gcs_uploaded": self.gcs_uploaded,
        }


_lock = threading.Lock()
_jobs: dict[str, RefreshJob] = {}


def create_job(*, source_id: str | None = None) -> RefreshJob:
    job_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    source_ids = list(REFRESH_ALL_ORDER) if source_id is None or source_id == "all" else [source_id]
    job = RefreshJob(
        job_id=job_id,
        status="queued",
        source_ids=source_ids,
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _jobs[job_id] = job
        _persist_job(job)
    return job


def get_job(job_id: str) -> RefreshJob | None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            return job
    return _load_job_file(job_id)


def start_job_async(job_id: str, *, on_complete: Callable[[RefreshJob], None] | None = None) -> None:
    thread = threading.Thread(target=_run_job, args=(job_id, on_complete), daemon=True)
    thread.start()


def _run_job(job_id: str, on_complete: Callable[[RefreshJob], None] | None) -> None:
    job = get_job(job_id)
    if job is None:
        return
    _update_job(job_id, status="running")

    paths = resolve_data_paths()
    results: list[dict[str, Any]] = []
    hard_error: str | None = None

    try:
        if job.source_ids == list(REFRESH_ALL_ORDER):
            for r in refresh_all(paths):
                results.append(r.to_dict())
                if not r.ok and r.error and _is_auth_error(r.error):
                    hard_error = r.error
                    break
        else:
            for sid in job.source_ids:
                r = refresh_source(sid, paths)
                results.append(r.to_dict())
                if not r.ok and r.error and _is_auth_error(r.error):
                    hard_error = r.error
                    break
    except Exception as e:  # noqa: BLE001
        hard_error = str(e)

    gcs_ok = False
    if hard_error is None and any(r.get("ok") for r in results):
        try:
            from golf_analysis.cloud_storage import upload_dashboard_data_to_gcs

            gcs_ok = upload_dashboard_data_to_gcs()
        except Exception as e:  # noqa: BLE001
            hard_error = f"GCS upload failed: {e}"

    status = "failed" if hard_error else "succeeded"
    if hard_error is None and results and not any(r.get("ok") for r in results):
        status = "failed"
        hard_error = "All sources failed"

    finished = _update_job(
        job_id,
        status=status,
        results=results,
        error=hard_error,
        gcs_uploaded=gcs_ok,
    )
    if on_complete and finished:
        on_complete(finished)


def _is_auth_error(msg: str) -> bool:
    lower = msg.lower()
    return any(
        x in lower
        for x in ("401", "403", "unauthorized", "not configured", "jwt", "garth", "token", "login")
    )


def _update_job(job_id: str, **kwargs: Any) -> RefreshJob | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            job = _load_job_file(job_id)
        if not job:
            return None
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = _now_iso()
        _jobs[job_id] = job
        _persist_job(job)
        return job


def _persist_job(job: RefreshJob) -> None:
    paths = resolve_data_paths()
    paths.refresh_jobs_dir.mkdir(parents=True, exist_ok=True)
    path = paths.refresh_jobs_dir / f"{job.job_id}.json"
    path.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")


def _load_job_file(job_id: str) -> RefreshJob | None:
    paths = resolve_data_paths()
    path = paths.refresh_jobs_dir / f"{job_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    job = RefreshJob(
        job_id=str(data.get("job_id", job_id)),
        status=str(data.get("status", "failed")),
        source_ids=list(data.get("source_ids") or []),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
        results=list(data.get("results") or []),
        error=data.get("error"),
        gcs_uploaded=bool(data.get("gcs_uploaded")),
    )
    with _lock:
        _jobs[job_id] = job
    return job


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
