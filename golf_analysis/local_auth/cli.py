"""CLI: ``uv run local-auth-login`` (local machine only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from golf_analysis.local_auth import LocalAuthError, ensure_garth_session, ensure_rapsodo_bearer
from golf_analysis.local_auth.runtime import is_cloud_runtime, local_auth_enabled
from golf_analysis.rapsodo_list_kinds import find_repo_root


def main(argv: list[str] | None = None) -> int:
    if is_cloud_runtime():
        print("local-auth-login cannot run on Cloud Run.", file=sys.stderr)
        return 1
    if not local_auth_enabled():
        print("Local auth is disabled (GOLF_LOCAL_AUTH=0).", file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(
        description="Log in to Rapsodo (Playwright) and/or Garmin (garth) using secrets.json credentials."
    )
    p.add_argument("--rapsodo", action="store_true", help="Refresh Rapsodo JWT only")
    p.add_argument("--garmin", action="store_true", help="Refresh Garmin Garth tokens only")
    p.add_argument(
        "--garth-dir",
        type=Path,
        default=None,
        help="Garth token directory (default: <repo>/data/garth)",
    )
    p.add_argument("--no-headless", action="store_true", help="Show browser window for Rapsodo login")
    p.add_argument("--force", action="store_true", help="Re-login even if tokens already exist")
    args = p.parse_args(argv)

    do_rapsodo = args.rapsodo or not (args.rapsodo or args.garmin)
    do_garmin = args.garmin or not (args.rapsodo or args.garmin)

    root = find_repo_root(Path.cwd())
    if root is None:
        print("Run from the golf-analysis repo root.", file=sys.stderr)
        return 1

    garth_dir = args.garth_dir or (root / "data" / "garth")

    try:
        if do_rapsodo:
            token = ensure_rapsodo_bearer(headless=not args.no_headless, force=args.force)
            print(f"Rapsodo JWT saved ({len(token)} chars) → secrets.json + dashboard_secrets bearer")
        if do_garmin:
            path = ensure_garth_session(garth_dir, force=args.force)
            print(f"Garmin Garth tokens saved → {path}")
    except LocalAuthError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
