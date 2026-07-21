# Provider Media Relay

Owner: infrastructure maintainers. Audience: operators deploying the controlled image relay for #156. Canonical location: `infra/provider-media-relay/`; replace this runbook in the same path if deployment moves to managed infrastructure.

This service exposes one short-lived, signed PNG/JPEG/WebP GET path to an external video Provider. It is not an upload endpoint, a public asset API, or a storage proxy. The service only listens on `127.0.0.1:8201`; Nginx exposes it under `https://newapi.doitbenai.cloud/_shanhai-provider-media/`.

## Prerequisites

- The deployed checkout is `/srv/shanhaiedu/repository` and its `.venv` contains the checked-out relay module.
- The existing TLS vhost is `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`.
- The runtime image directory is private and writable only by the trusted server-side producer. This relay must never be pointed at MinIO data, uploads, or an application-wide filesystem root.
- The operator has root access. Do not paste the signing secret into tickets, shell history, CI logs, Git, or a client application.

## Deploy

1. On the server, create the dedicated runtime directory and install the root-only configuration file:

   ```bash
   install -d -m 0750 -o shanhai-dev -g shanhai-dev /srv/shanhaiedu/runtime/provider-media
   install -d -m 0750 -o root -g root /etc/shanhaiedu
   install -m 0600 -o root -g root infra/provider-media-relay/provider-media-relay.env.example /etc/shanhaiedu/provider-media-relay.env
   ```

2. Edit `/etc/shanhaiedu/provider-media-relay.env` only on the server. Replace the placeholder with a unique random 64-hex-character secret. Keep `SHANHAI_PROVIDER_MEDIA_ROOT` on the dedicated runtime directory and use a TTL no greater than 300 seconds.

3. Install the relay, independent expiry-cleanup timer, and Nginx location. Back up the exact vhost before modifying it:

   ```bash
   install -m 0644 infra/provider-media-relay/provider-media-relay.service /etc/systemd/system/shanhai-provider-media-relay.service
   install -m 0644 infra/provider-media-relay/provider-media-cleanup.service /etc/systemd/system/provider-media-cleanup.service
   install -m 0644 infra/provider-media-relay/provider-media-cleanup.timer /etc/systemd/system/provider-media-cleanup.timer
   install -d -m 0755 /etc/nginx/snippets
   install -m 0644 infra/provider-media-relay/provider-media-relay.nginx.conf /etc/nginx/snippets/shanhai-provider-media-relay.conf
   cp --preserve=mode,ownership,timestamps /etc/nginx/sites-enabled/newapi.doitbenai.cloud /srv/shanhaiedu/backups/newapi.doitbenai.cloud.provider-media-relay.bak
   ```

4. Add this one line inside the existing `server {}` block in `/etc/nginx/sites-enabled/newapi.doitbenai.cloud`. Do not edit `/v1/videos` or any existing media route.

   ```nginx
   include /etc/nginx/snippets/shanhai-provider-media-relay.conf;
   ```

5. Validate before reloading. Only reload after both checks succeed:

   ```bash
   systemctl daemon-reload
   systemctl enable --now shanhai-provider-media-relay.service
   systemctl enable --now provider-media-cleanup.timer
   systemctl is-active --quiet shanhai-provider-media-relay.service
   systemctl is-active --quiet provider-media-cleanup.timer
   nginx -t
   systemctl reload nginx
   ```

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
