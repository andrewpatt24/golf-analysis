from __future__ import annotations

from pathlib import Path

from golf_analysis.connectors.garmin_fit import laps_to_holes, parse_fit_bytes
from golf_analysis.ingest import expand_paths, ingest_file
from golf_analysis.connectors.rapsodo import RapsodoCsvConnector


def test_expand_paths_nested(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.csv").write_text("h\n", encoding="utf-8")
    (tmp_path / "b.fit").write_bytes(b"\x00")
    out = expand_paths([tmp_path])
    assert len(out) == 2


def test_rapsodo_ingest_to_library(tmp_path: Path) -> None:
    csv_path = tmp_path / "session.csv"
    csv_path.write_text(
        "Club,Ball Speed (mph),Carry (yds),Spin Rate\n"
        "7-Iron,112,165,5200\n"
        "7-Iron,110,162,5350\n",
        encoding="utf-8",
    )
    db = tmp_path / "lib.db"
    result = ingest_file(csv_path, db_path=db)
    assert result.error is None
    assert not result.skipped_duplicate
    assert result.import_id is not None
    assert result.range_sessions == 1
    assert result.golf_rounds == 0
    result2 = ingest_file(csv_path, db_path=db)
    assert result2.skipped_duplicate


def test_rapsodo_combine_csv_skips_preamble_and_average(tmp_path: Path) -> None:
    """Combine exports often have a title row, blank line, then headers; footer may say Average."""

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "t"\n', encoding="utf-8")
    raw = tmp_path / "data" / "raw" / "rapsodo"
    raw.mkdir(parents=True)
    (raw / "rapsodo_session_list.json").write_text(
        '{"schema_version":2,"sessions_merged":[{"sessionid":"5226717","_list_source_kind":"combine"}]}',
        encoding="utf-8",
    )
    csv_body = (
        '"Rapsodo MLM2PRO: test",,,,,,,,,,,,,,,\n\n'
        '"Club Type","Club Brand","Club Model","Carry Distance","Total Distance","Ball Speed"\n'
        '"7i",,,"100.0","110.0","90.0"\n'
        '"Average",,,"100.0","110.0","90.0"\n'
    )
    p = raw / "rapsodo_session_5226717.csv"
    p.write_text(csv_body, encoding="utf-8")

    c = RapsodoCsvConnector()
    payload = c.ingest(p)
    assert len(payload.range_sessions[0].shots) == 1
    assert payload.range_sessions[0].shots[0].ball_speed_mph == 90.0
    assert payload.range_sessions[0].list_source_kind == "combine"
    assert any("preamble" in w for w in payload.warnings)


def test_rapsodo_connector_prefers_mapped_columns_for_extra() -> None:
    c = RapsodoCsvConnector()
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("Ball Speed,Carry,Notes\n80,100,test note\n")
        name = f.name
    p = Path(name)
    try:
        payload = c.ingest(p)
        shot = payload.range_sessions[0].shots[0]
        assert shot.ball_speed_mph == 80
        assert shot.carry_yards == 100
        assert shot.extra.get("Notes") == "test note"
    finally:
        p.unlink(missing_ok=True)


def test_garmin_laps_golf_scores() -> None:
    laps = [
        {"total_cycles": 4, "total_distance": 350.0, "total_timer_time": 600.0},
        {"total_cycles": 5, "total_distance": 410.0, "total_timer_time": 720.0},
    ]
    holes = laps_to_holes(laps, sport_is_golf=True)
    assert [h.score for h in holes] == [4, 5]


def test_parse_fit_bytes_invalid_header() -> None:
    payload = parse_fit_bytes(b"not a real fit", logical_name="dummy")
    assert not payload.rounds
    assert payload.warnings
    assert "Could not read FIT" in payload.warnings[0]
