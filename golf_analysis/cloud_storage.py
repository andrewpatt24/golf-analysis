"""GCS download/upload for Cloud Run dashboard data."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from golf_analysis.local_auth.sanitize import sanitize_secrets_document


def bucket_name() -> str | None:
    name = os.environ.get("GOLF_DATA_BUCKET", "").strip()
    return name or None


def upload_dashboard_data_to_gcs() -> bool:
    """Upload library, Garmin export, settings, secrets, and garth dir to GCS."""

    bucket = bucket_name()
    if not bucket:
        return False

    try:
        from google.cloud import storage
    except ImportError:
        return False

    client = storage.Client()
    b = client.bucket(bucket)
    data_dir = Path(os.environ.get("GOLF_DATA_DIR", "/data")).expanduser().resolve()

    uploads: list[tuple[Path, str]] = []
    for env_key, object_name in (
        ("GOLF_LIBRARY_DB", "library.db"),
        ("GOLF_GARMIN_JSON", "golf-export.json"),
        ("GOLF_DASHBOARD_SETTINGS", "dashboard_settings.json"),
        ("GOLF_ON_COURSE_PLAYBOOK", "on_course_playbook.json"),
        ("GOLF_ACCESS_TOKENS_FILE", "access_tokens.json"),
        ("GOLF_DRILL_SESSIONS", "drill_sessions.json"),
        ("GOLF_TRAINING_BLOCK", "training_block.json"),
    ):
        raw = os.environ.get(env_key)
        if not raw:
            continue
        local = Path(raw).expanduser().resolve()
        if local.is_file():
            uploads.append((local, object_name))

    secrets_raw = os.environ.get("GOLF_DASHBOARD_SECRETS", str(data_dir / "dashboard_secrets.json"))
    secrets_path = Path(secrets_raw).expanduser().resolve()
    secrets_upload_path: Path | None = None
    if secrets_path.is_file():
        secrets_upload_path = _sanitized_secrets_tempfile(secrets_path)
        uploads.append((secrets_upload_path, "dashboard_secrets.json"))

    garth_dir = data_dir / "garth"
    if garth_dir.is_dir():
        for f in garth_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(garth_dir)
                uploads.append((f, f"garth/{rel.as_posix()}"))

    try:
        for local_path, object_name in uploads:
            blob = b.blob(object_name)
            blob.upload_from_filename(str(local_path))
    finally:
        if secrets_upload_path is not None:
            secrets_upload_path.unlink(missing_ok=True)

    return True


def _sanitized_secrets_tempfile(secrets_path: Path) -> Path:
    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}
    safe = sanitize_secrets_document(data)
    fd, name = tempfile.mkstemp(suffix=".dashboard_secrets.json")
    os.close(fd)
    tmp = Path(name)
    tmp.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return tmp


def _upload_sanitized_secrets(bucket: object, secrets_path: Path) -> None:
    tmp = _sanitized_secrets_tempfile(secrets_path)
    try:
        bucket.blob("dashboard_secrets.json").upload_from_filename(str(tmp))  # type: ignore[attr-defined]
    finally:
        tmp.unlink(missing_ok=True)


def upload_credentials_to_gcs() -> bool:
    """Persist dashboard secrets and Garth token files to GCS (survives redeploy)."""

    bucket = bucket_name()
    if not bucket:
        return False

    try:
        from google.cloud import storage
    except ImportError:
        return False

    client = storage.Client()
    b = client.bucket(bucket)
    data_dir = Path(os.environ.get("GOLF_DATA_DIR", "/data")).expanduser().resolve()

    uploaded = False
    secrets_raw = os.environ.get("GOLF_DASHBOARD_SECRETS", str(data_dir / "dashboard_secrets.json"))
    secrets_path = Path(secrets_raw).expanduser().resolve()
    if secrets_path.is_file():
        _upload_sanitized_secrets(b, secrets_path)
        uploaded = True

    garth_dir = data_dir / "garth"
    if garth_dir.is_dir():
        for f in garth_dir.rglob("*.json"):
            if f.is_file():
                rel = f.relative_to(garth_dir)
                b.blob(f"garth/{rel.as_posix()}").upload_from_filename(str(f))
                uploaded = True

    return uploaded


def download_garth_prefix_if_present() -> int:
    """Download garth/* objects from GCS into data_dir/garth. Returns file count."""

    bucket = bucket_name()
    if not bucket:
        return 0

    try:
        from google.cloud import storage
    except ImportError:
        return 0

    data_dir = Path(os.environ.get("GOLF_DATA_DIR", "/data")).expanduser().resolve()
    garth_dir = data_dir / "garth"
    garth_dir.mkdir(parents=True, exist_ok=True)

    client = storage.Client()
    blobs = client.list_blobs(bucket, prefix="garth/")
    n = 0
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        rel = blob.name[len("garth/") :]
        if not rel:
            continue
        dest = garth_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        n += 1

    if n > 0:
        from golf_analysis.api.dashboard_secrets_store import save_secrets

        save_secrets({"garmin": {"garth_dir": str(garth_dir.resolve())}})
    return n
