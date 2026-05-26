#!/usr/bin/env bash
# Upload local library + Garmin export + settings to a private GCS bucket.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/lib/cloud-env.sh
source "${ROOT}/scripts/lib/cloud-env.sh"
load_cloud_env

BUCKET="${GOLF_DATA_BUCKET:?Set GOLF_DATA_BUCKET (e.g. source .env.cloud or export GOLF_DATA_BUCKET=yourname-golf-data)}"

DB="${GOLF_LIBRARY_DB:-$ROOT/data/library.db}"
GARMIN="${GOLF_GARMIN_JSON:-$ROOT/data/raw/garmin/golf-export.json}"
SETTINGS="${GOLF_DASHBOARD_SETTINGS:-$ROOT/data/dashboard_settings.json}"
PLAYBOOK="${GOLF_ON_COURSE_PLAYBOOK:-$ROOT/data/on_course_playbook.json}"

for f in "$DB" "$GARMIN"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing required file: $f" >&2
    exit 1
  fi
done

if [[ ! -f "$SETTINGS" ]]; then
  echo "Creating default settings at $SETTINGS ..."
  GOLF_DASHBOARD_SETTINGS="$SETTINGS" uv run python -c \
    'from golf_analysis.api.settings_store import save_settings; save_settings({})'
fi

if [[ ! -f "$PLAYBOOK" ]]; then
  echo "Creating default on-course playbook at $PLAYBOOK ..."
  GOLF_ON_COURSE_PLAYBOOK="$PLAYBOOK" uv run python -c \
    'from golf_analysis.api.on_course_playbook_store import save_playbook; save_playbook({})'
fi

if command -v gcloud >/dev/null 2>&1; then
  CP=(gcloud storage cp)
elif command -v gsutil >/dev/null 2>&1; then
  CP=(gsutil cp)
else
  echo "Install Google Cloud SDK (gcloud) to push files." >&2
  exit 1
fi

echo "Pushing to gs://${BUCKET}/ ..."
"${CP[@]}" "$DB" "gs://${BUCKET}/library.db"
"${CP[@]}" "$GARMIN" "gs://${BUCKET}/golf-export.json"
"${CP[@]}" "$SETTINGS" "gs://${BUCKET}/dashboard_settings.json"
"${CP[@]}" "$PLAYBOOK" "gs://${BUCKET}/on_course_playbook.json"

echo "Done. Restart Cloud Run to pick up changes:"
echo "  ./scripts/deploy-cloud-run.sh --reload-only"
