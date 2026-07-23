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
DELIVERY_MANIFEST_FIELD = "Delivery manifest"
DELIVERY_MANIFEST_PREFIX = "contracts/delivery-slices/"
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
    r"""\btest\s*\(\s*(?P<quote>["'])(?P<title>.*?)(?P=quote)""",
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
        if line.startswith(">") or line.startswith("    ") or line.startswith("\t"):
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
    if path.startswith(DELIVERY_MANIFEST_PREFIX) and path.endswith((".yaml", ".yml")):
        return True
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


def _decorator_name(decorator: ast.expr) -> str:
    if isinstance(decorator, ast.Call):
        return _decorator_name(decorator.func)
    if isinstance(decorator, ast.Attribute):
        owner = _decorator_name(decorator.value)
        return f"{owner}.{decorator.attr}" if owner else decorator.attr
    if isinstance(decorator, ast.Name):
        return decorator.id
    return ""


def _is_runnable_python_test(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    blocked = {"pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail"}
    return not any(_decorator_name(decorator) in blocked for decorator in node.decorator_list)


def _python_test_selectors(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return set()

    selectors: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            and _is_runnable_python_test(node)
        ):
            selectors.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if (
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name.startswith("test")
                    and _is_runnable_python_test(child)
                ):
                    selectors.add(f"{node.name}::{child.name}")
    return selectors


def _playwright_test_titles(path: Path) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set()
    return {match.group("title") for match in PLAYWRIGHT_TEST_TITLE.finditer(source)}


def _react_route_attributes(source: str) -> list[str]:
    attributes: list[str] = []
    start_pattern = re.compile(r"<Route\b")
    position = 0
    while (start := start_pattern.search(source, position)) is not None:
        index = start.end()
        braces = 0
        quote: str | None = None
        escaped = False
        while index < len(source):
            character = source[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in {'"', "'", "`"}:
                quote = character
            elif character == "{":
                braces += 1
            elif character == "}" and braces:
                braces -= 1
            elif character == ">" and braces == 0:
                attributes.append(source[start.end() : index])
                index += 1
                break
            index += 1
        position = max(index, start.end())
    return attributes


def _frontend_page_routes(repo_root: Path) -> set[str] | None:
    runtime_app = repo_root / "apps/web/src/app/RuntimeApp.tsx"
    if not runtime_app.is_file():
        return None
    try:
        source = runtime_app.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    source = _strip_typescript_comments(source)
    route_literals: set[str] = set()
    for attributes in _react_route_attributes(source):
        if "RuntimeUnavailablePage" in attributes or "<Navigate" in attributes:
            continue
        path_match = ROUTE_LITERAL.search(attributes)
        if path_match is None:
            continue
        route = path_match.group("path")
        if "*" not in route:
            route_literals.add(route)

    routes = {route for route in route_literals if route.startswith("/")}
    routes.update(
        f"/app/{route}".replace("//", "/")
        for route in route_literals
        if route and not route.startswith("/")
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
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_table_name = any(
                isinstance(child, (ast.Assign, ast.AnnAssign))
                and (
                    any(
                        isinstance(target, ast.Name) and target.id == "__tablename__"
                        for target in child.targets
                    )
                    if isinstance(child, ast.Assign)
                    else isinstance(child.target, ast.Name) and child.target.id == "__tablename__"
                )
                for child in node.body
            )
            if has_table_name:
                names.add(node.name)
    return names


def _real_api_playwright_source_error(path: Path, relative_path: str) -> str | None:
    real_api_root = path.parent
    while real_api_root.name != "real-api" and real_api_root != real_api_root.parent:
        real_api_root = real_api_root.parent
    sources = [path]
    if real_api_root.name == "real-api":
        sources = sorted(
            {
                candidate
                for suffix in ("*.ts", "*.tsx")
                for candidate in real_api_root.rglob(suffix)
                if candidate.is_file()
            }
        )
    forbidden = (
        re.compile(r"\binstallRuntimeApi\b"),
        re.compile(r"\b(?:page|context)\s*\.\s*route\s*\("),
        re.compile(r"\brouteFromHAR\s*\("),
        re.compile(r"\bsetupServer\s*\("),
        re.compile(r"""(?:from\s*["']msw|require\s*\(\s*["']msw)"""),
        re.compile(r"\bserviceWorker\s*\.\s*register\s*\("),
    )
    for source_path in sources:
        try:
            source = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if any(pattern.search(source) for pattern in forbidden):
            return (
                "vertical slice Real API Playwright uses request interception or "
                f"test API fixtures: {relative_path}"
            )
    return None


def _strip_typescript_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    quote: str | None = None
    escaped = False
    while index < len(source):
        character = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if quote is not None:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character in {'"', "'", "`"}:
            quote = character
            output.append(character)
            index += 1
            continue
        if character == "/" and following == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            continue
        if character == "/" and following == "*":
            index += 2
            while index + 1 < len(source) and source[index : index + 2] != "*/":
                if source[index] in "\r\n":
                    output.append(source[index])
                index += 1
            index = min(index + 2, len(source))
            continue
        output.append(character)
        index += 1
    return "".join(output)


def _workflow_has_real_api_job(document: object) -> bool:
    if not isinstance(document, dict):
        return False
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        services = job.get("services")
        if not isinstance(services, dict) or not {"postgres", "redis"} <= set(services):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        commands = [
            step.get("run", "")
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("run"), str)
        ]
        command_source = "\n".join(commands)
        starts_api = re.search(r"\buvicorn\s+apps\.api\.main:app\b", command_source)
        migrates = re.search(r"\balembic\s+upgrade\s+head\b", command_source)
        runs_browser = re.search(r"\btest:e2e:real-api\b", command_source)
        runs_exact_selectors = re.search(
            r"\bpython\s+scripts/run_delivery_slice_tests\.py\b", command_source
        )
        if starts_api and migrates and runs_browser and runs_exact_selectors:
            return True
    return False


def _validate_real_api_playwright_harness(repo_root: Path) -> list[str]:
    errors: list[str] = []
    config = repo_root / REAL_API_PLAYWRIGHT_CONFIG
    if not config.is_file():
        errors.append(
            "vertical slice real API Playwright config is missing: " + REAL_API_PLAYWRIGHT_CONFIG
        )
    else:
        try:
            config_source = _strip_typescript_comments(config.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            config_source = ""
        config_requirements = (
            re.compile(r"""testDir\s*:\s*["']\./e2e/real-api["']"""),
            re.compile(r"""VITE_API_MODE\s*:\s*["']real["']"""),
            re.compile(r"""VITE_API_BASE_URL\s*:\s*["']/api/v2["']"""),
            re.compile(r"""VITE_REAL_API_PROXY_TARGET\s*:\s*["']http://127\.0\.0\.1:8000["']"""),
        )
        if not all(pattern.search(config_source) for pattern in config_requirements) or re.search(
            r"\bVITE_RUNTIME_CONTRACT_TEST\b", config_source
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
            workflow_document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            workflow_document = None
        if not _workflow_has_real_api_job(workflow_document):
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
        if not relative_path.startswith("tests/integration/") or test_path.suffix != ".py":
            errors.append(
                "vertical slice Backend tests must use tests/integration/**/*.py: " + relative_path
            )
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
    operations = _active_operations(repo_root)
    return set(operations) if operations is not None else None


def _active_operations(repo_root: Path) -> dict[str, tuple[str, str]] | None:
    contract_path = repo_root / "contracts/api-surface.openapi.yaml"
    if not contract_path.is_file():
        return None
    document = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    operations: dict[str, tuple[str, str]] = {}
    for api_path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if str(method).lower() not in OPENAPI_HTTP_METHODS:
                continue
            if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                operations[operation["operationId"]] = (str(method).upper(), str(api_path))
    return operations


def _closing_issue_numbers(body: str) -> set[int]:
    return {
        int(match.group("number"))
        for match in re.finditer(
            r"(?im)^\s*(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(?P<number>\d+)\s*$",
            _governance_markdown(body),
        )
    }


def _manifest_list(row: dict[str, object], field: str) -> list[str] | None:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        return None
    return [item.strip() for item in value]


def _validate_delivery_manifest(
    body: str,
    section: str,
    declared_fields: dict[str, list[str]],
    changed_files: set[str],
    repo_root: Path,
) -> list[str]:
    values = _review_field_values(section, DELIVERY_MANIFEST_FIELD)
    if len(values) != 1:
        return ["vertical slice section must contain exactly one Delivery manifest field"]
    manifest_values = _declared_values(values[0])
    if len(manifest_values) != 1:
        return ["vertical slice Delivery manifest must declare exactly one file"]
    relative_path = manifest_values[0]
    manifest_path = _safe_repo_file(repo_root, relative_path)
    if (
        manifest_path is None
        or not relative_path.startswith(DELIVERY_MANIFEST_PREFIX)
        or not relative_path.endswith((".yaml", ".yml"))
    ):
        return ["vertical slice declares invalid Delivery manifest path: " + relative_path]
    if relative_path not in changed_files:
        return ["vertical slice Delivery manifest must be changed by this pull request"]
    if not manifest_path.is_file():
        return ["vertical slice declares missing Delivery manifest file: " + relative_path]

    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        document = None
    if not isinstance(document, dict):
        return ["vertical slice Delivery manifest must be a YAML mapping"]

    errors: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("vertical slice Delivery manifest schema_version must equal 1")
    issue = document.get("issue")
    if not isinstance(issue, int) or issue <= 0:
        errors.append("vertical slice Delivery manifest issue must be a positive integer")
    else:
        if issue not in _closing_issue_numbers(body):
            errors.append("vertical slice Delivery manifest issue must match a Closes #<issue>")
        if not PurePosixPath(relative_path).stem.startswith(f"{issue}-"):
            errors.append("vertical slice Delivery manifest filename must start with its issue")

    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("vertical slice Delivery manifest must contain at least one row")
        return errors

    manifest_fields: dict[str, set[str]] = {
        "Page routes": set(),
        "Active operationIds": set(),
        "Formal facts": set(),
        "Backend tests": set(),
        "Real API Playwright": set(),
    }
    active_operations = _active_operations(repo_root) or {}
    for index, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, dict):
            errors.append(f"vertical slice Delivery manifest row {index} must be a mapping")
            continue
        page_route = raw_row.get("page_route")
        navigation_path = raw_row.get("navigation_path")
        if not isinstance(page_route, str) or PAGE_ROUTE.fullmatch(page_route) is None:
            errors.append(f"vertical slice Delivery manifest row {index} has invalid page_route")
        else:
            manifest_fields["Page routes"].add(page_route)
        if (
            not isinstance(navigation_path, str)
            or PAGE_ROUTE.fullmatch(navigation_path) is None
            or ":" in navigation_path
            or "*" in navigation_path
        ):
            errors.append(
                f"vertical slice Delivery manifest row {index} has invalid navigation_path"
            )

        for manifest_key, declaration_key in (
            ("formal_facts", "Formal facts"),
            ("backend_tests", "Backend tests"),
            ("real_api_playwright", "Real API Playwright"),
        ):
            row_values = _manifest_list(raw_row, manifest_key)
            if row_values is None:
                errors.append(
                    f"vertical slice Delivery manifest row {index} requires {manifest_key}"
                )
            else:
                manifest_fields[declaration_key].update(row_values)

        requests = raw_row.get("api_requests")
        if not isinstance(requests, list) or not requests:
            errors.append(f"vertical slice Delivery manifest row {index} requires api_requests")
            continue
        for request in requests:
            if not isinstance(request, dict):
                errors.append(
                    f"vertical slice Delivery manifest row {index} has invalid api_request"
                )
                continue
            operation_id = request.get("operation_id")
            method = request.get("method")
            api_path = request.get("path")
            if not all(isinstance(value, str) for value in (operation_id, method, api_path)):
                errors.append(
                    f"vertical slice Delivery manifest row {index} has invalid api_request"
                )
                continue
            manifest_fields["Active operationIds"].add(operation_id)
            expected = active_operations.get(operation_id)
            actual = (method.upper(), api_path)
            if expected != actual:
                errors.append(
                    "vertical slice Delivery manifest row "
                    f"{index} api_request does not match active OpenAPI: {operation_id}"
                )

        browser_tests = _manifest_list(raw_row, "real_api_playwright") or []
        browser_sources: list[str] = []
        for declared_test in browser_tests:
            test_relative_path = declared_test.partition("::")[0].strip()
            test_path = _safe_repo_file(repo_root, test_relative_path)
            if test_path is None or not test_path.is_file():
                continue
            try:
                browser_sources.append(
                    _strip_typescript_comments(test_path.read_text(encoding="utf-8"))
                )
            except (OSError, UnicodeError):
                continue
        combined_browser_source = "\n".join(browser_sources)
        if isinstance(navigation_path, str) and PAGE_ROUTE.fullmatch(navigation_path):
            goto_pattern = re.compile(
                r"""page\s*\.\s*goto\s*\(\s*["']""" + re.escape(navigation_path) + r"""["']"""
            )
            if goto_pattern.search(combined_browser_source) is None:
                errors.append(
                    "vertical slice Delivery manifest row "
                    f"{index} Playwright evidence does not navigate to navigation_path"
                )
        observation_calls = set(
            re.findall(
                r"\b(?:observeApiRequests|expectObservedApi)\b",
                combined_browser_source,
            )
        )
        if not {"observeApiRequests", "expectObservedApi"} <= observation_calls:
            errors.append(
                "vertical slice Delivery manifest row "
                f"{index} Playwright evidence must observe and assert real API requests"
            )
        if isinstance(requests, list):
            for request in requests:
                if not isinstance(request, dict):
                    continue
                method = request.get("method")
                api_path = request.get("path")
                if isinstance(method, str) and isinstance(api_path, str):
                    if not (
                        re.search(
                            rf"""(?:\bmethod\b|["']method["'])\s*:\s*["']{re.escape(method.upper())}["']""",
                            combined_browser_source,
                        )
                        and re.search(
                            rf"""(?:\bpath\b|["']path["'])\s*:\s*["']{re.escape(api_path)}["']""",
                            combined_browser_source,
                        )
                    ):
                        errors.append(
                            "vertical slice Delivery manifest row "
                            f"{index} Playwright evidence does not assert "
                            f"{method.upper()} {api_path}"
                        )

    for field, manifest_values_set in manifest_fields.items():
        declared_values_set = set(declared_fields[field])
        if manifest_values_set != declared_values_set:
            errors.append(
                f"vertical slice Delivery manifest {field} union does not match the PR declaration"
            )
    return errors


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
        return _validate_real_api_playwright_harness(resolved_root)

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
    if base_sha is not None:
        errors.extend(
            _validate_delivery_manifest(
                body,
                section,
                declared_fields,
                normalized_files,
                resolved_root,
            )
        )

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
