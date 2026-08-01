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

set -a
source "$environment_file"
set +a
export SHANHAI_RELEASE_SHA="$previous_sha"
export SHANHAI_SECRET_DIR="${SHANHAI_SECRET_DIR:-$production_root/shared/secrets}"
compose=(docker compose --env-file "$environment_file" -f "$previous_source/infra/prod/compose.yaml")
"${compose[@]}" up -d --no-build api worker web
SHANHAI_RELEASE_SHA="$previous_sha" "$previous_source/infra/prod/verify.sh" --local

current_source="$(readlink -f "$production_root/current")"
ln -sfn "$current_source" "$production_root/previous-release"
ln -sfn "$previous_source" "$production_root/current"
nginx -t
systemctl reload nginx
echo "application rollback activated: $previous_sha"
