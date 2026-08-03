#!/bin/sh
set -eu

read_secret() {
  secret_path="/run/secrets/$1"
  if [ ! -r "$secret_path" ]; then
    echo "required runtime secret is unavailable: $1" >&2
    exit 1
  fi
  tr -d '\r\n' < "$secret_path"
}

postgres_password="$(read_secret postgres_password)"
minio_root_user="$(read_secret minio_root_user)"
minio_root_password="$(read_secret minio_root_password)"
export SHANHAI_DATABASE_URL="postgresql://${SHANHAI_POSTGRES_USER}:${postgres_password}@postgres:5432/${SHANHAI_POSTGRES_DB}"
export SHANHAI_OBJECT_STORAGE_ACCESS_KEY="$minio_root_user"
export SHANHAI_OBJECT_STORAGE_SECRET_KEY="$minio_root_password"
export SHANHAI_SESSION_ACCESS_CODE="$(read_secret session_access_code)"
export SHANHAI_SESSION_CSRF_SECRET="$(read_secret session_csrf_secret)"
unset postgres_password minio_root_user minio_root_password

if [ -n "${SHANHAI_TEXT_PROVIDER_SECRET_ENV:-}" ]; then
  case "$SHANHAI_TEXT_PROVIDER_SECRET_ENV" in
    [!A-Z]* | *[!A-Z0-9_]*)
      echo "invalid text provider secret environment name" >&2
      exit 1
      ;;
  esac
  if [ "${#SHANHAI_TEXT_PROVIDER_SECRET_ENV}" -lt 3 ]; then
    echo "invalid text provider secret environment name" >&2
    exit 1
  fi
  text_provider_api_key="$(read_secret text_provider_api_key)"
  export "$SHANHAI_TEXT_PROVIDER_SECRET_ENV=$text_provider_api_key"
  unset text_provider_api_key
fi

exec gosu 10001:10001 "$@"
