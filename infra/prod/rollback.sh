#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ "${EUID}" -ne 0 ]]; then
  echo "production rollback must run as root" >&2
  exit 1
fi

production_root="${SHANHAI_PRODUCTION_ROOT:-/opt/shanhaiedu-production}"
operation_lock="$production_root/shared/operations.lock"
script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_root/operation-lock.sh"
prepare_production_operation_lock "$production_root"
exec 9>"$operation_lock"
if ! flock --exclusive --wait 60 9; then
  echo "another production release or rollback is active" >&2
  exit 1
fi
previous="$production_root/previous-release"
environment_file="$production_root/shared/production.env"
if [[ ! -L "$previous" ]]; then
  echo "previous-release is unavailable" >&2
  exit 1
fi
previous_source="$(readlink -f "$previous")"
previous_sha="$(tr -d '\r\n' < "$previous_source/RELEASE_SHA")"
if [[ ! "$previous_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "previous release manifest is invalid" >&2
  exit 1
fi
if [[ ! -L "$production_root/current" ]]; then
  echo "current release is unavailable" >&2
  exit 1
fi
current_source="$(readlink -f "$production_root/current")"
current_sha="$(tr -d '\r\n' < "$current_source/RELEASE_SHA")"
if [[ ! "$current_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "current release manifest is invalid" >&2
  exit 1
fi

update_release_environment() {
  python3 "$script_root/update_production_release.py" "$environment_file" "$1" "$2" 0 600
}

environment_release_sha="$(
  python3 "$script_root/update_production_release.py" inspect "$environment_file" 0 600
)"
if [[ "$environment_release_sha" != "$current_sha" ]]; then
  echo "production environment release SHA does not match current release" >&2
  exit 1
fi
update_release_environment "$environment_release_sha" "$environment_release_sha" >/dev/null
set -a
source "$environment_file"
set +a
sourced_environment_release_sha="${SHANHAI_RELEASE_SHA:?"production environment release SHA is required"}"
if [[ "$sourced_environment_release_sha" != "$environment_release_sha" ]]; then
  echo "production environment release SHA changed during validation" >&2
  exit 1
fi
export SHANHAI_RELEASE_SHA="$previous_sha"
export SHANHAI_SECRET_DIR="${SHANHAI_SECRET_DIR:-$production_root/shared/secrets}"
compose=(docker compose --env-file "$environment_file" -f "$previous_source/infra/prod/compose.yaml")

rollback_rollback() {
  local status="$?"
  trap - ERR
  ln -sfn "$previous_source" "$production_root/previous-release"
  ln -sfn "$current_source" "$production_root/current"
  if ! update_release_environment "$previous_sha" "$current_sha"; then
    echo "production rollback environment restoration failed" >&2
  fi
  SHANHAI_RELEASE_SHA="$current_sha" docker compose \
    --env-file "$environment_file" \
    -f "$current_source/infra/prod/compose.yaml" \
    up -d --no-build api worker web || true
  echo "production rollback failed and application restoration was attempted" >&2
  exit "$status"
}
trap rollback_rollback ERR

"${compose[@]}" up -d --no-build api worker web
SHANHAI_RELEASE_SHA="$previous_sha" "$previous_source/infra/prod/verify.sh" --local

ln -sfn "$current_source" "$production_root/previous-release"
ln -sfn "$previous_source" "$production_root/current"
update_release_environment "$current_sha" "$previous_sha"
nginx -t
systemctl reload nginx
trap - ERR
echo "application rollback activated: $previous_sha"
