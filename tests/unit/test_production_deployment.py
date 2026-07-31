from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "infra" / "prod"


def test_production_release_assets_are_complete() -> None:
    required = {
        "compose.yaml",
        "Dockerfile.api",
        "Dockerfile.web",
        "api-entrypoint.sh",
        "web.conf",
        "host-nginx.conf.template",
        "env.example",
        "release.sh",
        "rollback.sh",
        "verify.sh",
        "monitor.sh",
        "README.md",
    }

    assert {path.name for path in PROD.iterdir()} >= required


def test_production_compose_isolated_persistent_and_loopback_only() -> None:
    compose = yaml.safe_load((PROD / "compose.yaml").read_text(encoding="utf-8"))

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
    assert compose["services"]["api"]["ports"] == ["127.0.0.1:18000:8000"]
    assert compose["services"]["web"]["ports"] == ["127.0.0.1:18080:8080"]
    assert compose["services"]["minio"]["ports"] == ["127.0.0.1:19000:9000"]
    for service in compose["services"].values():
        assert "restart" in service
        assert "healthcheck" in service
        assert "mem_limit" in service
        assert "cpus" in service
    worker_health = compose["services"]["worker"]["healthcheck"]["test"][1]
    assert "shanhai-entrypoint python -m workers.main --check" in worker_health


def test_host_nginx_contract_preserves_https_sse_and_private_services() -> None:
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")

    assert "server_name ${SHANHAI_PUBLIC_IP};" in nginx
    assert "listen 443 ssl" in nginx
    assert "return 301 https://$host$request_uri;" in nginx
    assert "proxy_pass http://127.0.0.1:18000;" in nginx
    assert "proxy_buffering off;" in nginx
    assert "proxy_pass http://127.0.0.1:19000;" in nginx
    assert "access_log off;" in nginx
    assert "proxy_pass http://127.0.0.1:18080;" in nginx


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


def test_api_image_reads_file_secrets_then_drops_root() -> None:
    dockerfile = (PROD / "Dockerfile.api").read_text(encoding="utf-8")
    entrypoint = (PROD / "api-entrypoint.sh").read_text(encoding="utf-8")

    assert "gosu" in dockerfile
    assert "USER 10001:10001" not in dockerfile
    assert 'exec gosu 10001:10001 "$@"' in entrypoint


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
