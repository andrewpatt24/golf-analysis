"""Strip password fields before secrets are written to GCS."""

from __future__ import annotations

import copy
from typing import Any

# Keys never uploaded to Cloud Storage (repo secrets.json may still hold them locally).
_SENSITIVE_TOP_LEVEL = frozenset(
    {
        "rapsodo_email",
        "rapsodo_password",
        "garmin_email",
        "garmin_password",
        "garmin_totp_secret",
    }
)
_SENSITIVE_NESTED: dict[str, frozenset[str]] = {
    "rapsodo": frozenset({"email", "password"}),
    "garmin": frozenset({"email", "password", "totp_secret", "totp"}),
}


def sanitize_secrets_document(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to upload to GCS / serve from Cloud Run."""

    out = copy.deepcopy(data)
    for key in _SENSITIVE_TOP_LEVEL:
        out.pop(key, None)
    for block, keys in _SENSITIVE_NESTED.items():
        section = out.get(block)
        if not isinstance(section, dict):
            continue
        for k in keys:
            section.pop(k, None)
    return out
