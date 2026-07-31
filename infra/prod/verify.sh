#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:---public}"
production_root="${SHANHAI_PRODUCTION_ROOT:-/opt/shanhaiedu-production}"
environment_file="${SHANHAI_ENV_FILE:-$production_root/shared/production.env}"
set -a
source "$environment_file"
set +a
release_sha="${SHANHAI_RELEASE_SHA:?exact release SHA is required}"
compose_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/compose.yaml"
compose=(docker compose --project-name "${SHANHAI_COMPOSE_PROJECT:-shanhaiedu-production}" --env-file "$environment_file" -f "$compose_file")

assert_release() {
  python3 -c 'import json,sys; payload=json.load(sys.stdin); expected=sys.argv[1]; actual=payload["data"]["release_sha"]; raise SystemExit(0 if actual == expected else 1)' "$release_sha"
}

curl -fsS --max-time 10 http://127.0.0.1:18000/health/live | assert_release
curl -fsS --max-time 10 http://127.0.0.1:18000/health/ready >/dev/null
curl -fsS --max-time 10 http://127.0.0.1:18080/ >/dev/null
curl -fsS --max-time 10 http://127.0.0.1:19000/minio/health/ready >/dev/null
"${compose[@]}" exec -T postgres pg_isready \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}"
"${compose[@]}" exec -T redis redis-cli ping | grep -qx PONG
"${compose[@]}" exec -T worker python -m workers.main --check

if "${compose[@]}" logs --since 10m 2>&1 | grep -Eiq \
  'MODEL_GATEWAY_API_KEY|SHANHAI_SESSION_ACCESS_CODE|SHANHAI_SESSION_CSRF_SECRET|postgres_password'; then
  echo "production logs contain a forbidden secret identifier" >&2
  exit 1
fi

if [[ "$mode" == "--public" ]]; then
  curl -fsS --max-time 15 "https://${SHANHAI_PUBLIC_IP}/health/live" | assert_release
  curl -fsS --max-time 15 "https://${SHANHAI_PUBLIC_IP}/" >/dev/null
  echo | openssl s_client -connect "${SHANHAI_PUBLIC_IP}:443" \
    -verify_ip "$SHANHAI_PUBLIC_IP" -verify_return_error 2>/dev/null | grep -q 'Verify return code: 0'
fi

echo "production verification passed: $release_sha"
