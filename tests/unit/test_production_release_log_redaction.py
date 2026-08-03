from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = ROOT / "infra" / "prod" / "release.sh"


def test_minio_backup_and_restore_commands_suppress_raw_object_paths() -> None:
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")
    object_operations = [
        line.strip()
        for line in release.splitlines()
        if re.search(r"\bmc (?:mirror|mb|diff|rb)\b", line)
    ]

    assert object_operations
    for operation in object_operations:
        assert ">/dev/null 2>&1" in operation or (
            'diff_output="$(mc diff' in operation and "2>/dev/null" in operation
        )


def test_minio_failures_emit_only_fixed_redacted_reasons() -> None:
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")

    for reason in (
        "MinIO pre-release backup failed",
        "MinIO post-release backup or restore verification failed",
    ):
        assert f'run_redacted "{reason}"' in release

    assert '"$@" >/dev/null 2>&1 || status=$?' in release
    assert 'return "$status"' in release


def test_production_bootstrap_commands_suppress_internal_identifiers() -> None:
    release = RELEASE_SCRIPT.read_text(encoding="utf-8")
    bootstrap_operations = [
        line.strip() for line in release.splitlines() if "python -m apps.api.cli" in line
    ]

    assert len(bootstrap_operations) == 3
    for operation in bootstrap_operations:
        assert operation.startswith("run_redacted")

    for reason in (
        "production storage bootstrap failed",
        "golden content publication failed",
        "production identity bootstrap failed",
    ):
        assert reason in release
