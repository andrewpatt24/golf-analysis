"""Static Reveal.js HTML deck: calendar-year rounds (Garmin) + range training (Rapsodo)."""

from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path
from typing import Any

from golf_analysis.analysis_plan_report import (
    dispersion_by_club,
    iter_last10_shots_with_sg,
    range_shot_rows_for_dispersion,
    scorecard_ids_for_calendar_year,
    scorecard_round_stats,
    summarize_last10_strokes_gained,
)
from golf_analysis.rapsodo_list_kinds import find_repo_root

_REVEAL_CSS = "https://cdn.jsdelivr.net/npm/reveal.js@5.0.4/dist/reveal.css"
_REVEAL_THEME = "https://cdn.jsdelivr.net/npm/reveal.js@5.0.4/dist/theme/white.css"
_REVEAL_JS = "https://cdn.jsdelivr.net/npm/reveal.js@5.0.4/dist/reveal.js"


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def build_executive_reveal_html(
    *,
    garmin_json: Path | None,
    db_path: Path,
    calendar_year: int | None = 2026,
    title: str | None = None,
) -> str:
    repo_root = find_repo_root(db_path.parent)
    year_label = "all years" if calendar_year is None else str(calendar_year)
    doc_title = title or f"Golf executive — {year_label}"

    garmin_data: dict[str, Any] | None = None
    garmin_err: str | None = None
    if garmin_json and garmin_json.is_file():
        try:
            garmin_data = json.loads(garmin_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            garmin_err = str(e)

    n_sc = 0
    mean_rel: float | None = None
    sc_count = 0
    sg_summary: dict[str, dict[str, float]] = {}
    sg_sample_n = 0
    sc_ids: set[str] | None = None
    if isinstance(garmin_data, dict):
        n_sc, mean_rel = scorecard_round_stats(garmin_data, calendar_year=calendar_year)
        if calendar_year is not None:
            sc_ids = scorecard_ids_for_calendar_year(garmin_data, calendar_year)
            sc_count = len(sc_ids)
        sg_summary = summarize_last10_strokes_gained(garmin_data, scorecard_ids=sc_ids)
        sg_sample_n = len(iter_last10_shots_with_sg(garmin_data, scorecard_ids=sc_ids))

    disp_rows: list[dict[str, Any]] = []
    shot_n = 0
    db_err: str | None = None
    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rshots = range_shot_rows_for_dispersion(
                conn,
                calendar_year=calendar_year,
                repo_root=repo_root,
            )
            shot_n = len(rshots)
            disp_rows = dispersion_by_club(rshots)
        finally:
            conn.close()
    else:
        db_err = f"Library DB not found: {db_path}"

    def sg_row(cat: str, label: str) -> str:
        s = sg_summary.get(cat, {})
        n = int(s.get("count", 0))
        if n == 0:
            return f"<tr><td>{_esc(label)}</td><td>—</td><td>—</td><td>—</td></tr>"
        return (
            f"<tr><td>{_esc(label)}</td><td>{n}</td>"
            f"<td>{s['sum_sg']:.3f}</td><td>{s['mean_sg']:.3f}</td></tr>"
        )

    ov = sg_summary.get("_overall", {})
    overall_tr = (
        f"<tr><td><strong>Combined</strong></td><td>{int(ov.get('count', 0))}</td>"
        f"<td>{ov.get('sum_sg', 0):.3f}</td><td>{ov.get('mean_sg', 0):.3f}</td></tr>"
    )

    club_rows_html = ""
    for row in disp_rows:
        flag = "Yes" if row["needs_work"] else ""
        rto = row["lateral_to_length_ratio"]
        rto_s = f"{rto:.3f}" if rto is not None else "—"
        std_o = row["std_offline_yards"]
        std_o_s = f"{std_o:.2f}" if std_o is not None else "—"
        club_rows_html += (
            f"<tr><td>{_esc(row['club'])}</td><td>{row['n']}</td>"
            f"<td>{row['mean_carry_yards']:.1f}</td>"
            f"<td>{row['std_carry_yards']:.2f}</td><td>{std_o_s}</td><td>{rto_s}</td>"
            f"<td>{_esc(flag)}</td></tr>\n"
        )
    if not club_rows_html:
        club_rows_html = (
            '<tr><td colspan="7"><em>No clubs met minimum shot count after filters.</em></td></tr>'
        )

    flagged = [r for r in disp_rows if r["needs_work"]]
    rec_li = ""
    if flagged:
        for r in sorted(flagged, key=lambda x: -x["n"]):
            rec_li += (
                f"<li><strong>{_esc(r['club'])}</strong> ({r['n']} shots): prioritize start-line "
                f"and face control; watch offline std ({r['std_offline_yards'] or 0:.1f} yd) "
                f"vs carry std ({r['std_carry_yards'] or 0:.1f} yd).</li>\n"
            )
    else:
        rec_li = "<li>No dispersion flags in this window — maintain tempo and baseline tracking.</li>"

    garmin_slides = ""
    if garmin_err:
        garmin_slides = f"<section><h2>Rounds (Garmin)</h2><p class=\"warn\">{_esc(garmin_err)}</p></section>"
    elif garmin_data is None:
        garmin_slides = (
            "<section><h2>Rounds (Garmin)</h2>"
            "<p>No export JSON provided or file missing.</p></section>"
        )
    else:
        mvp = f"{mean_rel:+.2f}" if mean_rel is not None else "—"
        caveat = (
            f"Last-10 SG rows are Garmin’s recent-window samples; only rows with "
            f"<code>scorecardId</code> tied to {year_label} scorecards are counted."
            if calendar_year is not None
            else "Last-10 SG rows are Garmin’s recent-window samples (not full history)."
        )
        garmin_slides = f"""
<section>
  <h2>Rounds — Garmin ({_esc(year_label)})</h2>
  <ul>
    <li>Scorecards in export ({_esc(year_label)}): <strong>{n_sc}</strong></li>
    <li>Mean vs par (where recorded): <strong>{_esc(mvp)}</strong></li>
    <li>Scorecards used for SG filter: <strong>{sc_count}</strong></li>
    <li>Sample shots with <code>strokesGained</code>: <strong>{sg_sample_n}</strong></li>
  </ul>
  <p class="small">{_esc(caveat)}</p>
</section>
<section>
  <h3>Strokes gained (sample)</h3>
  <table>
    <thead><tr><th>Category</th><th>n</th><th>Σ SG</th><th>Mean SG</th></tr></thead>
    <tbody>
      {sg_row("approach", "Approach")}
      {sg_row("around_the_green", "Around the green")}
      {overall_tr}
    </tbody>
  </table>
</section>
"""

    if db_err:
        training_slide = (
            f"<section><h2>Training — Rapsodo</h2><p class=\"warn\">{_esc(db_err)}</p></section>"
        )
    else:
        filt = (
            "Session year from <code>rapsodo_session_list.json</code> start dates, "
            "or <code>started_at</code> fallback."
            if calendar_year is not None
            else "All sessions (no calendar filter)."
        )
        training_slide = f"""
<section>
  <h2>Training — Rapsodo ({_esc(year_label)})</h2>
  <ul>
    <li>Shots in cohort after year filter: <strong>{shot_n}</strong></li>
    <li>{_esc(filt)}</li>
  </ul>
</section>
<section>
  <h3>Dispersion by club</h3>
  <small>FLAG = lateral dispersion vs length dispersion rules (see analysis-plan report).</small>
  <table class="dense">
    <thead>
      <tr>
        <th>Club</th><th>n</th><th>Mean carry</th><th>σ carry</th><th>σ offline</th><th>Lat/len</th><th>FLAG</th>
      </tr>
    </thead>
    <tbody>{club_rows_html}</tbody>
  </table>
</section>
<section>
  <h2>Next range session</h2>
  <ul>{rec_li}</ul>
</section>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(doc_title)}</title>
  <link rel="stylesheet" href="{_REVEAL_CSS}" />
  <link rel="stylesheet" href="{_REVEAL_THEME}" />
  <style>
    .reveal table {{ font-size: 0.55em; }}
    .reveal table.dense td, .reveal table.dense th {{ padding: 0.2em 0.35em; }}
    .reveal .small {{ font-size: 0.65em; opacity: 0.9; }}
    .reveal .warn {{ color: #a33; }}
    .reveal h1 {{ text-transform: none; }}
  </style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
      <section>
        <h1>{_esc(doc_title)}</h1>
        <p>Rounds + launch-monitor practice</p>
        <p><small>Generated locally — open this file in a browser.</small></p>
      </section>
      {garmin_slides}
      {training_slide}
      <section>
        <h2>Data sources</h2>
        <ul>
          <li>Garmin Golf Community JSON (scorecards, last-10 SG samples)</li>
          <li>SQLite library + Rapsodo CSV cohort rules</li>
        </ul>
      </section>
    </div>
  </div>
  <script src="{_REVEAL_JS}"></script>
  <script>
    Reveal.initialize({{ hash: true, slideNumber: true, transition: "slide" }});
  </script>
</body>
</html>
"""


def run_executive_reveal_report(
    *,
    garmin_json: Path | None,
    db_path: Path,
    calendar_year: int | None = 2026,
    output: Path,
    title: str | None = None,
) -> Path:
    html_out = build_executive_reveal_html(
        garmin_json=garmin_json,
        db_path=db_path,
        calendar_year=calendar_year,
        title=title,
    )
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_out, encoding="utf-8")
    return output
