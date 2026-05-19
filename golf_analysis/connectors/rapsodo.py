from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from golf_analysis.connectors.base import Connector
from golf_analysis.models import IngestPayload, RangeSession, RangeShot
from golf_analysis.rapsodo_list_kinds import find_repo_root, load_list_source_kind_map

_SESSION_ID_RE = re.compile(r"rapsodo_session_(\d+)\.csv$", re.IGNORECASE)

_SUMMARY_CLUB_MARKERS = frozenset(
    {"average", "median", "mean", "std", "stdev", "total", "subtotal", "min", "max", "sum"}
)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


# Map canonical field -> alternative header substrings (after normalization)
_ALIASES: dict[str, tuple[str, ...]] = {
    "club": ("club", "club name"),
    "ball_speed_mph": ("ball speed", "ballspeed", "ball vel"),
    "club_speed_mph": ("club speed", "clubspeed", "club head speed", "head speed"),
    "smash_factor": ("smash", "smash factor"),
    "launch_angle_deg": ("launch angle", "launch angle v", "v launch"),
    "launch_direction_deg": ("launch direction", "horizontal launch", "azimuth", "side angle"),
    "spin_rpm": ("spin rate", "back spin", "total spin", "spin"),
    "spin_axis_deg": ("spin axis", "tilt"),
    "carry_yards": ("carry", "carry dist", "carry distance"),
    "total_yards": ("total", "total dist", "total distance"),
    "apex_yards": ("apex", "max height", "peak height", "height"),
    "descent_angle_deg": ("descent", "descent angle"),
    "offline_yards": ("offline", "side carry", "lateral", "curve"),
    "attack_angle_deg": ("attack angle", "aoa"),
    "club_path_deg": ("club path", "path"),
    "face_to_path_deg": ("face to path", "face angle", "face to target"),
}


def _match_column(norm_headers: list[str], aliases: tuple[str, ...]) -> int | None:
    for i, h in enumerate(norm_headers):
        for a in aliases:
            if a in h or h == a:
                return i
    return None


def _build_column_map(headers: list[str]) -> dict[str, int]:
    norm = [_norm_header(h) for h in headers]
    out: dict[str, int] = {}
    for field, aliases in _ALIASES.items():
        idx = _match_column(norm, aliases)
        if idx is not None:
            out[field] = idx
    return out


def _decode_csv_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _float_cell(row: list[str], idx: int | None) -> float | None:
    if idx is None or idx >= len(row):
        return None
    raw = row[idx].strip()
    if not raw:
        return None
    raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _str_cell(row: list[str], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    s = row[idx].strip()
    return s or None


def _row_looks_like_lm_header(row: list[str]) -> bool:
    if not row or not any(c.strip() for c in row):
        return False
    first = _norm_header(row[0])
    if first == "club type" or first.startswith("club type"):
        return True
    cmap = _build_column_map(row)
    hits = sum(1 for k in ("ball_speed_mph", "club_speed_mph", "carry_yards", "total_yards") if k in cmap)
    return hits >= 2


def _find_header_row_index(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if _row_looks_like_lm_header(row):
            return i
    return 0


def _is_summary_or_junk_row(row: list[str], cmap: dict[str, int]) -> bool:
    club_raw = _str_cell(row, cmap.get("club")) if "club" in cmap else None
    club = (club_raw or "").strip().lower()
    if club == "club type":
        return True
    if club:
        if club in _SUMMARY_CLUB_MARKERS:
            return True
        if "average" in club or "median" in club:
            return True
        if "std" in club and "dev" in club:
            return True
    return False


def _csv_rows_from_text(text: str) -> list[list[str]]:
    return list(csv.reader(text.splitlines()))


class RapsodoCsvConnector(Connector):
    """CSV exports from R-Cloud, GSPro logs, or spreadsheets that list one shot per row."""

    id = "rapsodo_csv"

    def can_handle(self, path: Path) -> bool:
        if path.suffix.lower() != ".csv":
            return False
        try:
            text = _decode_csv_text(path)[:20000]
        except OSError:
            return False
        if "rapsodo" in text.lower():
            return True
        rows = _csv_rows_from_text(text)
        for row in rows[:80]:
            if _row_looks_like_lm_header(row):
                return True
        return False

    def ingest(self, path: Path) -> IngestPayload:
        warnings: list[str] = []
        text = _decode_csv_text(path)
        rows = _csv_rows_from_text(text)
        if not rows:
            return IngestPayload(warnings=["Empty CSV"])

        hdr_idx = _find_header_row_index(rows)
        if hdr_idx > 0:
            warnings.append(f"Using header row at index {hdr_idx} (skipped {hdr_idx} preamble row(s)).")

        headers = rows[hdr_idx]
        cmap = _build_column_map(headers)
        if len(cmap) < 2:
            warnings.append(
                "Few launch-monitor columns matched; check CSV headers or add aliases in rapsodo.py."
            )

        data_rows = rows[hdr_idx + 1 :]
        shots: list[RangeShot] = []
        mapped_indices = set(cmap.values())

        shot_counter = 0
        for row in data_rows:
            if not any(c.strip() for c in row):
                continue
            if _is_summary_or_junk_row(row, cmap):
                continue
            shot_counter += 1
            shot = RangeShot(shot_index=shot_counter)
            if "club" in cmap:
                shot.club = _str_cell(row, cmap["club"])
            for field in (
                "ball_speed_mph",
                "club_speed_mph",
                "smash_factor",
                "launch_angle_deg",
                "launch_direction_deg",
                "spin_rpm",
                "spin_axis_deg",
                "carry_yards",
                "total_yards",
                "apex_yards",
                "descent_angle_deg",
                "offline_yards",
                "attack_angle_deg",
                "club_path_deg",
                "face_to_path_deg",
            ):
                if field in cmap:
                    v = _float_cell(row, cmap[field])
                    setattr(shot, field, v)
            for j, h in enumerate(headers):
                if j >= len(row):
                    continue
                if j in mapped_indices:
                    continue
                cell = row[j].strip()
                if not cell:
                    continue
                label = h.strip()
                try:
                    shot.extra[label] = float(cell.replace(",", ""))
                except ValueError:
                    shot.extra[label] = cell

            shots.append(shot)

        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            mtime = datetime.now()

        practice_kind: str | None = None
        list_source_kind: str | None = None
        m = _SESSION_ID_RE.search(path.name)
        session_id_str: str | None = m.group(1) if m else None
        repo = find_repo_root(path.parent)
        if repo and session_id_str:
            list_source_kind = load_list_source_kind_map(repo).get(session_id_str)

        session = RangeSession(
            title=path.stem,
            started_at=mtime,
            venue=None,
            practice_kind=practice_kind,
            list_source_kind=list_source_kind,
            shots=shots,
            raw_headers=headers,
        )
        return IngestPayload(range_sessions=[session], warnings=warnings)
