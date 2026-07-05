"""Detect whether local credential automation is allowed."""

from __future__ import annotations

import os


def is_cloud_runtime() -> bool:
    """True on Google Cloud Run (never run Playwright / password login there)."""

    return bool(os.environ.get("K_SERVICE", "").strip())


def local_auth_enabled() -> bool:
    """Local Mac/CLI only; disabled on Cloud Run and when explicitly turned off."""

    if is_cloud_runtime():
        return False
    flag = os.environ.get("GOLF_LOCAL_AUTH", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return True
