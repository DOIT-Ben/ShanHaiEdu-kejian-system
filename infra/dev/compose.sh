#!/usr/bin/env bash
set -euo pipefail

project_root="$(git rev-parse --show-toplevel)"
git_common_dir="$(git -C "$project_root" rev-parse --path-format=absolute --git-common-dir)"
git_dir="$(git -C "$project_root" rev-parse --path-format=absolute --git-dir)"

if [[ "$git_dir" == "$git_common_dir" ]]; then
  container_git_dir="/git-common"
elif [[ "$git_dir" == "$git_common_dir"/* ]]; then
  container_git_dir="/git-common/${git_dir#"$git_common_dir"/}"
else
  echo "current Git directory is outside the common Git directory" >&2
  exit 1
fi

default_project="$(basename "$project_root" | tr '[:upper:]_' '[:lower:]-' | tr -cd 'a-z0-9-')"
compose_project="${SHANHAI_COMPOSE_PROJECT:-$default_project}"
if [[ -z "$compose_project" ]]; then
  echo "unable to derive a Compose project name" >&2
  exit 1
fi

export SHANHAI_GIT_COMMON_DIR="$git_common_dir"
export SHANHAI_CONTAINER_GIT_DIR="$container_git_dir"

exec docker compose \
  -p "$compose_project" \
  -f "$project_root/infra/compose.yaml" \
  -f "$project_root/infra/dev.compose.yaml" \
  "$@"
