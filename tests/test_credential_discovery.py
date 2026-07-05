"""Local credential discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from golf_analysis.api.credential_discovery import (
    discover_garth_home,
    discover_rapsodo_bearer,
    import_local_credentials_into_dashboard,
)


def test_discover_rapsodo_from_secrets_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (repo / "secrets.json").write_text('{"rapsodo_bearer": "jwt-from-file"}', encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(tmp_path / "empty.json"))
    token, source = discover_rapsodo_bearer()
    assert token == "jwt-from-file"
    assert source == "secrets.json"


def test_discover_garth_from_dot_garth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    garth = repo / ".garth"
    garth.mkdir(parents=True)
    (garth / "oauth1_token.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(tmp_path / "empty.json"))
    path, source = discover_garth_home()
    assert path is not None
    assert source == "./.garth"


def test_import_local_into_dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (repo / "secrets.json").write_text('{"rapsodo_bearer": "tok1234567890"}', encoding="utf-8")
    dash = tmp_path / "dashboard_secrets.json"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GOLF_DASHBOARD_SECRETS", str(dash))
    out = import_local_credentials_into_dashboard()
    assert "secrets.json" in out["imported"]
    token, source = discover_rapsodo_bearer()
    assert token == "tok1234567890"
    assert source == "dashboard_secrets"
