# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pytest

from scripts import build_frontend_package as package_builder

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_package_matches_current_source_tree() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_frontend_package.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_snapshot_and_archive_stay_stable_when_sources_do_not_change() -> None:
    sources = {"docs/backend/README.md": b"same source\n"}
    previous = {
        "generated_on_utc": "2026-07-18T08:00:00Z",
        "source_file_count": 1,
        "source_tree_sha256": package_builder._source_digest(sources),
    }

    selected = package_builder._select_snapshot(
        sources,
        previous=previous,
        now=datetime(2026, 7, 19, 9, 30, tzinfo=UTC),
    )

    assert selected == previous
    assert package_builder._build_archive(sources, selected) == package_builder._build_archive(
        sources, selected
    )


def test_non_frontend_source_change_refreshes_snapshot_timestamp() -> None:
    previous_sources = {"docs/backend/README.md": b"before\n"}
    current_sources = {"docs/backend/README.md": b"after\n"}
    previous = {
        "generated_on_utc": "2026-07-18T08:00:00Z",
        "source_file_count": 1,
        "source_tree_sha256": package_builder._source_digest(previous_sources),
    }

    selected = package_builder._select_snapshot(
        current_sources,
        previous=previous,
        now=datetime(2026, 7, 19, 9, 30, tzinfo=UTC),
    )

    assert selected == {
        "generated_on_utc": "2026-07-19T09:30:00Z",
        "source_file_count": 1,
        "source_tree_sha256": package_builder._source_digest(current_sources),
    }


def test_snapshot_must_match_current_sources(tmp_path: Path) -> None:
    sources = {"docs/backend/README.md": b"current\n"}
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_on_utc": "2026-07-18T08:00:00Z",
                "source_file_count": 1,
                "source_tree_sha256": hashlib.sha256(b"stale").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="snapshot metadata is stale"):
        package_builder._current_snapshot(sources, snapshot_path)


def test_git_symlink_source_is_rejected(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=tmp_path,
        input=b"../outside.md",
        capture_output=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            "120000",
            blob.decode("ascii"),
            "contracts/link.md",
        ],
        cwd=tmp_path,
        check=True,
    )

    with pytest.raises(ValueError, match="regular Git files"):
        package_builder._source_entries(tmp_path)


def test_resolved_source_path_must_stay_inside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside repository"):
        package_builder._canonical_bytes(repository, PurePosixPath("../outside.md"))


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("payload.pdf", b"%PDF-1.4\n1 0 obj\n", "unsupported text extension"),
        ("payload.md", b"invalid: " + bytes([0xFF]) + b"\n", "valid UTF-8"),
    ],
)
def test_non_text_source_is_rejected(
    tmp_path: Path,
    name: str,
    content: bytes,
    message: str,
) -> None:
    source = tmp_path / "docs" / "backend" / name
    source.parent.mkdir(parents=True)
    source.write_bytes(content)

    with pytest.raises(ValueError, match=message):
        package_builder._canonical_bytes(
            tmp_path,
            PurePosixPath("docs/backend") / name,
        )
