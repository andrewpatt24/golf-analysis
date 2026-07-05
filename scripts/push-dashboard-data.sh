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
SECRETS="${GOLF_DASHBOARD_SECRETS:-$ROOT/data/dashboard_secrets.json}"
GARTH_DIR="${GOLF_GARTH_DIR:-$ROOT/data/garth}"
ACCESS_TOKENS="${GOLF_ACCESS_TOKENS_FILE:-$ROOT/data/access_tokens.json}"
DRILL_SESSIONS="${GOLF_DRILL_SESSIONS:-$ROOT/data/drill_sessions.json}"
TRAINING_BLOCK="${GOLF_TRAINING_BLOCK:-$ROOT/data/training_block.json}"

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

if [[ -f "$SECRETS" ]]; then
  echo "Sanitizing dashboard secrets (passwords never leave this machine)..."
  SANITIZED="$(mktemp "${TMPDIR:-/tmp}/dashboard_secrets.XXXXXX.json")"
  UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.uv-cache}" uv run python -c "
from pathlib import Path
import json, sys
from golf_analysis.local_auth.sanitize import sanitize_secrets_document
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding='utf-8'))
Path(sys.argv[2]).write_text(json.dumps(sanitize_secrets_document(data), indent=2), encoding='utf-8')
" "$SECRETS" "$SANITIZED"
  "${CP[@]}" "$SANITIZED" "gs://${BUCKET}/dashboard_secrets.json"
  rm -f "$SANITIZED"
fi

if [[ -f "$ACCESS_TOKENS" ]]; then
  "${CP[@]}" "$ACCESS_TOKENS" "gs://${BUCKET}/access_tokens.json"
fi

if [[ -f "$DRILL_SESSIONS" ]]; then
  "${CP[@]}" "$DRILL_SESSIONS" "gs://${BUCKET}/drill_sessions.json"
fi

if [[ -f "$TRAINING_BLOCK" ]]; then
  "${CP[@]}" "$TRAINING_BLOCK" "gs://${BUCKET}/training_block.json"
fi

if [[ -d "$GARTH_DIR" ]]; then
  echo "Pushing garth tokens..."
  for f in "$GARTH_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"
    "${CP[@]}" "$f" "gs://${BUCKET}/garth/${base}"
  done
fi

echo "Done. Restart Cloud Run to pick up changes:"
echo "  ./scripts/deploy-cloud-run.sh --reload-only"
