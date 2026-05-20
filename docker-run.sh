#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# shellcheck source=scripts/env-files.sh
source "${ROOT}/scripts/env-files.sh"
require_env_files "$ROOT"
build_docker_env_file_args "$ROOT"
build_docker_secret_mount_args "$ROOT"

docker rm -f cc_mobile_backend 2>/dev/null || true
docker run -it \
  --cpus="4" \
  --cpu-shares="512" \
  --memory="8g" \
  -p 8675:8675 \
  "${DOCKER_ENV_FILE_ARGS[@]}" \
  "${DOCKER_SECRET_MOUNT_ARGS[@]}" \
  --name cc_mobile_backend \
  cc-mobile-backend
