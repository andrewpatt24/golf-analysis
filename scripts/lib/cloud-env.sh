#!/usr/bin/env bash
# Source shared Cloud Run / GCS env from .env.cloud (repo root).
cloud_env_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

load_cloud_env() {
  local root
  root="$(cloud_env_root)"
  if [[ -f "${root}/.env.cloud" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${root}/.env.cloud"
    set +a
  fi
}
