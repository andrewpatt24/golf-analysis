#!/usr/bin/env bash
# Run Vite dev server inside Docker (no local Node/npm required).
# Start the API on the host first: uv run golf-ingest --db data/library.db dashboard-api
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASH="$ROOT/dashboard"
API_PORT="${API_PORT:-8000}"
# bookworm-slim is smaller than full bookworm; good for old laptops
NODE_IMAGE="${NODE_IMAGE:-node:20-bookworm-slim}"
API_PROXY="${VITE_PROXY_TARGET:-http://host.docker.internal:${API_PORT}}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop or Colima (see dashboard/README.md)." >&2
  exit 1
fi

EXTRA_DOCKER_ARGS=()
# Linux Docker: host.docker.internal is not defined unless you add it
if [[ "$(uname -s)" == "Linux" ]]; then
  EXTRA_DOCKER_ARGS+=(--add-host=host.docker.internal:host-gateway)
fi

echo "Using image: $NODE_IMAGE"
echo "API proxy: $API_PROXY (start API on host port ${API_PORT})"
echo "UI: http://localhost:5173"
echo ""

docker run --rm -it \
  "${EXTRA_DOCKER_ARGS[@]}" \
  -v "$DASH:/app" \
  -w /app \
  -p 5173:5173 \
  -e "VITE_PROXY_TARGET=$API_PROXY" \
  "$NODE_IMAGE" \
  bash -lc "npm install && npx vite --host 0.0.0.0 --port 5173"
