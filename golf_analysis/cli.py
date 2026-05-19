from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from golf_analysis.ingest import expand_paths, ingest_paths
from golf_analysis.repository import connect, init_schema, library_stats


def _default_garth_home() -> Path:
    """Prefer ~/.garth, then ./.garth in cwd (e.g. after `garth login` from the repo)."""

    env = os.environ.get("GARTH_HOME")
    if env:
        return Path(env).expanduser()
    home = Path("~/.garth").expanduser()
    if home.is_dir():
        return home
    local = (Path.cwd() / ".garth").resolve()
    if local.is_dir():
        return local
    return home


def _default_import_roots() -> list[Path]:
    """Ensure ./data/raw exists with per-vendor folders, then scan the tree."""

    root = Path("data/raw")
    root.mkdir(parents=True, exist_ok=True)
    (root / "rapsodo").mkdir(exist_ok=True)
    (root / "garmin").mkdir(exist_ok=True)
    return [root.resolve()]


def _cmd_ingest(args: argparse.Namespace) -> int:
    raw_paths = list(args.paths) if args.paths else _default_import_roots()
    paths = expand_paths([Path(p) for p in raw_paths])
    if not paths:
        hint = (
            "Drop exports under ./data/raw/rapsodo (CSV) or ./data/raw/garmin (.fit / .zip), "
            "or pass explicit paths: golf-ingest ingest ~/Downloads/my-round.zip\n"
            "For Garmin Golf Community JSON: golf-ingest garmin-golf-sync --out ./data/raw/garmin/golf.json "
            "then golf-ingest ingest ./data/raw/garmin/golf.json"
        )
        print(f"No files found to import.\n{hint}", file=sys.stderr)
        return 1
    db_path = Path(args.db).expanduser().resolve()
    results = ingest_paths(paths, db_path=db_path)
    errors = 0
    for r in results:
        if r.error:
            print(f"[error] {r.path}: {r.error}", file=sys.stderr)
            errors += 1
            continue
        if r.skipped_duplicate:
            print(f"[skip]  {r.path} (duplicate)")
            continue
        warn = f" warnings={r.warnings}" if r.warnings else ""
        print(
            f"[ok]     {r.path} via {r.connector_id} "
            f"import_id={r.import_id} "
            f"range_sessions={r.range_sessions} rounds={r.golf_rounds}{warn}"
        )
    return 1 if errors else 0


def _cmd_info(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"No library at {db_path}", file=sys.stderr)
        return 1
    conn = connect(db_path)
    init_schema(conn)
    s = library_stats(conn)
    conn.close()
    print(f"Library: {db_path}")
    print(f"  imports:         {s.imports}")
    print(f"  range_sessions:  {s.range_sessions}")
    print(f"  range_shots:     {s.range_shots}")
    print(f"  golf_rounds:     {s.golf_rounds}")
    print(f"  round_holes:     {s.round_holes}")
    print(f"  track_points:    {s.track_points}")
    return 0


def _cmd_range_shots_report(args: argparse.Namespace) -> int:
    from golf_analysis.range_analysis import run_range_shots_report

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"No library at {db_path}", file=sys.stderr)
        return 1
    text = run_range_shots_report(db_path)
    out_path = getattr(args, "output", None)
    if out_path:
        Path(out_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text, encoding="utf-8")
        print(Path(out_path).resolve())
    else:
        print(text, end="")
    return 0


def _cmd_analysis_plan_report(args: argparse.Namespace) -> int:
    from golf_analysis.analysis_plan_report import run_analysis_plan_report

    db_path = Path(args.db).expanduser().resolve()
    gj = getattr(args, "garmin_json", None)
    garmin_path = Path(gj).expanduser().resolve() if gj else None
    calendar_year = None if getattr(args, "all_years", False) else int(args.year)
    text = run_analysis_plan_report(
        garmin_json=garmin_path,
        db_path=db_path,
        calendar_year=calendar_year,
    )
    out_path = getattr(args, "output", None)
    if out_path:
        Path(out_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text, encoding="utf-8")
        print(Path(out_path).resolve())
    else:
        print(text, end="")
    return 0


def _cmd_reveal_report(args: argparse.Namespace) -> int:
    from golf_analysis.executive_reveal_report import run_executive_reveal_report

    db_path = Path(args.db).expanduser().resolve()
    gj = getattr(args, "garmin_json", None)
    garmin_path = Path(gj).expanduser().resolve() if gj else None
    calendar_year = None if getattr(args, "all_years", False) else int(args.year)
    out = Path(args.output).expanduser().resolve()
    title = getattr(args, "title", None) or None
    path = run_executive_reveal_report(
        garmin_json=garmin_path,
        db_path=db_path,
        calendar_year=calendar_year,
        output=out,
        title=title,
    )
    print(path)
    return 0


def _cmd_dashboard_api(args: argparse.Namespace) -> int:
    import uvicorn

    db_path = Path(args.db).expanduser().resolve()
    os.environ["GOLF_LIBRARY_DB"] = str(db_path)
    host = str(args.host)
    port = int(args.port)
    reload = bool(getattr(args, "reload", False))
    uvicorn.run(
        "golf_analysis.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )
    return 0


def _cmd_garmin_sync(args: argparse.Namespace) -> int:
    try:
        from golf_analysis.sync.garmin_community import download_golf_activities
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 1
    garth_home = Path(args.garth_home).expanduser()
    out_dir = Path(args.out).expanduser()
    max_pages = None if getattr(args, "max_pages", 200) == 0 else args.max_pages
    try:
        paths = download_golf_activities(
            garth_home=garth_home,
            out_dir=out_dir,
            limit=args.limit,
            start=args.start,
            include_non_golf=args.all_activities,
            backfill=args.backfill,
            max_pages=max_pages,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[error] Garmin sync failed: {e}", file=sys.stderr)
        return 1
    for p in paths:
        print(f"[saved] {p}")
    if not paths:
        print(
            "No golf activities downloaded in this window. "
            "Try --all-activities to verify Connect returns data, or increase --limit.",
            file=sys.stderr,
        )
    if getattr(args, "also_ingest", False) and paths:
        db_path = Path(args.db).expanduser().resolve()
        results = ingest_paths(paths, db_path=db_path)
        for r in results:
            if r.error:
                print(f"[ingest error] {r.path}: {r.error}", file=sys.stderr)
            elif r.skipped_duplicate:
                print(f"[ingest skip]  {r.path}")
            else:
                print(f"[ingest ok]    {r.path} import_id={r.import_id}")
    return 0


def _cmd_garmin_golf_sync(args: argparse.Namespace) -> int:
    try:
        from golf_analysis.sync.garmin_golf_community import download_garmin_golf_export
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 1
    garth_home = Path(args.garth_home).expanduser()
    out = Path(args.out).expanduser()
    try:
        export = download_garmin_golf_export(
            garth_home=garth_home,
            out_path=out,
            max_scorecards=args.max_scorecards,
            skip_shots=args.skip_shots,
            pause_s=args.pause,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[error] Garmin golf community sync failed: {e}", file=sys.stderr)
        return 1

    summary = export.get("summary") if isinstance(export.get("summary"), dict) else {}
    summaries = summary.get("scorecardSummaries") or []
    n_details = len(export.get("details") or [])
    n_shots = len(export.get("shotDetails") or [])
    warnings = export.get("warnings") or []
    print(
        f"[ok] scorecard summaries: {len(summaries)}  "
        f"detail payloads: {n_details}  shot payloads: {n_shots}  "
        f"warnings: {len(warnings)}"
    )
    print(f"[saved] {out.resolve()}")
    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)

    if getattr(args, "also_ingest", False):
        db_path = Path(args.db).expanduser().resolve()
        results = ingest_paths([out], db_path=db_path)
        for r in results:
            if r.error:
                print(f"[ingest error] {r.path}: {r.error}", file=sys.stderr)
            elif r.skipped_duplicate:
                print(f"[ingest skip]  {r.path}")
            else:
                print(f"[ingest ok]    {r.path} import_id={r.import_id} rounds={r.golf_rounds}")
    return 0


def _cmd_rapsodo_sync(args: argparse.Namespace) -> int:
    try:
        from golf_analysis.sync.rapsodo_cloud import download_sessions_via_http, load_rapsodo_config
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 1
    config_path = Path(args.config).expanduser().resolve()
    cfg = load_rapsodo_config(config_path)
    out_dir = Path(args.out).expanduser()
    try:
        written, warnings, snapshot_path = download_sessions_via_http(cfg, out_dir=out_dir, config_path=config_path)
    except Exception as e:  # noqa: BLE001
        print(f"[error] Rapsodo sync failed: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)
    print(f"[saved] {snapshot_path.resolve()}")
    for p in written:
        print(f"[saved] {p}")
    if not written:
        print(
            "[info] No CSV files written this run; session list snapshot was still saved. See warnings above.",
            file=sys.stderr,
        )
    if getattr(args, "also_ingest", False) and written:
        db_path = Path(args.db).expanduser().resolve()
        results = ingest_paths(written, db_path=db_path)
        for r in results:
            if r.error:
                print(f"[ingest error] {r.path}: {r.error}", file=sys.stderr)
            elif r.skipped_duplicate:
                print(f"[ingest skip]  {r.path}")
            else:
                print(f"[ingest ok]    {r.path} import_id={r.import_id}")
    return 0


def _cmd_rapsodo_template(_args: argparse.Namespace) -> int:
    from golf_analysis.sync.rapsodo_cloud import default_endpoints_template

    print(default_endpoints_template())
    return 0


def _cmd_fit_inspect(args: argparse.Namespace) -> int:
    from golf_analysis.fit_inspect import inspect_path

    p = Path(args.path)
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                inspect_path(
                    p,
                    out=f,
                    sample_per_type=args.sample,
                    max_value_len=args.max_value_len,
                    record_stride=args.record_stride,
                )
        else:
            inspect_path(
                p,
                out=sys.stdout,
                sample_per_type=args.sample,
                max_value_len=args.max_value_len,
                record_stride=args.record_stride,
            )
    except (OSError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_fit_dump_json(args: argparse.Namespace) -> int:
    from golf_analysis.fit_inspect import dump_path_to_json_stream

    p = Path(args.path)
    indent = 2 if args.pretty else None
    try:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                dump_path_to_json_stream(
                    p,
                    out_stream=f,
                    omit_records=args.omit_records,
                    record_every=args.record_every,
                    indent=indent,
                )
        else:
            dump_path_to_json_stream(
                p,
                out_stream=sys.stdout,
                omit_records=args.omit_records,
                record_every=args.record_every,
                indent=indent,
            )
    except (OSError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="golf-ingest",
        description=(
            "Golf data: SQLite ingest, Garmin activity + golf-community sync, FIT tools, range analytics."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/library.db"),
        help="SQLite library path (default: ./data/library.db)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser(
        "ingest",
        help="Import files or directories (recursive). With no paths, scans ./data/raw.",
    )
    p_ingest.add_argument(
        "paths",
        nargs="*",
        type=Path,
        metavar="PATH",
        help="CSV / .fit / .zip / Garmin golf JSON export path or folders (default: ./data/raw)",
    )
    p_ingest.set_defaults(func=_cmd_ingest)

    p_info = sub.add_parser("info", help="Show row counts in the library")
    p_info.set_defaults(func=_cmd_info)

    p_rr = sub.add_parser(
        "range-shots-report",
        help="Summarize v1 LM range-shot cohort (Rapsodo practice+combine; excludes speed_training sim/course lists)",
    )
    p_rr.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write report to this path instead of stdout",
    )
    p_rr.set_defaults(func=_cmd_range_shots_report)

    p_ap = sub.add_parser(
        "analysis-plan-report",
        help="Garmin rounds + Rapsodo range report (default: calendar year 2026)",
    )
    p_ap.add_argument(
        "--garmin-json",
        type=Path,
        default=Path("data/raw/garmin/golf-export.json"),
        help="Garmin Golf Community export JSON (default: ./data/raw/garmin/golf-export.json)",
    )
    p_ap.add_argument(
        "--year",
        type=int,
        default=2026,
        metavar="YYYY",
        help="Calendar year for Garmin scorecards / last-10 SG filter and range sessions (default: 2026)",
    )
    p_ap.add_argument(
        "--all-years",
        action="store_true",
        help="Include all years (no calendar-year filters on Garmin or range shots)",
    )
    p_ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write report to this path instead of stdout",
    )
    p_ap.set_defaults(func=_cmd_analysis_plan_report)

    p_rv = sub.add_parser(
        "reveal-report",
        help="Write a Reveal.js HTML deck (Garmin rounds + Rapsodo training; default year 2026)",
    )
    p_rv.add_argument(
        "--garmin-json",
        type=Path,
        default=Path("data/raw/garmin/golf-export.json"),
        help="Garmin Golf Community export JSON (default: ./data/raw/garmin/golf-export.json)",
    )
    p_rv.add_argument(
        "--year",
        type=int,
        default=2026,
        metavar="YYYY",
        help="Calendar year for filters (default: 2026)",
    )
    p_rv.add_argument(
        "--all-years",
        action="store_true",
        help="Disable calendar-year filters",
    )
    p_rv.add_argument(
        "--title",
        type=str,
        default=None,
        help="Deck title (default: Golf executive — <year>)",
    )
    p_rv.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("docs/reports/golf-executive-deck.html"),
        help="Output HTML path (default: ./docs/reports/golf-executive-deck.html)",
    )
    p_rv.set_defaults(func=_cmd_reveal_report)

    p_dash = sub.add_parser(
        "dashboard-api",
        help="Run FastAPI JSON server for the dashboard (CORS for Vite dev on :5173)",
    )
    p_dash.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    p_dash.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port (default: 8000)",
    )
    p_dash.add_argument(
        "--reload",
        action="store_true",
        help="Dev auto-reload (watch Python files)",
    )
    p_dash.set_defaults(func=_cmd_dashboard_api)

    p_g = sub.add_parser(
        "garmin-sync",
        help="Download recent golf rounds from Garmin Connect (community client: garth-ng)",
    )
    p_g.add_argument(
        "--garth-home",
        type=Path,
        default=_default_garth_home(),
        help="Garth token directory (default: $GARTH_HOME, else ~/.garth, else ./.garth if present)",
    )
    p_g.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw/garmin"),
        help="Directory to write .zip/.fit exports",
    )
    p_g.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Activities per Garmin list request (includes all sports; we keep golf only). "
        "Use 100–200 with --backfill for fewer pages.",
    )
    p_g.add_argument(
        "--start",
        type=int,
        default=0,
        help="Starting offset into activity history (0 = most recent). Used as first page when backfilling.",
    )
    p_g.add_argument(
        "--backfill",
        action="store_true",
        help="Page through all older activities until history ends (uses --limit as page size).",
    )
    p_g.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Safety cap when --backfill (default 200 pages). Set 0 for no cap.",
    )
    p_g.add_argument(
        "--all-activities",
        action="store_true",
        help="Do not filter to golf only (for debugging)",
    )
    p_g.add_argument(
        "--also-ingest",
        action="store_true",
        help="After download, import files into the SQLite library (--db must precede subcommand)",
    )
    p_g.set_defaults(func=_cmd_garmin_sync)

    p_gg = sub.add_parser(
        "garmin-golf-sync",
        help=(
            "Download Garmin Golf Community export (scorecards, holes, shots, clubs) via garth-ng — "
            "same data as gsingers/garmin_golf bookmarklet"
        ),
    )
    p_gg.add_argument(
        "--garth-home",
        type=Path,
        default=_default_garth_home(),
        help="Garth token directory (default: $GARTH_HOME, else ~/.garth, else ./.garth if present)",
    )
    p_gg.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON path (e.g. ./data/raw/garmin/golf-export.json)",
    )
    p_gg.add_argument(
        "--max-scorecards",
        type=int,
        default=None,
        metavar="N",
        help="Only fetch the first N scorecards (for testing)",
    )
    p_gg.add_argument(
        "--skip-shots",
        action="store_true",
        help="Do not call per-hole shot endpoints (faster; smaller JSON)",
    )
    p_gg.add_argument(
        "--pause",
        type=float,
        default=0.15,
        help="Seconds to sleep between API calls (default: 0.15)",
    )
    p_gg.add_argument(
        "--also-ingest",
        action="store_true",
        help="After download, import the JSON into the SQLite library (--db before subcommand)",
    )
    p_gg.set_defaults(func=_cmd_garmin_golf_sync)

    p_r = sub.add_parser(
        "rapsodo-sync",
        help="Download R-Cloud CSVs using URLs from browser DevTools (see rapsodo-endpoints-template)",
    )
    p_r.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Endpoints JSON (session_list_sources or list_sessions_url; token in repo-root secrets.json)",
    )
    p_r.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw/rapsodo"),
        help="Directory for CSV exports and rapsodo_session_list.json (session metadata snapshot)",
    )
    p_r.add_argument(
        "--also-ingest",
        action="store_true",
        help="After download, import CSVs into the SQLite library (--db before subcommand)",
    )
    p_r.set_defaults(func=_cmd_rapsodo_sync)

    p_t = sub.add_parser(
        "rapsodo-endpoints-template",
        help="Print a JSON template for rapsodo-sync (paste URLs from R-Cloud DevTools)",
    )
    p_t.set_defaults(func=_cmd_rapsodo_template)

    p_fit = sub.add_parser(
        "fit-inspect",
        help="Print FIT message histogram + field samples (.fit or Garmin .zip export)",
    )
    p_fit.add_argument("path", type=Path, help="Path to .fit or .zip (original activity export)")
    p_fit.add_argument(
        "--sample",
        type=int,
        default=3,
        metavar="N",
        help="Sample payloads per non-record message type (default: 3)",
    )
    p_fit.add_argument(
        "--max-value-len",
        type=int,
        default=200,
        help="Truncate printed field values (default: 200)",
    )
    p_fit.add_argument(
        "--record-stride",
        type=int,
        default=50,
        help="Also print one record at this index (0 = skip mid sample)",
    )
    p_fit.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write report to this file instead of stdout",
    )
    p_fit.set_defaults(func=_cmd_fit_inspect)

    p_fdj = sub.add_parser(
        "fit-dump-json",
        help="Emit all FIT data messages as JSON (.fit or Garmin .zip); use --omit-records if huge",
    )
    p_fdj.add_argument("path", type=Path, help="Path to .fit or .zip (original activity export)")
    p_fdj.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write JSON to this file instead of stdout",
    )
    p_fdj.add_argument(
        "--omit-records",
        action="store_true",
        help="Skip GPS/time-series record messages (keeps laps, session, vendor messages, etc.)",
    )
    p_fdj.add_argument(
        "--record-every",
        type=int,
        default=1,
        metavar="N",
        help="If >1, keep every Nth record plus the last (default: 1 = all records)",
    )
    p_fdj.add_argument(
        "--pretty",
        action="store_true",
        help="Indent JSON (much larger; easier to read in an editor)",
    )
    p_fdj.set_defaults(func=_cmd_fit_dump_json)

    args = parser.parse_args()
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
