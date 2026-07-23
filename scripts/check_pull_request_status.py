#!/usr/bin/env python3
"""Validate a pull request's status, review, and size declarations."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import yaml

DECLARATION = re.compile(
    r"^-\s*\[[xX]\]\s*`(?P<choice>status-update-(?:required|not-required))`",
    re.MULTILINE,
)
REVIEW_MARKER = re.compile(r"`subagent-review-(?:pending|approved)`")
REVIEW_DECLARATION = re.compile(
    r"^-\s*\[(?P<checked>[ xX])\]\s*"
    r"`(?P<choice>subagent-review-(?:pending|approved))`",
    re.MULTILINE,
)
FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")
SIZE_MARKER = re.compile(r"`pr-size-(?:within-limit|review-map-required)`")
SIZE_DECLARATION = re.compile(
    r"^-\s*\[(?P<checked>[ xX])\]\s*"
    r"`(?P<choice>pr-size-(?:within-limit|review-map-required))`",
    re.MULTILINE,
)
MARKDOWN_H2_SECTION = re.compile(
    r"^##[ \t]+.*?(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)
VERTICAL_MARKER = re.compile(r"`vertical-slice-(?:required|not-required)`")
VERTICAL_DECLARATION = re.compile(
    r"^-\s*\[(?P<checked>[ xX])\]\s*"
    r"`(?P<choice>vertical-slice-(?:required|not-required))`",
    re.MULTILINE,
)
VERTICAL_REQUIRED_FIELDS = (
    "Page routes",
    "Active operationIds",
    "Formal facts",
    "Backend tests",
    "Real API Playwright",
)
VERTICAL_BOUNDARY_PREFIXES = (
    "apps/web/src/",
    "contracts/openapi/active/",
)
VERTICAL_BOUNDARY_PATHS = ("apps/api/main.py", "contracts/api-surface.openapi.yaml")
PAGE_ROUTE = re.compile(r"^/\S*$")
OPERATION_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FORMAL_FACT = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
ROUTE_LITERAL = re.compile(r"""\bpath\s*=\s*(?P<quote>["'])(?P<path>.*?)(?P=quote)""")
OPENAPI_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
REAL_API_PLAYWRIGHT_PREFIX = "apps/web/e2e/real-api/"
REAL_API_PLAYWRIGHT_CONFIG = "apps/web/playwright.real-api.config.ts"
REAL_API_PLAYWRIGHT_WORKFLOW = ".github/workflows/r1-real-api.yml"
PLAYWRIGHT_TEST_TITLE = re.compile(
    r"""\btest(?:\.(?:only|skip|fixme))?\s*\(\s*(?P<quote>["'])(?P<title>.*?)(?P=quote)""",
    re.DOTALL,
)
FIRST_REQUIRED_GOVERNANCE_PR = 93  # Remove under #94 after legacy PR #62 closes.


def _governance_markdown(body: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    kept_lines: list[str] = []
    fence: str | None = None
    for line in without_comments.splitlines():
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```"):
            fence = "```"
            continue
        if stripped.startswith("~~~"):
            fence = "~~~"
            continue
        if line.startswith(">") or line.startswith("    "):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def _exact_h2_sections(body: str, heading: str) -> list[str]:
    prefix = f"## {heading}"
    return [
        section
        for match in MARKDOWN_H2_SECTION.finditer(body)
        if (section := match.group()).splitlines()[0].strip() == prefix
    ]


def validate_status_declaration(body: str, changed_files: set[str]) -> list[str]:
    choices = DECLARATION.findall(_governance_markdown(body))
    if len(choices) != 1:
        return ["PR must select exactly one CURRENT_STATUS freshness declaration"]

    changes_status = "CURRENT_STATUS.md" in {path.replace("\\", "/") for path in changed_files}
    if choices[0] == "status-update-required" and not changes_status:
        return ["PR declares status-update-required but does not change CURRENT_STATUS.md"]
    if choices[0] == "status-update-not-required" and changes_status:
        return ["PR changes CURRENT_STATUS.md but declares status-update-not-required"]
    return []


def _review_field_values(section: str, label: str) -> list[str]:
    fields = re.finditer(
        rf"^\s*{re.escape(label)}\s*[\uFF1A:]\s*(?P<value>.*?)\s*$",
        section,
        re.MULTILINE,
    )
    return [field.group("value").strip().strip("`").strip() for field in fields]


def validate_review_declaration(
    body: str,
    base_sha: str,
    head_sha: str,
    *,
    required: bool = False,
    is_draft: bool = True,
) -> list[str]:
    normalized_body = _governance_markdown(body)
    if REVIEW_MARKER.search(normalized_body) is None:
        if required:
            return ["PR must contain exactly one subagent review section"]
        return []

    review_sections = _exact_h2_sections(normalized_body, "子智能体审查")
    if len(review_sections) != 1:
        return ["PR must contain exactly one subagent review section"]
    section = review_sections[0]

    choices = [
        match.group("choice")
        for match in REVIEW_DECLARATION.finditer(section)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one subagent review declaration"]

    errors: list[str] = []
    base_fields = _review_field_values(section, "Base SHA")
    head_fields = _review_field_values(section, "Head SHA")
    if len(base_fields) != 1:
        errors.append("subagent review section must contain exactly one Base SHA field")
    if len(head_fields) != 1:
        errors.append("subagent review section must contain exactly one Head SHA field")
    if errors:
        return errors

    if choices[0] == "subagent-review-pending":
        if not is_draft:
            return ["non-draft PR must select subagent-review-approved"]
        return []

    declared_base = base_fields[0]
    declared_head = head_fields[0]
    if FULL_SHA.fullmatch(declared_base) is None:
        errors.append("subagent-review-approved requires a full 40-character Base SHA")
    elif declared_base.lower() != base_sha.lower():
        errors.append("subagent review Base SHA does not match the pull request base SHA")
    if FULL_SHA.fullmatch(declared_head) is None:
        errors.append("subagent-review-approved requires a full 40-character Head SHA")
    elif declared_head.lower() != head_sha.lower():
        errors.append("subagent review Head SHA does not match the pull request head SHA")
    return errors


def validate_size_declaration(
    body: str,
    changed_file_count: int,
    additions: int,
    deletions: int,
    binary_file_count: int = 0,
    *,
    required: bool = False,
) -> list[str]:
    normalized_body = _governance_markdown(body)
    if SIZE_MARKER.search(normalized_body) is None:
        if required:
            return ["PR must select exactly one pull request size declaration"]
        return []

    choices = [
        match.group("choice")
        for match in SIZE_DECLARATION.finditer(normalized_body)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one pull request size declaration"]

    exceeds_raw_trigger = (
        changed_file_count > 20 or additions - deletions > 800 or binary_file_count > 0
    )
    if exceeds_raw_trigger and choices[0] != "pr-size-review-map-required":
        return ["PR exceeds the raw size trigger but does not require a review map"]
    if not exceeds_raw_trigger and choices[0] != "pr-size-within-limit":
        return ["PR declares a required review map but does not exceed the raw size trigger"]
    return []


def _looks_like_api_router(source: str) -> bool:
    return bool(
        re.search(r"\b(?:APIRouter|FastAPI)\s*\(", source)
        or re.search(
            r"@\s*(?:app|router)\.(?:get|post|put|patch|delete|options|head)\s*\(",
            source,
        )
    )


def _read_base_file(repo_root: Path, base_sha: str | None, path: str) -> str | None:
    if base_sha is None:
        return None
    result = subprocess.run(
        ["git", "show", f"{base_sha}:{path}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def _touches_vertical_boundary(
    path: str,
    *,
    repo_root: Path,
    base_sha: str | None,
) -> bool:
    if path.startswith(VERTICAL_BOUNDARY_PREFIXES) or path in VERTICAL_BOUNDARY_PATHS:
        return True
    if not path.startswith("apps/api/") or not path.endswith(".py"):
        return False

    name = PurePosixPath(path).name
    if name.endswith("router.py") or "/routers/" in path:
        return True

    current_path = repo_root / path
    if current_path.is_file():
        try:
            if _looks_like_api_router(current_path.read_text(encoding="utf-8")):
                return True
        except (OSError, UnicodeError):
            return True

    base_source = _read_base_file(repo_root, base_sha, path)
    return base_source is not None and _looks_like_api_router(base_source)


def _declared_values(value: str) -> list[str]:
    return [
        item.strip().strip("`") for item in re.split(r"[,;\uFF0C\uFF1B]", value) if item.strip()
    ]


def _safe_repo_file(repo_root: Path, relative_path: str) -> Path | None:
    pure_path = PurePosixPath(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or pure_path.is_absolute()
        or ".." in pure_path.parts
    ):
        return None
    root = repo_root.resolve()
    candidate = (root / Path(*pure_path.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _python_test_selectors(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return set()

    selectors: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            selectors.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and child.name.startswith("test"):
                    selectors.add(f"{node.name}::{child.name}")
    return selectors


def _playwright_test_titles(path: Path) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set()
    return {match.group("title") for match in PLAYWRIGHT_TEST_TITLE.finditer(source)}


def _frontend_page_routes(repo_root: Path) -> set[str] | None:
    runtime_app = repo_root / "apps/web/src/app/RuntimeApp.tsx"
    if not runtime_app.is_file():
        return None
    try:
        route_literals = {
            match.group("path")
            for match in ROUTE_LITERAL.finditer(runtime_app.read_text(encoding="utf-8"))
        }
    except (OSError, UnicodeError):
        return None

    routes = {route for route in route_literals if route.startswith("/")}
    routes.update(
        f"/app/{route}".replace("//", "/")
        for route in route_literals
        if route and not route.startswith("/") and route != "*"
    )
    return routes


def _persisted_model_class_names(repo_root: Path) -> set[str]:
    names: set[str] = set()
    source_root = repo_root / "apps/api"
    if not source_root.is_dir():
        return names
    for path in source_root.rglob("*.py"):
        if path.name != "models.py" and not path.name.endswith("_models.py"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        names.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    return names


def _real_api_playwright_source_error(path: Path, relative_path: str) -> str | None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    forbidden = (
        "installRuntimeApi",
        "page.route(",
        "context.route(",
        "setupServer(",
        'from "msw',
        "from 'msw",
    )
    if any(marker in source for marker in forbidden):
        return (
            "vertical slice Real API Playwright uses request interception or "
            f"test API fixtures: {relative_path}"
        )
    return None


def _validate_real_api_playwright_harness(repo_root: Path) -> list[str]:
    errors: list[str] = []
    config = repo_root / REAL_API_PLAYWRIGHT_CONFIG
    if not config.is_file():
        errors.append(
            "vertical slice real API Playwright config is missing: " + REAL_API_PLAYWRIGHT_CONFIG
        )
    else:
        try:
            config_source = config.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            config_source = ""
        required_config_markers = ('"./e2e/real-api"', "VITE_API_MODE", "real")
        if (
            not all(marker in config_source for marker in required_config_markers)
            or "VITE_RUNTIME_CONTRACT_TEST" in config_source
        ):
            errors.append(
                "vertical slice real API Playwright config does not enforce the "
                "real-api directory and real mode"
            )

    package_path = repo_root / "apps/web/package.json"
    package_script: str | None = None
    if package_path.is_file():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
            package_script = package.get("scripts", {}).get("test:e2e:real-api")
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            package_script = None
    if not isinstance(package_script, str) or "playwright.real-api.config.ts" not in package_script:
        errors.append(
            "vertical slice real API Playwright package script is missing: test:e2e:real-api"
        )

    workflow = repo_root / REAL_API_PLAYWRIGHT_WORKFLOW
    if not workflow.is_file():
        errors.append(
            "vertical slice real API Playwright CI workflow is missing: "
            + REAL_API_PLAYWRIGHT_WORKFLOW
        )
    else:
        try:
            workflow_source = workflow.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            workflow_source = ""
        required_workflow_markers = (
            "postgres",
            "redis",
            "apps.api.main:app",
            "test:e2e:real-api",
        )
        if not all(marker in workflow_source for marker in required_workflow_markers):
            errors.append(
                "vertical slice real API Playwright CI workflow must start "
                "PostgreSQL, Redis and FastAPI and run test:e2e:real-api"
            )
    return errors


def _validate_declared_test(
    declared: str,
    *,
    label: str,
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    relative_path, separator, selector = declared.partition("::")
    relative_path = relative_path.strip()
    selector = selector.strip()
    test_path = _safe_repo_file(repo_root, relative_path)
    if test_path is None:
        return [f"vertical slice declares invalid {label} path: {relative_path}"]

    if label == "Backend tests":
        if not relative_path.startswith("tests/") or test_path.suffix != ".py":
            errors.append(f"vertical slice Backend tests must use tests/**/*.py: {relative_path}")
    elif not (
        relative_path.startswith(REAL_API_PLAYWRIGHT_PREFIX)
        and (relative_path.endswith(".spec.ts") or relative_path.endswith(".spec.tsx"))
    ):
        errors.append(
            "vertical slice Real API Playwright must use "
            f"apps/web/e2e/real-api/**/*.spec.ts or .spec.tsx: {relative_path}"
        )

    if not separator or not selector:
        errors.append(
            f"vertical slice {label} must include an exact ::test selector: {relative_path}"
        )
    if not test_path.is_file():
        errors.append(f"vertical slice declares missing {label} file: {relative_path}")
        return errors
    if not separator or not selector:
        return errors

    if label == "Backend tests":
        selectors = _python_test_selectors(test_path)
    else:
        selectors = _playwright_test_titles(test_path)
        source_error = _real_api_playwright_source_error(test_path, relative_path)
        if source_error is not None:
            errors.append(source_error)
    if selector not in selectors:
        errors.append(f"vertical slice declares missing {label} selector: {declared}")
    return errors


def _active_operation_ids(repo_root: Path) -> set[str] | None:
    contract_path = repo_root / "contracts/api-surface.openapi.yaml"
    if not contract_path.is_file():
        return None
    document = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    operation_ids: set[str] = set()
    for path_item in document.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if str(method).lower() not in OPENAPI_HTTP_METHODS:
                continue
            if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                operation_ids.add(operation["operationId"])
    return operation_ids


def validate_vertical_slice_declaration(
    body: str,
    changed_files: set[str],
    *,
    required: bool = False,
    repo_root: Path | None = None,
    base_sha: str | None = None,
) -> list[str]:
    normalized_files = {path.replace("\\", "/") for path in changed_files}
    resolved_root = (repo_root or Path.cwd()).resolve()
    touches_boundary = any(
        _touches_vertical_boundary(
            path,
            repo_root=resolved_root,
            base_sha=base_sha,
        )
        for path in normalized_files
    )

    normalized_body = _governance_markdown(body)
    if VERTICAL_MARKER.search(normalized_body) is None:
        if required:
            return ["PR must select exactly one vertical slice declaration"]
        return []

    sections = _exact_h2_sections(normalized_body, "纵向切片交付")
    if len(sections) != 1:
        return ["PR must contain exactly one vertical slice delivery section"]
    section = sections[0]

    choices = [
        match.group("choice")
        for match in VERTICAL_DECLARATION.finditer(section)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one vertical slice declaration"]

    choice = choices[0]
    if touches_boundary and choice != "vertical-slice-required":
        return [
            "PR changes a production delivery boundary but declares vertical-slice-not-required"
        ]
    if choice == "vertical-slice-not-required":
        return []

    errors: list[str] = []
    field_values: dict[str, str] = {}
    for label in VERTICAL_REQUIRED_FIELDS:
        values = _review_field_values(section, label)
        if len(values) != 1:
            errors.append(f"vertical slice section must contain exactly one {label} field")
            continue
        field_values[label] = values[0]
        normalized_value = values[0].strip().lower()
        if normalized_value in {"", "pending", "n/a", "none", "not applicable"}:
            errors.append(f"vertical slice field {label} must be concrete")
    if errors:
        return errors

    declared_fields = {label: _declared_values(value) for label, value in field_values.items()}
    for label in VERTICAL_REQUIRED_FIELDS:
        if not declared_fields[label]:
            errors.append(f"vertical slice field {label} must declare at least one value")
    if errors:
        return errors

    invalid_routes = sorted(
        route for route in declared_fields["Page routes"] if PAGE_ROUTE.fullmatch(route) is None
    )
    if invalid_routes:
        errors.append("vertical slice declares invalid Page routes: " + ", ".join(invalid_routes))
    valid_routes = {
        route for route in declared_fields["Page routes"] if PAGE_ROUTE.fullmatch(route) is not None
    }
    runtime_routes = _frontend_page_routes(resolved_root)
    if runtime_routes is None:
        errors.append("RuntimeApp is unavailable for vertical slice Page routes validation")
    else:
        unknown_routes = sorted(valid_routes - runtime_routes)
        if unknown_routes:
            errors.append(
                "vertical slice declares Page routes absent from RuntimeApp: "
                + ", ".join(unknown_routes)
            )

    invalid_operation_ids = sorted(
        operation_id
        for operation_id in declared_fields["Active operationIds"]
        if OPERATION_ID.fullmatch(operation_id) is None
    )
    if invalid_operation_ids:
        errors.append(
            "vertical slice declares invalid active operationIds: "
            + ", ".join(invalid_operation_ids)
        )

    invalid_facts = sorted(
        fact for fact in declared_fields["Formal facts"] if FORMAL_FACT.fullmatch(fact) is None
    )
    if invalid_facts:
        errors.append("vertical slice declares invalid Formal facts: " + ", ".join(invalid_facts))
    valid_facts = {
        fact for fact in declared_fields["Formal facts"] if FORMAL_FACT.fullmatch(fact) is not None
    }
    unknown_facts = sorted(valid_facts - _persisted_model_class_names(resolved_root))
    if unknown_facts:
        errors.append(
            "vertical slice declares Formal facts absent from persisted model classes: "
            + ", ".join(unknown_facts)
        )

    active_operation_ids = _active_operation_ids(resolved_root)
    if active_operation_ids is None:
        errors.append("active OpenAPI contract is unavailable for vertical slice validation")
    else:
        declared_operation_ids = {
            operation_id
            for operation_id in declared_fields["Active operationIds"]
            if OPERATION_ID.fullmatch(operation_id) is not None
        }
        unknown_operation_ids = sorted(declared_operation_ids - active_operation_ids)
        if unknown_operation_ids:
            errors.append(
                "vertical slice declares unknown active operationIds: "
                + ", ".join(unknown_operation_ids)
            )

    for label in ("Backend tests", "Real API Playwright"):
        for declared_test in declared_fields[label]:
            errors.extend(
                _validate_declared_test(
                    declared_test,
                    label=label,
                    repo_root=resolved_root,
                )
            )
    errors.extend(_validate_real_api_playwright_harness(resolved_root))
    return errors


def changed_files(base_sha: str, head_sha: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def parse_numstat(output: str) -> tuple[int, int, int]:
    additions = 0
    deletions = 0
    binary_file_count = 0
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            binary_file_count += 1
            continue
        added, deleted, _path = parts
        if added.isdigit() and deleted.isdigit():
            additions += int(added)
            deletions += int(deleted)
        else:
            binary_file_count += 1
    return additions, deletions, binary_file_count


def changed_line_counts(base_sha: str, head_sha: str) -> tuple[int, int, int]:
    result = subprocess.run(
        ["git", "diff", "--numstat", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_numstat(result.stdout)


def parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--is-draft", required=True, type=parse_bool)
    args = parser.parse_args()

    files = changed_files(args.base_sha, args.head_sha)
    additions, deletions, binary_file_count = changed_line_counts(args.base_sha, args.head_sha)
    declarations_required = args.pr_number >= FIRST_REQUIRED_GOVERNANCE_PR
    errors = validate_status_declaration(args.body, files)
    errors.extend(
        validate_vertical_slice_declaration(
            args.body,
            files,
            required=declarations_required,
            base_sha=args.base_sha,
        )
    )
    errors.extend(
        validate_review_declaration(
            args.body,
            args.base_sha,
            args.head_sha,
            required=declarations_required,
            is_draft=args.is_draft,
        )
    )
    errors.extend(
        validate_size_declaration(
            args.body,
            len(files),
            additions,
            deletions,
            binary_file_count,
            required=declarations_required,
        )
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print("PR declarations are consistent with the pull request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
