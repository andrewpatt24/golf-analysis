#!/usr/bin/env bash
# Build and deploy the golf dashboard to Google Cloud Run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/lib/cloud-env.sh
source "${ROOT}/scripts/lib/cloud-env.sh"
load_cloud_env
SERVICE="${GOLF_CLOUD_RUN_SERVICE:-golf-dashboard}"
REGION="${GOLF_CLOUD_RUN_REGION:-us-central1}"
IMAGE="${GOLF_CLOUD_RUN_IMAGE:-gcr.io/$(gcloud config get-value project 2>/dev/null)/${SERVICE}}"

if [[ -z "${GOLF_DATA_BUCKET:-}" ]]; then
  echo "Set GOLF_DATA_BUCKET to your private GCS bucket name." >&2
  exit 1
fi

RELOAD_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --reload-only) RELOAD_ONLY=true ;;
    *) echo "Unknown arg: $arg (use --reload-only)" >&2; exit 1 ;;
  esac
done

ENV_VARS="GOLF_DATA_BUCKET=${GOLF_DATA_BUCKET},GOLF_DATA_VERSION=$(date +%s)"
if [[ -n "${GOLF_ACCESS_TOKEN:-}" ]]; then
  ENV_VARS="${ENV_VARS},GOLF_ACCESS_TOKEN=${GOLF_ACCESS_TOKEN}"
fi

if [[ "$RELOAD_ONLY" == true ]]; then
  echo "Rolling new revision (re-download data on startup)..."
  gcloud run services update "$SERVICE" \
    --region="$REGION" \
    --update-env-vars="$ENV_VARS"
  gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)'
  exit 0
fi

echo "Building image ${IMAGE} ..."
gcloud builds submit "$ROOT" --tag "$IMAGE" --quiet

PROJECT_NUMBER="$(gcloud projects describe "$(gcloud config get-value project)" --format='value(projectNumber)')"
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Granting ${SA} read access to gs://${GOLF_DATA_BUCKET} ..."
gcloud storage buckets add-iam-policy-binding "gs://${GOLF_DATA_BUCKET}" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectViewer" \
  --quiet >/dev/null || true

echo "Deploying ${SERVICE} to ${REGION} ..."
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=1 \
  --set-env-vars="$ENV_VARS"

URL="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')"
echo ""
echo "Deployed: ${URL}"
if [[ -n "${GOLF_ACCESS_TOKEN:-}" ]]; then
  echo "Phone bookmark: ${URL}/?token=${GOLF_ACCESS_TOKEN}"
else
  echo "Tip: set GOLF_ACCESS_TOKEN before deploy to require ?token= on the URL."
fi
