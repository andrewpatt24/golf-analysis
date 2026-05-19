"""Integration: ingest Rapsodo CSV + snapshot, then range-shots-report cohort."""

from __future__ import annotations

import json
from pathlib import Path

from golf_analysis.ingest import ingest_file
from golf_analysis.range_analysis import run_range_shots_report


def test_range_shots_report_after_ingest(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "t"\n', encoding="utf-8")
    raw = tmp_path / "data" / "raw" / "rapsodo"
    raw.mkdir(parents=True)
    (raw / "rapsodo_session_list.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sessions_merged": [
                    {"sessionid": "7", "_list_source_kind": "practice"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (raw / "rapsodo_session_7.csv").write_text(
        "Club Type,Ball Speed (mph),Carry Distance\n"
        "7i,90,150\n"
        "7i,92,155\n",
        encoding="utf-8",
    )
    db = tmp_path / "lib.db"
    r = ingest_file(raw / "rapsodo_session_7.csv", db_path=db)
    assert r.error is None
    assert r.range_sessions == 1
    text = run_range_shots_report(db)
    assert "Shots in cohort: 2" in text
    assert "practice" in text
