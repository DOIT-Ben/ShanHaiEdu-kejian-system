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
source "$source_root/infra/prod/operation-lock.sh"

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

set -a
source "$environment_file"
set +a
export SHANHAI_RELEASE_SHA="$release_sha"
export SHANHAI_PRODUCTION_ROOT="$production_root"
export SHANHAI_SECRET_DIR="${SHANHAI_SECRET_DIR:-$production_root/shared/secrets}"
export COMPOSE_PARALLEL_LIMIT=1

image_source="$(
  bash "$source_root/infra/prod/validate-image-source.sh" \
    "$release_sha" "$production_root" 0 600
)"

previous_source=""
if [[ -L "$production_root/current" ]]; then
  previous_source="$(readlink -f "$production_root/current")"
fi
rollback_release() {
  local status="$?"
  trap - ERR
  if [[ -n "$previous_source" ]]; then
    ln -sfn "$previous_source" "$production_root/current"
  else
    rm -f "$production_root/current"
  fi
  if [[ -n "$previous_source" && -r "$previous_source/RELEASE_SHA" ]]; then
    local previous_sha
    previous_sha="$(tr -d '\r\n' < "$previous_source/RELEASE_SHA")"
    if [[ "$previous_sha" =~ ^[0-9a-f]{40}$ ]]; then
      SHANHAI_RELEASE_SHA="$previous_sha" docker compose \
        --project-name shanhaiedu-production \
        --env-file "$environment_file" \
        -f "$previous_source/infra/prod/compose.yaml" \
        up -d --no-build api worker web || true
    fi
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
  ln -sfn "$previous_source" "$production_root/previous-release"
fi
ln -sfn "$source_root" "$production_root/current"
trap - ERR
echo "production release activated: $release_sha"
