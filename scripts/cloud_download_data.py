#!/usr/bin/env python3
"""Download dashboard data files from GCS into /data before uvicorn starts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("GOLF_DATA_DIR", "/data"))

OBJECTS: tuple[tuple[str, str], ...] = (
    ("library.db", "GOLF_LIBRARY_DB"),
    ("golf-export.json", "GOLF_GARMIN_JSON"),
    ("dashboard_settings.json", "GOLF_DASHBOARD_SETTINGS"),
    ("dashboard_secrets.json", "GOLF_DASHBOARD_SECRETS"),
    ("on_course_playbook.json", "GOLF_ON_COURSE_PLAYBOOK"),
    ("access_tokens.json", "GOLF_ACCESS_TOKENS_FILE"),
    ("drill_sessions.json", "GOLF_DRILL_SESSIONS"),
    ("training_block.json", "GOLF_TRAINING_BLOCK"),
)


def main() -> int:
    bucket_name = os.environ.get("GOLF_DATA_BUCKET", "").strip()
    if not bucket_name:
        print("cloud_download_data: GOLF_DATA_BUCKET not set; skipping GCS download", file=sys.stderr)
        return 0

    try:
        from google.cloud import storage
    except ImportError:
        print(
            "cloud_download_data: install google-cloud-storage (uv sync --group cloud)",
            file=sys.stderr,
        )
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    for object_name, env_key in OBJECTS:
        dest = Path(os.environ.get(env_key, str(DATA_DIR / object_name))).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob = bucket.blob(object_name)
        if not blob.exists():
            print(f"cloud_download_data: missing gs://{bucket_name}/{object_name}", file=sys.stderr)
            continue
        blob.download_to_filename(str(dest))
        print(f"cloud_download_data: downloaded {object_name} -> {dest}", file=sys.stderr)

    try:
        from golf_analysis.cloud_storage import download_garth_prefix_if_present

        n = download_garth_prefix_if_present()
        if n:
            print(f"cloud_download_data: downloaded {n} garth token file(s)", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"cloud_download_data: garth download skipped: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
