from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from golf_analysis.connectors.base import Connector, default_connectors, pick_connector
from golf_analysis.repository import (
    connect,
    existing_import_id,
    file_sha256,
    init_schema,
    insert_payload,
)


@dataclass
class IngestResult:
    path: Path
    connector_id: str | None
    skipped_duplicate: bool = False
    import_id: int | None = None
    range_sessions: int = 0
    golf_rounds: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def expand_paths(paths: list[Path]) -> list[Path]:
    """Expand directories to supported files (recursive)."""

    seen: set[Path] = set()
    out: list[Path] = []
    for raw in paths:
        p = raw.expanduser().resolve()
        if not p.exists():
            continue
        if p.is_dir():
            for pattern in ("**/*.csv", "**/*.fit", "**/*.zip"):
                for f in sorted(p.glob(pattern)):
                    if f.is_file() and f not in seen:
                        seen.add(f)
                        out.append(f)
        elif p.is_file():
            if p not in seen:
                seen.add(p)
                out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def ingest_file(
    path: Path,
    *,
    db_path: Path,
    connectors: list[Connector] | None = None,
) -> IngestResult:
    path = path.expanduser().resolve()
    c_list = connectors if connectors is not None else default_connectors()
    connector = pick_connector(path, c_list)
    if connector is None:
        return IngestResult(path=path, connector_id=None, error="No connector accepts this file type.")

    try:
        digest = file_sha256(path)
        size = path.stat().st_size
    except OSError as e:
        return IngestResult(path=path, connector_id=connector.id, error=str(e))

    conn = connect(db_path)
    init_schema(conn)
    if existing_import_id(conn, digest) is not None:
        conn.close()
        return IngestResult(
            path=path,
            connector_id=connector.id,
            skipped_duplicate=True,
            warnings=["Same file contents already imported (SHA-256 match)."],
        )

    try:
        payload = connector.ingest(path)
    except Exception as e:  # noqa: BLE001 — surface parse errors per file
        conn.close()
        return IngestResult(
            path=path,
            connector_id=connector.id,
            error=f"{type(e).__name__}: {e}",
        )

    if not payload.range_sessions and not payload.rounds:
        conn.close()
        return IngestResult(
            path=path,
            connector_id=connector.id,
            warnings=payload.warnings + ["Connector returned no sessions or rounds."],
        )

    try:
        import_id, n_rs, n_rr = insert_payload(
            conn,
            connector_id=connector.id,
            source_path=path,
            content_sha256=digest,
            file_size_bytes=size,
            payload=payload,
        )
    except Exception as e:  # noqa: BLE001
        conn.close()
        return IngestResult(
            path=path,
            connector_id=connector.id,
            error=f"database: {type(e).__name__}: {e}",
        )

    conn.close()
    return IngestResult(
        path=path,
        connector_id=connector.id,
        import_id=import_id,
        range_sessions=n_rs,
        golf_rounds=n_rr,
        warnings=list(payload.warnings),
    )


def ingest_paths(
    paths: list[Path],
    *,
    db_path: Path,
    connectors: list[Connector] | None = None,
) -> list[IngestResult]:
    return [ingest_file(p, db_path=db_path, connectors=connectors) for p in expand_paths(paths)]
