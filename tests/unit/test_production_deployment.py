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
    assert compose["services"]["api"]["ports"] == ["127.0.0.1:18000:8000"]
    assert compose["services"]["web"]["ports"] == ["127.0.0.1:18080:8080"]
    assert compose["services"]["minio"]["ports"] == ["127.0.0.1:19000:9000"]
    for service in compose["services"].values():
        assert "restart" in service
        assert "healthcheck" in service
        assert "mem_limit" in service
        assert "cpus" in service


def test_host_nginx_contract_preserves_https_sse_and_private_services() -> None:
    nginx = (PROD / "host-nginx.conf.template").read_text(encoding="utf-8")

    assert "server_name ${SHANHAI_PUBLIC_IP};" in nginx
    assert "listen 443 ssl" in nginx
    assert "return 301 https://$host$request_uri;" in nginx
    assert "proxy_pass http://127.0.0.1:18000;" in nginx
    assert "proxy_buffering off;" in nginx
    assert "proxy_pass http://127.0.0.1:19000;" in nginx
    assert "proxy_pass http://127.0.0.1:18080;" in nginx


def test_release_script_requires_exact_sha_backup_and_reversible_activation() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    rollback = (PROD / "rollback.sh").read_text(encoding="utf-8")

    assert "^[0-9a-f]{40}$" in release
    assert "pg_dump" in release
    assert "alembic upgrade head" in release
    assert "publish-golden-content" in release
    assert "bootstrap-production-identity" in release
    assert "nginx -t" in release
    assert "previous-release" in release
    assert "docker compose" in rollback
    assert "nginx -t" in rollback
