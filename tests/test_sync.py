"""Tests for sync helpers (no network, no garth session required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from golf_analysis.sync.garmin_community import (
    _is_golf,
    _normalize_activity_list,
)
from golf_analysis.sync.rapsodo_cloud import (
    RapsodoSyncConfig,
    _authorization_header_value,
    _first_dict_list,
    _session_id,
    _set_url_query,
    _template_format,
    default_endpoints_template,
    write_rapsodo_session_list_snapshot,
)


def test_normalize_activity_list_shapes() -> None:
    a = {"activityId": "1"}
    assert _normalize_activity_list([a]) == [a]
    assert _normalize_activity_list({"activities": [a]}) == [a]
    assert _normalize_activity_list({"activityList": [a]}) == [a]
    assert _normalize_activity_list({}) == []


def test_is_golf() -> None:
    assert _is_golf({"activityType": {"typeKey": "golf"}})
    assert not _is_golf({"activityType": {"typeKey": "running"}})
    assert _is_golf({"activityName": "Sunday Golf"})


def test_first_dict_list_nested() -> None:
    body = {"result": {"items": [{"id": 1}]}}
    assert _first_dict_list(body) == [{"id": 1}]


def test_set_url_query_skip_take() -> None:
    out = _set_url_query(
        "https://mlm.rapsodo.com/session/user/list?skip=0&take=200&type=0",
        {"skip": 200, "take": 200},
    )
    assert "skip=200" in out and "take=200" in out


def test_rapsodo_template_json() -> None:
    raw = json.loads(default_endpoints_template())
    assert "session_list_sources" in raw
    assert isinstance(raw["session_list_sources"], list)


def test_rapsodo_template_format() -> None:
    url = _template_format(
        "https://example.com/s/{session_id}/csv",
        {"sessionId": "abc"},
        ("sessionId",),
    )
    assert url == "https://example.com/s/abc/csv"


def test_rapsodo_session_id_keys() -> None:
    cfg = RapsodoSyncConfig.model_validate(
        {
            "list_sessions_url": "https://example.com/list",
            "session_id_keys": ["foo", "bar"],
        }
    )
    assert cfg.session_id_keys == ("foo", "bar")
    assert _session_id({"foo": "x"}, cfg.session_id_keys) == "x"


def test_write_rapsodo_session_list_snapshot(tmp_path: Path) -> None:
    p = write_rapsodo_session_list_snapshot(
        tmp_path,
        sources_document=[{"kind": "practice", "url": "https://example.com/l", "pages": []}],
        sessions_merged=[{"sessionid": "1", "_list_source_kind": "practice"}],
        rows_before_dedupe=1,
        duplicate_session_ids=[],
    )
    assert p.name == "rapsodo_session_list.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert raw["stats"]["sessions_unique_after_dedupe"] == 1
    assert raw["sessions_merged"][0]["sessionid"] == "1"
    assert "fetched_at" in raw


def test_rapsodo_merge_dedupe() -> None:
    from golf_analysis.sync.rapsodo_cloud import _merge_session_rows

    keys = ("sessionid",)
    labeled = [
        ("a", {"sessionid": "1", "x": 1}),
        ("b", {"sessionid": "1", "x": 2}),
        ("b", {"sessionid": "2", "x": 3}),
    ]
    merged, dups, w = _merge_session_rows(labeled, session_id_keys=keys)
    assert len(merged) == 2
    assert dups == ["1"]
    assert merged[0]["_list_source_kind"] == "a"
    assert any("appeared in multiple lists" in x for x in w)


def test_rapsodo_config_requires_list_url() -> None:
    with pytest.raises(ValidationError):
        RapsodoSyncConfig.model_validate({})


def test_rapsodo_authorization_scheme_default_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPSODO_BEARER", "abc")
    monkeypatch.delenv("RAPSODO_BEARER_FILE", raising=False)
    cfg = RapsodoSyncConfig.model_validate({"list_sessions_url": "https://example.com/list"})
    assert _authorization_header_value(cfg, config_path=None) == "Bearer abc"


def test_rapsodo_authorization_scheme_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAPSODO_BEARER", "eyJhbGciOiJIUzI1NiJ9.sig")
    monkeypatch.delenv("RAPSODO_BEARER_FILE", raising=False)
    cfg = RapsodoSyncConfig.model_validate(
        {
            "list_sessions_url": "https://example.com/list",
            "authorization_scheme": "JWT",
        }
    )
    assert _authorization_header_value(cfg, config_path=None) == "JWT eyJhbGciOiJIUzI1NiJ9.sig"


def test_rapsodo_secrets_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAPSODO_BEARER", raising=False)
    monkeypatch.delenv("RAPSODO_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("RAPSODO_BEARER_FILE", raising=False)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (tmp_path / "secrets.json").write_text(
        json.dumps({"rapsodo_bearer": "from_secrets"}),
        encoding="utf-8",
    )
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "endpoints.json"
    cfg_path.write_text("{}", encoding="utf-8")
    cfg = RapsodoSyncConfig.model_validate(
        {
            "list_sessions_url": "https://example.com/list",
            "authorization_scheme": "JWT",
        }
    )
    assert _authorization_header_value(cfg, config_path=cfg_path) == "JWT from_secrets"


def test_rapsodo_secrets_json_invalid_json_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAPSODO_BEARER", raising=False)
    monkeypatch.delenv("RAPSODO_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("RAPSODO_BEARER_FILE", raising=False)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (tmp_path / "secrets.json").write_text("{not json", encoding="utf-8")
    cfg_path = tmp_path / "endpoints.json"
    cfg_path.write_text("{}", encoding="utf-8")
    cfg = RapsodoSyncConfig.model_validate({"list_sessions_url": "https://example.com/list"})
    assert _authorization_header_value(cfg, config_path=cfg_path) is None
