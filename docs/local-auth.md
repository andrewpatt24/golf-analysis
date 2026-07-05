# Local credential login (not on Cloud Run)

Store **email/password only** in repo-root `secrets.json` (gitignored). Cloud Run never receives passwords — only JWT / Garth token files, and uploads are sanitized.

## Setup (once per machine)

```bash
cp secrets.json.example secrets.json
# edit secrets.json with your Rapsodo + Garmin credentials

uv sync --group local-auth
uv run playwright install chromium
```

## Refresh tokens

```bash
uv run local-auth-login
# or Rapsodo only with visible browser:
uv run local-auth-login --rapsodo --no-headless
```

This writes:

| Output | Purpose |
|--------|---------|
| `secrets.json` → `rapsodo_bearer` | CLI / local API |
| `data/dashboard_secrets.json` → `rapsodo.bearer` | Pushed to GCS for phone dashboard |
| `data/garth/*.json` | Garmin Connect OAuth (also pushed as `garth/*`) |

**Never** commit `secrets.json`. `push-dashboard-data.sh` strips password fields from `dashboard_secrets.json` before upload.

## Automatic refresh

When running the API locally, **Settings → Data sources → Refresh** will:

1. Use existing JWT / Garth tokens.
2. On 401/403 (Rapsodo) or Garmin auth errors, re-run local login if `secrets.json` has passwords.

On **Cloud Run**, only stored tokens are used — paste JWT or upload Garth zip in Settings if sync fails.

## Disable local auth

```bash
export GOLF_LOCAL_AUTH=0
```
