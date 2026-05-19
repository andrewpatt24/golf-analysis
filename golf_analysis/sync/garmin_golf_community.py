from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from golf_analysis.sync.garmin_community import resume_garth_session

# Browser bookmarklet uses connect.garmin.com + /modern/proxy/...
# Garth can use the same path on ``connect`` (often needs a Connect ``Referer``).
# Fallback: ``connectapi`` may expose the same API without the ``/modern/proxy`` prefix.
_GOLF_PROXY_CONNECT = "/modern/proxy/gcs-golfcommunity/api/v2"
_GOLF_API_CONNECTAPI = "/gcs-golfcommunity/api/v2"


def _require_garth() -> Any:
    try:
        import garth
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Garmin golf community sync needs garth-ng. Install sync extras: uv sync --group sync"
        ) from e
    return garth


def _golf_request_json(client: Any, rel_path: str, *, params: dict[str, Any] | None = None) -> Any:
    """
    GET JSON from Garmin Golf Community APIs (authenticated Garth session).

    Tries ``connect.garmin.com`` proxy URL first (with a web ``Referer``), then
    ``connectapi.garmin.com`` direct path — Garmin has changed routing before.
    """

    if not rel_path.startswith("/"):
        rel_path = "/" + rel_path
    params = params or {}

    attempts: list[tuple[str, str, dict[str, str] | None]] = [
        (
            "connect",
            f"{_GOLF_PROXY_CONNECT}{rel_path}",
            {"referer": "https://connect.garmin.com/modern/home"},
        ),
        ("connectapi", f"{_GOLF_API_CONNECTAPI}{rel_path}", None),
        ("connectapi", f"{_GOLF_PROXY_CONNECT}{rel_path}", None),
    ]

    errors: list[str] = []
    for subdomain, full_path, extra_headers in attempts:
        try:
            resp = client.request(
                "GET",
                subdomain,
                full_path,
                api=True,
                params=params,
                headers=extra_headers,
            )
        except Exception as e:  # noqa: BLE001 — GarthHTTPError, etc.
            errors.append(f"{subdomain} {full_path}: {type(e).__name__}: {e}")
            continue

        if resp.status_code == 204:
            errors.append(f"{subdomain} {full_path}: HTTP 204 (no content)")
            continue

        raw = (resp.text or "").strip()
        if not raw:
            errors.append(
                f"{subdomain} {full_path}: empty body (HTTP {resp.status_code}, "
                f"content-type={resp.headers.get('Content-Type')!r})"
            )
            continue

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            snippet = raw[:500].replace("\n", " ")
            errors.append(
                f"{subdomain} {full_path}: not JSON (HTTP {resp.status_code}, "
                f"content-type={resp.headers.get('Content-Type')!r}): {snippet!r}"
            )

    raise RuntimeError(
        "Golf community HTTP response was not usable JSON. Tried:\n  "
        + "\n  ".join(errors)
        + "\nHint: confirm `garth login` against the same Garmin account that has "
        "Golf / scorecard data; if this persists, capture the failing URL in "
        "Connect DevTools (Network) while opening Golf Scorecards and open an issue "
        "with the path + status line."
    )


def download_garmin_golf_export(
    *,
    garth_home: Path,
    out_path: Path | None = None,
    max_scorecards: int | None = None,
    skip_shots: bool = False,
    pause_s: float = 0.15,
) -> dict[str, Any]:
    """
    Pull the same JSON surface as ``garmin_golf``'s ``garmin-download.js``:
    scorecard summary + per-card detail + per-hole shot payloads, plus club bag
    and last-10 shot stats.

    Writes ``out_path`` when given (UTF-8 JSON). Returns the export dict either way.
    """

    garth = _require_garth()
    resume_garth_session(garth_home)
    client = garth.client
    warnings: list[str] = []

    def pause() -> None:
        if pause_s > 0:
            time.sleep(pause_s)

    clubs: list[Any] = []
    last10_stats: Any = {}
    last10_drive: Any = {}
    last10_approach: Any = {}
    last10_chip: Any = {}
    last10_putt: Any = {}

    try:
        clubs = _golf_request_json(
            client,
            "/club/player",
            params={"per-page": "1000", "include-stats": "true"},
        )
        if not isinstance(clubs, list):
            clubs = []
    except Exception as e:  # noqa: BLE001
        warnings.append(f"club/player: {type(e).__name__}: {e}")
        clubs = []

    pause()

    def safe_get(rel: str, label: str) -> Any:
        try:
            return _golf_request_json(client, rel)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{label}: {type(e).__name__}: {e}")
            return {}

    last10_stats = safe_get("/player/stats", "player/stats")
    pause()
    last10_drive = safe_get("/shot/stats/drive", "shot/stats/drive")
    pause()
    last10_approach = safe_get("/shot/stats/approach", "shot/stats/approach")
    pause()
    last10_chip = safe_get("/shot/stats/chip", "shot/stats/chip")
    pause()
    last10_putt = safe_get("/shot/stats/putt", "shot/stats/putt")
    pause()

    summary = _golf_request_json(
        client,
        "/scorecard/summary",
        params={"per-page": "10000", "user-locale": "en"},
    )
    if not isinstance(summary, dict):
        raise ValueError(f"Unexpected scorecard/summary payload: {type(summary).__name__}")

    scorecard_summaries = summary.get("scorecardSummaries") or []
    if not isinstance(scorecard_summaries, list):
        scorecard_summaries = []

    if max_scorecards is not None:
        scorecard_summaries = scorecard_summaries[: max(0, max_scorecards)]

    details: list[dict[str, Any]] = []
    shot_rows: list[dict[str, Any]] = []

    for card in scorecard_summaries:
        if not isinstance(card, dict):
            continue
        sc_id = card.get("id")
        if sc_id is None:
            continue
        sc_id_str = str(sc_id)
        pause()
        card_details = _golf_request_json(
            client,
            "/scorecard/detail",
            params={
                "scorecard-ids": sc_id_str,
                "include-longest-shot-distance": "true",
            },
        )
        if not isinstance(card_details, dict):
            warnings.append(f"scorecard/detail id={sc_id_str}: unexpected {type(card_details).__name__}")
            continue

        merged = {
            "startTime": _get_scorecard_field(card_details, "startTime"),
            "formattedStartTime": _get_scorecard_field(card_details, "formattedStartTime"),
            **card_details,
        }
        details.append(merged)

        if skip_shots:
            continue

        holes = _get_scorecard_field(card_details, "holes")
        if not isinstance(holes, list):
            continue
        for hole in holes:
            if not isinstance(hole, dict):
                continue
            hole_no = hole.get("number") if hole.get("number") is not None else hole.get("holeNumber")
            if hole_no is None:
                continue
            pause()
            try:
                shot_payload = _golf_request_json(
                    client,
                    f"/shot/scorecard/{sc_id_str}/hole",
                    params={
                        "hole-numbers": str(hole_no),
                        "image-size": "IMG_730X730",
                    },
                )
            except Exception as e:  # noqa: BLE001
                warnings.append(f"shot/scorecard/{sc_id_str} hole={hole_no}: {type(e).__name__}: {e}")
                continue
            shot_rows.append(
                {
                    "scorecardId": sc_id_str,
                    "holeNumber": hole_no,
                    "response": shot_payload,
                }
            )

    export: dict[str, Any] = {
        "summary": summary,
        "details": details,
        "shotDetails": shot_rows,
        "clubs": clubs,
        "last10DataStats": last10_stats,
        "last10DataDrive": last10_drive,
        "last10DataApproach": last10_approach,
        "last10DataChip": last10_chip,
        "last10DataPutt": last10_putt,
        "warnings": warnings,
    }

    if out_path is not None:
        out_path = out_path.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(export, indent=2, default=str), encoding="utf-8")

    return export


def _get_scorecard_field(card_details: dict[str, Any], field: str) -> Any:
    """Match bookmarklet ``getCardField``."""

    details = card_details.get("scorecardDetails")
    if not isinstance(details, list):
        return None
    for el in details:
        if not isinstance(el, dict):
            continue
        sc = el.get("scorecard")
        if isinstance(sc, dict) and field in sc:
            return sc.get(field)
    return None
