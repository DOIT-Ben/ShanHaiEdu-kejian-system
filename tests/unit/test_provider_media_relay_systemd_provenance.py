from __future__ import annotations

import re
import subprocess
from pathlib import Path


def test_relay_deploy_fails_closed_when_systemd_runtime_is_stale() -> None:
    root = Path(__file__).resolve().parents[2]
    service = (root / "infra/provider-media-relay/provider-media-relay.service").read_text(
        encoding="utf-8"
    )
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")
    deploy = runbook.split("## Deploy", 1)[1].split("## HTTPS Smoke", 1)[0]

    expected_fragment = "/etc/systemd/system/shanhai-provider-media-relay.service"
    expected_runtime = "/opt/shanhaiedu/provider-media-relay/provider_media_relay.py"
    assert expected_runtime in service
    assert "relay_deploy_phase=relay-fragment-path" in deploy
    assert 'relay_fragment_path="$(systemctl show ' in deploy
    assert f'test "${{relay_fragment_path}}" = "{expected_fragment}"' in deploy
    assert 'relay_exec_start="$(systemctl show ' in deploy
    assert "ExecStart --value | grep" not in deploy

    bootstrap = deploy.split("```bash", 1)[1].split("repository_root=", 1)[0]
    provenance_gates = (
        "relay_deploy_phase=relay-fragment-path\n"
        + deploy.split("relay_deploy_phase=relay-fragment-path\n", 1)[1].split(
            "relay_deploy_phase=relay-pid-owner", 1
        )[0]
    )
    fake_systemctl = """
systemctl() {
  case "$*" in
    *"-p FragmentPath --value"*) printf '%s\\n' "${FAKE_FRAGMENT_PATH}" ;;
    *"-p ExecStart --value"*) printf '%s\\n' "${FAKE_EXEC_START}" ;;
    *) return 99 ;;
  esac
}
"""

    scenarios = (
        (
            expected_fragment,
            f"{{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 {expected_runtime} "
            "--port 8201 ; ignore_errors=no ; start_time=[not set] ; }}",
            0,
            None,
        ),
        (
            expected_fragment,
            "/srv/shanhaiedu/repository/apps/api/provider_media_relay.py --port 8201",
            1,
            "relay-exec-start",
        ),
        (
            expected_fragment,
            "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 "
            "/srv/shanhaiedu/repository/apps/api/provider_media_relay.py "
            f"--audit-label={expected_runtime} ; ignore_errors=no ; }}",
            1,
            "relay-exec-start",
        ),
        (
            "/usr/lib/systemd/system/shanhai-provider-media-relay.service",
            f"{{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 {expected_runtime} "
            "--port 8201 ; ignore_errors=no ; }}",
            1,
            "relay-fragment-path",
        ),
    )
    for fragment_path, exec_start, expected_status, expected_phase in scenarios:
        completed = subprocess.run(
            ["bash", "-s"],
            input=(
                bootstrap
                + fake_systemctl
                + f"FAKE_FRAGMENT_PATH='{fragment_path}'\n"
                + f"FAKE_EXEC_START='{exec_start}'\n"
                + provenance_gates
            ).encode("utf-8"),
            check=False,
            capture_output=True,
        )

        assert completed.returncode == expected_status
        assert completed.stdout == b""
        if expected_phase is None:
            assert completed.stderr == b""
            continue
        assert re.fullmatch(
            rf"relay-deploy-failed phase={expected_phase} line=\d+ status=1\n?",
            completed.stderr.decode("utf-8"),
        )
        assert fragment_path.encode("utf-8") not in completed.stderr
        assert exec_start.encode("utf-8") not in completed.stderr
