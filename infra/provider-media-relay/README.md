# Provider Media Relay

Owner: infrastructure maintainers. Audience: operators deploying the controlled image relay for #156. Canonical location: `infra/provider-media-relay/`; replace this runbook in the same path if deployment moves to managed infrastructure.

This service exposes one short-lived, signed PNG/JPEG/WebP GET path to an external video Provider. It is not an upload endpoint, a public asset API, or a storage proxy. The service only listens on `127.0.0.1:8201`; Nginx exposes it under `https://newapi.doitbenai.cloud/_shanhai-provider-media/`.

## Prerequisites

- The source checkout is `/srv/shanhaiedu/repository`; deployment installs the standard-library-only relay module into a root-owned, non-writable runtime under `/opt/shanhaiedu/provider-media-relay`.
- The existing TLS vhost is `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`.
- The runtime image directory is private and writable only by the trusted server-side producer. This relay must never be pointed at MinIO data, uploads, or an application-wide filesystem root.
- The operator has root access. Do not paste the signing secret into tickets, shell history, CI logs, Git, or a client application.

## Deploy

Run all deploy steps below in one privileged shell so the pinned `origin/main` SHA and blob hash remain unchanged between preflight, installation, and restart. Any failed command must stop the deployment; do not continue from a failed step.

1. Before `useradd`, `install`, service restart, or Nginx reload, fetch and pin the canonical source. Fail closed unless `HEAD` equals the fetched `origin/main` and the working-tree relay file is byte-for-byte identical to the relay blob at that exact commit. The content SHA-256 is evidence; the `cmp` check prevents a dirty working-tree file from being attributed to that commit:

   ```bash
   set -euo pipefail
   cd /srv/shanhaiedu/repository
   git fetch origin --prune
   deployment_origin_main_sha="$(git rev-parse origin/main)"
   test "$(git rev-parse HEAD)" = "${deployment_origin_main_sha}"
   git show "${deployment_origin_main_sha}:apps/api/provider_media_relay.py" | cmp --silent - apps/api/provider_media_relay.py
   relay_blob_sha256="$(git show "${deployment_origin_main_sha}:apps/api/provider_media_relay.py" | sha256sum | cut -d ' ' -f 1)"
   relay_source_sha256="$(sha256sum apps/api/provider_media_relay.py | cut -d ' ' -f 1)"
   test "${relay_source_sha256}" = "${relay_blob_sha256}"
   ```

2. Create a dedicated relay identity, the runtime directory, and separate relay/cleanup configuration files. The cleanup process must never receive the signing secret:

   ```bash
   id -u shanhai-relay >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin shanhai-relay
   install -d -m 0755 -o root -g root /opt/shanhaiedu/provider-media-relay
   install -m 0555 -o root -g root apps/api/provider_media_relay.py /opt/shanhaiedu/provider-media-relay/provider_media_relay.py
   install -d -m 0750 -o shanhai-dev -g shanhai-dev /srv/shanhaiedu/runtime/provider-media
   install -d -m 0750 -o root -g root /etc/shanhaiedu
   install -m 0600 -o root -g root infra/provider-media-relay/provider-media-relay.env.example /etc/shanhaiedu/provider-media-relay.env
   install -m 0600 -o root -g root infra/provider-media-relay/provider-media-cleanup.env.example /etc/shanhaiedu/provider-media-cleanup.env
   ```

   If `shanhai-relay` already exists, verify it is a locked system account with no interactive shell instead of recreating it. The relay runs root-owned installed code as `shanhai-relay` with the `shanhai-dev` group so it can read opaque `0640` relay files without sharing a UID or writable executable code with the producer.

3. Edit `/etc/shanhaiedu/provider-media-relay.env` only on the server. Generate 32 random bytes with an approved cryptographic random source, encode them as exactly 64 hexadecimal characters, and write the `SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET` assignment directly to the root-only file without printing the value or placing it in shell history. The checked-in example deliberately contains no signing-secret assignment and cannot start the relay by itself. Do not use repeated characters, published examples, placeholders, or values copied from another environment. Keep `SHANHAI_PROVIDER_MEDIA_ROOT` on the dedicated runtime directory and use a TTL no greater than 300 seconds. When migrating from a relay that ran under the producer UID, rotate the signing secret before restart because the previous process environment must be treated as exposed to that UID. Keep `/etc/shanhaiedu/provider-media-cleanup.env` limited to the non-sensitive root and TTL values.

4. Install the independent expiry-cleanup timer and Nginx location. Back up the exact vhost before modifying it:

   ```bash
   install -m 0644 infra/provider-media-relay/provider-media-relay.service /etc/systemd/system/shanhai-provider-media-relay.service
   install -m 0644 infra/provider-media-relay/provider-media-cleanup.service /etc/systemd/system/provider-media-cleanup.service
   install -m 0644 infra/provider-media-relay/provider-media-cleanup.timer /etc/systemd/system/provider-media-cleanup.timer
   install -d -m 0755 /etc/nginx/snippets
   install -m 0644 infra/provider-media-relay/provider-media-relay.nginx.conf /etc/nginx/snippets/shanhai-provider-media-relay.conf
   cp --preserve=mode,ownership,timestamps /etc/nginx/sites-enabled/newapi.doitbenai.cloud /srv/shanhaiedu/backups/newapi.doitbenai.cloud.provider-media-relay.bak
   ```

5. Add this one line inside the existing `server {}` block in `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`. Do not edit `/v1/videos` or any existing media route.

   ```nginx
   include /etc/nginx/snippets/shanhai-provider-media-relay.conf;
   ```

6. Before any service restart or Nginx reload, compare the installed `/opt` relay byte-for-byte with the same pinned Git blob and verify its SHA-256. Record only the pinned `origin/main` SHA, the verified blob/installed-file SHA-256, and UTC validation time with the operations evidence for #165. Never include environment contents or the signing secret. Continue to service and Nginx validation only after these provenance checks succeed:

   ```bash
   git show "${deployment_origin_main_sha}:apps/api/provider_media_relay.py" | cmp --silent - /opt/shanhaiedu/provider-media-relay/provider_media_relay.py
   relay_installed_sha256="$(sha256sum /opt/shanhaiedu/provider-media-relay/provider_media_relay.py | cut -d ' ' -f 1)"
   test "${relay_installed_sha256}" = "${relay_blob_sha256}"
   systemctl daemon-reload
   systemctl enable shanhai-provider-media-relay.service
   systemctl restart shanhai-provider-media-relay.service
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
   unset deployment_origin_main_sha relay_blob_sha256 relay_source_sha256 relay_installed_sha256 validation_time_utc
   ```

   The explicit restart is mandatory for an existing active deployment: `enable --now` alone does not replace the old process identity, code path, environment, or signing secret.

## HTTPS Smoke

Create a runtime-only test frame. It is not an application asset and must be removed after the check.

```bash
set -euo pipefail
base64 -d > /srv/shanhaiedu/runtime/provider-media/provider-relay-smoke.png <<'EOF'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+3MxZ5wAAAABJRU5ErkJggg==
EOF
chown shanhai-dev:shanhai-dev /srv/shanhaiedu/runtime/provider-media/provider-relay-smoke.png
chmod 0640 /srv/shanhaiedu/runtime/provider-media/provider-relay-smoke.png
```

Generate and consume a URL without printing it or putting it in a shell command line:

```bash
set -euo pipefail
set -a
. /etc/shanhaiedu/provider-media-relay.env
set +a
url="$(cd /srv/shanhaiedu/repository && .venv/bin/python -c 'from apps.api.provider_media_relay import sign_media_path; import os, time; print("https://newapi.doitbenai.cloud/_shanhai-provider-media" + sign_media_path("provider-relay-smoke.png", expires_at=int(time.time()) + 60, secret=os.environ["SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET"]))')"
curl --fail --silent --show-error --output /dev/null "$url"
if curl --fail --silent --output /dev/null "${url}x"; then exit 1; fi
unset url SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET
rm -f /srv/shanhaiedu/runtime/provider-media/provider-relay-smoke.png
```

The valid request must return `200` and the modified request must return `404`. Confirm that no `signature=` value appears in the relay journal or the Nginx access log. Do not call the billable video Provider in this infrastructure issue.

## Rollback

Stop the relay and restore the exact backed-up vhost. Do not leave the public Nginx location pointing at a stopped service.

```bash
systemctl disable --now provider-media-cleanup.timer shanhai-provider-media-relay.service
install -m 0644 /srv/shanhaiedu/backups/newapi.doitbenai.cloud.provider-media-relay.bak /etc/nginx/sites-enabled/newapi.doitbenai.cloud
nginx -t
systemctl reload nginx
```

Keep the root-only environment file and runtime directory private for diagnosis; delete them only through a separately approved credential-rotation and data-cleanup task.
