from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "infra" / "prod"


def test_production_release_assets_are_complete() -> None:
    required = {
        "compose.yaml",
        "Dockerfile.api",
        "Dockerfile.web",
        "configure_debian_mirror.py",
        "api-entrypoint.sh",
        "web.conf",
        "host-nginx.conf.template",
        "env.example",
        "release.sh",
        "validate-image-source.sh",
        "rollback.sh",
        "verify.sh",
        "monitor.sh",
        "operation-lock.sh",
        "update_production_release.py",
        "README.md",
    }

    assert {path.name for path in PROD.iterdir()} >= required


def test_production_compose_isolated_persistent_and_loopback_only() -> None:
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))
    environment_example = (PROD / "env.example").read_text(encoding="utf-8")

    assert compose["name"] == "shanhaiedu-production"
    assert set(compose["services"]) == {
        "postgres",
        "redis",
        "minio",
        "api",
        "worker",
        "web",
    }
    assert set(compose["volumes"]) == {
        "postgres_data",
        "redis_data",
        "minio_data",
    }
    assert "ports" not in compose["services"]["postgres"]
    assert "ports" not in compose["services"]["redis"]
    assert compose["networks"]["production"]["internal"] is True
    assert "ports" not in compose["services"]["api"]
    assert compose["services"]["web"]["ports"] == ["127.0.0.1:18080:8080"]
    assert "ports" not in compose["services"]["minio"]
    for service in compose["services"].values():
        assert "restart" in service
        assert "healthcheck" in service
        assert "mem_limit" in service
        assert "cpus" in service
    worker_health = compose["services"]["worker"]["healthcheck"]["test"][1]
    assert "shanhai-entrypoint python -m workers.main --check" in worker_health
    assert compose["x-app"]["environment"]["SHANHAI_OBJECT_STORAGE_REGION"] == (
        "${SHANHAI_OBJECT_STORAGE_REGION:-us-east-1}"
    )
    assert "SHANHAI_OBJECT_STORAGE_REGION=us-east-1" in environment_example


def test_secretless_web_is_the_only_non_nat_loopback_ingress_service() -> None:
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))

    loopback = compose["networks"]["loopback"]
    assert loopback["driver"] == "bridge"
    assert loopback["internal"] is False
    assert loopback["driver_opts"] == {
        "com.docker.network.bridge.enable_ip_masquerade": "false",
        "com.docker.network.bridge.host_binding_ipv4": "127.0.0.1",
    }

    assert set(compose["services"]["web"]["networks"]) == {"production", "loopback"}
    assert "secrets" not in compose["services"]["web"]
    assert set(compose["services"]["api"]["networks"]) == {"production"}
    assert set(compose["services"]["minio"]["networks"]) == {"production"}
    assert set(compose["services"]["postgres"]["networks"]) == {"production"}
    assert set(compose["services"]["redis"]["networks"]) == {"production"}
    assert set(compose["services"]["worker"]["networks"]) == {
        "production",
        "provider-egress",
    }


def test_text_provider_egress_and_secret_are_scoped_to_the_worker() -> None:
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]

    assert compose["networks"]["provider-egress"] == {
        "driver": "bridge",
        "internal": False,
        "driver_opts": {
            "com.docker.network.bridge.enable_icc": "false",
            "com.docker.network.bridge.enable_ip_masquerade": "true",
        },
    }
    assert worker["networks"]["provider-egress"]["gw_priority"] == 1

    provider_environment = {
        "SHANHAI_TEXT_PROVIDER_NAME": (
            "${SHANHAI_TEXT_PROVIDER_NAME:?text provider name is required}"
        ),
        "SHANHAI_TEXT_PROVIDER_BASE_URL": (
            "${SHANHAI_TEXT_PROVIDER_BASE_URL:?text provider base URL is required}"
        ),
        "SHANHAI_TEXT_PROVIDER_MODEL": (
            "${SHANHAI_TEXT_PROVIDER_MODEL:?text provider model is required}"
        ),
        "SHANHAI_TEXT_PROVIDER_SECRET_ENV": "MODEL_GATEWAY_API_KEY",
        "SHANHAI_TEXT_PROVIDER_TIMEOUT_SECONDS": ("${SHANHAI_TEXT_PROVIDER_TIMEOUT_SECONDS:-300}"),
    }
    for name, value in provider_environment.items():
        assert worker["environment"][name] == value
        assert name not in compose["x-app"]["environment"]

    assert "text_provider_api_key" in worker["secrets"]
    assert compose["secrets"]["text_provider_api_key"]["file"] == (
        "${SHANHAI_SECRET_DIR}/text_provider_api_key"
    )
    for service_name, service in compose["services"].items():
        if service_name == "worker":
            continue
        assert "provider-egress" not in service.get("networks", {})
        assert "text_provider_api_key" not in service.get("secrets", [])


def test_host_nginx_contract_preserves_https_sse_and_private_services() -> None:
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")
    web = (PROD / "web.conf").read_text(encoding="utf-8")

    assert "server_name ${SHANHAI_PUBLIC_IP};" in nginx
    assert "listen 443 ssl" in nginx
    assert "return 301 https://$host$request_uri;" in nginx
    assert "proxy_pass http://127.0.0.1:18000;" not in nginx
    assert "proxy_pass http://127.0.0.1:19000;" not in nginx
    assert nginx.count("proxy_pass http://127.0.0.1:18080;") == 4
    assert "proxy_buffering off;" in nginx
    assert "access_log off;" in nginx
    assert "@api path /api/v2 /api/v2/*" in web
    assert "handle @api" in web
    assert "handle /health/*" in web
    assert "reverse_proxy api:8000" in web
    assert "handle /shanhaiedu-production/*" in web
    assert "reverse_proxy minio:9000" in web


def test_host_nginx_is_default_tls_server_for_ip_clients_without_sni() -> None:
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")

    assert "listen 443 ssl http2 default_server;" in nginx
    assert "listen [::]:443 ssl http2 default_server;" in nginx


def test_web_image_makes_caddyfile_readable_to_the_non_root_runtime() -> None:
    dockerfile = (PROD / "Dockerfile.web").read_text(encoding="utf-8")
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))
    web = compose["services"]["web"]

    assert "COPY --chmod=0444 infra/prod/web.conf /etc/caddy/Caddyfile" in dockerfile
    assert "XDG_CONFIG_HOME=/tmp/caddy-config" in dockerfile
    assert "XDG_DATA_HOME=/tmp/caddy-data" in dockerfile
    assert "USER 1000:1000" in dockerfile
    assert web["read_only"] is True
    assert web["tmpfs"] == ["/tmp:size=16m,mode=1777"]
    assert web["security_opt"] == ["no-new-privileges:true"]


def test_host_proxy_overwrites_forwarded_ip_and_caddy_uses_a_strict_trust_chain() -> None:
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")
    web = (PROD / "web.conf").read_text(encoding="utf-8")

    assert nginx.count("proxy_set_header X-Forwarded-For $remote_addr;") == 3
    assert "$proxy_add_x_forwarded_for" not in nginx
    assert "trusted_proxies static private_ranges" in web
    assert "trusted_proxies_strict" in web
    assert compose["x-app"]["environment"]["SHANHAI_SESSION_TRUSTED_PROXY_HOSTS"] == (
        '["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]'
    )


def test_host_configuration_supports_the_approved_shared_ecs_layout() -> None:
    configure = (PROD / "configure-host.sh").read_text(encoding="utf-8")
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")

    assert "SHANHAI_NGINX_SITE_DIR" in configure
    assert "SHANHAI_LEGACY_NGINX_SITE" in configure
    assert "SHANHAI_TLS_CERTIFICATE" in configure
    assert "SHANHAI_TLS_PRIVATE_KEY" in configure
    assert "apt-get" not in configure
    assert "ExecStartPost=$nginx_binary -t" in configure
    assert "pgrep -x nginx" in configure
    assert "systemctl start nginx" in configure
    assert '"$nginx_binary" -s reload' in configure
    assert "ExecStartPost=$nginx_binary -s reload" in configure
    assert "systemctl reload nginx" not in configure
    assert "ssl_certificate ${SHANHAI_TLS_CERTIFICATE};" in nginx
    assert "ssl_certificate_key ${SHANHAI_TLS_PRIVATE_KEY};" in nginx
    assert 'configured TLS material is unavailable" >&2\n  false' in configure
    assert "shanhaiedu-healthcheck.timer" in configure
    prepare_lock = 'prepare_production_operation_lock "$production_root"'
    assert prepare_lock in configure
    assert configure.index(prepare_lock) < configure.index(
        "systemctl enable --now shanhaiedu-healthcheck.timer"
    )
    assert "UMask=0077" in configure
    systemd_monitor_lock = (
        "ExecStart=/usr/bin/flock --shared --nonblock --conflict-exit-code 0 "
        "$production_root/shared/operations.lock "
        "$production_root/current/infra/prod/monitor.sh"
    )
    assert systemd_monitor_lock in configure


def test_api_image_reads_file_secrets_then_drops_root() -> None:
    dockerfile = (PROD / "Dockerfile.api").read_text(encoding="utf-8")
    entrypoint = (PROD / "api-entrypoint.sh").read_text(encoding="utf-8")

    assert "gosu" in dockerfile
    assert "USER 10001:10001" not in dockerfile
    assert 'exec gosu 10001:10001 "$@"' in entrypoint


def test_worker_entrypoint_maps_the_provider_secret_without_a_literal_value() -> None:
    entrypoint = (PROD / "api-entrypoint.sh").read_text(encoding="utf-8")

    assert "SHANHAI_TEXT_PROVIDER_SECRET_ENV" in entrypoint
    assert "read_secret text_provider_api_key" in entrypoint
    assert 'export "$SHANHAI_TEXT_PROVIDER_SECRET_ENV=$text_provider_api_key"' in entrypoint
    assert "unset text_provider_api_key" in entrypoint
    assert "invalid text provider secret environment name" in entrypoint


def test_release_requires_a_preprovisioned_provider_secret() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    verify = (PROD / "verify.sh").read_text(encoding="utf-8")
    environment_example = (PROD / "env.example").read_text(encoding="utf-8")

    assert "require_existing_secret text_provider_api_key" in release
    assert "require_text_provider_configuration" in release
    assert "ensure_secret text_provider_api_key" not in release
    assert release.index("require_existing_secret text_provider_api_key") < release.index(
        "image_source="
    )
    assert release.index("require_existing_secret text_provider_api_key") < release.index(
        "trap rollback_release ERR"
    )
    assert "text_provider_api_key" in verify
    assert "build_real_text_gateway" in verify
    for name in (
        "SHANHAI_TEXT_PROVIDER_NAME",
        "SHANHAI_TEXT_PROVIDER_BASE_URL",
        "SHANHAI_TEXT_PROVIDER_MODEL",
        "SHANHAI_TEXT_PROVIDER_TIMEOUT_SECONDS",
    ):
        assert f"{name}=" in environment_example
    assert "MODEL_GATEWAY_API_KEY=" not in environment_example


def test_release_preflights_the_runtime_provider_before_persistent_services() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")

    provider_preflight = '"${compose[@]}" run --rm --no-deps worker python -c'
    assert provider_preflight in release
    assert "build_real_text_gateway(Settings())" in release
    assert release.index('image_source="$(') < release.index(provider_preflight)
    assert release.index('"${compose[@]}" build api worker web') < release.index(provider_preflight)
    for persistent_service_or_write in (
        '"${compose[@]}" up -d --wait --wait-timeout 120 postgres',
        '"${compose[@]}" up -d --wait --wait-timeout 120 redis minio',
        "pg_dump",
        "alembic upgrade head",
        "bootstrap-production-storage",
        "publish-golden-content",
        "bootstrap-production-identity",
    ):
        assert release.index(provider_preflight) < release.index(persistent_service_or_write)


def test_production_runbook_documents_worker_only_provider_access() -> None:
    runbook = (PROD / "README.md").read_text(encoding="utf-8")

    assert "只有 Worker" in runbook
    assert "provider-egress" in runbook
    assert "text_provider_api_key" in runbook
    assert "目的地址未由网络层限制" in runbook
    assert "首次发布不注入 Provider 配置" not in runbook


def test_api_image_normalizes_runtime_permissions_after_dependency_sync() -> None:
    dockerfile = (PROD / "Dockerfile.api").read_text(encoding="utf-8")

    dependency_sync = "uv sync --frozen --no-dev --no-editable"
    runtime_permissions = "chmod -R a=rX /app"
    assert runtime_permissions in dockerfile
    assert dockerfile.index(dependency_sync) < dockerfile.index(runtime_permissions)


def test_api_image_allows_a_controlled_debian_mirror_override() -> None:
    dockerfile = (PROD / "Dockerfile.api").read_text(encoding="utf-8")
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))
    environment_example = (PROD / "env.example").read_text(encoding="utf-8")

    assert "ARG DEBIAN_MIRROR=https://deb.debian.org/debian" in dockerfile
    assert "configure_debian_mirror.py" in dockerfile
    assert compose["x-app"]["build"]["args"]["DEBIAN_MIRROR"] == (
        "${SHANHAI_DEBIAN_MIRROR:-https://deb.debian.org/debian}"
    )
    assert "SHANHAI_DEBIAN_MIRROR=https://deb.debian.org/debian" in environment_example


@pytest.mark.parametrize(
    "mirror",
    ["https://deb.debian.org/debian", "https://mirrors.aliyun.com/debian"],
)
def test_debian_mirror_configurator_writes_main_and_security_sources(
    tmp_path: Path, mirror: str
) -> None:
    sources = tmp_path / "debian.sources"
    sources.write_text(
        "URIs: http://deb.debian.org/debian\n"
        "Suites: bookworm bookworm-updates\n"
        "URIs: http://deb.debian.org/debian-security\n"
        "Suites: bookworm-security\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(PROD / "configure_debian_mirror.py"), mirror, sources],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    configured = sources.read_text(encoding="utf-8")
    assert f"URIs: {mirror}\n" in configured
    assert f"URIs: {mirror}-security\n" in configured
    assert "http://deb.debian.org" not in configured


@pytest.mark.parametrize(
    "mirror",
    [
        "http://mirror.example/debian",
        "https://user:token@mirror.example/debian",
        "https://mirror.example/debian/",
        "https://mirror.example/debian?token=secret",
        "https://mirror.example/debian#private",
    ],
)
def test_debian_mirror_configurator_rejects_private_or_ambiguous_urls(
    tmp_path: Path, mirror: str
) -> None:
    sources = tmp_path / "debian.sources"
    original = "URIs: http://deb.debian.org/debian\nURIs: http://deb.debian.org/debian-security\n"
    sources.write_text(original, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(PROD / "configure_debian_mirror.py"), mirror, sources],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert mirror not in result.stderr
    assert sources.read_text(encoding="utf-8") == original


def test_production_monitor_covers_resource_and_request_health() -> None:
    monitor = (PROD / "monitor.sh").read_text(encoding="utf-8")

    assert "5242880" in monitor
    assert "pg_stat_activity" in monitor
    assert "dramatiq:*" in monitor
    assert 'redis-cli type "$key"' in monitor
    assert 'zcard "$key"' in monitor
    assert "dramatiq:__*) continue" in monitor
    assert "*.msgs) continue" in monitor
    assert "*.XQ) continue" in monitor
    assert "time_total" in monitor
    assert '"http_status":5' in monitor
    assert "SHANHAI_DB_CONNECTION_MAX" in monitor
    assert "http://127.0.0.1:18080/health/live" in monitor


def test_release_rollback_and_monitor_coordinate_with_one_operation_lock() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    rollback = (PROD / "rollback.sh").read_text(encoding="utf-8")
    monitor = (PROD / "monitor.sh").read_text(encoding="utf-8")
    lock_path = 'operation_lock="$production_root/shared/operations.lock"'
    prepare_lock = 'prepare_production_operation_lock "$production_root"'

    for mutation_script in (release, rollback):
        assert "umask 077" in mutation_script
        assert lock_path in mutation_script
        assert prepare_lock in mutation_script
        assert mutation_script.index(prepare_lock) < mutation_script.index(
            'exec 9>"$operation_lock"'
        )
        assert 'exec 9>"$operation_lock"' in mutation_script
        assert "flock --exclusive --wait 60 9" in mutation_script

    assert release.index("flock --exclusive --wait 60 9") < release.index(
        'bash "$source_root/infra/prod/validate-image-source.sh"'
    )
    assert rollback.index("flock --exclusive --wait 60 9") < rollback.index(
        '"${compose[@]}" up -d --no-build api worker web'
    )
    assert "umask 077" in monitor
    assert lock_path in monitor
    assert prepare_lock in monitor
    assert monitor.index(prepare_lock) < monitor.index('exec 9>"$operation_lock"')
    assert 'exec 9>"$operation_lock"' in monitor
    assert "flock --shared --nonblock 9" in monitor
    assert monitor.index("flock --shared --nonblock 9") < monitor.index(
        '"$production_root/current/infra/prod/verify.sh" --public'
    )
    assert "production monitor skipped while a release or rollback is active" in monitor


def test_operation_lock_initializer_is_root_only_inode_preserving_and_link_safe() -> None:
    initializer = (PROD / "operation-lock.sh").read_text(encoding="utf-8")

    assert 'shared_dir="$production_root/shared"' in initializer
    assert 'operation_lock="$shared_dir/operations.lock"' in initializer
    assert '[[ -L "$shared_dir" || ! -d "$shared_dir" ]]' in initializer
    assert '[[ -L "$operation_lock" ]]' in initializer
    assert '[[ ! -f "$operation_lock" ]]' in initializer
    assert "umask 077" in initializer
    assert "set -o noclobber" in initializer
    assert initializer.index("umask 077") < initializer.index("set -o noclobber")
    assert 'stat -c "%u %g %a %h" -- "$operation_lock"' in initializer
    assert '[[ "$lock_links" != "1" ]]' in initializer
    assert 'chown root:root -- "$operation_lock"' in initializer
    assert 'chmod 0600 -- "$operation_lock"' in initializer
    assert '[[ "$lock_owner:$lock_group:$lock_mode:$lock_links" != "0:0:600:1" ]]' in initializer
    assert "mv " not in initializer
    assert "install " not in initializer


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="production lock behavior requires a root Linux runtime",
)
def test_monitor_skips_cleanly_while_an_operation_lock_is_held(tmp_path: Path) -> None:
    import fcntl

    production_root = tmp_path / "production"
    shared = production_root / "shared"
    shared.mkdir(parents=True)
    lock_path = shared / "operations.lock"

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            ["bash", str(PROD / "monitor.sh")],
            check=False,
            capture_output=True,
            env={"SHANHAI_PRODUCTION_ROOT": str(production_root)},
            text=True,
        )

    assert result.returncode == 0
    assert result.stdout == ("production monitor skipped while a release or rollback is active\n")
    assert result.stderr == ""


def test_release_script_requires_exact_sha_backup_and_reversible_activation() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    rollback = (PROD / "rollback.sh").read_text(encoding="utf-8")

    assert "^[0-9a-f]{40}$" in release
    assert "pg_dump" in release
    assert "umask 077" in release
    assert "rev-parse --verify HEAD" in release
    assert "diff --quiet" in release
    assert "trap rollback_release ERR" in release
    assert "mc mirror" in release
    assert "mc diff" in release
    assert "alembic upgrade head" in release
    assert "publish-golden-content" in release
    assert "bootstrap-production-identity" in release
    assert "nginx -t" in release
    assert "previous-release" in release
    assert "docker compose" in rollback
    assert "nginx -t" in rollback


def test_release_validates_exact_checkout_before_sourcing_operation_lock() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    source_lock = 'source "$source_root/infra/prod/operation-lock.sh"'

    for validation in (
        'if [[ "$source_root" != "$production_root/releases/$release_sha" ]]',
        'if [[ ! -r "$manifest" ]]',
        'if [[ "$(git -C "$source_root" rev-parse --verify HEAD)" != "$release_sha" ]]',
        'if ! git -C "$source_root" diff --quiet',
        'unexpected_files="$(git -C "$source_root" status --porcelain',
        'if [[ -n "$unexpected_files" ]]',
    ):
        assert release.index(validation) < release.index(source_lock)


def test_release_waits_for_database_and_object_storage_health_before_writes() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")

    postgres_wait = '"${compose[@]}" up -d --wait --wait-timeout 120 postgres'
    redis_minio_wait = '"${compose[@]}" up -d --wait --wait-timeout 120 redis minio'
    application_wait = '"${compose[@]}" up -d --wait --wait-timeout 120 api worker web'
    assert postgres_wait in release
    assert redis_minio_wait in release
    assert application_wait in release
    assert release.index(postgres_wait) < release.index("pg_dump")
    assert release.index(redis_minio_wait) < release.index("mc mirror")
    assert release.index(application_wait) < release.index(
        '"$source_root/infra/prod/verify.sh" --local'
    )


def test_release_preflights_images_before_production_persistent_writes() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")

    preflight = 'bash "$source_root/infra/prod/validate-image-source.sh"'
    assert preflight in release
    assert '"$release_sha" "$production_root" 0 600' in release
    assert release.index(preflight) < release.index(
        'install -d -m 0700 -o root -g root "$SHANHAI_SECRET_DIR"'
    )
    assert release.index(preflight) < release.index(
        'install -d -m 0700 -o root -g root "$production_root/backups"'
    )
    assert '"${compose[@]}" build api worker web' in release


def test_release_validates_nginx_before_current_switch_and_restores_symlink() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")

    assert release.index("nginx -t") < release.index(
        'ln -sfn "$source_root" "$production_root/current"'
    )
    assert 'ln -sfn "$previous_source" "$production_root/current"' in release
    assert 'rm -f "$production_root/current"' in release


def test_release_requires_strict_empty_minio_diff() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")

    assert 'diff_output="$(mc diff' in release
    assert '[[ -z "$diff_output" ]]' in release
    assert "minio-pre-$release_sha-$timestamp" in release
    assert release.index("minio-pre-$release_sha-$timestamp") < release.index(
        "bootstrap-production-storage"
    )


def test_host_configuration_persists_fallback_certificate_paths() -> None:
    configure = (PROD / "configure-host.sh").read_text(encoding="utf-8")

    assert "SHANHAI_TLS_CERTIFICATE=" in configure
    assert "SHANHAI_TLS_PRIVATE_KEY=" in configure


def test_local_verification_does_not_scan_unrelated_host_nginx_logs() -> None:
    verify = (PROD / "verify.sh").read_text(encoding="utf-8")
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")

    assert verify.index('if [[ "$mode" == "--public" ]]') < verify.index(
        'nginx_log_root="${SHANHAI_NGINX_LOG_ROOT:-/var/log/nginx}"'
    )
    assert '"$nginx_log_root"/*.log' not in verify
    assert "shanhaiedu-production-access.log" in nginx
    assert "shanhaiedu-production-error.log" in nginx


def test_local_verification_preserves_explicit_release_sha_over_env_file() -> None:
    verify = (PROD / "verify.sh").read_text(encoding="utf-8")

    preserve_explicit = 'explicit_release_sha="${SHANHAI_RELEASE_SHA:-}"'
    source_environment = 'source "$environment_file"'
    resolve_release = (
        'release_sha="${explicit_release_sha:-${SHANHAI_RELEASE_SHA:?'
        'exact release SHA is required}}"'
    )
    assert verify.index(preserve_explicit) < verify.index(source_environment)
    assert verify.index(source_environment) < verify.index(resolve_release)


def test_local_verification_runs_worker_check_through_entrypoint() -> None:
    verify = (PROD / "verify.sh").read_text(encoding="utf-8")

    expected = (
        '"${compose[@]}" exec -T worker /usr/local/bin/shanhai-entrypoint '
        "python -m workers.main --check"
    )
    assert expected in verify
