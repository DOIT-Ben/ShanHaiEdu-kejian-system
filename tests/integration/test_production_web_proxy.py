from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB_CONFIG = ROOT / "infra" / "prod" / "web.conf"
CADDY_IMAGE = (
    "caddy:2.8-alpine@sha256:af32e97399febea808609119bb21544d0265c58a02836576e32a2d082c262c17"
)


@dataclass(frozen=True)
class ProxyStack:
    network: str
    echo: str
    web: str
    ingress: str
    clients: tuple[str, str]


def _docker(
    *arguments: str,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        pytest.fail(
            f"docker {' '.join(arguments[:3])} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _mount(path: Path, target: str) -> str:
    return f"{path.resolve()}:{target}:ro"


def _start_caddy(
    *,
    name: str,
    network: str,
    config: Path,
    aliases: tuple[str, ...],
) -> None:
    alias_arguments = [item for alias in aliases for item in ("--network-alias", alias)]
    _docker(
        "run",
        "--detach",
        "--name",
        name,
        "--network",
        network,
        *alias_arguments,
        "--read-only",
        "--tmpfs",
        "/tmp:size=16m,mode=1777",
        "--volume",
        _mount(config, "/etc/caddy/Caddyfile"),
        CADDY_IMAGE,
        "caddy",
        "run",
        "--config",
        "/etc/caddy/Caddyfile",
        "--adapter",
        "caddyfile",
    )


def _client_ip(container: str, network: str) -> str:
    result = _docker(
        "inspect",
        "--format",
        f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}',
        container,
    )
    return result.stdout.strip()


def _request(
    client: str,
    url: str,
    *,
    forwarded_for: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    arguments = ["exec", client, "wget", "-qO-", "--timeout=5"]
    if forwarded_for is not None:
        arguments.extend(("--header", f"X-Forwarded-For: {forwarded_for}"))
    arguments.append(url)
    return _docker(*arguments, check=check, timeout=15)


@pytest.fixture
def proxy_stack(tmp_path: Path) -> Iterator[ProxyStack]:
    if shutil.which("docker") is None:
        pytest.fail("Docker is required for the production proxy integration contract")
    _docker("info", "--format", "{{.ServerVersion}}")

    suffix = uuid4().hex[:12]
    network = f"shanhai-pr261-{suffix}"
    echo = f"shanhai-pr261-echo-{suffix}"
    web = f"shanhai-pr261-web-{suffix}"
    ingress = f"shanhai-pr261-ingress-{suffix}"
    clients = (
        f"shanhai-pr261-client-a-{suffix}",
        f"shanhai-pr261-client-b-{suffix}",
    )
    containers = [echo, web, ingress, *clients]

    echo_config = tmp_path / "echo.Caddyfile"
    echo_config.write_text(
        """{
\tauto_https off
\tadmin off
}

:8000 {
\trespond \"{http.request.header.X-Forwarded-For}\"
}

:9000 {
\trespond \"minio\"
}
""",
        encoding="utf-8",
    )
    ingress_config = tmp_path / "ingress.Caddyfile"
    ingress_config.write_text(
        """{
\tauto_https off
\tadmin off
}

:8081 {
\treverse_proxy web:8080 {
\t\theader_up X-Forwarded-For {http.request.remote.host}
\t\theader_up X-Forwarded-Proto https
\t}
}
""",
        encoding="utf-8",
    )

    _docker("network", "create", network)
    try:
        _start_caddy(
            name=echo,
            network=network,
            config=echo_config,
            aliases=("api", "minio"),
        )
        _start_caddy(
            name=web,
            network=network,
            config=WEB_CONFIG,
            aliases=("web",),
        )
        _start_caddy(
            name=ingress,
            network=network,
            config=ingress_config,
            aliases=("ingress",),
        )
        for client in clients:
            _docker(
                "run",
                "--detach",
                "--name",
                client,
                "--network",
                network,
                "--entrypoint",
                "sh",
                CADDY_IMAGE,
                "-c",
                "sleep 120",
            )

        for _ in range(30):
            if (
                _request(
                    clients[0],
                    "http://ingress:8081/api/v2/client-ip",
                    check=False,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        else:
            pytest.fail(
                "proxy stack did not become ready: " + _docker("logs", ingress, check=False).stderr
            )

        yield ProxyStack(
            network=network,
            echo=echo,
            web=web,
            ingress=ingress,
            clients=clients,
        )
    finally:
        for container in reversed(containers):
            _docker("rm", "--force", container, check=False)
        _docker("network", "rm", network, check=False)


def test_two_proxy_chain_preserves_distinct_clients_and_rejects_spoofed_xff(
    proxy_stack: ProxyStack,
) -> None:
    spoofed_ip = "203.0.113.250"
    observed: list[list[str]] = []

    for client in proxy_stack.clients:
        expected_client_ip = _client_ip(client, proxy_stack.network)
        response = _request(
            client,
            "http://ingress:8081/api/v2/client-ip",
            forwarded_for=spoofed_ip,
        )
        forwarded_chain = [part.strip() for part in response.stdout.split(",")]
        assert forwarded_chain[0] == expected_client_ip
        assert spoofed_ip not in forwarded_chain
        observed.append(forwarded_chain)

    assert observed[0][0] != observed[1][0]


def test_failed_minio_proxy_log_omits_presigned_query_credentials(
    proxy_stack: ProxyStack,
) -> None:
    _docker("rm", "--force", proxy_stack.echo)
    failed = _request(
        proxy_stack.clients[0],
        "http://ingress:8081/shanhaiedu-production/object.mp4"
        "?X-Amz-Credential=redacted&X-Amz-Signature=redacted",
        check=False,
    )

    assert failed.returncode != 0
    logs = _docker("logs", proxy_stack.web).stderr
    assert "X-Amz-Credential" not in logs
    assert "X-Amz-Signature" not in logs
    assert '"status":502' in logs
    assert "reverseproxy.statusError" in logs
