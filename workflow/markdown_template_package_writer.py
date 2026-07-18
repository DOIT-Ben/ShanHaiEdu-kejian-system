"""Validated, exclusive filesystem publishing for compiled template packages."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from workflow.content_package import (
    ContentPackageValidationError,
    resolve_content_package_item_path,
    validate_content_package,
)

OUTPUT_LOCK_SUFFIX = ".compile.lock"
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
_RENAME_EXCL = 0x4


class MarkdownTemplateCompilationError(ValueError):
    """Raised when a reviewed draft cannot become a safe content package."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CompiledMarkdownTemplatePackage:
    """An in-memory package ready for deterministic validated writing."""

    manifest: dict[str, Any]
    items: Mapping[str, dict[str, Any]]
    contracts_root: Path = field(repr=False, compare=False)


def write_compiled_content_package(
    compiled: CompiledMarkdownTemplatePackage,
    output_root: Path,
) -> None:
    """Atomically write and validate a compiled package without overwriting paths."""

    output = Path(os.path.abspath(output_root))
    if _path_exists(output):
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_OUTPUT_EXISTS",
            f"Output path already exists: {output.name}",
        )
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_WRITE_FAILED",
            "Cannot prepare compiled content package output",
        ) from exc

    with _reserve_output_path(output):
        _write_reserved_content_package(compiled, output)


def _write_reserved_content_package(
    compiled: CompiledMarkdownTemplatePackage,
    output: Path,
) -> None:
    temporary: Path | None = None
    try:
        _require_output_absent(output)
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        for entry in cast(list[dict[str, Any]], compiled.manifest["items"]):
            item_path = resolve_content_package_item_path(
                temporary,
                cast(str, entry["path"]),
            )
            item_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(item_path, compiled.items[cast(str, entry["item_key"])])
        _write_json(temporary / "manifest.json", compiled.manifest)
        try:
            validate_content_package(temporary, contracts_root=compiled.contracts_root)
        except ContentPackageValidationError as exc:
            raise MarkdownTemplateCompilationError(
                "MARKDOWN_COMPILE_PACKAGE_INVALID",
                f"Compiled content package failed validation: {exc.code}",
            ) from exc
        _require_output_absent(output)
        _publish_directory_no_replace(temporary, output)
    except MarkdownTemplateCompilationError:
        raise
    except OSError as exc:
        code = (
            "MARKDOWN_COMPILE_OUTPUT_EXISTS"
            if _target_exists(exc, output)
            else "MARKDOWN_COMPILE_WRITE_FAILED"
        )
        raise MarkdownTemplateCompilationError(
            code,
            "Cannot write compiled content package",
        ) from exc
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _require_output_absent(output: Path) -> None:
    if _path_exists(output):
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_OUTPUT_EXISTS",
            f"Output path already exists: {output.name}",
        )


def _path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _target_exists(error: OSError, output: Path) -> bool:
    return error.errno in {errno.EEXIST, errno.ENOTEMPTY} or _path_exists(output)


def _publish_directory_no_replace(source: Path, output: Path) -> None:
    if sys.platform == "win32":
        os.rename(source, output)
        return
    if sys.platform.startswith("linux"):
        _call_no_replace(
            "renameat2",
            (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint),
            (_AT_FDCWD, os.fsencode(source), _AT_FDCWD, os.fsencode(output), _RENAME_NOREPLACE),
            output,
        )
        return
    if sys.platform == "darwin":
        _call_no_replace(
            "renamex_np",
            (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint),
            (os.fsencode(source), os.fsencode(output), _RENAME_EXCL),
            output,
        )
        return
    raise OSError(errno.ENOTSUP, "Atomic no-replace directory publishing is unavailable")


def _call_no_replace(
    function_name: str,
    argument_types: tuple[Any, ...],
    arguments: tuple[Any, ...],
    output: Path,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    function = cast(Any, getattr(library, function_name, None))
    if function is None:
        raise OSError(errno.ENOTSUP, f"{function_name} is unavailable")
    function.argtypes = list(argument_types)
    function.restype = ctypes.c_int
    if function(*arguments) == 0:
        return
    error_number = ctypes.get_errno()
    raise OSError(error_number, os.strerror(error_number), output)


@contextmanager
def _reserve_output_path(output: Path) -> Generator[None, None, None]:
    lock_path = output.with_name(f".{output.name}{OUTPUT_LOCK_SUFFIX}")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_OUTPUT_BUSY",
            "Another compiler is already writing this output path",
        ) from exc
    except OSError as exc:
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_WRITE_FAILED",
            "Cannot reserve compiled content package output",
        ) from exc
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    path.write_text(payload + "\n", encoding="utf-8", newline="\n")
