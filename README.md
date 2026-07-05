# Golf analysis

**For AI agents:** operational runbook → [AGENTS.md](AGENTS.md) (data refresh, auth, deploy).

Personal golf analytics: ingest **Rapsodo** range sessions and **Garmin** on-course data into a local SQLite library, run reports from the CLI, and explore trends in a **React dashboard** (Strategy, Performance, Training, Plans).

## What it does

| Area | Source | Highlights |
|------|--------|------------|
| **Range / practice** | Rapsodo LM CSV (and cloud sync) | Carry dispersion, landing side, gapping, club comparison, shot shape |
| **On-course** | Garmin Golf Community export JSON, FIT activity files | Scorecards, ESZ / DSZ (Scoring Method), round proxies, round-by-round charts |
| **Library** | SQLite (`data/library.db`) | Normalized `range_shots`, `golf_rounds`, `round_holes`; shot traces in `extra_json` when ingested |

The dashboard talks to a local **FastAPI** service (`/api/v1`). Garmin **ESZ / DSZ** metrics are computed from `shotDetails` in the export (geometry → Garmin distances → straight-hole heuristic). See [docs/on-course-analysis-methodology.md](docs/on-course-analysis-methodology.md) and [docs/frameworks/scoring-method.md](docs/frameworks/scoring-method.md).

## Requirements

- **Python 3.11+** and [uv](https://docs.astral.sh/uv/) (recommended) or pip
- **Node.js 18+** (for the dashboard UI)
- Optional: Docker (see [dashboard/README.md](dashboard/README.md)) if you prefer not to install Node locally

## Quick start

### 1. Python environment and library

```bash
cd golf-analysis
uv sync
```

Create raw-data folders (created automatically on first ingest):

```text
data/raw/rapsodo/   # Rapsodo CSV exports
data/raw/garmin/    # FIT/ZIP rounds and golf-export.json
```

Ingest everything under `data/raw`:

```bash
uv run golf-ingest --db data/library.db ingest
```

Check the library:

```bash
uv run golf-ingest --db data/library.db info
```

### 2. Garmin Golf export (for Strategy / ESZ / DSZ)

Download your community export (or sync via CLI) and point the API at it:

```bash
# Optional: sync from Garmin Connect (requires garth login — see golf-ingest garmin-golf-sync --help)
uv run golf-ingest --db data/library.db garmin-golf-sync --out ./data/raw/garmin/golf-export.json

export GOLF_GARMIN_JSON="$(pwd)/data/raw/garmin/golf-export.json"
```

### 3. API + dashboard

**Terminal 1 — API:**

```bash
uv run golf-ingest --db data/library.db dashboard-api --reload
```

**Terminal 2 — UI:**

```bash
cd dashboard
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to port **8000**.

For Docker-only UI setup, env vars, and production build notes, see [dashboard/README.md](dashboard/README.md).

### Phone access (Google Cloud)

Push your local SQLite library (+ Garmin JSON + settings) to a private bucket and run one **Cloud Run** URL on your phone. After `gcloud auth login`, run `./scripts/setup-cloud-mobile.sh` or follow [docs/deploy-google-cloud.md](docs/deploy-google-cloud.md).

**On Course prep (new courses):** Woldingham (White tees) in On Course → Course tab; more courses via `manual_courses.py` until GolfAPI ingest — see [docs/new-course-prep-plan.md](docs/new-course-prep-plan.md).

**Data refresh:** Locally, `uv run local-auth-login` then ingest/push; or Coach → Settings → **Data sources** to refresh. Cloud Run uses stored JWT/Garth tokens only (no passwords). See [docs/local-auth.md](docs/local-auth.md) and [docs/deploy-google-cloud.md](docs/deploy-google-cloud.md).

## CLI overview

| Command | Purpose |
|---------|---------|
| `golf-ingest ingest [paths…]` | Import CSV / FIT / ZIP / Garmin JSON into SQLite |
| `golf-ingest info` | Row counts in the library |
| `golf-ingest dashboard-api` | FastAPI server for the dashboard |
| `golf-ingest range-shots-report` | Text report from range data |
| `golf-ingest analysis-plan-report` | Garmin + library summary report |
| `golf-ingest garmin-sync` | Download recent Garmin activity files |
| `golf-ingest garmin-golf-sync` | Download Garmin Golf Community JSON |
| `golf-ingest rapsodo-sync` | Pull Rapsodo cloud sessions (needs credentials) |

Run `uv run golf-ingest --help` for all subcommands and flags.

## Configuration

| Variable | Default | Role |
|----------|---------|------|
| `GOLF_LIBRARY_DB` | `data/library.db` | SQLite path |
| `GOLF_GARMIN_JSON` | `data/raw/garmin/golf-export.json` | Garmin export for Strategy / Performance |
| `GOLF_DASHBOARD_SETTINGS` | `data/dashboard_settings.json` | Dashboard year, limits (via API) |
| `GOLF_CORS_ORIGINS` | `http://localhost:5173,…` | CORS for the dev UI |

**Secrets and local data (not committed):**

- Copy `secrets.json.example` → `secrets.json` (Rapsodo/Garmin email+password for local login, or paste JWT manually). See [docs/local-auth.md](docs/local-auth.md).
- Copy `config/rapsodo-endpoints.example.json` → `config/rapsodo-endpoints.json` if using cloud sync
- Put exports under `data/raw/` and run ingest; `data/library.db` stays local

## Tests

```bash
uv run pytest
```

## Documentation

| Doc | Topic |
|-----|--------|
| [docs/sqlite-library-schema.md](docs/sqlite-library-schema.md) | Database tables |
| [docs/raw-data-inventory.md](docs/raw-data-inventory.md) | On-disk export shapes |
| [docs/architecture/full-system-tech-spec.md](docs/architecture/full-system-tech-spec.md) | System design |
| [docs/feature-list.md](docs/feature-list.md) | Product wish list |
| [dashboard/README.md](dashboard/README.md) | UI dev / Docker |

## Project layout

```text
golf_analysis/     # Python package (connectors, ingest, API, analytics)
dashboard/       # Vite + React + MUI dashboard
data/raw/        # Your exports (gitignored except .gitkeep)
tests/           # pytest suite
docs/            # Specs and frameworks
```

## License

Private / personal use unless you add a license file.
