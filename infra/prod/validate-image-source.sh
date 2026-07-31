#!/usr/bin/env bash
set -Eeuo pipefail

release_sha="${1:-}"
production_root="${2:-}"
expected_owner_uid="${3:-0}"
expected_mode="${4:-600}"
image_source="${SHANHAI_IMAGE_SOURCE:-build}"

if [[ ! "$release_sha" =~ ^[0-9a-f]{40}$ ]] || [[ -z "$production_root" ]]; then
  echo "image source preflight requires an exact release SHA and production root" >&2
  exit 2
fi
if [[ ! "$expected_owner_uid" =~ ^[0-9]+$ ]] || [[ ! "$expected_mode" =~ ^[0-7]{3,4}$ ]]; then
  echo "image source preflight manifest ownership contract is invalid" >&2
  exit 2
fi

case "$image_source" in
  build)
    printf 'build\n'
    exit 0
    ;;
  preloaded)
    ;;
  *)
    echo "SHANHAI_IMAGE_SOURCE must be build or preloaded" >&2
    exit 2
    ;;
esac

manifest="$production_root/shared/preloaded-images/$release_sha.env"
if [[ ! -f "$manifest" || -L "$manifest" ]]; then
  echo "preloaded image manifest is unavailable" >&2
  exit 1
fi
read -r manifest_owner manifest_mode < <(stat -c '%u %a' -- "$manifest")
if [[ "$manifest_owner" != "$expected_owner_uid" || "$manifest_mode" != "$expected_mode" ]]; then
  echo "preloaded image manifest ownership or mode is invalid" >&2
  exit 1
fi

manifest_release_sha=""
api_image_id=""
web_image_id=""
archive_sha256=""
declare -A seen=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  if [[ "$line" != *=* ]]; then
    echo "preloaded image manifest contains an invalid entry" >&2
    exit 1
  fi
  key="${line%%=*}"
  value="${line#*=}"
  if [[ -n "${seen[$key]:-}" ]]; then
    echo "preloaded image manifest contains a duplicate entry" >&2
    exit 1
  fi
  seen[$key]=1
  case "$key" in
    SHANHAI_RELEASE_SHA) manifest_release_sha="$value" ;;
    SHANHAI_PRELOADED_API_IMAGE_ID) api_image_id="$value" ;;
    SHANHAI_PRELOADED_WEB_IMAGE_ID) web_image_id="$value" ;;
    SHANHAI_PRELOADED_ARCHIVE_SHA256) archive_sha256="$value" ;;
    *)
      echo "preloaded image manifest contains an unexpected entry" >&2
      exit 1
      ;;
  esac
done < "$manifest"

if [[ "$manifest_release_sha" != "$release_sha" ]]; then
  echo "preloaded image manifest release SHA does not match" >&2
  exit 1
fi
if [[ ! "$api_image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || \
   [[ ! "$web_image_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "preloaded image manifest image ID is invalid" >&2
  exit 1
fi
if [[ ! "$archive_sha256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "preloaded image manifest archive SHA-256 is invalid" >&2
  exit 1
fi

verify_image() {
  local image="$1"
  local expected_image_id="$2"
  local actual_image_id revision

  if ! actual_image_id="$(docker image inspect "$image" --format '{{.Id}}' 2>/dev/null)"; then
    echo "preloaded production image is unavailable: $image" >&2
    return 1
  fi
  if [[ ! "$actual_image_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "preloaded production image ID is invalid: $image" >&2
    return 1
  fi
  if [[ "$actual_image_id" != "$expected_image_id" ]]; then
    echo "preloaded production image ID does not match manifest: $image" >&2
    return 1
  fi
  if ! revision="$(docker image inspect "$image" \
    --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null)"; then
    echo "preloaded production image revision is unavailable: $image" >&2
    return 1
  fi
  if [[ -z "$revision" || "$revision" == "<no value>" ]]; then
    echo "preloaded production image revision is missing: $image" >&2
    return 1
  fi
  if [[ "$revision" != "$release_sha" ]]; then
    echo "preloaded production image revision does not match release SHA: $image" >&2
    return 1
  fi
}

verify_image "shanhaiedu-api:$release_sha" "$api_image_id"
verify_image "shanhaiedu-web:$release_sha" "$web_image_id"
printf 'preloaded\n'
