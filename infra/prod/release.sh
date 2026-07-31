#!/usr/bin/env bash
set -Eeuo pipefail

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
manifest="$source_root/RELEASE_SHA"
compose=(docker compose --env-file "$environment_file" -f "$source_root/infra/prod/compose.yaml")

if [[ "$source_root" != "$production_root/releases/$release_sha" ]]; then
  echo "release source is outside the exact production release directory" >&2
  exit 1
fi
if [[ ! -r "$manifest" ]] || [[ "$(tr -d '\r\n' < "$manifest")" != "$release_sha" ]]; then
  echo "release manifest does not match requested SHA" >&2
  exit 1
fi
if [[ ! -r "$environment_file" ]]; then
  echo "production environment file is unavailable" >&2
  exit 1
fi

set -a
source "$environment_file"
set +a
export SHANHAI_RELEASE_SHA="$release_sha"
export SHANHAI_PRODUCTION_ROOT="$production_root"
export SHANHAI_SECRET_DIR="${SHANHAI_SECRET_DIR:-$production_root/shared/secrets}"

install -d -m 0700 -o root -g root "$SHANHAI_SECRET_DIR"
install -d -m 0700 -o root -g root "$production_root/backups"
ensure_secret() {
  local name="$1"
  local bytes="$2"
  local path="$SHANHAI_SECRET_DIR/$name"
  if [[ ! -e "$path" ]]; then
    umask 077
    openssl rand -hex "$bytes" > "$path"
  fi
  chown root:root "$path"
  chmod 0600 "$path"
}
ensure_secret postgres_password 24
if [[ ! -e "$SHANHAI_SECRET_DIR/minio_root_user" ]]; then
  umask 077
  printf '%s\n' shanhai-prod > "$SHANHAI_SECRET_DIR/minio_root_user"
fi
chmod 0600 "$SHANHAI_SECRET_DIR/minio_root_user"
ensure_secret minio_root_password 24
ensure_secret session_access_code 24
ensure_secret session_csrf_secret 32

"${compose[@]}" config --quiet

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -n "$("${compose[@]}" ps -q postgres 2>/dev/null)" ]]; then
  pre_backup="$production_root/backups/pre-$release_sha-$timestamp.dump"
  "${compose[@]}" exec -T postgres pg_dump \
    -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
    -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}" \
    --format=custom > "$pre_backup"
  chmod 0600 "$pre_backup"
fi

"${compose[@]}" build api worker web
"${compose[@]}" up -d postgres redis minio
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

"${compose[@]}" up -d api worker web
SHANHAI_RELEASE_SHA="$release_sha" "$source_root/infra/prod/verify.sh" --local

if [[ -L "$production_root/current" ]]; then
  previous="$(readlink -f "$production_root/current")"
  ln -sfn "$previous" "$production_root/previous-release"
fi
ln -sfn "$source_root" "$production_root/current"
if command -v nginx >/dev/null 2>&1; then
  nginx -t
fi

echo "production release activated: $release_sha"
