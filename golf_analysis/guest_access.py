"""CLI: create / list / revoke guest dashboard access tokens."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from golf_analysis.api.access_tokens_store import (
    create_guest_token,
    list_guests,
    revoke_guest,
)
from golf_analysis.rapsodo_list_kinds import find_repo_root


def _dashboard_base_url() -> str | None:
    raw = os.environ.get("GOLF_CLOUD_RUN_URL", "").strip().rstrip("/")
    if raw:
        return raw
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Manage revocable guest URLs for the dashboard.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Create a new guest token")
    c.add_argument("--label", default="guest", help="Who this link is for (notes only)")

    sub.add_parser("list", help="List guest tokens (masked)")

    r = sub.add_parser("revoke", help="Revoke a guest token by id")
    r.add_argument("guest_id", help="Guest id from list/create output")

    args = p.parse_args(argv)

    if find_repo_root(Path.cwd()) is None:
        print("Run from the golf-analysis repo root.", file=sys.stderr)
        return 1

    if args.cmd == "create":
        row = create_guest_token(label=args.label)
        print(f"Created guest “{row['label']}” (id={row['id']})")
        print(f"Token: {row['token']}")
        base = _dashboard_base_url()
        if base:
            print(f"Share URL: {base}/?token={row['token']}")
        else:
            print("Share URL: https://YOUR-CLOUD-RUN-URL/?token=" + row["token"])
            print("(Set GOLF_CLOUD_RUN_URL in .env.cloud to print the full link.)")
        print(f"\nRevoke later: uv run golf-guest-token revoke {row['id']}")
        print("Then: ./scripts/push-dashboard-data.sh && ./scripts/deploy-cloud-run.sh --reload-only")
        return 0

    if args.cmd == "list":
        guests = list_guests()
        if not guests:
            print("No guest tokens.")
            return 0
        for g in guests:
            tok = str(g.get("token", ""))
            masked = f"{tok[:6]}…{tok[-4:]}" if len(tok) > 12 else "••••"
            print(f"{g.get('id')}  {g.get('label')!r}  {masked}  {g.get('created_at', '')}")
        return 0

    if args.cmd == "revoke":
        if revoke_guest(guest_id=args.guest_id):
            print(f"Revoked guest id={args.guest_id}")
            print("Push + reload Cloud Run for the change to apply on phone:")
            print("  ./scripts/push-dashboard-data.sh && ./scripts/deploy-cloud-run.sh --reload-only")
            return 0
        print(f"No guest with id={args.guest_id!r}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
