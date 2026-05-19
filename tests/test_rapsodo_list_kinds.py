from __future__ import annotations

import json
from pathlib import Path

from golf_analysis.rapsodo_list_kinds import (
    find_repo_root,
    load_list_source_kind_map,
    load_session_ids_for_calendar_year,
)


def test_find_repo_root(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert find_repo_root(sub) == tmp_path.resolve()


def test_load_list_source_kind_map_v2(tmp_path: Path) -> None:
    (tmp_path / "data" / "raw" / "rapsodo").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "rapsodo" / "rapsodo_session_list.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sessions_merged": [
                    {"sessionid": "1", "_list_source_kind": "practice"},
                    {"sessionid": 2, "_list_source_kind": "combine"},
                    {"id": 99, "_list_source_kind": "courses"},
                ],
            }
        ),
        encoding="utf-8",
    )
    m = load_list_source_kind_map(tmp_path)
    assert m["1"] == "practice"
    assert m["2"] == "combine"
    assert m["99"] == "courses"


def test_load_session_ids_for_calendar_year(tmp_path: Path) -> None:
    (tmp_path / "data" / "raw" / "rapsodo").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "rapsodo" / "rapsodo_session_list.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sessions_merged": [
                    {"sessionid": "2026a", "startdate": "2026-01-02T00:00:00.000Z"},
                    {"sessionid": "2025x", "startdate": "2025-12-31T00:00:00.000Z"},
                    {"simulationid": "sim1", "startDate": "2026-06-01T00:00:00.000Z"},
                ],
            }
        ),
        encoding="utf-8",
    )
    ids = load_session_ids_for_calendar_year(tmp_path, 2026)
    assert ids == {"2026a", "sim1"}


def test_load_list_source_kind_map_missing(tmp_path: Path) -> None:
    assert load_list_source_kind_map(tmp_path) == {}


def test_rapsodo_ingest_sets_list_source_kind_not_practice_kind(tmp_path: Path) -> None:
    from golf_analysis.ingest import ingest_file

    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    raw = tmp_path / "data" / "raw" / "rapsodo"
    raw.mkdir(parents=True)
    (raw / "rapsodo_session_list.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sessions_merged": [{"sessionid": "5", "_list_source_kind": "combine"}],
            }
        ),
        encoding="utf-8",
    )
    (raw / "rapsodo_session_5.csv").write_text(
        "Club Type,Ball Speed,Carry\n7i,90,150\n",
        encoding="utf-8",
    )
    db = tmp_path / "lib.db"
    assert ingest_file(raw / "rapsodo_session_5.csv", db_path=db).error is None
    import sqlite3

    row = sqlite3.connect(str(db)).execute(
        "SELECT practice_kind, list_source_kind FROM range_sessions"
    ).fetchone()
    assert row[0] is None
    assert row[1] == "combine"
