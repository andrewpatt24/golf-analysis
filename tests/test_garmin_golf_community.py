from __future__ import annotations

import json
import shutil
from pathlib import Path

from golf_analysis.connectors.base import pick_connector
from golf_analysis.connectors.garmin_golf_community import (
    GarminGolfCommunityConnector,
    parse_garmin_golf_export,
)
from golf_analysis.ingest import ingest_file


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"


def test_parse_minimal_fixture_round() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = parse_garmin_golf_export(data)
    assert not payload.range_sessions
    assert len(payload.rounds) == 1
    rnd = payload.rounds[0]
    assert rnd.course_name == "Fixture Links"
    assert rnd.total_strokes == 8
    assert rnd.total_putts == 4
    assert rnd.score_relative_to_par == 2
    assert len(rnd.holes) == 2
    assert rnd.holes[0].hole_number == 1
    assert rnd.holes[0].score == 5
    assert rnd.holes[0].putts == 2
    assert str(rnd.extra.get("scorecard_id")) == "999001"
    assert rnd.extra.get("garmin_golf_shot_details")


def test_connector_pick_and_ingest(tmp_path: Path) -> None:
    dst = tmp_path / "export.json"
    shutil.copy(FIXTURE, dst)
    c = pick_connector(dst)
    assert isinstance(c, GarminGolfCommunityConnector)
    db = tmp_path / "lib.db"
    r = ingest_file(dst, db_path=db)
    assert r.error is None
    assert r.connector_id == "garmin_golf_community"
    assert r.golf_rounds == 1


def test_connector_rejects_random_json(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text('{"foo": 1}', encoding="utf-8")
    assert pick_connector(p) is None
