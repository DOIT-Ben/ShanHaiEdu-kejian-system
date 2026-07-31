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
available=/etc/nginx/sites-available/shanhaiedu-production-ip
enabled=/etc/nginx/sites-enabled/shanhaiedu-production-ip
legacy_enabled=/etc/nginx/sites-enabled/image-studio-theme-qa-ip
backup_root="$production_root/shared/nginx-backup"
backup="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$backup"
if [[ -L "$legacy_enabled" ]]; then
  readlink "$legacy_enabled" > "$backup/legacy-enabled-target"
  cp -a "$(readlink -f "$legacy_enabled")" "$backup/legacy-site"
fi

restore_legacy() {
  rm -f "$enabled"
  if [[ -r "$backup/legacy-enabled-target" ]]; then
    legacy_target="$(cat "$backup/legacy-enabled-target")"
    cp -a "$backup/legacy-site" "$legacy_target"
    ln -sfn "$legacy_target" "$legacy_enabled"
  fi
  nginx -t && systemctl reload nginx
}
trap restore_legacy ERR

install -d -m 0755 /var/lib/letsencrypt/.well-known/acme-challenge
sed "s/\${SHANHAI_PUBLIC_IP}/$public_ip/g" \
  "$source_root/infra/prod/host-nginx-http.conf.template" > "$available"
rm -f "$legacy_enabled"
ln -sfn "$available" "$enabled"
nginx -t
systemctl reload nginx

certbot_root="$production_root/shared/certbot"
if [[ ! -x "$certbot_root/bin/certbot" ]]; then
  apt-get update
  apt-get install --yes --no-install-recommends python3-venv
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

sed "s/\${SHANHAI_PUBLIC_IP}/$public_ip/g" \
  "$source_root/infra/prod/host-nginx.conf.template" > "$available"
nginx -t
systemctl reload nginx

cat > /etc/systemd/system/shanhaiedu-ip-cert-renew.service <<EOF
[Unit]
Description=Renew ShanHaiEdu short-lived IP certificate
After=network-online.target

[Service]
Type=oneshot
ExecStart=$certbot_root/bin/certbot renew --quiet --preferred-profile shortlived
ExecStartPost=/usr/sbin/nginx -t
ExecStartPost=/usr/bin/systemctl reload nginx
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
printf '%s\n' "$backup" > "$backup_root/latest"
trap - ERR
echo "host HTTPS configured for $public_ip"
