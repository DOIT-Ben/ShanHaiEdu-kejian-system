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

wait_for_local_endpoint() {
  local url="$1"
  local attempt response
  for ((attempt = 1; attempt <= 30; attempt++)); do
    if response="$(curl -fsS --connect-timeout 1 --max-time 3 "$url")"; then
      printf '%s' "$response"
      return 0
    fi
    if ((attempt < 30)); then
      sleep 1
    fi
  done
  echo "production loopback endpoint did not become ready: $url" >&2
  return 1
}

live_payload="$(wait_for_local_endpoint "http://127.0.0.1:18080/health/live")"
printf '%s' "$live_payload" | assert_release
wait_for_local_endpoint "http://127.0.0.1:18080/health/ready" >/dev/null
wait_for_local_endpoint "http://127.0.0.1:18080/" >/dev/null
"${compose[@]}" exec -T postgres pg_isready \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}"
"${compose[@]}" exec -T redis redis-cli ping | grep -qx PONG
"${compose[@]}" exec -T minio \
  curl -fsS http://127.0.0.1:9000/minio/health/ready >/dev/null
"${compose[@]}" exec -T worker python -m workers.main --check

if "${compose[@]}" logs --since 10m 2>&1 | grep -Eiq \
  'MODEL_GATEWAY_API_KEY|SHANHAI_SESSION_ACCESS_CODE|SHANHAI_SESSION_CSRF_SECRET|postgres_password'; then
  echo "production logs contain a forbidden secret identifier" >&2
  exit 1
fi

if [[ "$mode" == "--public" ]]; then
  nginx_log_root="${SHANHAI_NGINX_LOG_ROOT:-/var/log/nginx}"
  for nginx_log in \
    "$nginx_log_root/shanhaiedu-production-access.log" \
    "$nginx_log_root/shanhaiedu-production-error.log"; do
    [[ -f "$nginx_log" ]] || continue
    if tail -n 2000 "$nginx_log" | grep -Eiq \
      'X-Amz-(Credential|Signature)|SHANHAI_SESSION_ACCESS_CODE|SHANHAI_SESSION_CSRF_SECRET'; then
      echo "host proxy logs contain a forbidden credential marker" >&2
      exit 1
    fi
  done
  curl -fsS --max-time 15 "https://${SHANHAI_PUBLIC_IP}/health/live" | assert_release
  curl -fsS --max-time 15 "https://${SHANHAI_PUBLIC_IP}/" >/dev/null
  if [[ -n "${SHANHAI_TLS_CERTIFICATE:-}" ]]; then
    openssl x509 -checkend 86400 -noout -in "$SHANHAI_TLS_CERTIFICATE"
  fi
fi

echo "production verification passed: $release_sha"
