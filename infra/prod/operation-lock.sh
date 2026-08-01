#!/usr/bin/env bash

prepare_production_operation_lock() {
  local production_root="$1"
  local shared_dir="$production_root/shared"
  local operation_lock="$shared_dir/operations.lock"
  local shared_owner shared_group shared_mode
  local lock_owner lock_group lock_mode lock_links

  if [[ -L "$shared_dir" || ! -d "$shared_dir" ]]; then
    echo "production shared directory is invalid" >&2
    return 1
  fi
  read -r shared_owner shared_group shared_mode < <(stat -c "%u %g %a" -- "$shared_dir")
  if [[ "$shared_owner:$shared_group" != "0:0" ]] || (( (8#$shared_mode & 8#022) != 0 )); then
    echo "production shared directory permissions are unsafe" >&2
    return 1
  fi
  if [[ -L "$operation_lock" ]]; then
    echo "production operation lock must not be a symbolic link" >&2
    return 1
  fi
  if [[ ! -e "$operation_lock" ]]; then
    if ! (umask 077; set -o noclobber; : > "$operation_lock") 2>/dev/null && [[ ! -e "$operation_lock" ]]; then
      echo "production operation lock could not be created" >&2
      return 1
    fi
  fi
  if [[ -L "$operation_lock" ]] || [[ ! -f "$operation_lock" ]]; then
    echo "production operation lock is not a regular file" >&2
    return 1
  fi
  read -r lock_owner lock_group lock_mode lock_links < <(
    stat -c "%u %g %a %h" -- "$operation_lock"
  )
  if [[ "$lock_links" != "1" ]]; then
    echo "production operation lock has an unsafe link count" >&2
    return 1
  fi
  if [[ "$lock_owner:$lock_group" != "0:0" ]]; then
    chown root:root -- "$operation_lock"
  fi
  if [[ "$lock_mode" != "600" ]]; then
    chmod 0600 -- "$operation_lock"
  fi
  read -r lock_owner lock_group lock_mode lock_links < <(
    stat -c "%u %g %a %h" -- "$operation_lock"
  )
  if [[ "$lock_owner:$lock_group:$lock_mode:$lock_links" != "0:0:600:1" ]]; then
    echo "production operation lock permissions are unsafe" >&2
    return 1
  fi
}
