"""Deterministic Python module-boundary and size governance checks."""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILE_LINE_LIMIT = 400
FUNCTION_LINE_LIMIT = 60
ISSUE_REFERENCE = re.compile(r"^(?:#\d+|https://github\.com/[^/]+/[^/]+/issues/\d+)$")
MODEL_MODULE = re.compile(r"^apps\.api\.([a-z0-9_]+)\.(?:models|[a-z0-9_]+_models)$")
TYPE_ALIAS = re.compile(r"(?m)^type ([A-Za-z_][A-Za-z0-9_]*) = ")
TYPE_ALIAS_LINE = re.compile(r"^type [A-Za-z_][A-Za-z0-9_]* = ")


@dataclass(frozen=True, slots=True)
class OwnedException:
    owner: str
    reason: str
    exit_issue: str


@dataclass(frozen=True, slots=True)
class ModelImportException(OwnedException):
    source: str
    target: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileSizeException(OwnedException):
    path: str
    line_count: int


@dataclass(frozen=True, slots=True)
class FunctionSizeException(OwnedException):
    path: str
    qualname: str
    line_count: int


@dataclass(frozen=True, slots=True)
class RepositoryGovernanceBaseline:
    model_imports: tuple[ModelImportException, ...]
    oversized_files: tuple[FileSizeException, ...]
    oversized_functions: tuple[FunctionSizeException, ...]


@dataclass(frozen=True, slots=True)
class ModelImport:
    source: str
    target: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FunctionSize:
    path: str
    qualname: str
    line_count: int


def load_repository_governance_baseline(
    path: Path, errors: list[str]
) -> RepositoryGovernanceBaseline | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read repository governance baseline: {exc}")
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        errors.append("repository governance baseline must use schema_version 1")
        return None

    start = len(errors)
    model_imports = _load_model_imports(payload, errors)
    oversized_files = _load_file_sizes(payload, errors)
    oversized_functions = _load_function_sizes(payload, errors)
    if len(errors) != start:
        return None
    return RepositoryGovernanceBaseline(
        model_imports=tuple(model_imports),
        oversized_files=tuple(oversized_files),
        oversized_functions=tuple(oversized_functions),
    )


def check_cross_module_model_imports(
    files: list[Path],
    root: Path,
    baseline: RepositoryGovernanceBaseline,
    errors: list[str],
) -> None:
    allowed = {(item.source, item.target, item.names) for item in baseline.model_imports}
    for item in _find_cross_module_model_imports(files, root, errors):
        if (item.source, item.target, item.names) not in allowed:
            names = ", ".join(item.names)
            errors.append(
                f"unauthorized cross-module ORM import: {item.source} -> {item.target} [{names}]"
            )


def check_python_size_limits(
    files: list[Path],
    root: Path,
    baseline: RepositoryGovernanceBaseline,
    errors: list[str],
) -> None:
    file_baseline = {item.path: item for item in baseline.oversized_files}
    function_baseline = {(item.path, item.qualname): item for item in baseline.oversized_functions}
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        try:
            line_count = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot inspect Python source {relative}: {exc}")
            continue
        if line_count <= FILE_LINE_LIMIT:
            continue
        print(
            f"warning: oversized file: {relative} has {line_count} lines",
            file=sys.stderr,
        )
        exception = file_baseline.get(relative)
        if exception is None:
            errors.append(f"unowned oversized file: {relative} has {line_count} lines")
        elif line_count > exception.line_count:
            errors.append(
                "oversized file grew beyond its owned baseline: "
                f"{relative} has {line_count} lines (baseline {exception.line_count})"
            )

    for item in _find_function_sizes(files, root, errors):
        if item.line_count <= FUNCTION_LINE_LIMIT:
            continue
        print(
            f"warning: long function: {item.path}::{item.qualname} has {item.line_count} lines",
            file=sys.stderr,
        )
        exception = function_baseline.get((item.path, item.qualname))
        if exception is None:
            errors.append(
                f"unowned long function: {item.path}::{item.qualname} has {item.line_count} lines"
            )
        elif item.line_count > exception.line_count:
            errors.append(
                "long function grew beyond its owned baseline: "
                f"{item.path}::{item.qualname} has {item.line_count} lines "
                f"(baseline {exception.line_count})"
            )


def production_python_files(files: list[Path], root: Path) -> list[Path]:
    result: list[Path] = []
    for path in files:
        relative = path.relative_to(root)
        if path.suffix != ".py":
            continue
        if relative.parts[:2] == ("apps", "api") or relative.parts[:1] == ("workers",):
            result.append(path)
    return sorted(result)


def _find_cross_module_model_imports(
    files: list[Path], root: Path, errors: list[str]
) -> list[ModelImport]:
    imports: list[ModelImport] = []
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        tree = _parse(path, relative, errors)
        if tree is None:
            continue
        source_owner = _source_owner(Path(relative))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = _resolve_import(relative, node)
                target_owner = _model_owner(target)
                if target_owner is not None and target_owner != source_owner:
                    imports.append(
                        ModelImport(
                            source=relative,
                            target=target,
                            names=tuple(sorted(alias.name for alias in node.names)),
                        )
                    )
                    continue
                for alias in node.names:
                    candidate = f"{target}.{alias.name}" if target else alias.name
                    candidate_owner = _model_owner(candidate)
                    if (
                        candidate_owner is not None
                        and candidate_owner != source_owner
                        and _module_exists(root, candidate)
                    ):
                        imports.append(
                            ModelImport(
                                source=relative,
                                target=candidate,
                                names=(alias.name,),
                            )
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target_owner = _model_owner(alias.name)
                    if target_owner is not None and target_owner != source_owner:
                        imports.append(
                            ModelImport(
                                source=relative,
                                target=alias.name,
                                names=(alias.name,),
                            )
                        )
    return sorted(imports, key=lambda item: (item.source, item.target, item.names))


def _find_function_sizes(files: list[Path], root: Path, errors: list[str]) -> list[FunctionSize]:
    result: list[FunctionSize] = []
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        tree = _parse(path, relative, errors)
        if tree is None:
            continue
        visitor = _FunctionVisitor(relative)
        visitor.visit(tree)
        result.extend(visitor.functions)
    return sorted(result, key=lambda item: (item.path, item.qualname))


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self._path = path
        self._scope: list[str] = []
        self.functions: list[FunctionSize] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scope.append(node.name)
        self.functions.append(
            FunctionSize(
                path=self._path,
                qualname=".".join(self._scope),
                line_count=(node.end_lineno or node.lineno) - node.lineno + 1,
            )
        )
        self.generic_visit(node)
        self._scope.pop()


def _parse(path: Path, relative: str, errors: list[str]) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8")
        try:
            return ast.parse(source, filename=relative)
        except SyntaxError as exc:
            lines = source.splitlines()
            if (
                exc.lineno is None
                or exc.lineno > len(lines)
                or TYPE_ALIAS_LINE.match(lines[exc.lineno - 1]) is None
            ):
                raise
            compatible_source = TYPE_ALIAS.sub(r"\1 = ", source)
            return ast.parse(compatible_source, filename=relative)
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"cannot parse Python source {relative}: {exc}")
        return None


def _source_owner(path: Path) -> str:
    if path.parts[:2] == ("apps", "api") and len(path.parts) > 3:
        return path.parts[2]
    if path.parts[:1] == ("workers",):
        return "workers"
    return "api-root"


def _model_owner(module: str) -> str | None:
    match = MODEL_MODULE.fullmatch(module)
    return match.group(1) if match is not None else None


def _module_exists(root: Path, module: str) -> bool:
    path = root.joinpath(*module.split("."))
    return path.with_suffix(".py").is_file() or path.joinpath("__init__.py").is_file()


def _resolve_import(source: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = list(Path(source).parts[:-1])
    keep = max(0, len(package) - node.level + 1)
    suffix = (node.module or "").split(".") if node.module else []
    return ".".join([*package[:keep], *suffix])


def _load_model_imports(payload: dict[str, Any], errors: list[str]) -> list[ModelImportException]:
    result: list[ModelImportException] = []
    for index, item in _entries(payload, "cross_module_model_imports", errors):
        label = f"cross_module_model_imports[{index}]"
        metadata = _metadata(item, label, errors)
        source = _text(item, "source", label, errors)
        target = _text(item, "target", label, errors)
        names_value = item.get("names")
        if (
            not isinstance(names_value, list)
            or not names_value
            or not all(isinstance(name, str) and name for name in names_value)
        ):
            errors.append(f"invalid governance baseline {label}: names must be non-empty strings")
            names: tuple[str, ...] = ()
        else:
            names = tuple(sorted(names_value))
        if metadata and source and target and names:
            result.append(ModelImportException(*metadata, source, target, names))
    return result


def _load_file_sizes(payload: dict[str, Any], errors: list[str]) -> list[FileSizeException]:
    result: list[FileSizeException] = []
    for index, item in _entries(payload, "oversized_files", errors):
        label = f"oversized_files[{index}]"
        metadata = _metadata(item, label, errors)
        path = _text(item, "path", label, errors)
        line_count = _positive_int(item, "line_count", label, errors)
        if metadata and path and line_count:
            result.append(FileSizeException(*metadata, path, line_count))
    return result


def _load_function_sizes(payload: dict[str, Any], errors: list[str]) -> list[FunctionSizeException]:
    result: list[FunctionSizeException] = []
    for index, item in _entries(payload, "oversized_functions", errors):
        label = f"oversized_functions[{index}]"
        metadata = _metadata(item, label, errors)
        path = _text(item, "path", label, errors)
        qualname = _text(item, "qualname", label, errors)
        line_count = _positive_int(item, "line_count", label, errors)
        if metadata and path and qualname and line_count:
            result.append(FunctionSizeException(*metadata, path, qualname, line_count))
    return result


def _entries(
    payload: dict[str, Any], key: str, errors: list[str]
) -> list[tuple[int, dict[str, Any]]]:
    value = payload.get(key)
    if not isinstance(value, list):
        errors.append(f"repository governance baseline {key} must be a list")
        return []
    result: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"invalid governance baseline {key}[{index}]: object is required")
        else:
            result.append((index, item))
    return result


def _metadata(item: dict[str, Any], label: str, errors: list[str]) -> tuple[str, str, str] | None:
    owner = item.get("owner")
    reason = item.get("reason")
    exit_issue = item.get("exit_issue")
    if not isinstance(owner, str) or not owner.strip():
        errors.append(f"invalid governance baseline {label}: owner is required")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(f"invalid governance baseline {label}: reason is required")
    if not isinstance(exit_issue, str) or ISSUE_REFERENCE.fullmatch(exit_issue) is None:
        errors.append(
            f"invalid governance baseline {label}: exit_issue must reference a GitHub issue"
        )
    if not all(isinstance(value, str) and value.strip() for value in (owner, reason, exit_issue)):
        return None
    if ISSUE_REFERENCE.fullmatch(exit_issue) is None:
        return None
    return owner.strip(), reason.strip(), exit_issue.strip()


def _text(item: dict[str, Any], key: str, label: str, errors: list[str]) -> str | None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"invalid governance baseline {label}: {key} is required")
        return None
    return value.strip()


def _positive_int(item: dict[str, Any], key: str, label: str, errors: list[str]) -> int | None:
    value = item.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        errors.append(f"invalid governance baseline {label}: {key} must be positive")
        return None
    return value
