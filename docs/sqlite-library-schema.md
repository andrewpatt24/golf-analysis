# SQLite library schema (`data/library.db`)

Default path is `./data/library.db` (override with `golf-ingest --db`). Schema is created/updated by `golf_analysis.repository.init_schema`.

**`imports.connector_id`** tells you which pipeline wrote a row:

| `connector_id` | Source |
|----------------|--------|
| `rapsodo_csv` | `rapsodo_session_*.csv` |
| `garmin_fit` | `.fit` / `.zip` (FIT binary) |
| `garmin_golf_community` | Golf Community–style `golf-export.json` |

**Deduplication:** one `imports` row per **`content_sha256`** of the **entire source file**; re-ingesting identical bytes is skipped.

---

## 1. `imports`

Provenance for every file ingested.

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key; referenced by child tables. |
| `connector_id` | TEXT | Parser / source system id (see table above). |
| `source_path` | TEXT | Absolute path to the file at import time. |
| `content_sha256` | TEXT | SHA-256 of raw file bytes; **UNIQUE**. |
| `imported_at` | TEXT | ISO-8601 UTC when imported. |
| `file_size_bytes` | INTEGER | File size in bytes. |

| Column | Meaning (TBD) |
|--------|----------------|
| | |

---

## 2. `range_sessions`

One row per **range / LM session** (one Rapsodo CSV file → one session today).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `import_id` | INTEGER FK → `imports.id` | Parent import; **ON DELETE CASCADE**. |
| `title` | TEXT | Usually CSV stem (e.g. `rapsodo_session_5955333`). |
| `started_at` | TEXT | ISO datetime; from file **mtime** at ingest (Rapsodo CSV has no session timestamp in-file). |
| `ended_at` | TEXT | |
| `venue` | TEXT | Not set by Rapsodo connector. |
| `notes` | TEXT | Not set by Rapsodo connector. |
| `practice_kind` | TEXT | Reserved for future connectors; **NULL** for Rapsodo CSV imports. Use **`list_source_kind`** for Rapsodo session type. |
| `list_source_kind` | TEXT | From `data/raw/rapsodo/rapsodo_session_list.json` `sessions_merged` (`practice`, `combine`, …) when snapshot present. |
| `raw_headers_json` | TEXT | JSON array of CSV header cell strings from the detected header row. |

| Column | Meaning (TBD) |
|--------|----------------|
| `ended_at` | |
| `venue` | Intended use for facility / bay name if you add it later. |

**Joining to raw Rapsodo metadata:** parse session id from `title` / `rapsodo_session_<id>.csv` pattern, then look up the same id in `rapsodo_session_list.json` for `startdate`, `algoMode`, etc.

---

## 3. `range_shots`

One row per **tracked shot** in a range session.

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `session_id` | INTEGER FK → `range_sessions.id` | Parent session; **ON DELETE CASCADE**. |
| `shot_index` | INTEGER | 1-based order within the CSV after parser skips preamble/summary rows. |
| `club` | TEXT | Club label from CSV (e.g. `7i`, `d`). |
| `ball_speed_mph` | REAL | Ball speed (mph). |
| `club_speed_mph` | REAL | Clubhead speed (mph). |
| `smash_factor` | REAL | Ball speed / club speed when both present. |
| `launch_angle_deg` | REAL | Vertical launch angle (degrees). |
| `launch_direction_deg` | REAL | Horizontal launch / starting direction (degrees). |
| `spin_rpm` | REAL | Spin rate (rpm); often absent on outdoor exports. |
| `spin_axis_deg` | REAL | Spin axis / tilt (degrees). |
| `carry_yards` | REAL | Carry distance (yards). |
| `total_yards` | REAL | Total distance (yards). |
| `apex_yards` | REAL | Apex / max height (yards in Rapsodo exports). |
| `descent_angle_deg` | REAL | Descent angle (degrees). |
| `offline_yards` | REAL | Lateral / side carry (yards) per export naming. |
| `attack_angle_deg` | REAL | Attack angle (degrees). |
| `club_path_deg` | REAL | Club path (degrees). |
| `face_to_path_deg` | REAL | Face-to-path or face angle (degrees) per header alias match. |
| `extra_json` | TEXT | JSON object: unmapped CSV columns keyed by header label. |

| Column | Meaning (TBD) |
|--------|----------------|
| `launch_direction_deg` | Sign convention (left/right) vs target line — confirm from Rapsodo docs. |
| `spin_axis_deg` | Exact definition (side spin vs tilt) — |
| `offline_yards` | Sign / unit confirmation if export uses meters in some modes. |

---

## 4. `golf_rounds`

One row per **on-course round** (Garmin FIT or Garmin Golf JSON).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `import_id` | INTEGER FK → `imports.id` | Parent import; **ON DELETE CASCADE**. |
| `title` | TEXT | FIT: logical file stem. JSON: course name or formatted start time. |
| `course_name` | TEXT | Course name when parser extracts it. |
| `started_at` | TEXT | ISO start time when available. |
| `ended_at` | TEXT | ISO end time when available. |
| `total_strokes` | INTEGER | Round strokes when inferred from totals or sum of holes. |
| `total_putts` | INTEGER | Sum of hole putts when enough holes have putts (JSON); FIT per connector rules. |
| `score_relative_to_par` | INTEGER | vs par total when present (**often NULL for FIT**). |
| `extra_json` | TEXT | Connector-specific JSON blob (see below). |

### 4.1 `golf_rounds.extra_json` by connector

**`garmin_golf_community`**

| JSON key | Meaning |
|----------|---------|
| `source` | Literal `garmin_golf_community`. |
| `scorecard_id` | Garmin scorecard id. |
| `garmin_golf_shot_details` | List of per-shot dicts from `shotDetails` for this scorecard. |
| `clubs_summary` | Optional `clubs` blob from top-level export. |
| `scorecard` | Full scorecard object as JSON-safe copy. |

**`garmin_fit`**

| JSON key | Meaning |
|----------|---------|
| `source_name` | Logical FIT name. |
| `sport`, `sub_sport` | FIT enums as strings. |
| `total_timer_time_s`, `total_distance_m` | Session-level totals when present. |
| `session_fields` | JSON-safe copy of merged FIT **session** message fields. |

| Other keys / fields | Meaning (TBD) |
|---------------------|----------------|
| | |

---

## 5. `round_holes`

One row per **hole** on a round (scorecard hole from JSON, or FIT lap heuristic).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `round_id` | INTEGER FK → `golf_rounds.id` | **ON DELETE CASCADE**. |
| `hole_number` | INTEGER | Hole index (1–18 typical). |
| `par` | INTEGER | Par when present. |
| `stroke_index` | INTEGER | Handicap stroke index when present (JSON path). |
| `score` | INTEGER | Strokes on hole. |
| `putts` | INTEGER | Putts on hole. |
| `fairway_hit` | INTEGER | `1` = true, `0` = false, `NULL` = unknown (JSON); FIT often NULL. |
| `green_in_regulation` | INTEGER | Same encoding as `fairway_hit`. |
| `penalty_strokes` | INTEGER | |
| `distance_meters` | REAL | Hole yardage from JSON (converted to meters); FIT: may be lap distance. |
| `duration_s` | REAL | FIT lap timer when present. |
| `extra_json` | TEXT | Remaining hole fields (JSON) or full lap field map (FIT). |

| Column | Meaning (TBD) |
|--------|----------------|
| | |

---

## 6. `round_track_points`

Time-ordered **GPS / sensor samples** for a round (FIT **record** messages mainly).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `round_id` | INTEGER FK → `golf_rounds.id` | **ON DELETE CASCADE**. |
| `seq` | INTEGER | 0-based sequence within round; **UNIQUE** with `round_id`. |
| `time` | TEXT | ISO timestamp from device when present. |
| `lat` | REAL | Latitude (degrees; converted from FIT semicircles). |
| `lon` | REAL | Longitude (degrees). |
| `altitude_m` | REAL | Altitude (meters) when present. |
| `distance_m` | REAL | Cumulative or segment distance when FIT provides `distance`. |
| `heart_rate` | INTEGER | BPM when present. |
| `extra_json` | TEXT | Other record fields JSON-safe (excludes duplicated lat/lon keys). |

**Garmin Golf JSON path:** `round_track_points` is typically **empty** (no track ingested from JSON today).

| Column | Meaning (TBD) |
|--------|----------------|
| `distance_m` | Exact semantics (lap vs cumulative) depends on device — |

---

## 7. Indexes

| Index | Table | Columns |
|-------|-------|---------|
| `idx_range_sessions_import` | `range_sessions` | `import_id` |
| `idx_range_shots_session` | `range_shots` | `session_id` |
| `idx_rounds_import` | `golf_rounds` | `import_id` |
| `idx_holes_round` | `round_holes` | `round_id` |
| `idx_track_round` | `round_track_points` | `round_id` |

---

## 8. Analysis cohorts (reference)

**Rapsodo LM v1 shot cohort** (implementation: `golf_analysis.range_analysis`):

- `imports.connector_id = 'rapsodo_csv'`
- `list_source_kind IN ('practice', 'combine')` **or** `list_source_kind IS NULL` (legacy ingests)

CLI: `golf-ingest range-shots-report`.

---

*Extend blank “TBD” rows as you lock definitions for metrics.*
