from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_package_matches_current_source_tree() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_frontend_package.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
