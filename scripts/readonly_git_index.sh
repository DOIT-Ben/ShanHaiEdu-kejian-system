#!/usr/bin/env bash

readonly_git_index_file=""

prepare_readonly_git_index() {
  local repo_root source_index
  repo_root="$(GIT_INDEX_FILE=/dev/null GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel)"
  source_index="$(GIT_INDEX_FILE=/dev/null GIT_OPTIONAL_LOCKS=0 git -C "$repo_root" rev-parse --path-format=absolute --git-dir)/index"
  readonly_git_index_file="$(mktemp "${TMPDIR:-/tmp}/shanhaiedu-git-index.XXXXXX")"
  cp -- "$source_index" "$readonly_git_index_file"
  export GIT_INDEX_FILE="$readonly_git_index_file"
  export GIT_OPTIONAL_LOCKS=0
}

cleanup_readonly_git_index() {
  if [[ -n "$readonly_git_index_file" ]]; then
    rm -f -- "$readonly_git_index_file"
    readonly_git_index_file=""
  fi
}
