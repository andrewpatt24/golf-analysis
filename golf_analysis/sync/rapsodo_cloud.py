from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self
from urllib.parse import parse_qsl, urlparse, urlencode, urlunparse

from pydantic import BaseModel, Field, model_validator


class SessionListSource(BaseModel):
    """One session-list API URL (same auth headers as other MLM calls)."""

    url: str = Field(..., description="Full list URL from DevTools (may include skip/take; take is used for page size).")
    kind: str = Field(
        default="unknown",
        description="Stored on each row as _list_source_kind and in the snapshot (e.g. practice, combine, courses).",
    )


class RapsodoSyncConfig(BaseModel):
    """
    Fill this from browser DevTools (Network tab) after logging into R-Cloud.
    R-Cloud is a SPA; endpoints are not officially documented and can change.
    """

    list_sessions_url: str | None = Field(
        default=None,
        description="Single list URL (legacy). Use session_list_sources to query multiple game/mode endpoints.",
    )
    session_list_sources: list[SessionListSource] | None = Field(
        default=None,
        description="Fetch and merge sessions from each URL (practice + combine + simulation game types, etc.).",
    )
    bearer_token: str | None = Field(
        default=None,
        description="Optional inline raw token (discouraged). Prefer repo-root secrets.json (rapsodo_bearer) or RAPSODO_BEARER.",
    )
    authorization_scheme: str = Field(
        default="Bearer",
        description='Authorization scheme prefix. R-Cloud → mlm.rapsodo.com uses "JWT" (header looks like "Authorization: JWT eyJ...").',
    )
    cookie: str | None = Field(
        default=None,
        description="Optional raw Cookie header if R-Cloud uses cookie-based auth.",
    )
    extra_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Extra headers to mirror the browser (e.g. Origin, Referer, x-api-key).",
    )
    export_csv_url_template: str | None = Field(
        default=None,
        description="Optional URL template with {session_id} to download CSV per session.",
    )
    session_id_keys: tuple[str, ...] = Field(
        default=("sessionid", "simulationid", "_id", "id", "sessionId", "session_id", "SessionId"),
        description="Keys to try on each session object when resolving an id.",
    )
    list_max_pages: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Safety cap: max paginated GETs per session_list source.",
    )
    default_list_take: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Used when the list URL has no take= query param.",
    )

    @model_validator(mode="after")
    def _require_list_config(self) -> Self:
        if self.session_list_sources:
            return self
        if self.list_sessions_url and str(self.list_sessions_url).strip():
            return self
        raise ValueError("Set list_sessions_url or a non-empty session_list_sources array.")

    def resolved_list_sources(self) -> list[SessionListSource]:
        if self.session_list_sources:
            return list(self.session_list_sources)
        assert self.list_sessions_url and self.list_sessions_url.strip()
        return [SessionListSource(url=self.list_sessions_url.strip(), kind="list")]


def _template_format(template: str, session: dict[str, Any], id_keys: tuple[str, ...]) -> str:
    """Support {session_id} and a few common alternate placeholders."""

    sid = _session_id(session, id_keys)
    if sid is None:
        raise ValueError("Could not resolve session id for URL template")
    try:
        return template.format(session_id=sid, id=sid, sessionId=sid)
    except KeyError as e:
        raise ValueError(f"URL template {template!r} needs placeholders like {{session_id}}: {e}") from e


def _session_id(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if k in row and row[k] is not None:
            return str(row[k])
    return None


def _first_dict_list(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for v in obj.values():
            found = _first_dict_list(v)
            if found:
                return found
    return []


def load_rapsodo_config(path: Path) -> RapsodoSyncConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RapsodoSyncConfig.model_validate(raw)


def _repo_root(*, anchor_config_file: Path | None) -> Path | None:
    """Directory containing pyproject.toml, walking up from the config file's directory or cwd."""

    start = Path.cwd()
    if anchor_config_file is not None:
        start = anchor_config_file.resolve().parent
    for d in [start, *start.parents]:
        if (d / "pyproject.toml").is_file():
            return d
    return None


def _read_bearer_token_file(path: Path) -> str | None:
    """First non-empty, non-comment line from UTF-8 text file."""

    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return s
    return None


def _resolve_token_file_path(raw: str, *, config_path: Path | None) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    if config_path is not None:
        return (config_path.parent / p).resolve()
    return p.resolve()


def _rapsodo_bearer_from_secrets_json(config_path: Path | None) -> str | None:
    root = _repo_root(anchor_config_file=config_path)
    if root is None:
        return None
    path = root / "secrets.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("rapsodo_bearer")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _bearer_token_raw(cfg: RapsodoSyncConfig, *, config_path: Path | None) -> str | None:
    import os

    if cfg.bearer_token and cfg.bearer_token.strip():
        return cfg.bearer_token.strip()
    for key in ("RAPSODO_BEARER", "RAPSODO_BEARER_TOKEN"):
        v = os.environ.get(key)
        if v and v.strip():
            return v.strip()
    file_env = os.environ.get("RAPSODO_BEARER_FILE")
    if file_env and file_env.strip():
        path = _resolve_token_file_path(file_env.strip(), config_path=config_path)
        token = _read_bearer_token_file(path)
        if token:
            return token
        raise FileNotFoundError(f"RAPSODO_BEARER_FILE set but file missing or empty: {path}")
    token = _rapsodo_bearer_from_secrets_json(config_path)
    if token:
        return token
    return None


def _authorization_header_value(cfg: RapsodoSyncConfig, *, config_path: Path | None = None) -> str | None:
    token = _bearer_token_raw(cfg, config_path=config_path)
    if not token:
        return None
    scheme = (cfg.authorization_scheme or "Bearer").strip()
    return f"{scheme} {token.strip()}"


def _set_url_query(url: str, updates: dict[str, str | int]) -> str:
    parts = urlparse(url.strip())
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k, v in updates.items():
        q[k] = str(v)
    new_query = urlencode(q, doseq=True)
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))


def _effective_take(url: str, *, default_take: int) -> int:
    q = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    raw = q.get("take")
    if raw is not None and str(raw).strip().isdigit():
        return int(str(raw).strip())
    return default_take


def _fetch_paginated_list_rows(
    client: Any,
    base_url: str,
    *,
    max_pages: int,
    default_take: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Follow skip/take pagination until a page returns fewer than ``take`` rows or zero rows.

    Returns (all_row_dicts, page_records) where each page_record is
    {"skip": int, "take": int, "row_count": int, "response": ...}.
    """

    take = _effective_take(base_url, default_take=default_take)
    all_rows: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []

    for page_idx in range(max_pages):
        skip = page_idx * take
        page_url = _set_url_query(base_url, {"skip": skip, "take": take})
        r = client.get(page_url)
        r.raise_for_status()
        body = r.json()
        rows = _first_dict_list(body)
        pages.append({"skip": skip, "take": take, "row_count": len(rows), "response": body})
        all_rows.extend(rows)
        if not rows or len(rows) < take:
            break

    return all_rows, pages


def _merge_session_rows(
    labeled: list[tuple[str, dict[str, Any]]],
    *,
    session_id_keys: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """
    ``labeled`` is (list_kind, row) per row. Dedupe by first session id key hit; tag each row with _list_source_kind.

    Returns (merged_rows, duplicate_session_ids, warnings).
    """

    by_id: dict[str, dict[str, Any]] = {}
    dup_ids: list[str] = []
    warnings: list[str] = []

    for kind, row in labeled:
        row = dict(row)
        row["_list_source_kind"] = kind
        sid = _session_id(row, session_id_keys)
        if not sid:
            continue
        if sid in by_id:
            if sid not in dup_ids:
                dup_ids.append(sid)
            warnings.append(
                f"Session id {sid} appeared in multiple lists; keeping first occurrence, skipping duplicate from {kind!r}."
            )
            continue
        by_id[sid] = row

    merged = list(by_id.values())

    def sort_key(r: dict[str, Any]) -> tuple[str, str]:
        t = r.get("startdate") or r.get("startDate") or ""
        return (str(t), str(_session_id(r, session_id_keys) or ""))

    merged.sort(key=sort_key)
    return merged, dup_ids, warnings


def write_rapsodo_session_list_snapshot(
    out_dir: Path,
    *,
    sources_document: list[dict[str, Any]],
    sessions_merged: list[dict[str, Any]],
    rows_before_dedupe: int,
    duplicate_session_ids: list[str],
) -> Path:
    """Write ``rapsodo_session_list.json`` (schema v2) for offline metadata and analysis."""

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "schema_version": 2,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources_document,
        "stats": {
            "rows_total_before_dedupe": rows_before_dedupe,
            "sessions_unique_after_dedupe": len(sessions_merged),
            "duplicate_session_ids": duplicate_session_ids,
        },
        "sessions_merged": sessions_merged,
    }
    path = out_dir / "rapsodo_session_list.json"
    path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    return path


def download_sessions_via_http(
    cfg: RapsodoSyncConfig,
    *,
    out_dir: Path,
    config_path: Path | None = None,
) -> tuple[list[Path], list[str], Path]:
    """
    GET all configured session list URLs (paginated), merge, write ``rapsodo_session_list.json``,
    optionally GET each CSV from ``export_csv_url_template``.

    Returns (written_csv_paths, warnings, session_list_snapshot_path).
    """

    try:
        import httpx
    except ImportError as e:  # pragma: no cover
        raise ImportError("Rapsodo HTTP sync needs httpx. Install: uv sync --group sync") from e

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    headers: dict[str, str] = {
        "Accept": "application/json, text/plain, */*",
        **cfg.extra_headers,
    }
    auth_val = _authorization_header_value(cfg, config_path=config_path)
    if auth_val:
        headers["Authorization"] = auth_val
    if cfg.cookie:
        headers["Cookie"] = cfg.cookie

    sources_document: list[dict[str, Any]] = []
    labeled_flat: list[tuple[str, dict[str, Any]]] = []
    rows_before_dedupe = 0

    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        for src in cfg.resolved_list_sources():
            try:
                rows, pages = _fetch_paginated_list_rows(
                    client,
                    src.url.strip(),
                    max_pages=cfg.list_max_pages,
                    default_take=cfg.default_list_take,
                )
            except Exception as e:  # noqa: BLE001
                warnings.append(f"List fetch failed for kind={src.kind!r} url={src.url!r}: {e}")
                sources_document.append({"kind": src.kind, "url": src.url, "error": str(e), "pages": []})
                continue

            sources_document.append({"kind": src.kind, "url": src.url, "pages": pages})
            for row in rows:
                labeled_flat.append((src.kind, row))
            rows_before_dedupe += len(rows)

        merged, dup_ids, merge_warn = _merge_session_rows(labeled_flat, session_id_keys=cfg.session_id_keys)
        warnings.extend(merge_warn)

        snapshot_path = write_rapsodo_session_list_snapshot(
            out_dir,
            sources_document=sources_document,
            sessions_merged=merged,
            rows_before_dedupe=rows_before_dedupe,
            duplicate_session_ids=dup_ids,
        )

        if not merged:
            warnings.append("No session rows after list fetches — check session_list_sources / list_sessions_url.")
            return [], warnings, snapshot_path

        if not cfg.export_csv_url_template:
            warnings.append(
                "export_csv_url_template not set — only wrote session list snapshot; "
                "add CSV export URL from DevTools to download shots."
            )
            return [], warnings, snapshot_path

        written: list[Path] = []
        for row in merged:
            sid = _session_id(row, cfg.session_id_keys)
            if not sid:
                warnings.append(
                    f"Skipping merged row without id keys {cfg.session_id_keys}: {repr(row)[:200]}"
                )
                continue
            url = _template_format(cfg.export_csv_url_template, row, cfg.session_id_keys)
            cr = client.get(url, headers={**headers, "Accept": "text/csv,*/*"})
            if cr.status_code >= 400:
                warnings.append(f"CSV fetch failed {cr.status_code} for session {sid} ({row.get('_list_source_kind')})")
                continue
            text = cr.text
            if not text.strip():
                warnings.append(f"Empty CSV for session {sid}")
                continue
            safe = re.sub(r"[^\w.\-]+", "_", sid)[:120]
            path = out_dir / f"rapsodo_session_{safe}.csv"
            path.write_text(text, encoding="utf-8")
            written.append(path)

    return written, warnings, snapshot_path


def default_endpoints_template() -> str:
    """JSON template for users to save and edit after capturing URLs from DevTools."""

    sources = [
        {
            "kind": "practice",
            "url": "https://mlm.rapsodo.com/session/user/list?skip=0&take=200&type=0,%201,%202,%203",
        },
        {"kind": "combine", "url": "https://mlm.rapsodo.com/session/user/list?skip=0&take=200&type=4"},
        {
            "kind": "closest_to_pin",
            "url": "https://mlm.rapsodo.com/simulation/sessions?skip=0&take=200&gameType=4",
        },
        {
            "kind": "target_range",
            "url": "https://mlm.rapsodo.com/simulation/sessions?skip=0&take=200&gameType=2",
        },
        {"kind": "range", "url": "https://mlm.rapsodo.com/simulation/sessions?skip=0&take=200&gameType=1"},
        {
            "kind": "courses",
            "url": "https://mlm.rapsodo.com/simulation/sessions?skip=0&take=200&gameType=0,8,9",
        },
    ]
    sample: dict[str, Any] = {
        "session_list_sources": sources,
        "authorization_scheme": "JWT",
        "bearer_token": None,
        "cookie": "OPTIONAL_BROWSER_COOKIE_STRING_IF_NO_BEARER",
        "extra_headers": {
            "Origin": "https://golf-cloud.rapsodo.com",
            "Referer": "https://golf-cloud.rapsodo.com/",
            "os": "web",
        },
        "export_csv_url_template": "PASTE_URL_WITH_{session_id}_PLACEHOLDER",
        "session_id_keys": ["sessionid", "simulationid", "_id", "id", "sessionId", "session_id", "SessionId"],
        "list_max_pages": 100,
        "default_list_take": 200,
    }
    return json.dumps(sample, indent=2)
