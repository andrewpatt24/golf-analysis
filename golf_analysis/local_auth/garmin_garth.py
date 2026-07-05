"""Garmin Connect login via garth-ng (local only)."""

from __future__ import annotations

from pathlib import Path

from golf_analysis.api.dashboard_secrets_store import garth_configured, save_secrets
from golf_analysis.local_auth.repo_secrets import GarminLoginCredentials, LocalAuthError
from golf_analysis.sync.garmin_community import resume_garth_session


def _mfa_handler(creds: GarminLoginCredentials):
    if not creds.totp_secret:
        raise LocalAuthError(
            "Garmin MFA required. Add garmin_totp_secret to secrets.json or run garth login once manually."
        )
    try:
        import pyotp
    except ImportError as e:
        raise LocalAuthError("Garmin TOTP needs pyotp (uv sync --group local-auth)") from e

    totp = pyotp.TOTP(creds.totp_secret.replace(" ", ""))

    def _prompt() -> str:
        return totp.now()

    return _prompt


def login_garmin_via_garth(
    creds: GarminLoginCredentials,
    garth_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Run garth.login and persist OAuth JSON under ``garth_dir``."""

    garth_dir = garth_dir.expanduser().resolve()
    garth_dir.mkdir(parents=True, exist_ok=True)

    if not force and garth_configured(garth_dir):
        try:
            resume_garth_session(garth_dir)
            return garth_dir
        except Exception:
            pass

    try:
        import garth
    except ImportError as e:
        raise LocalAuthError("Install garth-ng: uv sync --group sync") from e

    prompt_mfa = None
    if creds.totp_secret:
        prompt_mfa = _mfa_handler(creds)
    try:
        result = garth.login(creds.email, creds.password, prompt_mfa=prompt_mfa)
    except TypeError:
        result = garth.login(creds.email, creds.password)

    if hasattr(result, "prompt_mfa") and callable(getattr(result, "prompt_mfa", None)):
        raise LocalAuthError(
            "Garmin MFA required. Add garmin_totp_secret to secrets.json or run: garth login"
        )

    garth.save(str(garth_dir))

    if not garth_configured(garth_dir):
        raise LocalAuthError(f"garth.login did not write token JSON under {garth_dir}")

    save_secrets({"garmin": {"garth_dir": str(garth_dir)}})
    return garth_dir
