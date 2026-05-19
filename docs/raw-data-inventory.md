# Raw data inventory (Garmin + Rapsodo)

This document describes **what lives on disk before or beside SQLite**, how files are organized, and the **shape of the raw payloads** so you can design metrics and joins. For normalized columns in `data/library.db`, see [sqlite-library-schema.md](./sqlite-library-schema.md).

Fill in **Meaning (TBD)** cells where noted when you learn field semantics from Garmin / Rapsodo or device manuals.

---

## 1. Filesystem layout (typical)

| Path | Role |
|------|------|
| `data/library.db` | SQLite library produced by `golf-ingest ingest` (default `--db`). |
| `data/raw/garmin/*.fit`, `*.zip` | Garmin Connect **original** exports (binary FIT, often zipped). |
| `data/raw/garmin/golf-export.json` (or similar name) | Garmin **Golf Community**–style JSON from `garmin-golf-sync` or manual export. |
| `data/raw/rapsodo/rapsodo_session_list.json` | Rapsodo **session list snapshot** (multi-endpoint merge); **not** ingested as rows. |
| `data/raw/rapsodo/rapsodo_session_<id>.csv` | Per-session **shot CSV** from R-Cloud export URL. |

Config (not raw telemetry, but drives sync):

| Path | Role |
|------|------|
| `config/rapsodo-endpoints.json` | Rapsodo HTTP list/export URLs (often gitignored; see `config/rapsodo-endpoints.example.json` in repo). |

---

## 2. Garmin — Golf Community JSON (`golf-export.json`)

**Producer:** `golf-ingest garmin-golf-sync` (writes JSON) or equivalent export. **Ingest connector:** `garmin_golf_community` (see `golf_analysis/connectors/garmin_golf_community.py`).

### 2.1 Top-level object (expected keys)

| Key | Type | Meaning |
|-----|------|---------|
| `summary` | object | Must contain `scorecardSummaries` (list) for the file to be recognized. |
| `details` | list | One element per round / scorecard payload; each item wraps `scorecardDetails` → `scorecard`. |
| `shotDetails` | list (optional) | Per-shot rows; linked to a scorecard via `scorecardId`. |
| `clubs` | any (optional) | Club bag / summary blob; copied into round `extra_json` as `clubs_summary`. |
| `warnings` | list (optional) | Strings propagated into ingest warnings. |

### 2.2 Each `details[]` entry

Nested structure: `scorecardDetails[]` → objects with a **`scorecard`** object.

**`scorecard` (core round fields used by the parser)**

| Field (camelCase common) | Meaning |
|---------------------------|---------|
| `id` | Scorecard id (string/number); stored as `golf_rounds.extra_json.scorecard_id`. |
| `courseName` / `course_name` | Course label → `golf_rounds.course_name`. |
| `startTime`, `endTime` | ISO timestamps → `golf_rounds.started_at` / `ended_at`. |
| `holes` | List of hole dicts → `round_holes` rows (see below). |
| `totalScore` / `total_strokes`, `totalPutts`, `scoreRelativeToPar` / `relativeScore` | Promoted to `golf_rounds` columns when present. |
| `formattedStartTime` | Fallback for round title if course name missing. |

**Other `scorecard` keys:** preserved inside `golf_rounds.extra_json` under key **`scorecard`** (JSON-safe).

### 2.3 Each `holes[]` hole object

Mapped columns: `number` / `holeNumber`, `par`, `strokeIndex` / `handicapStrokeIndex`, `score` / `strokes`, `putts`, `fairwayHit`, `greenInRegulation`, `penaltyStrokes` / `penalties`, `yardage` / `yardageYards` (converted to **meters** in SQLite).

**All other non-null keys** on the hole dict are preserved in **`round_holes.extra_json`**.

### 2.4 `shotDetails[]` row (raw)

Each element is a dict. Parser indexes by **`scorecardId`** (string) and stores the full list for that scorecard under `golf_rounds.extra_json.garmin_golf_shot_details`.

| Field | Meaning |
|-------|---------|
| `scorecardId` | Join key to `scorecard.id`. |

**Additional fields:** vendor-specific (lie, distance to pin, club, coordinates, etc.). **Not** exploded into separate SQLite tables today — inspect JSON for metric design.

| Common / observed keys (examples) | Meaning (TBD) |
|-----------------------------------|-----------------|
| | *Add rows as you discover fields in your exports.* |

---

## 3. Garmin — FIT (`.fit` / `.zip`)

**Producer:** Garmin Connect “Export Original”, or `golf-ingest garmin-sync`. **Ingest connector:** `garmin_fit`.

FIT is **binary**. Messages of interest: **`sport`**, **`session`**, **`lap`**, **`record`**. Parsed with **python-fitparse**; field names follow FIT profile where known.

**Conceptual mapping:** laps → holes, records → GPS/time series. See [garmin-data-reference.md](./garmin-data-reference.md) for message-level detail and heuristics.

| Raw concept | SQLite target |
|-------------|----------------|
| One `.fit` (or each `.fit` inside a `.zip`) | One `golf_rounds` row (+ holes + track). |
| `lap` message fields | `round_holes` + `round_holes.extra_json`. |
| `record` message fields | `round_track_points` + `extra_json`. |
| `session` message fields | `golf_rounds.extra_json.session_fields` + promoted totals. |

---

## 4. Rapsodo — session list snapshot (`rapsodo_session_list.json`)

**Producer:** `golf-ingest rapsodo-sync`. **Not imported** as SQL rows; used at **CSV ingest** time to set `range_sessions.list_source_kind` and for offline analysis.

### 4.1 Schema version 2 (current)

| Key | Type | Meaning |
|-----|------|---------|
| `schema_version` | int | `2` for merged multi-source snapshots. |
| `fetched_at` | string | ISO timestamp when written. |
| `sources` | list | Per–list-endpoint fetch: `kind`, `url`, `pages` (each page: `skip`, `take`, `row_count`, `response`). |
| `stats` | object | `rows_total_before_dedupe`, `sessions_unique_after_dedupe`, `duplicate_session_ids`. |
| `sessions_merged` | list | Deduped session rows; each includes **`_list_source_kind`** (`practice`, `combine`, `courses`, `range`, …). |

### 4.2 Row shapes (varies by `_list_source_kind`)

**`practice` / `combine`** (from `session/user/list` API, `data` array in responses)

| Field (typical) | Meaning (partial) |
|-----------------|---------------------|
| `sessionid` | MLM session id (matches `rapsodo_session_<id>.csv`). |
| `startdate` | Session start (ISO string). |
| `numberOfShots`, `numberOfClub` | Counts (often strings in JSON). |
| `sessionType` | Rapsodo mode enum (e.g. outdoor vs indoor vs combine-related). |
| `algoType`, `algoMode` | Algorithm / indoor-outdoor hints. |
| `ballType`, `elevation`, `count` | |

**`courses`** (from `simulation/sessions`, `simulations` array)

| Field (typical) | Meaning |
|-----------------|---------|
| `id` | Simulation / round id (often **no** MLM CSV export at current URL template). |
| `courseName`, `startDate`, `gameType`, `scoreToPar`, `holesCompleted` | On-course sim metadata. |

**`range`** (simulation range games)

| Field (typical) | Meaning (TBD) |
|-----------------|-----------------|
| `sessionid` | Often present; CSV export may 404 with current template. |

---

## 5. Rapsodo — shot CSV (`rapsodo_session_<id>.csv`)

**Producer:** `rapsodo-sync` using `export_csv_url_template`, or manual download. **Ingest connector:** `rapsodo_csv`.

- **Encoding:** UTF-8 with or without BOM, or CP1252 fallback when reading.
- **Header row:** May be preceded by title rows (e.g. combine); parser finds the row that looks like LM headers (`Club Type` or enough launch-monitor columns).
- **Rows:** One data row ≈ one tracked shot; footer rows (`Average`, `Std. Dev.`, …) are skipped.

**Typical header columns** (exact names vary by export / indoor vs outdoor):

| Raw column (examples) | Mapped SQLite (`range_shots`) |
|----------------------|-------------------------------|
| Club Type / Club Name | `club` |
| Ball Speed | `ball_speed_mph` |
| Club Speed | `club_speed_mph` |
| Smash Factor | `smash_factor` |
| Launch Angle | `launch_angle_deg` |
| Launch Direction | `launch_direction_deg` |
| Spin Rate / Back Spin | `spin_rpm` |
| Spin Axis | `spin_axis_deg` |
| Carry / Total Distance | `carry_yards`, `total_yards` |
| Apex / Max Height | `apex_yards` |
| Descent Angle | `descent_angle_deg` |
| Side Carry / Offline | `offline_yards` |
| Attack Angle | `attack_angle_deg` |
| Club Path | `club_path_deg` |
| Face to Path / Face Angle | `face_to_path_deg` |

**Unmapped numeric/string columns** → `range_shots.extra_json` keyed by header label.

| Other raw columns you see | Meaning (TBD) |
|---------------------------|-----------------|
| | *Add as you catalog exports.* |

---

## 6. Cross-source linkage (for later frameworks)

There is **no shared primary key** between Garmin rounds and Rapsodo sessions today. Practical joins for metrics are usually:

- **Calendar date** (`golf_rounds.started_at`, `range_sessions.started_at` / file mtime),
- **`list_source_kind`** (and other fields from `rapsodo_session_list.json` joined by session id),
- Or future **user-defined session ids** in your own tables.

---

*Generated for analysis framework design; extend “TBD” rows as you validate fields in your own exports.*
