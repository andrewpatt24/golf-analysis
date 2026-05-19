"""Tests for API dependency helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from golf_analysis.api.deps import garmin_export_path


def test_garmin_export_path_relative_resolves_via_library_db_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Default relative Garmin path must resolve from repo root, not process cwd."""

    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
    gar = root / "data" / "raw" / "garmin"
    gar.mkdir(parents=True, exist_ok=True)
    target = gar / "golf-export.json"
    target.write_text("{}", encoding="utf-8")

    db = root / "data" / "library.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_GARMIN_JSON", "data/raw/garmin/golf-export.json")

    p = garmin_export_path()
    assert p is not None
    assert p.resolve() == target.resolve()
