#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "host configuration must run as root" >&2
  exit 1
fi

production_root="${SHANHAI_PRODUCTION_ROOT:-/opt/shanhaiedu-production}"
environment_file="$production_root/shared/production.env"
set -a
source "$environment_file"
set +a
public_ip="${SHANHAI_PUBLIC_IP:?public IP is required}"
if [[ ! "$public_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "public IPv4 address is invalid" >&2
  exit 1
fi

source_root="$(readlink -f "$production_root/current")"
nginx_binary="$(command -v nginx)"
nginx_site_dir="${SHANHAI_NGINX_SITE_DIR:-/etc/nginx/sites-enabled}"
nginx_log_root="${SHANHAI_NGINX_LOG_ROOT:-/var/log/nginx}"
legacy_site="${SHANHAI_LEGACY_NGINX_SITE:-}"
enabled="$nginx_site_dir/shanhaiedu-production-ip.conf"
tls_certificate="${SHANHAI_TLS_CERTIFICATE:-}"
tls_private_key="${SHANHAI_TLS_PRIVATE_KEY:-}"
backup_root="$production_root/shared/nginx-backup"
backup="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0755 "$nginx_site_dir"
install -d -m 0755 "$nginx_log_root"
install -d -m 0700 "$backup"
if [[ -e "$enabled" ]]; then
  cp -a "$enabled" "$backup/previous-production-site"
fi
if [[ -n "$legacy_site" && -e "$legacy_site" ]]; then
  cp -a "$legacy_site" "$backup/legacy-site"
  printf '%s\n' "$legacy_site" > "$backup/legacy-site-path"
fi

activate_nginx() {
  "$nginx_binary" -t
  if pgrep -x nginx >/dev/null; then
    "$nginx_binary" -s reload
  else
    systemctl start nginx
  fi
  pgrep -x nginx >/dev/null
}

restore_legacy() {
  rm -f "$enabled"
  if [[ -r "$backup/previous-production-site" ]]; then
    cp -a "$backup/previous-production-site" "$enabled"
  fi
  if [[ -r "$backup/legacy-site-path" ]]; then
    legacy_target="$(cat "$backup/legacy-site-path")"
    cp -a "$backup/legacy-site" "$legacy_target"
  fi
  activate_nginx
}
trap restore_legacy ERR

if [[ -n "$legacy_site" ]]; then
  rm -f "$legacy_site"
fi
if [[ -z "$tls_certificate" || -z "$tls_private_key" ]]; then
  install -d -m 0755 /var/lib/letsencrypt/.well-known/acme-challenge
  sed "s/\${SHANHAI_PUBLIC_IP}/$public_ip/g" \
    "$source_root/infra/prod/host-nginx-http.conf.template" > "$enabled"
  activate_nginx

  certbot_root="$production_root/shared/certbot"
  if [[ ! -x "$certbot_root/bin/certbot" ]]; then
    python3 -m venv "$certbot_root"
    "$certbot_root/bin/pip" install --disable-pip-version-check 'certbot==5.4.0'
  fi
  "$certbot_root/bin/certbot" certonly \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --preferred-profile shortlived \
    --webroot \
    --webroot-path /var/lib/letsencrypt \
    --ip-address "$public_ip" \
    --cert-name "$public_ip"
  tls_certificate="/etc/letsencrypt/live/$public_ip/fullchain.pem"
  tls_private_key="/etc/letsencrypt/live/$public_ip/privkey.pem"
  if grep -q '^SHANHAI_TLS_CERTIFICATE=' "$environment_file"; then
    sed -i "s|^SHANHAI_TLS_CERTIFICATE=.*|SHANHAI_TLS_CERTIFICATE=$tls_certificate|" "$environment_file"
  else
    printf 'SHANHAI_TLS_CERTIFICATE=%s\n' "$tls_certificate" >> "$environment_file"
  fi
  if grep -q '^SHANHAI_TLS_PRIVATE_KEY=' "$environment_file"; then
    sed -i "s|^SHANHAI_TLS_PRIVATE_KEY=.*|SHANHAI_TLS_PRIVATE_KEY=$tls_private_key|" "$environment_file"
  else
    printf 'SHANHAI_TLS_PRIVATE_KEY=%s\n' "$tls_private_key" >> "$environment_file"
  fi
  chmod 0600 "$environment_file"
fi
if [[ ! -r "$tls_certificate" || ! -r "$tls_private_key" ]]; then
  echo "configured TLS material is unavailable" >&2
  false
fi

sed \
  -e "s|\${SHANHAI_PUBLIC_IP}|$public_ip|g" \
  -e "s|\${SHANHAI_TLS_CERTIFICATE}|$tls_certificate|g" \
  -e "s|\${SHANHAI_TLS_PRIVATE_KEY}|$tls_private_key|g" \
  -e "s|\${SHANHAI_NGINX_LOG_ROOT}|$nginx_log_root|g" \
  "$source_root/infra/prod/host-nginx.conf.template" > "$enabled"
activate_nginx

cat > /etc/systemd/system/shanhaiedu-health-alert@.service <<'EOF'
[Unit]
Description=Record a redacted ShanHaiEdu production health alert

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/bin/systemd-cat -p err -t shanhaiedu-monitor echo "production healthcheck failed unit=%i"'
EOF
cat > /etc/systemd/system/shanhaiedu-healthcheck.service <<EOF
[Unit]
Description=Verify ShanHaiEdu production health and certificate lifetime
After=docker.service nginx.service
OnFailure=shanhaiedu-health-alert@%n.service

[Service]
Type=oneshot
ExecStart=$production_root/current/infra/prod/monitor.sh
EOF
cat > /etc/systemd/system/shanhaiedu-healthcheck.timer <<'EOF'
[Unit]
Description=Verify ShanHaiEdu production every five minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=30
Persistent=true

[Install]
WantedBy=timers.target
EOF

if [[ -n "${certbot_root:-}" ]]; then
  cat > /etc/systemd/system/shanhaiedu-ip-cert-renew.service <<EOF
[Unit]
Description=Renew ShanHaiEdu short-lived IP certificate
After=network-online.target
OnFailure=shanhaiedu-health-alert@%n.service

[Service]
Type=oneshot
ExecStart=$certbot_root/bin/certbot renew --quiet --preferred-profile shortlived
ExecStartPost=$nginx_binary -t
ExecStartPost=$nginx_binary -s reload
EOF
  cat > /etc/systemd/system/shanhaiedu-ip-cert-renew.timer <<'EOF'
[Unit]
Description=Check ShanHaiEdu short-lived IP certificate twice daily

[Timer]
OnCalendar=*-*-* 00,12:17:00
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now shanhaiedu-ip-cert-renew.timer
fi
systemctl daemon-reload
systemctl enable --now shanhaiedu-healthcheck.timer
printf '%s\n' "$backup" > "$backup_root/latest"
trap - ERR
echo "host HTTPS configured for $public_ip"
