"""Guest access tokens and multi-token middleware."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from golf_analysis.api.access import valid_access_tokens
from golf_analysis.api.access_tokens_store import create_guest_token, revoke_guest
from golf_analysis.api.main import create_app
from golf_analysis.repository import connect, init_schema


@pytest.fixture
def token_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("GOLF_ACCESS_TOKEN", "owner-token")
    monkeypatch.setenv("GOLF_ACCESS_TOKENS_FILE", str(tmp_path / "access_tokens.json"))
    return db


def test_guest_token_valid_and_revoked(token_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    del token_db
    row = create_guest_token(label="friend")
    valid = valid_access_tokens()
    assert "owner-token" in valid
    assert row["token"] in valid

    app = create_app()
    client = TestClient(app)
    assert client.get("/api/v1/meta").status_code == 401
    assert client.get(f"/api/v1/meta?token={row['token']}").status_code == 200

    assert revoke_guest(guest_id=row["id"])
    # Reload valid set (same process — guest_token_values reads file again)
    assert row["token"] not in valid_access_tokens()
    client2 = TestClient(create_app())
    assert client2.get(f"/api/v1/meta?token={row['token']}").status_code == 401
    assert client2.get("/api/v1/meta?token=owner-token").status_code == 200


def test_env_extra_tokens(token_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    del token_db
    monkeypatch.setenv("GOLF_ACCESS_TOKENS", "extra-one,extra-two")
    assert "extra-one" in valid_access_tokens()
    client = TestClient(create_app())
    assert client.get("/api/v1/meta?token=extra-one").status_code == 200
