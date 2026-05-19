# Project status: Garmin + Rapsodo (May 2026)

This note captures **where the repo stands**, **what was implemented recently**, and **sensible next steps**. For Garmin FIT and SQLite details, see [garmin-data-reference.md](./garmin-data-reference.md). For on-course methodology, see [on-course-analysis-methodology.md](./on-course-analysis-methodology.md).

---

## 1. Current state

### Data on disk (typical layout)

| Area | Location | Role |
|------|----------|------|
| Garmin golf export (JSON) | `data/raw/garmin/golf-export.json` (or similar) | Scorecard + shot payloads from Golf Community / Connect-style APIs. |
| Garmin FIT / zip | `data/raw/garmin/*.fit`, `*.zip` | Original exports for FIT inspection and FIT-based connectors. |
| Rapsodo raw | `data/raw/rapsodo/` | Per-session CSVs (`rapsodo_session_<id>.csv`) and **`rapsodo_session_list.json`** (merged session list snapshot). |
| SQLite library | `data/library.db` (default) | Imports from connectors (`golf-ingest`). |

### Configuration (local, partly gitignored)

| File | Tracked? | Purpose |
|------|----------|---------|
| `config/rapsodo-endpoints.json` | **gitignored** | Rapsodo list URLs, `session_list_sources`, export template, `extra_headers`, `authorization_scheme`. Copy from `config/rapsodo-endpoints.example.json`. |
| `config/rapsodo-endpoints.example.json` | yes | Example multi-source endpoints (practice + combine + simulation game types). |
| `secrets.json` (repo root) | **gitignored** | `rapsodo_bearer` JWT (raw token, no `JWT ` prefix). See `secrets.json.example`. |

### CLI entrypoints (high level)

- **Garmin golf community JSON:** `golf-ingest garmin-golf-sync` (Garth session + proxy URLs).
- **Rapsodo HTTP:** `golf-ingest rapsodo-sync --config … --out data/raw/rapsodo` (multi-list fetch, snapshot, optional CSV download).
- **Ingest:** `golf-ingest ingest` / `golf-ingest` with paths (CSV, FIT, zip, golf JSON).
- **FIT inspection:** `golf-ingest fit-inspect` (histograms / samples).

### Modelling assumptions

- **On-course Garmin:** primary source for rounds; methodology doc describes gates and SG caveats.
- **Rapsodo:** **`list_source_kind`** on `range_sessions` comes from merged **`_list_source_kind`** in `rapsodo_session_list.json` (per list URL / `kind` in config). Use that plus raw snapshot fields (e.g. `sessionType`) for analysis splits; no separate session-kinds config file.

---

## 2. What has been done (recent work)

### Rapsodo sync and metadata

- **Multi-source session lists:** `session_list_sources` in endpoints JSON — each `{ "kind", "url" }` is fetched with **pagination** (`skip` / `take`, capped by `list_max_pages`). Legacy single **`list_sessions_url`** still supported.
- **Merged snapshot:** `data/raw/rapsodo/rapsodo_session_list.json` is **schema v2**: `sources` (per-source paginated responses), **`sessions_merged`** (deduped by session id, each row tagged **`_list_source_kind`**), `stats` (counts, duplicate ids).
- **Auth:** JWT via **`authorization_scheme`: `"JWT"`** and token from **`secrets.json`** (`rapsodo_bearer`) or env `RAPSODO_BEARER`.
- **CSV export:** single `export_csv_url_template` (e.g. `…/session/{session_id}/details/export`). Session id resolution includes **`sessionid`** (R-Cloud list) and **`simulationid`** (guess for simulation rows).
- **CLI:** prints path to snapshot; warns if no CSVs written; `--out` help mentions snapshot file.

### Rapsodo → SQLite

- **`range_sessions.list_source_kind`** set from **`rapsodo_session_list.json`** `sessions_merged` when ingesting `rapsodo_session_*.csv` (repo root from `pyproject.toml`).
- **`range_sessions.practice_kind`** remains available for future non-Rapsodo use; **not** populated by the Rapsodo CSV connector.

### Garmin

- Golf Community JSON connector + `garmin-golf-sync` path (Garth, Referer / connect vs connectapi fallbacks) — working export to `golf-export.json`-shaped JSON and ingest.
- FIT tools (`fit-inspect`, `fit-dump-json` where present) and docs for raw vs Connect.

### Tests

- Rapsodo config validation, JWT/bearer resolution, snapshot writer, merge/dedupe, template JSON, connectors, Garmin community fixtures — see `tests/`.

---

## 3. Next steps (recommended order)

### Rapsodo

1. **Align local config with the example**  
   Ensure `config/rapsodo-endpoints.json` includes **`session_list_sources`** for all modes you care about (practice, combine, simulation `gameType`s). Re-run **`rapsodo-sync`** and confirm **`rapsodo_session_list.json`** contains expected sessions and **`_list_source_kind`** distribution.

2. **Export URL for simulation sessions**  
   If `…/session/{session_id}/details/export` fails for some **`_list_source_kind`** values, capture the correct CSV URL from DevTools for those modes and add **per-kind export templates** (code change: extend config + downloader).

3. **Re-ingest Rapsodo CSVs**  
   After updating endpoints or snapshot schema, re-run **`rapsodo-sync`** and **`golf-ingest ingest data/raw/rapsodo`** so `list_source_kind` matches the latest merge.

4. **Session list schema consumers**  
   Any ad-hoc scripts that read **v1** snapshot (`list_sessions_url` + `response` only) should be updated for **v2** (`sessions_merged`, `sources`).

### Garmin / analysis

5. **Continue on-course reports** from `golf-export.json` / library — document any new gates or SG dependencies alongside [on-course-analysis-methodology.md](./on-course-analysis-methodology.md).

6. **Cross-source analysis (later)**  
   Join practice (Rapsodo) to on-course (Garmin) by date/club or hand-built labels; no unified schema yet.

### Housekeeping

7. **Optional:** add **`docs/rapsodo-data-reference.md`** mirroring Garmin doc depth (field tables, snapshot schema, API caveats) once the multi-source export paths are stable.

8. **Pagination / API limits**  
   If Rapsodo throttles large `take`, lower **`default_list_take`** or per-URL `take=` and rely on more pages under **`list_max_pages`**.

---

## 4. Known limitations (short)

- **`sessionType`** in MLM list payloads is a **coarse mode** (correlates with indoor/outdoor and algo/ball enums in your snapshot); it does **not** fully encode “speed training vs combine vs main practice” without extra snapshot fields or ad-hoc analysis rules.
- **Jan 2025 speed-training dates** may not appear if they are outside the list query, deleted in cloud, or filtered; widening `session_list_sources` and pagination addresses **visibility**, not deleted history.
- **Rapsodo CSV** shot exports do not include session-level dates/types; use **`rapsodo_session_list.json`** for that.

---

*Last updated to reflect repo state as of this document’s addition.*
