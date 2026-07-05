"""Local auth helpers (no Playwright / network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from golf_analysis.local_auth import rapsodo_auth_failed
from golf_analysis.local_auth.repo_secrets import (
    garmin_login_credentials,
    normalize_bearer_token,
    rapsodo_login_credentials,
    write_rapsodo_bearer,
)
from golf_analysis.local_auth.runtime import is_cloud_runtime, local_auth_enabled
from golf_analysis.local_auth.sanitize import sanitize_secrets_document


def test_normalize_bearer_strips_jwt_prefix() -> None:
    assert normalize_bearer_token("JWT eyJabc.def.ghi") == "eyJabc.def.ghi"
    assert normalize_bearer_token("eyJx") == "eyJx"


def test_rapsodo_auth_failed_detects_403() -> None:
    assert rapsodo_auth_failed(["List fetch failed: 403 Forbidden"])
    assert not rapsodo_auth_failed(["ok"])


def test_sanitize_removes_password_fields() -> None:
    raw = {
        "rapsodo_email": "a@b.com",
        "rapsodo_password": "secret",
        "rapsodo_bearer": "eyJx",
        "rapsodo": {"email": "x", "password": "y", "bearer": "eyJx"},
        "garmin": {"email": "g", "password": "p", "garth_dir": "/data/garth"},
    }
    safe = sanitize_secrets_document(raw)
    assert "rapsodo_email" not in safe
    assert "rapsodo_password" not in safe
    assert safe["rapsodo_bearer"] == "eyJx"
    assert "email" not in safe.get("rapsodo", {})
    assert safe["rapsodo"]["bearer"] == "eyJx"
    assert "password" not in safe.get("garmin", {})


def test_repo_secrets_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    path = write_rapsodo_bearer("JWT eyJtoken")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["rapsodo_bearer"] == "eyJtoken"

    path.write_text(
        json.dumps(
            {
                "rapsodo_email": "r@example.com",
                "rapsodo_password": "rp",
                "garmin_email": "g@example.com",
                "garmin_password": "gp",
                "garmin_totp_secret": "ABCD",
            }
        ),
        encoding="utf-8",
    )
    rc = rapsodo_login_credentials()
    assert rc is not None
    assert rc.email == "r@example.com"
    gc = garmin_login_credentials()
    assert gc is not None
    assert gc.totp_secret == "ABCD"


def test_local_auth_disabled_on_cloud_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "golf-dashboard")
    assert is_cloud_runtime()
    assert not local_auth_enabled()
    monkeypatch.delenv("K_SERVICE")
    assert local_auth_enabled()
