#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ "${EUID}" -ne 0 ]]; then
  echo "production release must run as root" >&2
  exit 1
fi

release_sha="${1:-}"
if [[ ! "$release_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: release.sh <exact-40-character-sha>" >&2
  exit 2
fi

source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
production_root="${SHANHAI_PRODUCTION_ROOT:-/opt/shanhaiedu-production}"
environment_file="$production_root/shared/production.env"
operation_lock="$production_root/shared/operations.lock"
manifest="$source_root/RELEASE_SHA"
compose=(docker compose --project-name shanhaiedu-production --env-file "$environment_file" -f "$source_root/infra/prod/compose.yaml")

if [[ "$source_root" != "$production_root/releases/$release_sha" ]]; then
  echo "release source is outside the exact production release directory" >&2
  exit 1
fi
if [[ ! -r "$manifest" ]] || [[ "$(tr -d '\r\n' < "$manifest")" != "$release_sha" ]]; then
  echo "release manifest does not match requested SHA" >&2
  exit 1
fi
if [[ "$(git -C "$source_root" rev-parse --verify HEAD)" != "$release_sha" ]]; then
  echo "release Git object does not match requested SHA" >&2
  exit 1
fi
if ! git -C "$source_root" diff --quiet || ! git -C "$source_root" diff --cached --quiet; then
  echo "release Git worktree contains tracked modifications" >&2
  exit 1
fi
unexpected_files="$(git -C "$source_root" status --porcelain --untracked-files=all | grep -v '^?? RELEASE_SHA$' || true)"
if [[ -n "$unexpected_files" ]]; then
  echo "release Git worktree contains unexpected files" >&2
  exit 1
fi
source "$source_root/infra/prod/operation-lock.sh"
if [[ ! -r "$environment_file" ]]; then
  echo "production environment file is unavailable" >&2
  exit 1
fi
prepare_production_operation_lock "$production_root"
exec 9>"$operation_lock"
if ! flock --exclusive --wait 60 9; then
  echo "another production release or rollback is active" >&2
  exit 1
fi

update_release_environment() {
  python3 "$source_root/infra/prod/update_production_release.py" "$environment_file" "$1" "$2" 0 600
}

environment_release_sha="$(
  python3 "$source_root/infra/prod/update_production_release.py" inspect "$environment_file" 0 600
)"
if [[ ! "$environment_release_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "production environment release SHA is invalid" >&2
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
export SHANHAI_RELEASE_SHA="$release_sha"
export SHANHAI_PRODUCTION_ROOT="$production_root"
export SHANHAI_SECRET_DIR="${SHANHAI_SECRET_DIR:-$production_root/shared/secrets}"
export COMPOSE_PARALLEL_LIMIT=1

require_text_provider_configuration() {
  local name
  for name in \
    SHANHAI_TEXT_PROVIDER_NAME \
    SHANHAI_TEXT_PROVIDER_BASE_URL \
    SHANHAI_TEXT_PROVIDER_MODEL; do
    if [[ -z "${!name:-}" ]]; then
      echo "production text provider configuration is incomplete" >&2
      exit 1
    fi
  done
  if [[ ! "$SHANHAI_TEXT_PROVIDER_BASE_URL" =~ ^https:// ]]; then
    echo "production text provider base URL must use HTTPS" >&2
    exit 1
  fi
}
require_text_provider_configuration

require_existing_secret() {
  local name="$1"
  local path="$SHANHAI_SECRET_DIR/$name"
  local owner group mode links size secret_value
  if [[ -L "$path" || ! -f "$path" ]]; then
    echo "required production secret is unavailable: $name" >&2
    exit 1
  fi
  read -r owner group mode links < <(stat -c '%u %g %a %h' -- "$path")
  if [[ "$owner:$group:$mode:$links" != "0:0:600:1" ]]; then
    echo "required production secret has unsafe metadata: $name" >&2
    exit 1
  fi
  size="$(stat -c '%s' -- "$path")"
  if ((size < 1 || size > 4096)); then
    echo "required production secret has an invalid size: $name" >&2
    exit 1
  fi
  secret_value="$(< "$path")"
  if [[ -z "$secret_value" || "$secret_value" == *$'\n'* || "$secret_value" == *$'\r'* ]]; then
    echo "required production secret has an invalid value: $name" >&2
    exit 1
  fi
  unset secret_value
}
require_existing_secret text_provider_api_key

previous_source=""
previous_sha=""
previous_release_path="$production_root/previous-release"
original_previous_release_present=false
original_previous_release_target=""
if [[ -L "$production_root/current" ]]; then
  previous_source="$(readlink -f "$production_root/current")"
  if [[ ! -r "$previous_source/RELEASE_SHA" ]]; then
    echo "current production release manifest is unavailable" >&2
    exit 1
  fi
  previous_sha="$(tr -d '\r\n' < "$previous_source/RELEASE_SHA")"
  if [[ ! "$previous_sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "current production release manifest is invalid" >&2
    exit 1
  fi
  if [[ "$environment_release_sha" != "$previous_sha" ]]; then
    echo "production environment release SHA does not match current release" >&2
    exit 1
  fi
elif [[ -e "$production_root/current" ]]; then
  echo "current production release is not a symbolic link" >&2
  exit 1
elif [[ "$environment_release_sha" != "$release_sha" ]]; then
  echo "initial production environment release SHA does not match requested release" >&2
  exit 1
fi
if [[ -L "$previous_release_path" ]]; then
  original_previous_release_present=true
  original_previous_release_target="$(readlink "$previous_release_path")"
elif [[ -e "$previous_release_path" ]]; then
  echo "previous-release is not a symbolic link" >&2
  exit 1
fi

image_source="$(
  bash "$source_root/infra/prod/validate-image-source.sh" \
    "$release_sha" "$production_root" 0 600
)"

rollback_release() {
  local status="$?"
  trap - ERR
  if [[ -n "$previous_source" ]]; then
    ln -sfn "$previous_source" "$production_root/current"
  else
    rm -f "$production_root/current"
  fi
  if [[ "$original_previous_release_present" == true ]]; then
    ln -sfn "$original_previous_release_target" "$previous_release_path"
  else
    rm -f "$previous_release_path"
  fi
  if ! update_release_environment "$release_sha" "$environment_release_sha"; then
    echo "production release environment rollback failed" >&2
  fi
  if [[ -n "$previous_source" ]]; then
    SHANHAI_RELEASE_SHA="$previous_sha" docker compose \
      --project-name shanhaiedu-production \
      --env-file "$environment_file" \
      -f "$previous_source/infra/prod/compose.yaml" \
      up -d --no-build api worker web || true
  else
    "${compose[@]}" stop api worker web >/dev/null 2>&1 || true
  fi
  echo "production release failed and application rollback was attempted" >&2
  exit "$status"
}
trap rollback_release ERR

install -d -m 0700 -o root -g root "$SHANHAI_SECRET_DIR"
install -d -m 0700 -o root -g root "$production_root/backups"
ensure_secret() {
  local name="$1"
  local bytes="$2"
  local path="$SHANHAI_SECRET_DIR/$name"
  if [[ ! -e "$path" ]]; then
    openssl rand -hex "$bytes" > "$path"
  fi
  chown root:root "$path"
  chmod 0600 "$path"
}
ensure_secret postgres_password 24
if [[ ! -e "$SHANHAI_SECRET_DIR/minio_root_user" ]]; then
  printf '%s\n' shanhai-prod > "$SHANHAI_SECRET_DIR/minio_root_user"
fi
chown root:root "$SHANHAI_SECRET_DIR/minio_root_user"
chmod 0600 "$SHANHAI_SECRET_DIR/minio_root_user"
ensure_secret minio_root_password 24
ensure_secret session_access_code 24
ensure_secret session_csrf_secret 32

"${compose[@]}" config --quiet
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ "$image_source" == "build" ]]; then
  "${compose[@]}" build api worker web
fi
"${compose[@]}" run --rm --no-deps worker python -c \
  'from apps.api.model_gateway.factory import build_real_text_gateway; from apps.api.settings import Settings; build_real_text_gateway(Settings())'
"${compose[@]}" up -d --wait --wait-timeout 120 postgres
pre_backup="$production_root/backups/pre-$release_sha-$timestamp.dump"
"${compose[@]}" exec -T postgres pg_dump \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}" \
  --format=custom > "$pre_backup"
chmod 0600 "$pre_backup"

"${compose[@]}" up -d --wait --wait-timeout 120 redis minio
minio_pre_backup="/backups/minio-pre-$release_sha-$timestamp"
"${compose[@]}" exec -T minio sh -eu -c '
  umask 077
  access_key="$(cat /run/secrets/minio_root_user)"
  secret_key="$(cat /run/secrets/minio_root_password)"
  export MC_HOST_production="http://${access_key}:${secret_key}@127.0.0.1:9000"
  bucket="$1"
  backup="$2"
  rm -rf "$backup"
  install -d -m 0700 "$backup"
  if mc stat "production/$bucket" >/dev/null 2>&1; then
    mc mirror --overwrite "production/$bucket" "$backup"
    printf "present\n" > "$backup/.bucket-state"
  else
    printf "absent\n" > "$backup/.bucket-state"
  fi
' sh "${SHANHAI_OBJECT_STORAGE_BUCKET:-shanhaiedu-production}" "$minio_pre_backup"
"${compose[@]}" run --rm api alembic upgrade head
"${compose[@]}" run --rm api python -m apps.api.cli bootstrap-production-storage
"${compose[@]}" run --rm api python -m apps.api.cli publish-golden-content
"${compose[@]}" run --rm api python -m apps.api.cli bootstrap-production-identity

post_backup="$production_root/backups/post-$release_sha-$timestamp.dump"
"${compose[@]}" exec -T postgres pg_dump \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}" \
  --format=custom > "$post_backup"
chmod 0600 "$post_backup"
restore_database="shanhai_restore_${release_sha:0:12}"
"${compose[@]}" exec -T postgres dropdb --if-exists \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" "$restore_database"
"${compose[@]}" exec -T postgres createdb \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" "$restore_database"
"${compose[@]}" exec -T postgres pg_restore \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "$restore_database" --exit-on-error < "$post_backup"
"${compose[@]}" exec -T postgres psql \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "$restore_database" -Atqc 'select version_num from alembic_version'
"${compose[@]}" exec -T postgres dropdb \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" "$restore_database"

minio_backup="/backups/minio-post-$release_sha-$timestamp"
restore_bucket="shanhai-restore-${release_sha:0:12}-$(date -u +%s)"
"${compose[@]}" exec -T minio sh -eu -c '
  umask 077
  access_key="$(cat /run/secrets/minio_root_user)"
  secret_key="$(cat /run/secrets/minio_root_password)"
  export MC_HOST_production="http://${access_key}:${secret_key}@127.0.0.1:9000"
  bucket="$1"
  backup="$2"
  restore_bucket="$3"
  rm -rf "$backup"
  install -d -m 0700 "$backup"
  mc mirror --overwrite "production/$bucket" "$backup"
  mc mb --ignore-existing "production/$restore_bucket"
  mc mirror --overwrite --remove "$backup" "production/$restore_bucket"
  if diff_output="$(mc diff "production/$bucket" "production/$restore_bucket")"; then
    if ! [[ -z "$diff_output" ]]; then
      echo "MinIO restore diff detected" >&2
      exit 1
    fi
  else
    echo "MinIO restore diff command failed" >&2
    exit 1
  fi
  mc rb --force "production/$restore_bucket"
' sh "${SHANHAI_OBJECT_STORAGE_BUCKET:-shanhaiedu-production}" "$minio_backup" "$restore_bucket"

"${compose[@]}" up -d --wait --wait-timeout 120 api worker web
SHANHAI_RELEASE_SHA="$release_sha" "$source_root/infra/prod/verify.sh" --local

if command -v nginx >/dev/null 2>&1; then
  nginx -t
fi
if [[ -n "$previous_source" ]]; then
  ln -sfn "$previous_source" "$previous_release_path"
fi
ln -sfn "$source_root" "$production_root/current"
update_release_environment "$environment_release_sha" "$release_sha"
trap - ERR
echo "production release activated: $release_sha"
