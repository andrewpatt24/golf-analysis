"""Unit tests for Garmin export analytics helpers."""

from __future__ import annotations

import json
from pathlib import Path

from golf_analysis.garmin_export_analytics import (
    iter_scorecards,
    load_garmin_export,
    performance_round_rollups,
    scoring_method_proxy_metrics,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "garmin_golf_export_minimal.json"


def test_load_garmin_export_missing() -> None:
    assert load_garmin_export(None) is None
    assert load_garmin_export(Path("/nonexistent/no.json")) is None


def test_iter_scorecards_fixture_year_filter() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    rows_2026 = iter_scorecards(data, calendar_year=2026, limit=10)
    assert len(rows_2026) == 1
    assert rows_2026[0]["course_name"] == "Fixture Links"
    assert rows_2026[0]["strokes"] == 8
    rows_2025 = iter_scorecards(data, calendar_year=2025, limit=10)
    assert rows_2025 == []


def test_scoring_method_proxies_fixture() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    cards = iter_scorecards(data, calendar_year=2026, limit=10)
    sm = scoring_method_proxy_metrics(cards)
    assert sm["rounds"] == 1
    assert "esz_dsz_note" in sm
    pr = performance_round_rollups(cards)
    assert pr["rounds"] == 1
    assert pr["mean_strokes_per_round"] == 8.0
