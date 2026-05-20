#!/usr/bin/env bash
# Shared env/secrets checks for shell scripts and Docker.
#
# Local:  .env + repo-root .secrets (gitignored)
# Render: upload `.secrets` as a Secret File → /etc/secrets/.secrets
# Docker: docker-run.sh mounts local .secrets at /etc/secrets/.secrets (same as Render)
#
# Usage (from repo root):
#   source scripts/env-files.sh
#   require_env_files
#   docker run ... "${DOCKER_ENV_FILE_ARGS[@]}" "${DOCKER_SECRET_MOUNT_ARGS[@]}" ...

_env_files_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "${script_dir}/.." && pwd
}

# Print path to secrets file, or return 1 if none found.
resolve_secrets_file() {
  local root="${1:-$(_env_files_root)}"

  if [[ -n "${SECRETS_FILE:-}" && -f "${SECRETS_FILE}" ]]; then
    echo "${SECRETS_FILE}"
    return 0
  fi
  if [[ -f /etc/secrets/.secrets ]]; then
    echo /etc/secrets/.secrets
    return 0
  fi
  if [[ -f "${root}/.secrets" ]]; then
    echo "${root}/.secrets"
    return 0
  fi
  return 1
}

require_env_files() {
  local root="${1:-$(_env_files_root)}"
  local missing=0

  if [[ ! -f "${root}/.env" ]]; then
    echo "❌ Missing ${root}/.env" >&2
    missing=1
  fi
  if ! resolve_secrets_file "${root}" >/dev/null; then
    echo "❌ Missing secrets file. Local: ${root}/.secrets (copy: cp .secrets.example .secrets)" >&2
    echo "   Render: add Secret File with filename \`.secrets\` → /etc/secrets/.secrets" >&2
    missing=1
  fi
  if [[ "${missing}" -ne 0 ]]; then
    return 1
  fi
  return 0
}

# Non-secret config only (.env). Secrets are loaded in-container via /etc/secrets/.secrets.
DOCKER_ENV_FILE_ARGS=()

build_docker_env_file_args() {
  local root="${1:-$(_env_files_root)}"
  DOCKER_ENV_FILE_ARGS=(--env-file "${root}/.env")
}

# Mount local .secrets at Render path so the app uses the same loader as production.
DOCKER_SECRET_MOUNT_ARGS=()

build_docker_secret_mount_args() {
  local root="${1:-$(_env_files_root)}"
  local secrets_path

  DOCKER_SECRET_MOUNT_ARGS=()
  if ! secrets_path="$(resolve_secrets_file "${root}")"; then
    return 1
  fi
  # Already on Render mount path (e.g. re-run inside container) — no bind mount needed.
  if [[ "${secrets_path}" == /etc/secrets/.secrets ]]; then
    return 0
  fi
  DOCKER_SECRET_MOUNT_ARGS=(-v "${secrets_path}:/etc/secrets/.secrets:ro")
  return 0
}
