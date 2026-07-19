#!/usr/bin/env bash
set -euo pipefail

work_tree="${SHANHAI_CONTAINER_GIT_WORK_TREE:-}"
git_dir="${SHANHAI_CONTAINER_GIT_DIR:-}"

if [[ -n "$work_tree" && -n "$git_dir" ]]; then
  case "$PWD/" in
    "$work_tree/"*)
      exec env GIT_DIR="$git_dir" GIT_WORK_TREE="$work_tree" /usr/bin/git "$@"
      ;;
  esac
fi

exec /usr/bin/git "$@"
