#!/usr/bin/env bash
set -Eeuo pipefail

production_root="${SHANHAI_PRODUCTION_ROOT:-/opt/shanhaiedu-production}"
environment_file="$production_root/shared/production.env"
set -a
source "$environment_file"
set +a

"$production_root/current/infra/prod/verify.sh" --public
if [[ -n "${SHANHAI_TLS_CERTIFICATE:-}" ]]; then
  openssl x509 -checkend 86400 -noout -in "$SHANHAI_TLS_CERTIFICATE"
fi

compose=(docker compose --project-name shanhaiedu-production --env-file "$environment_file" -f "$production_root/current/infra/prod/compose.yaml")
available_kib="$(df -Pk "$production_root" | awk 'NR == 2 {print $4}')"
if [[ ! "$available_kib" =~ ^[0-9]+$ || "$available_kib" -lt 5242880 ]]; then
  echo "production disk space is below the 5 GiB monitor floor" >&2
  exit 1
fi

db_connections="$("${compose[@]}" exec -T postgres psql \
  -U "${SHANHAI_POSTGRES_USER:-shanhai_prod}" \
  -d "${SHANHAI_POSTGRES_DB:-shanhai_prod}" -Atqc \
  'select count(*) from pg_stat_activity where datname = current_database()')"
if [[ ! "$db_connections" =~ ^[0-9]+$ ]]; then
  echo "production database connection metric is unavailable" >&2
  exit 1
fi

queue_depth="$("${compose[@]}" exec -T redis sh -c \
  'redis-cli --scan --pattern "dq.*" | while read -r key; do redis-cli llen "$key"; done' \
  | awk '{sum += $1} END {print sum + 0}')"
if [[ ! "$queue_depth" =~ ^[0-9]+$ || "$queue_depth" -gt "${SHANHAI_QUEUE_DEPTH_MAX:-1000}" ]]; then
  echo "production queue depth is above the configured monitor limit" >&2
  exit 1
fi

latency_seconds="$(curl -fsS -o /dev/null -w '%{time_total}' --max-time 10 http://127.0.0.1:18000/health/live)"
if ! awk -v value="$latency_seconds" 'BEGIN {exit !(value < 5)}'; then
  echo "production liveness latency is above the 5 second monitor limit" >&2
  exit 1
fi

http_5xx="$("${compose[@]}" logs --since 5m api 2>&1 | awk '/"http_status":5[0-9][0-9]/ {count++} END {print count + 0}')"
if [[ "$http_5xx" =~ ^[0-9]+$ && "$http_5xx" -gt "${SHANHAI_HTTP_5XX_MAX:-10}" ]]; then
  echo "production HTTP 5xx count is above the configured monitor limit" >&2
  exit 1
fi
echo "production monitor passed"
