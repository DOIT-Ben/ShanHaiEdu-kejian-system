#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import secrets
import stat
import sys
from pathlib import Path

SHA_PATTERN = re.compile(rb"^[0-9a-f]{40}$")
RELEASE_PREFIX = b"SHANHAI_RELEASE_SHA="


class UpdateError(RuntimeError):
    pass


def _validate_file(
    metadata: os.stat_result,
    *,
    expected_owner: int,
    expected_mode: int,
) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise UpdateError("production environment file is unsafe")
    if metadata.st_uid != expected_owner:
        raise UpdateError("production environment file owner is unsafe")
    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise UpdateError("production environment file mode is unsafe")
    if metadata.st_nlink != 1:
        raise UpdateError("production environment file link count is unsafe")


def _read_file(
    path: Path,
    *,
    expected_owner: int,
    expected_mode: int,
) -> tuple[bytes, os.stat_result]:
    initial = os.lstat(path)
    _validate_file(initial, expected_owner=expected_owner, expected_mode=expected_mode)
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        _validate_file(opened, expected_owner=expected_owner, expected_mode=expected_mode)
        if (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino):
            raise UpdateError("production environment file changed during validation")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read(), opened
    finally:
        os.close(descriptor)


def _validate_environment_path(
    path: Path,
    *,
    expected_owner: int,
    expected_mode: int,
) -> os.stat_result:
    if not path.is_absolute():
        raise UpdateError("production environment path must be absolute")
    if expected_owner < 0 or not 0 <= expected_mode <= 0o777:
        raise UpdateError("production environment metadata contract is invalid")
    if os.geteuid() != expected_owner:
        raise UpdateError("production environment updater identity is unsafe")

    parent_metadata = os.lstat(path.parent)
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != expected_owner
        or stat.S_IMODE(parent_metadata.st_mode) & 0o022
    ):
        raise UpdateError("production environment directory is unsafe")
    return parent_metadata


def _extract_release_sha(content: bytes) -> bytes:
    lines = content.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith(RELEASE_PREFIX)]
    if len(matches) != 1:
        raise UpdateError("production environment must contain exactly one release SHA entry")
    current_line = lines[matches[0]]
    current_sha = current_line[len(RELEASE_PREFIX) :].rstrip(b"\r\n")
    if not SHA_PATTERN.fullmatch(current_sha):
        raise UpdateError("production environment release SHA is invalid")
    return current_sha


def inspect_release(
    path: Path,
    expected_owner: int,
    expected_mode: int,
) -> bytes:
    _validate_environment_path(
        path,
        expected_owner=expected_owner,
        expected_mode=expected_mode,
    )
    content, _ = _read_file(
        path,
        expected_owner=expected_owner,
        expected_mode=expected_mode,
    )
    return _extract_release_sha(content)


def _replace_file_atomically(
    path: Path,
    replacement: bytes,
    initial: os.stat_result,
    parent_metadata: os.stat_result,
    *,
    expected_owner: int,
    expected_mode: int,
) -> None:
    parent = path.parent
    parent_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    parent_flags |= getattr(os, "O_NOFOLLOW", 0)
    parent_descriptor = os.open(parent, parent_flags)
    temporary_name = f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    try:
        opened_parent = os.fstat(parent_descriptor)
        if (opened_parent.st_dev, opened_parent.st_ino) != (
            parent_metadata.st_dev,
            parent_metadata.st_ino,
        ):
            raise UpdateError("production environment directory changed during validation")
        current = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        _validate_file(current, expected_owner=expected_owner, expected_mode=expected_mode)
        if (current.st_dev, current.st_ino) != (initial.st_dev, initial.st_ino):
            raise UpdateError("production environment file changed before replacement")

        temporary_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        temporary_descriptor = os.open(
            temporary_name,
            temporary_flags,
            expected_mode,
            dir_fd=parent_descriptor,
        )
        try:
            with os.fdopen(temporary_descriptor, "wb", closefd=False) as handle:
                handle.write(replacement)
                handle.flush()
            os.fchown(temporary_descriptor, expected_owner, initial.st_gid)
            os.fchmod(temporary_descriptor, expected_mode)
            os.fsync(temporary_descriptor)
        finally:
            os.close(temporary_descriptor)

        os.replace(
            temporary_name,
            path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        os.fsync(parent_descriptor)
        updated = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        _validate_file(updated, expected_owner=expected_owner, expected_mode=expected_mode)
    finally:
        try:
            os.unlink(temporary_name, dir_fd=parent_descriptor)
        except FileNotFoundError:
            pass
        os.close(parent_descriptor)


def update_release(
    path: Path,
    expected_sha: bytes,
    new_sha: bytes,
    expected_owner: int,
    expected_mode: int,
) -> bool:
    if not SHA_PATTERN.fullmatch(expected_sha) or not SHA_PATTERN.fullmatch(new_sha):
        raise UpdateError("production release SHA argument is invalid")
    parent_metadata = _validate_environment_path(
        path,
        expected_owner=expected_owner,
        expected_mode=expected_mode,
    )

    content, initial = _read_file(
        path,
        expected_owner=expected_owner,
        expected_mode=expected_mode,
    )
    current_sha = _extract_release_sha(content)
    lines = content.splitlines(keepends=True)
    index = next(index for index, line in enumerate(lines) if line.startswith(RELEASE_PREFIX))
    current_line = lines[index]
    if current_sha == new_sha:
        return False
    if current_sha != expected_sha:
        raise UpdateError("production environment release SHA does not match expected SHA")

    line_ending = current_line[len(current_line.rstrip(b"\r\n")) :]
    lines[index] = RELEASE_PREFIX + new_sha + line_ending
    _replace_file_atomically(
        path,
        b"".join(lines),
        initial,
        parent_metadata,
        expected_owner=expected_owner,
        expected_mode=expected_mode,
    )
    return True


def main() -> int:
    inspect_mode = len(sys.argv) == 5 and sys.argv[1] == "inspect"
    if not inspect_mode and len(sys.argv) != 6:
        print(
            "usage: update_production_release.py inspect <env> <uid> <mode> | "
            "<env> <expected-sha> <new-sha> <uid> <mode>",
            file=sys.stderr,
        )
        return 2
    try:
        if inspect_mode:
            release_sha = inspect_release(
                Path(sys.argv[2]),
                int(sys.argv[3], 10),
                int(sys.argv[4], 8),
            )
            print(release_sha.decode("ascii"))
            return 0
        changed = update_release(
            Path(sys.argv[1]),
            sys.argv[2].encode("ascii"),
            sys.argv[3].encode("ascii"),
            int(sys.argv[4], 10),
            int(sys.argv[5], 8),
        )
    except (OSError, UnicodeError, ValueError, UpdateError) as error:
        print(str(error) or "production environment update failed", file=sys.stderr)
        return 1
    print(
        "production release environment updated"
        if changed
        else "production release environment already current"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
