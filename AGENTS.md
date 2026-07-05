# Agent guide — golf-analysis

This file is the **operational runbook** for AI agents working in this repo. Follow it end-to-end so the owner does not have to repeat deploy, auth, or data-update steps in chat.

**Human docs:** [README.md](README.md) · [docs/local-auth.md](docs/local-auth.md) · [docs/deploy-google-cloud.md](docs/deploy-google-cloud.md) · [docs/architecture/full-system-tech-spec.md](docs/architecture/full-system-tech-spec.md)

---

## What this project is

Personal golf analytics monorepo:

| Layer | Path | Role |
|-------|------|------|
| Python package | `golf_analysis/` | Ingest connectors, SQLite library, sync (Rapsodo/Garmin), FastAPI `/api/v1` |
| Dashboard UI | `dashboard/` | Vite + React + MUI; dev server proxies `/api` → port 8000 |
| Data | `data/` | `library.db`, `raw/`, settings, secrets (mostly gitignored) |
| Cloud | `scripts/*.sh`, `Dockerfile` | GCS bucket + Cloud Run for phone access |

**Data flow:** raw exports → `golf-ingest ingest` → `data/library.db` + `golf-export.json` → optional GCS push → Cloud Run downloads on instance start.

---

## Agent principles

1. **Run commands yourself** — do not only tell the user what to run unless blocked (missing credentials, gcloud auth, MFA in browser).
2. **Minimize scope** — match existing style; no drive-by refactors.
3. **Never commit secrets** — `secrets.json`, `data/dashboard_secrets.json`, `.env.cloud`, `data/library.db`, garth tokens, JWTs.
4. **Never commit unless the user explicitly asks** for a git commit.
5. **Never push to git remote** unless asked.
6. **Cloud Run ≠ local** — no Playwright, no `secrets.json` passwords, no `local-auth-login` on Cloud Run (`K_SERVICE` is set there).
7. **Use full shell permissions** when needed: `uv` writes to `~/.cache/uv`; `gcloud` writes to `~/.config/gcloud`. If commands fail with permission errors, re-run with `required_permissions: ["all"]` or set `UV_CACHE_DIR=$REPO/.uv-cache`.

---

## One-time machine setup

From repo root:

```bash
cd /path/to/golf-analysis
uv sync
uv sync --group sync          # garth-ng, httpx (Garmin/Rapsodo HTTP sync)
uv sync --group local-auth    # playwright, pyotp (local login only)
uv run playwright install chromium

cp secrets.json.example secrets.json   # edit with real credentials (gitignored)
cp config/rapsodo-endpoints.example.json config/rapsodo-endpoints.json  # if missing

cd dashboard && npm install && cd ..
```

**`secrets.json`** (repo root, gitignored) — local only:

```json
{
  "rapsodo_email": "...",
  "rapsodo_password": "...",
  "garmin_email": "...",
  "garmin_password": "...",
  "garmin_totp_secret": "optional-base32-if-garmin-mfa"
}
```

After login, `rapsodo_bearer` is written automatically. Do **not** put email/password in `data/dashboard_secrets.json`.

---

## Standard workflows (run these agentically)

### A. Full local data refresh

Use when the user asks to **update data** or before a cloud push.

```bash
export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"
cd /path/to/golf-analysis

# 1) Refresh API tokens (local only; requires secrets.json)
uv run local-auth-login

# 2) Cloud sync (needs valid tokens + config/rapsodo-endpoints.json)
uv sync --group sync
uv run golf-ingest --db data/library.db rapsodo-sync \
  --config config/rapsodo-endpoints.json --also-ingest
uv run golf-ingest --db data/library.db garmin-golf-sync \
  --out ./data/raw/garmin/golf-export.json
uv run golf-ingest --db data/library.db garmin-sync \
  --garth-home data/garth --out data/raw/garmin

# 3) Re-import everything under data/raw (skip rapsodo_session_list.json if ingest errors — it is metadata only)
uv run golf-ingest --db data/library.db ingest data/raw/garmin data/raw/rapsodo

# 4) Verify
uv run golf-ingest --db data/library.db info
```

**If Rapsodo sync returns 403:** run `uv run local-auth-login --rapsodo --no-headless`, update JWT, retry.

**If Garmin sync fails (Garth/OAuth):** run `uv run local-auth-login --garmin` or check `garmin_totp_secret` for MFA.

**Alternative:** start API locally and POST refresh (uses same `refresh_runner` + local auth hooks):

```bash
uv run golf-ingest --db data/library.db dashboard-api --reload
# UI: Coach → Settings → Data sources → Refresh all
```

---

### B. Deploy updated app + data to Google Cloud (phone dashboard)

Prerequisites: `gcloud auth login`, project set, **`.env.cloud`** at repo root (created by `scripts/setup-cloud-mobile.sh`) containing at least `GOLF_DATA_BUCKET=...`.

```bash
export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"
cd /path/to/golf-analysis
source .env.cloud   # or: export GOLF_DATA_BUCKET=your-bucket

# 1) Fresh local data (workflow A)
uv run local-auth-login
uv run golf-ingest --db data/library.db ingest data/raw/garmin data/raw/rapsodo
# … rapsodo-sync / garmin-golf-sync as needed

# 2) Push artifacts to GCS (sanitizes dashboard_secrets — no passwords)
chmod +x scripts/push-dashboard-data.sh scripts/deploy-cloud-run.sh
./scripts/push-dashboard-data.sh

# 3) Deploy
./scripts/deploy-cloud-run.sh              # full image rebuild + deploy
# OR after data-only push:
./scripts/deploy-cloud-run.sh --reload-only   # new revision, re-downloads GCS into /data
```

**First-time cloud setup** (bucket + Cloud Run + `.env.cloud` + access token):

```bash
chmod +x scripts/setup-cloud-mobile.sh
./scripts/setup-cloud-mobile.sh
```

Save the printed **phone URL** with `?token=...` from setup or deploy output.

| Push target | Local path | GCS object |
|-------------|------------|------------|
| SQLite | `data/library.db` | `library.db` |
| Garmin export | `data/raw/garmin/golf-export.json` | `golf-export.json` |
| Settings | `data/dashboard_settings.json` | `dashboard_settings.json` |
| Playbook | `data/on_course_playbook.json` | `on_course_playbook.json` |
| Tokens (sanitized) | `data/dashboard_secrets.json` | `dashboard_secrets.json` |
| Garth OAuth | `data/garth/*.json` | `garth/*.json` |

**Never push** repo-root `secrets.json` to GCS.

---

### C. Local dev (API + UI)

```bash
# Terminal 1
uv run golf-ingest --db data/library.db dashboard-api --reload

# Terminal 2
cd dashboard && npm run dev
# http://localhost:5173
```

---

### D. Run tests

```bash
export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.uv-cache}"
uv sync --group dev
uv run python -m pytest
```

Targeted: `uv run python -m pytest tests/test_local_auth.py -q`

---

## Authentication model

```text
LOCAL (Mac / agent)                         CLOUD RUN
─────────────────                         ───────────
secrets.json                              NOT present
  ├─ rapsodo_email/password               dashboard_secrets.json (from GCS)
  ├─ garmin_email/password                  ├─ rapsodo.bearer (JWT only)
  └─ rapsodo_bearer (after login)           └─ garmin.garth_dir → /data/garth
data/dashboard_secrets.json
data/garth/*.json
local-auth-login
  ├─ Playwright → Rapsodo JWT
  └─ garth.login → data/garth/
```

| Command | Where | Purpose |
|---------|-------|---------|
| `uv run local-auth-login` | Local only | Refresh Rapsodo JWT + Garmin Garth files |
| `uv run local-auth-login --rapsodo --no-headless` | Local | Debug Rapsodo login UI |
| `uv run local-auth-login --garmin` | Local | Garmin only |
| Settings → paste JWT / upload Garth zip | Local or Cloud | Manual token update on phone host |
| `golf-ingest rapsodo-sync` | Local (or cloud with stored JWT) | Download Rapsodo CSVs |

**Detection:** `golf_analysis.local_auth.runtime.local_auth_enabled()` is false when `K_SERVICE` is set (Cloud Run). Do not install Playwright in the Docker image.

**Disable auto-login:** `export GOLF_LOCAL_AUTH=0`

---

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `GOLF_LIBRARY_DB` | `data/library.db` | SQLite path |
| `GOLF_GARMIN_JSON` | `data/raw/garmin/golf-export.json` | Strategy / Performance / ESZ |
| `GOLF_DASHBOARD_SETTINGS` | `data/dashboard_settings.json` | |
| `GOLF_DASHBOARD_SECRETS` | `data/dashboard_secrets.json` | Tokens only on cloud |
| `GOLF_DATA_DIR` | parent of library db | API data root |
| `GOLF_DATA_BUCKET` | — | GCS bucket name (no `gs://`); in `.env.cloud` |
| `GOLF_ACCESS_TOKEN` | — | Optional Cloud Run URL gate (`?token=`) |
| `GOLF_LOCAL_AUTH` | enabled locally | Set `0` to disable password login |
| `GOLF_RAPSODO_CONFIG` | `config/rapsodo-endpoints.json` | Cloud image uses baked example |
| `GOLF_CORS_ORIGINS` | localhost dev ports | |
| `K_SERVICE` | — | Set by Cloud Run; disables local auth |
| `UV_CACHE_DIR` | — | Use `$REPO/.uv-cache` if sandbox blocks `~/.cache` |

Load cloud vars: `source .env.cloud` (from `scripts/lib/cloud-env.sh`).

---

## Key paths

```text
golf_analysis/
  cli.py                    # golf-ingest entry
  ingest.py                 # connectors → SQLite
  data_sources/refresh_runner.py   # Settings “Refresh” backend
  local_auth/               # Playwright + garth login (local only)
  sync/rapsodo_cloud.py     # Rapsodo HTTP
  sync/garmin_golf_community.py
  api/                      # FastAPI app
dashboard/src/              # React UI
config/rapsodo-endpoints.json   # gitignored; copy from .example
scripts/
  push-dashboard-data.sh
  deploy-cloud-run.sh
  setup-cloud-mobile.sh
  cloud_download_data.py    # Cloud Run startup: pull GCS → /data
data/
  library.db
  raw/rapsodo/  raw/garmin/
  garth/
  dashboard_secrets.json
secrets.json                # gitignored; passwords live here only
.env.cloud                  # gitignored; GOLF_DATA_BUCKET, etc.
```

---

## CLI quick reference

```bash
uv run golf-ingest --db data/library.db ingest [paths…]
uv run golf-ingest --db data/library.db info
uv run golf-ingest --db data/library.db dashboard-api [--reload]
uv run golf-ingest --db data/library.db rapsodo-sync --config config/rapsodo-endpoints.json [--also-ingest]
uv run golf-ingest --db data/library.db garmin-golf-sync --out data/raw/garmin/golf-export.json
uv run golf-ingest --db data/library.db garmin-sync --garth-home data/garth --out data/raw/garmin
uv run local-auth-login [--rapsodo] [--garmin] [--no-headless] [--force]
```

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `uv` cache permission error | `export UV_CACHE_DIR=$REPO/.uv-cache` and `required_permissions: ["all"]` |
| `gcloud` credential permission error | Run with full permissions; or `export CLOUDSDK_CONFIG=$REPO/.gcloud-config` after copying config |
| Rapsodo 403 on sync | `uv run local-auth-login`; confirm `config/rapsodo-endpoints.json` exists |
| Garmin Garth / OAuth 403 | `uv run local-auth-login --garmin`; add `garmin_totp_secret` if MFA |
| `ingest` fails on `rapsodo_session_list.json` | Ingest specific dirs only; that file is not an importable connector input |
| Cloud 503 “Library database not found” | Run `push-dashboard-data.sh`; check `gsutil ls gs://$GOLF_DATA_BUCKET/` |
| Stale data on phone after push | `./scripts/deploy-cloud-run.sh --reload-only` |
| Cloud 401 | Append `?token=` matching `GOLF_ACCESS_TOKEN` or a guest token |
| Share dashboard with someone | `uv run golf-guest-token create --label NAME` → push → reload; revoke with `golf-guest-token revoke ID` |
| Strategy tab empty | Ensure `golf-export.json` was pushed |
| Playwright missing | `uv sync --group local-auth && uv run playwright install chromium` |

---

## Git / PR rules for agents

- **Do not create commits** unless the user explicitly requests it.
- **Do not push** unless asked.
- **Never** stage `secrets.json`, `data/`, `.env.cloud`, or credential files.
- Prefer focused diffs; run `uv run python -m pytest` before claiming done.

---

## When the user says…

| Request | Do |
|---------|-----|
| “Update my data” | Workflow **A** (auth → sync → ingest → `info`) |
| “Deploy” / “update cloud app” | Workflow **A**, then **B** (push + deploy) |
| “Fix auth” / “sync failing” | `local-auth-login`; check secrets.json; read troubleshooting table |
| “Refresh phone dashboard” | Push data + `--reload-only` (or full deploy if code changed) |
| Feature / bug in UI | `dashboard/` + `golf_analysis/api/`; add tests under `tests/` |

---

## Docker / Cloud Run notes

- Image: `Dockerfile` — Python API + built React `dashboard/dist`; **no Playwright**.
- Startup: `scripts/cloud_download_data.py` then `uvicorn golf_analysis.api.main:app`.
- Garth + `dashboard_secrets.json` downloaded from GCS; refresh on Cloud Run can write back via `golf_analysis.cloud_storage`.
- Optional URL auth: `GOLF_ACCESS_TOKEN` at deploy time.

---

## Extending the system

- New raw format → connector under `golf_analysis/connectors/`, register in ingest, document in `docs/raw-data-inventory.md`.
- Schema changes → `golf_analysis/repository.py` + `docs/sqlite-library-schema.md`.
- New API route → `golf_analysis/api/routers/`, wire in `api/main.py`, test with `httpx` in `tests/`.
- Course prep → `docs/new-course-prep-plan.md`, `golf_analysis/course_layout/manual_courses.py`.

Keep this file updated when deploy paths, auth flows, or standard agent workflows change.
