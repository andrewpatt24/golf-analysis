"""Data source refresh and credential management."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from golf_analysis.api.credential_discovery import import_local_credentials_into_dashboard
from golf_analysis.api.dashboard_secrets_store import save_secrets, secrets_for_api
from golf_analysis.cloud_storage import upload_credentials_to_gcs
from golf_analysis.data_sources.garth_upload import extract_garth_zip, write_garth_json_file
from golf_analysis.data_sources.job_store import create_job, get_job, start_job_async
from golf_analysis.data_sources.paths import DataPaths, resolve_data_paths
from golf_analysis.data_sources.refresh_runner import source_status

router = APIRouter(tags=["data-sources"])


def _gcs_enabled() -> bool:
    return bool(os.environ.get("GOLF_DATA_BUCKET", "").strip())


def _persist_credentials() -> bool:
    if not _gcs_enabled():
        return False
    return upload_credentials_to_gcs()


def _credential_response(*, paths: DataPaths | None = None) -> dict[str, object]:
    p = paths or resolve_data_paths()
    return {
        "ok": True,
        "credentials": secrets_for_api(data_dir=p.data_dir),
        "persisted_to_cloud": _persist_credentials(),
    }


class RapsodoCredentialsUpdate(BaseModel):
    bearer: str = Field(..., min_length=10, description="R-Cloud JWT (raw token, no Bearer prefix)")
    authorization_scheme: str | None = Field(None, description="Usually JWT")


class GarminJsonCredential(BaseModel):
    filename: str | None = Field(
        None,
        description="Optional JSON filename; defaults to oauth2_token.json",
        min_length=5,
    )
    content: str = Field(..., description="Raw JSON contents of a Garth token file")


@router.get("/data-sources")
def list_data_sources() -> dict[str, object]:
    return {"sources": source_status()}


@router.get("/data-sources/credentials")
def get_credentials() -> dict[str, object]:
    paths = resolve_data_paths()
    creds = secrets_for_api(data_dir=paths.data_dir)
    cloud = _gcs_enabled()
    local_hints: list[str] = []
    if not cloud:
        if creds["rapsodo"].get("source") == "secrets.json":
            local_hints.append("Rapsodo JWT from repo secrets.json")
        if creds["garmin"].get("source") in ("~/.garth", "./.garth", "GARTH_HOME", "data/garth"):
            local_hints.append(f"Garmin Garth from {creds['garmin'].get('source')}")
    return {
        "credentials": creds,
        "rapsodo_config": str(paths.rapsodo_config) if paths.rapsodo_config.is_file() else None,
        "gcs_enabled": cloud,
        "local_hints": local_hints,
    }


@router.post("/data-sources/credentials/import-local")
def post_import_local_credentials() -> dict[str, object]:
    """Copy secrets.json / discovered Garth dir into dashboard_secrets (local dev only)."""

    if _gcs_enabled():
        raise HTTPException(
            status_code=400,
            detail="Use the credential forms below; cloud saves automatically.",
        )

    paths = resolve_data_paths()
    result = import_local_credentials_into_dashboard(data_dir=paths.data_dir)
    return {
        **result,
        "credentials": secrets_for_api(data_dir=paths.data_dir),
    }


@router.put("/data-sources/credentials/rapsodo")
def put_rapsodo_credentials(body: RapsodoCredentialsUpdate) -> dict[str, object]:
    scheme = (body.authorization_scheme or "JWT").strip()
    save_secrets(
        {
            "rapsodo": {
                "bearer": body.bearer.strip(),
                "authorization_scheme": scheme,
            },
        }
    )
    return _credential_response(paths=resolve_data_paths())


@router.post("/data-sources/credentials/garth")
async def post_garth_credentials(file: UploadFile = File(...)) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip of your ~/.garth folder")

    raw = await file.read()
    if len(raw) < 50:
        raise HTTPException(status_code=400, detail="Zip file is empty or too small")

    paths = resolve_data_paths()
    dest = paths.data_dir / "garth"
    n = extract_garth_zip(raw, dest_dir=dest)
    if n == 0:
        raise HTTPException(
            status_code=400,
            detail="No .json token files found in zip (zip your ~/.garth folder contents)",
        )
    out = _credential_response(paths=paths)
    out["files_extracted"] = n
    return out


@router.post("/data-sources/credentials/garth-json")
def post_garth_json(body: GarminJsonCredential) -> dict[str, object]:
    """Accept a single Garth OAuth token JSON (pasted). Persists to cloud storage when enabled."""

    paths = resolve_data_paths()
    dest_dir = paths.data_dir / "garth"
    name = (body.filename or "oauth2_token.json").strip() or "oauth2_token.json"
    import json

    try:
        dest = write_garth_json_file(body.content, dest_dir=dest_dir, filename=name)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out = _credential_response(paths=paths)
    out["written"] = str(dest)
    return out


@router.post("/data-sources/refresh-all")
def refresh_all_sources(background_tasks: BackgroundTasks) -> dict[str, object]:
    job = create_job(source_id=None)
    background_tasks.add_task(start_job_async, job.job_id)
    return {"job_id": job.job_id, "status": job.status}


@router.post("/data-sources/{source_id}/refresh")
def refresh_one_source(source_id: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    valid = {s["id"] for s in source_status()}
    if source_id not in valid:
        raise HTTPException(status_code=404, detail=f"Unknown data source: {source_id}")
    job = create_job(source_id=source_id)
    background_tasks.add_task(start_job_async, job.job_id)
    return {"job_id": job.job_id, "status": job.status, "source_id": source_id}


@router.get("/data-sources/jobs/{job_id}")
def get_refresh_job(job_id: str) -> dict[str, object]:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()
