"""Tests for Reveal.js executive HTML generator."""

from __future__ import annotations

from pathlib import Path

from golf_analysis.executive_reveal_report import build_executive_reveal_html, run_executive_reveal_report


def test_build_executive_reveal_html_minimal(tmp_path: Path) -> None:
    missing_db = tmp_path / "nope.db"
    html = build_executive_reveal_html(garmin_json=None, db_path=missing_db, calendar_year=2026)
    assert "reveal.js" in html
    assert "Reveal.initialize" in html
    assert "<section>" in html
    assert "Library DB not found" in html


def test_run_executive_reveal_report_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "deck.html"
    p = run_executive_reveal_report(
        garmin_json=None,
        db_path=tmp_path / "missing.db",
        calendar_year=2026,
        output=out,
        title="Test deck",
    )
    assert p == out.resolve()
    text = out.read_text(encoding="utf-8")
    assert "Test deck" in text
