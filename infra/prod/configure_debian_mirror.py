#!/usr/bin/env python3
"""Configure public Debian package mirrors without persisting credentials."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

OFFICIAL_MAIN = "http://deb.debian.org/debian"
OFFICIAL_SECURITY = "http://deb.debian.org/debian-security"
INVALID_MIRROR = "Debian mirror must be a public credential-free HTTPS URL ending in /debian"


def validate_mirror(value: str) -> None:
    parsed = urlsplit(value)
    if (
        not value.startswith("https://")
        or any(character.isspace() for character in value)
        or any(character in value for character in "@?#%")
        or parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith("/debian")
    ):
        raise ValueError(INVALID_MIRROR)


def configure_sources(path: Path, mirror: str) -> None:
    validate_mirror(mirror)
    source = path.read_text(encoding="utf-8")
    if source.count(OFFICIAL_MAIN) != 2 or source.count(OFFICIAL_SECURITY) != 1:
        raise ValueError("Debian source file does not match the pinned base image")
    source = source.replace(OFFICIAL_SECURITY, f"{mirror}-security")
    source = source.replace(OFFICIAL_MAIN, mirror)
    path.write_text(source, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: configure_debian_mirror.py <mirror> <sources-file>", file=sys.stderr)
        return 2
    try:
        configure_sources(Path(sys.argv[2]), sys.argv[1])
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
