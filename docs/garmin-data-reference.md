# Garmin data reference (raw FIT → SQLite)

Human-oriented notes for **Garmin on-course golf** data in this project: what the **raw export** looks like, how it is **interpreted**, and how it lands in **SQLite**.

Default library path: `data/library.db` (configurable via `golf-ingest --db`).

---

## 1. Raw data (what you download from Garmin)

### 1.1 How files arrive here

- **Garmin Connect** → activity → **Export Original** usually gives a **`.zip`**.
- That zip contains one or more **`.fit`** files (ANT / Garmin binary activity format).
- Community sync (`garmin-sync`) writes the same bytes under `data/raw/garmin/` (often `*.zip`).

### 1.2 What a `.fit` file is (conceptually)

A FIT file is a **binary stream of typed messages**, not CSV. Common message types for a round include:

| Message (FIT) | Typical role for golf |
|---------------|------------------------|
| **sport** | Declares sport (e.g. `golf`) and sub-sport. |
| **session** | One summary for the whole activity: start time, optional name, totals, etc. |
| **lap** | Often **one lap per hole** (or per segment, depending on device/software). Carries per-segment distance, time, and sometimes stroke-like counters. |
| **record** | Time series **track points** (GPS position, altitude, heart rate, …) when the device recorded them. |

Official binary layout and field IDs are defined in Garmin’s **FIT SDK** (see [FIT overview](https://developer.garmin.com/fit/overview/)). This repo parses FIT with **python-fitparse** (`fitparse`), which maps fields to names where possible.

### 1.3 Zip vs single FIT

- If the export is **`.zip`**, we read every `*.fit` inside and treat each as its own activity (usually one round per file for golf).
- If the export is a **single `.fit`**, we parse that file directly.

### 1.4 Important limitations (raw side)

- **Vendor-specific fields** (e.g. some scorecard details) may appear only in **developer data** or newer profile fields; fitparse’s bundled profile may not name every field your watch writes.
- **Laps are not always 18 holes** in edge cases (incomplete round, multi-session file, non-golf activity mis-tagged). The database stores whatever laps/records the file contains after our heuristics.

---

## 2. How we turn FIT into “logical” golf data

Implementation: `golf_analysis/connectors/garmin_fit.py` (`parse_fit_bytes`).

### 2.1 Round (`GolfRound`)

- **Title**: derived from the file name (e.g. zip stem), not necessarily the course name.
- **Course name**: from session fields `name` or `sport_profile_name` when present.
- **Times**: `started_at` / `ended_at` from session `start_time` / `timestamp` when present.
- **Totals**:
  - `total_strokes`: from session `total_cycles` when sport is golf and value looks like a full-round stroke total, **or** sum of per-hole scores when we have enough hole rows.
  - `total_putts`: sum of per-hole putts when at least nine holes have putt values.
  - `score_relative_to_par`: not populated today (`NULL` in SQLite).

### 2.2 Holes (`RoundHole` per lap)

Each FIT **lap** becomes one `RoundHole` row (heuristic mapping):

| Column | Source / rule |
|--------|----------------|
| `hole_number` | Prefer keys whose names look like hole number; else FIT `message_index` if 1–18; else **lap index + 1**. |
| `score` | For sport **golf**, `total_cycles` on the lap when it looks like a hole score (1–20). |
| `putts` | Any lap field whose **name contains `"putt"`** with a small integer value. |
| `par` | Any field named like `par` / `*_par` with value 3–6. |
| `distance_meters` | Lap `total_distance` (meters in FIT). |
| `duration_s` | Lap `total_timer_time` or `total_elapsed_time` (seconds). |
| `fairway_hit`, `green_in_regulation`, `penalty_strokes`, `stroke_index` | Not filled from standard lap fields today (`NULL`). |
| `extra_json` | **Full lap field map** (JSON-safe): preserves unknown or device-specific keys for later analysis. |

### 2.3 Track (`RoundTrackPoint` per `record`)

Each FIT **record** with position or timestamp becomes a track point (capped at **25,000** points per round; beyond that we truncate and record a warning):

| Column | Source |
|--------|--------|
| `time` | `timestamp` |
| `lat` / `lon` | `position_lat` / `position_long` (semicircles → degrees) |
| `altitude_m`, `distance_m`, `heart_rate` | Same-named record fields when present |
| `extra_json` | Other record fields (JSON-safe) |

### 2.4 Round-level JSON (`golf_rounds.extra_json`)

Stored as a single JSON object, typically including:

- `source_name` — logical file name used when parsing.
- `sport`, `sub_sport` — stringified enums from FIT.
- `total_timer_time_s`, `total_distance_m` — session-level totals when present.
- `session_fields` — JSON-safe dump of merged **session** message fields (useful for fields we do not promote to columns).

---

## 3. SQLite layout (Garmin-related tables)

All Garmin rounds use connector id **`garmin_fit`** in `imports`. Range / launch-monitor data uses other tables (`range_sessions`, `range_shots`); Garmin golf does **not** populate those.

### 3.1 Entity relationship (Garmin path)

```
imports (one row per unique file content)
   └── golf_rounds (one row per parsed FIT activity in that file)
          ├── round_holes (one row per FIT lap after normalization)
          └── round_track_points (one row per GPS/time-series sample, ordered by seq)
```

### 3.2 `imports`

One row per **unique file** ingested (dedupe by SHA-256 of file bytes).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `connector_id` | TEXT | Always `garmin_fit` for Connect exports handled by this connector. |
| `source_path` | TEXT | Absolute path to the `.zip` or `.fit` at import time. |
| `content_sha256` | TEXT | SHA-256 of raw file bytes; **unique** — re-importing the same file skips. |
| `imported_at` | TEXT | ISO-8601 UTC timestamp when ingested. |
| `file_size_bytes` | INTEGER | File size on disk. |

### 3.3 `golf_rounds`

One row per **round / activity** (one primary FIT activity per import file in the common case).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `import_id` | INTEGER FK | Parent `imports.id`. |
| `title` | TEXT | Usually the stem of the FIT / inner file name. |
| `course_name` | TEXT | From FIT session when available. |
| `started_at` | TEXT | ISO-8601 session start when parsed. |
| `ended_at` | TEXT | ISO-8601 session end when parsed. |
| `total_strokes` | INTEGER | See §2.1; may be `NULL` if not inferable. |
| `total_putts` | INTEGER | Sum of hole putts when enough holes have putts; else `NULL`. |
| `score_relative_to_par` | INTEGER | Not used yet (`NULL`). |
| `extra_json` | TEXT | JSON object; see §2.4. |

### 3.4 `round_holes`

One row per **lap** after mapping (intended to align with **holes** for a full round).

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `round_id` | INTEGER FK | `golf_rounds.id`. |
| `hole_number` | INTEGER | Inferred hole index (see §2.2). |
| `par` | INTEGER | When a par-like field exists (3–6). |
| `stroke_index` | INTEGER | Not populated (`NULL`). |
| `score` | INTEGER | Strokes for the hole when inferred. |
| `putts` | INTEGER | When a putt-like field exists. |
| `fairway_hit` | INTEGER | `NULL`, `0`, or `1` (boolean); Garmin path usually `NULL`. |
| `green_in_regulation` | INTEGER | Same; usually `NULL`. |
| `penalty_strokes` | INTEGER | Usually `NULL`. |
| `distance_meters` | REAL | Lap distance (m). |
| `duration_s` | REAL | Lap duration (s). |
| `extra_json` | TEXT | JSON object: **all** lap fields we saw (names from fitparse), JSON-safe. |

**Human check:** if you expect 18 holes but see **one** `round_holes` row, the FIT laps did not split per hole the way we assume—inspect `extra_json` and compare with Garmin Connect’s scorecard.

### 3.5 `round_track_points`

Time-ordered samples for mapping / analysis.

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | Surrogate key. |
| `round_id` | INTEGER FK | `golf_rounds.id`. |
| `seq` | INTEGER | Zero-based order within the round (**unique** with `round_id`). |
| `time` | TEXT | ISO-8601 when present. |
| `lat`, `lon` | REAL | WGS-84 degrees when GPS present. |
| `altitude_m` | REAL | Meters when present. |
| `distance_m` | REAL | FIT record distance when present. |
| `heart_rate` | INTEGER | bpm when present. |
| `extra_json` | TEXT | JSON object of other record fields. |

---

## 4. Example queries (SQLite CLI)

```sql
-- Recent rounds with course name
SELECT id, course_name, started_at, total_strokes, total_putts
FROM golf_rounds
ORDER BY started_at DESC
LIMIT 10;
```

```sql
-- Holes for one round (replace :rid)
SELECT hole_number, score, putts, par, distance_meters, duration_s
FROM round_holes
WHERE round_id = :rid
ORDER BY hole_number;
```

```sql
-- Sample track for a round (first 20 points)
SELECT seq, time, lat, lon, altitude_m, heart_rate
FROM round_track_points
WHERE round_id = :rid
ORDER BY seq
LIMIT 20;
```

```sql
-- Raw lap blob for debugging a hole
SELECT hole_number, extra_json
FROM round_holes
WHERE round_id = :rid AND hole_number = 7;
```

---

## 5. Inspecting raw FIT files (find hole scores / extra messages)

Garmin often stores golf scorecard data in **message types we do not yet map** into SQLite. To see everything fitparse decodes from an export:

```bash
cd golf-analysis
uv run golf-ingest fit-inspect path/to/activity.zip
# or
uv run golf-ingest fit-inspect path/to/activity.fit -o report.txt
```

Options:

| Flag | Meaning |
|------|---------|
| `--sample N` | How many full `get_values()` samples to print per **non-record** message type (default 3). |
| `--max-value-len L` | Truncate long field values in the report. |
| `--record-stride K` | If there are many GPS `record` rows, also print the record at index `K` (default 50). |
| `-o FILE` | Write the report to a file instead of stdout. |

The report lists **global message numbers** (`mesg_num`) and **names** (from the bundled FIT profile), counts per type, union of field keys, and sample payloads. Use it to spot candidate fields for **strokes, putts, par**, or unknown `unknown_*` fields that correspond to newer SDK definitions.

When the file contains **mesg 325 or 326** (typical on modern Garmin golf activities), the same command appends a short **Golf vendor forensics** block: distributions of `unknown_2` / `unknown_1` on mesg 325, a cross-check against mesg **79** (`unknown_6` often equals the mesg 325 row count), and session/lap `unknown_196` / `unknown_178` / `unknown_155` / `unknown_145` lines for correlation with totals.

Implementation: `golf_analysis/fit_inspect.py`.

### 5.1 What we inferred from a real round (`docs/garmin-fit-inspect-2026-05-08.txt`)

Garmin’s **public** FIT profile (and **garmin_fit_sdk** 21.x `mesg_num` enums) **do not name** global message numbers **22, 79, 140, 141, 147, 216, 233, 288, 325, 326, 327** on this export. They are still valid FIT data definitions embedded in the file; **fitparse** exposes them as `unknown_<field_num>` where **field 253** is almost always the standard **timestamp** (`date_time`).

| Mesg | Count (sample file) | Role (evidence-based, not official Garmin names) |
|------|--------------------:|--------------------------------------------------|
| **session** / **lap** | 1 each | Whole-round summary only (`num_laps: 1`); **not** 18 hole laps. `total_cycles` null — do **not** rely on lap-based score parsing for this format. |
| **325** | 187 | **Primary candidate for per-shot (or per-lie) rows**: `unknown_2` clusters like a **hole index** (1–18); `unknown_1` increments within a hole like **stroke index**; `unknown_0` scales like **distance remaining** (often tens–hundreds); `unknown_253` = shot time. |
| **326** | 108 | **Secondary golf table** (fewer rows than 325): plausible **putts**, **penalties**, or **green-side** events; needs UI cross-check. |
| **79** | 1 | **Round header**: in the sample, `unknown_6` **equals** the mesg **325** row count (187); `unknown_2` ≈ 188 — strong link to the shot list. |
| **216** | 2 | SDK defines 216 as `time_in_zone`; here arrays include **187** as the last element — may index shot boundaries or hole splits. |
| **unknown_22** | 1 | Small integers only; likely **metadata** (format, tee, hole count), not strokes. |
| **session/lap `unknown_196` / `unknown_155`** | 171 | Matches **lap** `unknown_155`; aligns with **total strokes**–style totals (compare to Connect). |
| **session/lap `unknown_178` / `unknown_145`** | 953 | Same cross-session/lap pairing; likely another stroke or **score**-adjacent counter (units unknown until mapped). |
| **233** + **gps_metadata** | 6416 each | **Parallel GPS assist** stream, not the scorecard. |

**Parser takeaway:** for Connect “original” golf FIT from current watches, **per-hole SQLite rows should eventually be derived from mesg 325 (and possibly 326)**, not from `lap` rows, when `num_laps == 1` and mesg 325 is present. Until Garmin documents those messages, keep raw rows or `extra_json` for forensics.

---

## 6. Related code paths

| Concern | Location |
|---------|----------|
| FIT → models | `golf_analysis/connectors/garmin_fit.py` |
| Models (field meanings) | `golf_analysis/models.py` (`GolfRound`, `RoundHole`, `RoundTrackPoint`) |
| SQLite DDL + insert | `golf_analysis/repository.py` (`init_schema`, `insert_payload`) |
| Download from Connect | `golf_analysis/sync/garmin_community.py` + `golf-ingest garmin-sync` |

---

## 7. Version note

Schema and heuristics evolve with the codebase. If this document disagrees with `init_schema()` in `repository.py`, **trust the code** and update this file.
