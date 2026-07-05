"""Data source refresh runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from golf_analysis.data_sources.paths import DataPaths
from golf_analysis.data_sources.refresh_runner import refresh_source, source_status
from golf_analysis.repository import connect, init_schema


@pytest.fixture()
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DataPaths:
    db = tmp_path / "lib.db"
    conn = connect(db)
    init_schema(conn)
    conn.close()
    raw = tmp_path / "raw"
    (raw / "rapsodo").mkdir(parents=True)
    (raw / "garmin").mkdir(parents=True)
    monkeypatch.setenv("GOLF_LIBRARY_DB", str(db))
    monkeypatch.setenv("GOLF_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GOLF_GARMIN_JSON", str(raw / "garmin" / "golf-export.json"))
    from golf_analysis.data_sources.paths import resolve_data_paths

    return resolve_data_paths()


def test_local_ingest_empty(paths: DataPaths) -> None:
    r = refresh_source("local_ingest", paths)
    assert r.ok is True
    assert "No files" in r.message


def test_source_status_includes_all(paths: DataPaths) -> None:
    rows = source_status(paths)
    ids = {row["id"] for row in rows}
    assert ids == {"rapsodo", "garmin_golf", "garmin_fit", "local_ingest"}


def test_rapsodo_not_configured(
    paths: DataPaths, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    (empty / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    monkeypatch.chdir(empty)
    r = refresh_source("rapsodo", paths)
    assert r.ok is False
    assert r.error
