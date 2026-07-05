"""Extract uploaded Garth session zip to configured directory."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from golf_analysis.api.dashboard_secrets_store import garth_configured, save_secrets


def write_garth_json_file(
    content: str,
    *,
    dest_dir: Path,
    filename: str = "oauth2_token.json",
) -> Path:
    """Write one Garth OAuth token JSON file and register garth_dir in dashboard secrets."""

    import json

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")

    dest_dir = dest_dir.expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = filename.strip() or "oauth2_token.json"
    if not name.lower().endswith(".json"):
        name = f"{name}.json"

    dest = (dest_dir / name).resolve()
    if dest_dir not in dest.parents:
        raise ValueError("Invalid filename path")

    dest.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    if garth_configured(dest_dir):
        save_secrets({"garmin": {"garth_dir": str(dest_dir)}})
    return dest


def extract_garth_zip(zip_bytes: bytes, *, dest_dir: Path) -> int:
    """
    Extract oauth token files from a zip of ~/.garth into dest_dir.

    Returns number of files written.
    """

    dest_dir = dest_dir.expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            base = Path(name).name
            if not base.endswith(".json"):
                continue
            data = zf.read(name)
            out = dest_dir / base
            out.write_bytes(data)
            written += 1

    if written > 0:
        save_secrets({"garmin": {"garth_dir": str(dest_dir)}})
    return written
