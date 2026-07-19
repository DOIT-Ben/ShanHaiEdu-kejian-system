#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "$1" >&2
  exit 1
}

project_root="$(git rev-parse --show-toplevel)"
git_common_dir="$(git -C "$project_root" rev-parse --path-format=absolute --git-common-dir)"
git_dir="$(git -C "$project_root" rev-parse --path-format=absolute --git-dir)"

if [[ "$git_dir" == "$git_common_dir" ]]; then
  container_git_dir="/git-common"
elif [[ "$git_dir" == "$git_common_dir"/* ]]; then
  container_git_dir="/git-common/${git_dir#"$git_common_dir"/}"
else
  fail "current Git directory is outside the common Git directory"
fi

default_project="$(basename "$project_root" | tr '[:upper:]_' '[:lower:]-' | tr -cd 'a-z0-9-')"
compose_project="${SHANHAI_COMPOSE_PROJECT:-$default_project}"
if [[ -z "$compose_project" ]]; then
  fail "unable to derive a Compose project name"
fi

isolation_mode="${SHANHAI_DOCKER_ISOLATION_MODE:-}"
case "$isolation_mode" in
  rootless)
    security_options="$(docker info --format '{{json .SecurityOptions}}')"
    [[ "$security_options" == *rootless* ]] || fail "Docker daemon is not rootless"
    workspace_uid=0
    workspace_gid=0
    rootless_userns=true
    ;;
  dedicated-ecs)
    marker="${SHANHAI_DEDICATED_HOST_MARKER:-/etc/shanhaiedu/dedicated-development-host}"
    [[ -f "$marker" ]] || fail "dedicated ECS marker is missing: $marker"
    grep -qx 'shanhaiedu-dedicated-development-host-v1' "$marker" || \
      fail "dedicated ECS marker is invalid: $marker"
    [[ "$(id -u)" == "1000" && "$(id -g)" == "1000" ]] || \
      fail "dedicated ECS shanhai-dev user must use UID/GID 1000:1000"
    workspace_uid=1000
    workspace_gid=1000
    rootless_userns=false
    ;;
  *)
    fail "SHANHAI_DOCKER_ISOLATION_MODE must be rootless or dedicated-ecs"
    ;;
esac

case "${1:-}" in
  build|create|up)
    available_kib="$(df -Pk "$project_root" | awk 'NR == 2 { print $4 }')"
    [[ "$available_kib" =~ ^[0-9]+$ ]] || fail "unable to determine available disk space"
    (( available_kib >= 30 * 1024 * 1024 )) || fail "at least 30 GiB free space is required"
    ;;
esac

if [[ "$compose_project" =~ ([0-9]+) ]]; then
  port_offset=$((10#${BASH_REMATCH[1]} % 2000))
else
  checksum="$(printf '%s' "$compose_project" | cksum | awk '{ print $1 }')"
  port_offset=$((2000 + checksum % 2000))
fi

export SHANHAI_GIT_COMMON_DIR="$git_common_dir"
export SHANHAI_CONTAINER_GIT_DIR="$container_git_dir"
export SHANHAI_COMPOSE_PROJECT="$compose_project"
export SHANHAI_WORKSPACE_UID="$workspace_uid"
export SHANHAI_WORKSPACE_GID="$workspace_gid"
export SHANHAI_CONTAINER_ROOTLESS_USERNS="$rootless_userns"
export SHANHAI_POSTGRES_PORT="${SHANHAI_POSTGRES_PORT:-$((55432 + port_offset))}"
export SHANHAI_REDIS_PORT="${SHANHAI_REDIS_PORT:-$((56379 + port_offset))}"
export SHANHAI_DEV_API_PORT="${SHANHAI_DEV_API_PORT:-$((58000 + port_offset))}"
export SHANHAI_MINIO_API_PORT="${SHANHAI_MINIO_API_PORT:-$((59000 + port_offset))}"
export SHANHAI_MINIO_CONSOLE_PORT="${SHANHAI_MINIO_CONSOLE_PORT:-$((59001 + port_offset))}"

exec docker compose \
  -p "$compose_project" \
  -f "$project_root/infra/compose.yaml" \
  -f "$project_root/infra/dev.compose.yaml" \
  "$@"
