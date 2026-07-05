"""Local-only credential refresh (Playwright / garth). Disabled on Cloud Run."""

from __future__ import annotations

from pathlib import Path

from golf_analysis.local_auth.repo_secrets import LocalAuthError
from golf_analysis.local_auth.runtime import is_cloud_runtime, local_auth_enabled

__all__ = [
    "LocalAuthError",
    "ensure_garth_session",
    "ensure_rapsodo_bearer",
    "is_cloud_runtime",
    "local_auth_enabled",
    "rapsodo_auth_failed",
]


def rapsodo_auth_failed(warnings: list[str]) -> bool:
    joined = " ".join(warnings).lower()
    return "403" in joined or "401" in joined or "forbidden" in joined or "unauthorized" in joined


def ensure_rapsodo_bearer(
    *,
    headless: bool = True,
    force: bool = False,
    start: Path | None = None,
) -> str:
    from golf_analysis.local_auth.rapsodo_playwright import login_rapsodo_via_playwright
    from golf_analysis.local_auth.repo_secrets import rapsodo_login_credentials, write_rapsodo_bearer

    if not local_auth_enabled():
        raise LocalAuthError("Local auth is disabled on Cloud Run. Use Settings to paste a JWT.")
    creds = rapsodo_login_credentials(start=start)
    if creds is None:
        raise LocalAuthError(
            "Add rapsodo_email and rapsodo_password to repo-root secrets.json (never pushed to cloud)."
        )
    token = login_rapsodo_via_playwright(creds, headless=headless)
    write_rapsodo_bearer(token, start=start)
    from golf_analysis.api.dashboard_secrets_store import save_secrets

    save_secrets({"rapsodo": {"bearer": token, "authorization_scheme": "JWT"}})
    return token


def ensure_garth_session(
    garth_dir: Path,
    *,
    force: bool = False,
    start: Path | None = None,
) -> Path:
    from golf_analysis.local_auth.garmin_garth import login_garmin_via_garth
    from golf_analysis.local_auth.repo_secrets import garmin_login_credentials

    if not local_auth_enabled():
        raise LocalAuthError("Local auth is disabled on Cloud Run. Upload Garth tokens in Settings.")
    creds = garmin_login_credentials(start=start)
    if creds is None:
        raise LocalAuthError(
            "Add garmin_email and garmin_password to repo-root secrets.json (never pushed to cloud)."
        )
    return login_garmin_via_garth(creds, garth_dir, force=force)
