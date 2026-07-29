# Provider Media Relay

Owner: infrastructure maintainers. Audience: operators deploying the controlled image relay for #156. Canonical location: `infra/provider-media-relay/`; replace this runbook in the same path if deployment moves to managed infrastructure.

This service exposes one short-lived, signed PNG/JPEG/WebP GET path to an external video Provider. It is not an upload endpoint, a public asset API, or a storage proxy. The service only listens on `127.0.0.1:8201`; Nginx exposes it under `https://newapi.doitbenai.cloud/_shanhai-provider-media/`.

## Prerequisites

- The Git object database is `/srv/shanhaiedu/repository`; deployment reads exact files from the fetched `origin/main` commit without checking out or modifying the canonical worktree.
- Relay serving and scheduled cleanup both use the standard-library-only, root-owned runtime under `/opt/shanhaiedu/provider-media-relay`; no project virtual environment is required.
- The existing TLS vhost is `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`.
- The controlled producer configuration is `/etc/shanhaiedu/image-video-smoke.env`; it and the relay environment must receive the same rotated secret in one privileged shell.
- The runtime image directory is private and writable only by the trusted server-side producer. This relay must never be pointed at MinIO data, uploads, or an application-wide filesystem root.
- The operator has root access. Do not paste the signing secret into tickets, shell history, CI logs, Git, or a client application.

## Deploy

Run all deploy steps below in one privileged shell so the pinned `origin/main` SHA and blob hash remain unchanged between preflight, installation, and restart. Any failed command must stop the deployment; do not continue from a failed step.

1. Before `useradd`, `install`, service restart, or Nginx reload, fetch as the repository owner and pin `origin/main`. Stage every installed file directly from that commit's Git objects. This deliberately leaves the canonical checkout's branch, index, and dirty files untouched:

   ```bash
   set -euo pipefail
   repository_root=/srv/shanhaiedu/repository
   producer_env=/etc/shanhaiedu/image-video-smoke.env
   test -f "${producer_env}"
   test "$(grep -c '^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=' "${producer_env}")" -eq 1
   sudo -u shanhai-dev -H git -C "${repository_root}" fetch origin --prune
   deployment_origin_main_sha="$(sudo -u shanhai-dev -H git -C "${repository_root}" rev-parse origin/main)"
   deployment_staging="$(mktemp -d)"
   smoke_path=/srv/shanhaiedu/runtime/provider-media/provider-relay-smoke.png
   relay_staging="${deployment_staging}/provider_media_relay.py"
   relay_service_staging="${deployment_staging}/provider-media-relay.service"
   cleanup_service_staging="${deployment_staging}/provider-media-cleanup.service"
   cleanup_timer_staging="${deployment_staging}/provider-media-cleanup.timer"
   relay_env_staging="${deployment_staging}/provider-media-relay.env"
   cleanup_env_staging="${deployment_staging}/provider-media-cleanup.env"
   nginx_staging="${deployment_staging}/provider-media-relay.nginx.conf"
   cleanup_staging() {
     rm -f -- "${relay_staging}" "${relay_service_staging}" \
       "${cleanup_service_staging}" "${cleanup_timer_staging}" \
       "${relay_env_staging}" "${cleanup_env_staging}" "${nginx_staging}"
     rm -f -- "${smoke_path}"
     rmdir -- "${deployment_staging}"
   }
   trap cleanup_staging EXIT
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:apps/api/provider_media_relay.py" > "${relay_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-relay.service" > "${relay_service_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-cleanup.service" > "${cleanup_service_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-cleanup.timer" > "${cleanup_timer_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-relay.env.example" > "${relay_env_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-cleanup.env.example" > "${cleanup_env_staging}"
   sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:infra/provider-media-relay/provider-media-relay.nginx.conf" > "${nginx_staging}"
   relay_blob_sha256="$(sudo -u shanhai-dev -H git -C "${repository_root}" show "${deployment_origin_main_sha}:apps/api/provider_media_relay.py" | sha256sum | cut -d ' ' -f 1)"
   relay_staged_sha256="$(sha256sum "${relay_staging}" | cut -d ' ' -f 1)"
   test "${relay_staged_sha256}" = "${relay_blob_sha256}"
   test ! -e "${smoke_path}"
   base64 -d > "${smoke_path}" <<'EOF'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+3MxZ5wAAAABJRU5ErkJggg==
EOF
   chown shanhai-dev:shanhai-dev "${smoke_path}"
   chmod 0640 "${smoke_path}"
   . /etc/shanhaiedu/provider-media-relay.env
   old_secret="${SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET}"
   unset SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET
   old_url_preflight="$(printf '%s' "${old_secret}" | (cd "${deployment_staging}" && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -c 'from provider_media_relay import sign_media_path; import sys, time; print("https://newapi.doitbenai.cloud/_shanhai-provider-media" + sign_media_path("provider-relay-smoke.png", expires_at=int(time.time()) + 60, secret=sys.stdin.read()))'))"
   curl --fail --silent --show-error --output /dev/null "${old_url_preflight}"
   unset old_url_preflight
   ```

2. Create a dedicated relay identity, the runtime directory, and separate relay/cleanup configuration files. The cleanup process must never receive the signing secret:

   ```bash
   relay_was_active="$(systemctl is-active shanhai-provider-media-relay.service 2>/dev/null || true)"
   relay_was_enabled="$(systemctl is-enabled shanhai-provider-media-relay.service 2>/dev/null || true)"
   timer_was_active="$(systemctl is-active provider-media-cleanup.timer 2>/dev/null || true)"
   timer_was_enabled="$(systemctl is-enabled provider-media-cleanup.timer 2>/dev/null || true)"
   backup_root="$(mktemp -d /srv/shanhaiedu/backups/provider-media-relay-prechange.XXXXXX)"
   for source in \
     /opt/shanhaiedu/provider-media-relay/provider_media_relay.py \
     /etc/shanhaiedu/provider-media-relay.env \
     /etc/shanhaiedu/provider-media-cleanup.env \
     /etc/shanhaiedu/image-video-smoke.env \
     /etc/systemd/system/shanhai-provider-media-relay.service \
     /etc/systemd/system/provider-media-cleanup.service \
     /etc/systemd/system/provider-media-cleanup.timer \
     /etc/nginx/snippets/shanhai-provider-media-relay.conf \
     /etc/nginx/sites-enabled/newapi.doitbenai.cloud; do
     if test -e "${source}"; then
       cp --preserve=mode,ownership,timestamps "${source}" "${backup_root}/$(basename "${source}")"
     fi
   done
   id -u shanhai-relay >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin shanhai-relay
   relay_uid="$(id -u shanhai-relay)"
   uid_min="$(awk '$1 == "UID_MIN" {print $2; exit}' /etc/login.defs)"
   test -n "${uid_min}" && test "${relay_uid}" -lt "${uid_min}"
   test "$(getent passwd shanhai-relay | cut -d: -f7)" = "/usr/sbin/nologin"
   relay_password_state="$(passwd -S shanhai-relay | awk '{print $2}')"
   case "${relay_password_state}" in L|LK) ;; *) exit 1 ;; esac
   test ! -d "$(getent passwd shanhai-relay | cut -d: -f6)"
   unset relay_uid uid_min relay_password_state
   install -d -m 0755 -o root -g root /opt/shanhaiedu/provider-media-relay
   install -m 0555 -o root -g root "${relay_staging}" /opt/shanhaiedu/provider-media-relay/provider_media_relay.py
   install -d -m 0750 -o shanhai-dev -g shanhai-dev /srv/shanhaiedu/runtime/provider-media
   install -d -m 0750 -o root -g root /etc/shanhaiedu
   install -m 0600 -o root -g root "${relay_env_staging}" /etc/shanhaiedu/provider-media-relay.env
   install -m 0600 -o root -g root "${cleanup_env_staging}" /etc/shanhaiedu/provider-media-cleanup.env
   ```

   These checks fail closed if a pre-existing `shanhai-relay` is not a locked system account with no interactive shell or has an existing home directory. The relay runs root-owned installed code as `shanhai-relay` with the `shanhai-dev` group so it can read opaque `0640` relay files without sharing a UID or writable executable code with the producer.

3. Generate 32 random bytes on the server, encode them as exactly 64 hexadecimal characters, and atomically place the same value in the relay and controlled producer environments. The value is passed to the updater on standard input, never printed or placed in a command argument. The cleanup environment remains non-secret:

   ```bash
   new_secret="$(openssl rand -hex 32)"
   test "${#new_secret}" -eq 64
   test "${old_secret}" != "${new_secret}"
   printf '\nSHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=%s\n' "${new_secret}" >> /etc/shanhaiedu/provider-media-relay.env
   printf '%s' "${new_secret}" | /usr/bin/python3 -c '
import os
from pathlib import Path
import sys
import tempfile
path = Path(sys.argv[1])
secret = sys.stdin.read()
prefix = "SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET="
lines = path.read_text(encoding="utf-8").splitlines()
if sum(line.startswith(prefix) for line in lines) != 1:
    raise SystemExit("producer signing-secret assignment is not unique")
updated = "\n".join(prefix + secret if line.startswith(prefix) else line for line in lines) + "\n"
descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
try:
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(updated)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
' "${producer_env}"
   relay_secret="$(sed -n 's/^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=//p' /etc/shanhaiedu/provider-media-relay.env)"
   producer_secret="$(sed -n 's/^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=//p' "${producer_env}")"
   test "${relay_secret}" = "${new_secret}"
   test "${producer_secret}" = "${new_secret}"
   test "$(grep -c '^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=' /etc/shanhaiedu/provider-media-relay.env)" -eq 1
   test "$(grep -c '^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=' "${producer_env}")" -eq 1
   test "$(grep -c '^SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=' /etc/shanhaiedu/provider-media-cleanup.env || true)" -eq 0
   unset new_secret relay_secret producer_secret
   ```

   Do not use repeated characters, published examples, placeholders, or values copied from another environment. Keep the dedicated root and TTL no greater than 300 seconds. The previous process ran under the producer UID, so the old secret is treated as exposed and must not be reused.

4. Install the independent expiry-cleanup timer and Nginx location. Back up the exact vhost before modifying it:

   ```bash
   install -m 0644 "${relay_service_staging}" /etc/systemd/system/shanhai-provider-media-relay.service
   install -m 0644 "${cleanup_service_staging}" /etc/systemd/system/provider-media-cleanup.service
   install -m 0644 "${cleanup_timer_staging}" /etc/systemd/system/provider-media-cleanup.timer
   install -d -m 0755 /etc/nginx/snippets
   install -m 0644 "${nginx_staging}" /etc/nginx/snippets/shanhai-provider-media-relay.conf
   ```

5. Ensure this line already appears exactly once inside the existing `server {}` block in `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`. Add it only when absent; never duplicate it or edit `/v1/videos` or any existing media route.

   ```nginx
   include /etc/nginx/snippets/shanhai-provider-media-relay.conf;
   ```

   ```bash
   test "$(grep -Fc 'include /etc/nginx/snippets/shanhai-provider-media-relay.conf;' /etc/nginx/sites-enabled/newapi.doitbenai.cloud)" -eq 1
   ```

6. Before any service restart or Nginx reload, compare the installed `/opt` relay byte-for-byte with the same pinned Git blob and verify its SHA-256. Record only the pinned `origin/main` SHA, the verified blob/installed-file SHA-256, and UTC validation time with the operations evidence for #165. Never include environment contents or the signing secret. Continue to service and Nginx validation only after these provenance checks succeed:

   ```bash
   cmp --silent "${relay_staging}" /opt/shanhaiedu/provider-media-relay/provider_media_relay.py
   relay_installed_sha256="$(sha256sum /opt/shanhaiedu/provider-media-relay/provider_media_relay.py | cut -d ' ' -f 1)"
   test "${relay_installed_sha256}" = "${relay_blob_sha256}"
   systemctl daemon-reload
   systemctl enable shanhai-provider-media-relay.service
   systemctl restart shanhai-provider-media-relay.service
   systemctl start provider-media-cleanup.service
   test "$(systemctl show provider-media-cleanup.service -p Result --value)" = "success"
   test "$(systemctl show provider-media-cleanup.service -p ExecMainStatus --value)" = "0"
   systemctl enable --now provider-media-cleanup.timer
   systemctl is-active --quiet shanhai-provider-media-relay.service
   systemctl is-active --quiet provider-media-cleanup.timer
   test "$(systemctl show shanhai-provider-media-relay.service -p User --value)" = "shanhai-relay"
   systemctl show shanhai-provider-media-relay.service -p ExecStart --value | grep -Fq '/opt/shanhaiedu/provider-media-relay/provider_media_relay.py'
   relay_pid="$(systemctl show shanhai-provider-media-relay.service -p MainPID --value)"
   test "$(stat -c '%U' "/proc/${relay_pid}")" = "shanhai-relay"
   if sudo -u shanhai-dev -- cat "/proc/${relay_pid}/environ" >/dev/null 2>&1; then exit 1; fi
   unset relay_pid
   nginx -t
   systemctl reload nginx
   validation_time_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   printf 'origin/main=%s\nrelay-sha256=%s\nvalidated-at=%s\n' \
     "${deployment_origin_main_sha}" "${relay_installed_sha256}" "${validation_time_utc}"
   unset deployment_origin_main_sha relay_blob_sha256 relay_staged_sha256 relay_installed_sha256 validation_time_utc
   ```

   The explicit restart is mandatory for an existing active deployment: `enable --now` alone does not replace the old process identity, code path, environment, or signing secret.

## HTTPS Smoke

Reuse the runtime-only test frame that returned `200` before rotation. It is not an application asset and must be removed after the check.

```bash
set -euo pipefail
test -f "${smoke_path}"
test "$(stat -c '%U:%G:%a' "${smoke_path}")" = "shanhai-dev:shanhai-dev:640"
```

Generate and consume a URL without printing it or putting it in a shell command line:

```bash
set -euo pipefail
set -a
. /etc/shanhaiedu/provider-media-relay.env
set +a
url="$(cd /opt/shanhaiedu/provider-media-relay && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -c 'from provider_media_relay import sign_media_path; import os, time; print("https://newapi.doitbenai.cloud/_shanhai-provider-media" + sign_media_path("provider-relay-smoke.png", expires_at=int(time.time()) + 60, secret=os.environ["SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET"]))')"
old_url="$(printf '%s' "${old_secret}" | (cd /opt/shanhaiedu/provider-media-relay && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -c 'from provider_media_relay import sign_media_path; import sys, time; print("https://newapi.doitbenai.cloud/_shanhai-provider-media" + sign_media_path("provider-relay-smoke.png", expires_at=int(time.time()) + 60, secret=sys.stdin.read()))'))"
curl --fail --silent --show-error --output /dev/null "$url"
if curl --fail --silent --output /dev/null "${url}x"; then exit 1; fi
if curl --fail --silent --output /dev/null "${old_url}"; then exit 1; fi
unset url old_url old_secret SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET
rm -f -- "${smoke_path}"
```

The new request must return `200`; its modified form and a freshly signed request using the old secret must both return `404`. Confirm that no `signature=` value appears in the relay journal or the Nginx access log. Do not call the billable video Provider in this infrastructure issue.

## Cleanup Timer Smoke

Create only strict cleanup candidates plus one unrelated marker, then wait for the enabled timer rather than invoking a generation request:

```bash
set -euo pipefail
cleanup_root=/srv/shanhaiedu/runtime/provider-media
opaque_smoke="${cleanup_root}/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"
partial_smoke="${cleanup_root}/.provider-media-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.partial"
keep_smoke="${cleanup_root}/provider-media-cleanup-keep.txt"
test ! -e "${opaque_smoke}" && test ! -e "${partial_smoke}" && test ! -e "${keep_smoke}"
install -m 0640 -o shanhai-dev -g shanhai-dev /dev/null "${opaque_smoke}"
install -m 0640 -o shanhai-dev -g shanhai-dev /dev/null "${partial_smoke}"
install -m 0640 -o shanhai-dev -g shanhai-dev /dev/null "${keep_smoke}"
touch -d '10 minutes ago' "${opaque_smoke}" "${partial_smoke}" "${keep_smoke}"
for _attempt in $(seq 1 90); do
  if test ! -e "${opaque_smoke}" && test ! -e "${partial_smoke}"; then break; fi
  sleep 1
done
test ! -e "${opaque_smoke}"
test ! -e "${partial_smoke}"
test -f "${keep_smoke}"
rm -f -- "${keep_smoke}"
test "$(systemctl show provider-media-cleanup.service -p Result --value)" = "success"
if journalctl -u shanhai-provider-media-relay.service --since '-10 minutes' --no-pager | grep -Fq 'signature='; then exit 1; fi
if grep -Fq 'signature=' /var/log/nginx/access.log 2>/dev/null; then exit 1; fi
unset cleanup_root opaque_smoke partial_smoke keep_smoke
```

## Rollback

Stop the new units, restore every replaced file, and return relay/timer enablement and activity to their recorded pre-change states.

```bash
systemctl disable --now provider-media-cleanup.timer shanhai-provider-media-relay.service
test -n "${backup_root:-}"
restore_or_remove() {
  backup_name="$1" destination="$2" mode="$3"
  if test -f "${backup_root}/${backup_name}"; then
    install -m "${mode}" "${backup_root}/${backup_name}" "${destination}"
  else
    rm -f -- "${destination}"
  fi
}
restore_or_remove provider_media_relay.py /opt/shanhaiedu/provider-media-relay/provider_media_relay.py 0555
restore_or_remove shanhai-provider-media-relay.conf /etc/nginx/snippets/shanhai-provider-media-relay.conf 0644
restore_or_remove newapi.doitbenai.cloud /etc/nginx/sites-enabled/newapi.doitbenai.cloud 0644
for unit in shanhai-provider-media-relay.service provider-media-cleanup.service provider-media-cleanup.timer; do
  restore_or_remove "${unit}" "/etc/systemd/system/${unit}" 0644
done
for env_file in provider-media-relay.env provider-media-cleanup.env image-video-smoke.env; do
  restore_or_remove "${env_file}" "/etc/shanhaiedu/${env_file}" 0600
done
systemctl daemon-reload
if test -f /etc/systemd/system/shanhai-provider-media-relay.service; then
  if test "${relay_was_enabled}" = enabled; then systemctl enable shanhai-provider-media-relay.service; else systemctl disable shanhai-provider-media-relay.service; fi
  if test "${relay_was_active}" = active; then systemctl restart shanhai-provider-media-relay.service; else systemctl stop shanhai-provider-media-relay.service; fi
fi
if test -f /etc/systemd/system/provider-media-cleanup.timer; then
  if test "${timer_was_enabled}" = enabled; then systemctl enable provider-media-cleanup.timer; else systemctl disable provider-media-cleanup.timer; fi
  if test "${timer_was_active}" = active; then systemctl start provider-media-cleanup.timer; else systemctl stop provider-media-cleanup.timer; fi
fi
nginx -t
systemctl reload nginx
```

Keep the root-only environment file and runtime directory private for diagnosis; delete them only through a separately approved credential-rotation and data-cleanup task.
