"""Dashboard secrets store."""

from __future__ import annotations

from pathlib import Path

import pytest

from golf_analysis.api.dashboard_secrets_store import (
    load_secrets,
    mask_secret,
    rapsodo_bearer_from_secrets,
    save_secrets,
    secrets_for_api,
)


def test_mask_secret() -> None:
    assert mask_secret("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123xyz") == "eyJ…123xyz"


def test_save_and_load_rapsodo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "dashboard_secrets.json"
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(path))
    save_secrets({"rapsodo": {"bearer": "test-token-xyz", "authorization_scheme": "JWT"}})
    assert rapsodo_bearer_from_secrets() == "test-token-xyz"
    api_view = secrets_for_api()
    assert api_view["rapsodo"]["configured"] is True
    assert api_view["rapsodo"]["bearer_masked"]
    assert "xyz" in api_view["rapsodo"]["bearer_masked"]


def test_defaults_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(tmp_path / "nope.json"))
    s = load_secrets()
    assert s["rapsodo"]["bearer"] is None
