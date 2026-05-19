from __future__ import annotations

import io
from pathlib import Path

import pytest

from golf_analysis.fit_inspect import (
    dump_fit_bytes_to_jsonable,
    dump_path_to_json_stream,
    inspect_fit_bytes,
    inspect_path,
)


def test_inspect_fit_bytes_invalid() -> None:
    buf = io.StringIO()
    inspect_fit_bytes(b"not a fit", label="bad", out=buf)
    out = buf.getvalue()
    assert "FitParseError" in out


def test_inspect_path_bad_suffix(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nope")
    with pytest.raises(ValueError, match="Expected .fit or .zip"):
        inspect_path(f, out=io.StringIO())


def test_dump_fit_bytes_parse_error() -> None:
    doc = dump_fit_bytes_to_jsonable(b"not a fit", label="bad")
    assert doc["fit_error"]
    assert doc["messages"] == []


def test_dump_path_bad_suffix(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nope")
    with pytest.raises(ValueError, match="Expected .fit or .zip"):
        dump_path_to_json_stream(f, out_stream=io.StringIO())
