# Deploy the dashboard on Google Cloud (phone access)

Personal setup: **one HTTPS URL** on your phone, data updated by **pushing files from your Mac** after local ingest/sync. No database server to run — just SQLite + Garmin JSON in a private bucket.

## Architecture

```text
Mac (local)                         Google Cloud
─────────                           ────────────
golf-ingest ingest                  Cloud Storage bucket (private)
  → data/library.db        push →    library.db
  → golf-export.json                 golf-export.json
  → dashboard_settings.json          dashboard_settings.json

                                    Cloud Run (one service)
                                      FastAPI + built React UI
                                      downloads bucket → /data on start
                                      https://golf-dashboard-xxxxx.run.app
```

The container serves **API and UI on the same origin** (`GOLF_DASHBOARD_DIST`), so the phone browser only needs one bookmark.

## What to push

| File | Local path | GCS object |
|------|------------|------------|
| SQLite library | `data/library.db` | `library.db` |
| Garmin export (Strategy / ESZ / DSZ) | `data/raw/garmin/golf-export.json` | `golf-export.json` |
| Dashboard settings | `data/dashboard_settings.json` | `dashboard_settings.json` |
| Connector secrets (optional) | `data/dashboard_secrets.json` | `dashboard_secrets.json` |
| Garmin Garth tokens (optional) | `data/garth/*.json` | `garth/*.json` |

Range and Performance tabs need the DB; Strategy needs the Garmin JSON as well.

### Refresh from the dashboard (recommended)

Coach → **Settings** → **Data sources**:

1. **Rapsodo** — paste your R-Cloud JWT, then **Refresh** (or use **Refresh all**).
2. **Garmin Connect** — zip your `~/.garth` folder (after `garth login` on Mac) and upload, then refresh **Garmin Golf** and/or **Garmin activities**.
3. Successful refresh on Cloud Run **writes back** to your GCS bucket (`library.db`, `golf-export.json`, secrets).

You can still use CLI (`golf-ingest rapsodo-sync`, `garmin-golf-sync`, `ingest`) and `push-dashboard-data.sh` when developing locally.

## Quick start (recommended)

After [installing the gcloud CLI](https://cloud.google.com/sdk/docs/install) and `gcloud auth login`:

```bash
chmod +x scripts/setup-cloud-mobile.sh scripts/push-dashboard-data.sh scripts/deploy-cloud-run.sh
./scripts/setup-cloud-mobile.sh
```

The script enables APIs, creates a private bucket, writes `.env.cloud` (gitignored), pushes your local data, deploys Cloud Run, and prints a **phone bookmark URL** with `?token=…`.

## One-time setup (manual)

### 1. Google Cloud project

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and log in:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

3. Enable APIs:

```bash
gcloud services enable run.googleapis.com storage.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```

### 2. Storage bucket

Pick a globally unique name (e.g. `yourname-golf-data`):

```bash
export GOLF_DATA_BUCKET=yourname-golf-data
gcloud storage buckets create "gs://${GOLF_DATA_BUCKET}" --location=us-central1
```

Keep the bucket **private** (default). Only Cloud Run’s service account will read it.

### 3. First push from your Mac

From the repo root, after ingest and Garmin export are current:

```bash
export GOLF_DATA_BUCKET=yourname-golf-data
./scripts/push-dashboard-data.sh
```

### 4. Build and deploy Cloud Run

```bash
export GOLF_DATA_BUCKET=yourname-golf-data
export GOLF_ACCESS_TOKEN="$(openssl rand -hex 24)"   # optional; save for phone bookmark
./scripts/deploy-cloud-run.sh
```

The script builds a Docker image, deploys to Cloud Run, and configures the service to download your bucket into `/data` on each new instance.

Save the printed URL and token. On your phone, open:

```text
https://YOUR-SERVICE-xxxxx.run.app/?token=YOUR_TOKEN
```

(If you skip `GOLF_ACCESS_TOKEN`, the service is public — only use that if the URL stays private.)

### 5. Lock down who can open it (recommended)

With `GOLF_ACCESS_TOKEN` set, the API and UI require that token (query `?token=…` or header `Authorization: Bearer …`). Store the full URL in a phone bookmark or password manager.

**Sharing with someone else (revocable guest link):**

```bash
# optional in .env.cloud: GOLF_CLOUD_RUN_URL=https://your-service.run.app
uv run golf-guest-token create --label "Alex"
./scripts/push-dashboard-data.sh
./scripts/deploy-cloud-run.sh --reload-only
```

Send them the printed `/?token=…` URL. Your owner token in `.env.cloud` is unchanged.

**Revoke a guest:**

```bash
uv run golf-guest-token list
uv run golf-guest-token revoke GUEST_ID
./scripts/push-dashboard-data.sh && ./scripts/deploy-cloud-run.sh --reload-only
```

Guests are stored in `data/access_tokens.json` (pushed to GCS). After revoke, their cookie stops working on the next request.

For stricter Google-account-only access, add [Identity-Aware Proxy](https://cloud.google.com/iap/docs) in front of Cloud Run later; the token gate is enough for a personal deployment.

## Day-to-day workflow

On your Mac after new rounds / range sessions:

```bash
uv run golf-ingest --db data/library.db ingest
# optional: garmin-golf-sync, rapsodo-sync, then ingest again

export GOLF_DATA_BUCKET=yourname-golf-data
./scripts/push-dashboard-data.sh

# Force Cloud Run to load fresh files (bumps env → new revision)
./scripts/deploy-cloud-run.sh --reload-only
```

`--reload-only` skips image rebuild and only rolls a new revision so startup re-downloads from GCS.

## Environment variables (Cloud Run)

| Variable | Purpose |
|----------|---------|
| `GOLF_DATA_BUCKET` | GCS bucket name (no `gs://` prefix) |
| `GOLF_LIBRARY_DB` | `/data/library.db` (set in image) |
| `GOLF_GARMIN_JSON` | `/data/golf-export.json` |
| `GOLF_DASHBOARD_SETTINGS` | `/data/dashboard_settings.json` |
| `GOLF_DASHBOARD_DIST` | `/app/dashboard/dist` (UI baked into image) |
| `GOLF_ACCESS_TOKEN` | Optional shared secret for phone/browser |

## Costs (ballpark)

For personal use (low traffic, small files): Cloud Run free tier + cents for storage and occasional builds. No always-on VM.

## Troubleshooting

| Issue | Check |
|-------|--------|
| 503 “Library database not found” | Bucket objects exist? `gsutil ls gs://$GOLF_DATA_BUCKET/` |
| Strategy empty | `golf-export.json` pushed? `GOLF_GARMIN_JSON` on Cloud Run |
| Stale data after push | Run `./scripts/deploy-cloud-run.sh --reload-only` |
| 401 on phone | Add `?token=` matching `GOLF_ACCESS_TOKEN` |

## Local test of the production image

```bash
docker build -t golf-dashboard .
docker run --rm -p 8080:8080 \
  -e GOLF_DATA_BUCKET=yourname-golf-data \
  -e GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/creds.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds.json \
  golf-dashboard
```

Open `http://localhost:8080` (use the same `?token=` if configured).
