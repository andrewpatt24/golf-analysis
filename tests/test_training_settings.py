"""Training FLAG threshold and club exclusions."""

from __future__ import annotations

from golf_analysis.api.training_data import training_dispersion_settings


def test_training_dispersion_settings_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GOLF_DASHBOARD_SETTINGS", str(tmp_path / "settings.json"))
    thresh, excluded = training_dispersion_settings()
    assert thresh == 0.1
    assert excluded == set()
