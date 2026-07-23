from __future__ import annotations

from pathlib import Path

from scripts.check_pull_request_status import (
    parse_numstat,
    validate_review_declaration,
    validate_size_declaration,
    validate_status_declaration,
    validate_vertical_slice_declaration,
)

REQUIRED = "- [x] `status-update-required`: status changed"
NOT_REQUIRED = "- [x] `status-update-not-required`: status did not change"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
PENDING = "- [x] `subagent-review-pending`: review pending"
APPROVED = "- [x] `subagent-review-approved`: review approved"
PENDING_UNCHECKED = "- [ ] `subagent-review-pending`: review pending"
APPROVED_UNCHECKED = "- [ ] `subagent-review-approved`: review approved"
FULLWIDTH_COLON = "\uff1a"
SIZE_WITHIN = "- [x] `pr-size-within-limit`: within limit"
SIZE_MAP_REQUIRED = "- [x] `pr-size-review-map-required`: map required"
SIZE_WITHIN_UNCHECKED = "- [ ] `pr-size-within-limit`: within limit"
SIZE_MAP_UNCHECKED = "- [ ] `pr-size-review-map-required`: map required"
VERTICAL_REQUIRED = "- [x] `vertical-slice-required`: product slice"
VERTICAL_NOT_REQUIRED = "- [x] `vertical-slice-not-required`: internal-only change"
VERTICAL_REQUIRED_UNCHECKED = "- [ ] `vertical-slice-required`: product slice"
VERTICAL_NOT_REQUIRED_UNCHECKED = "- [ ] `vertical-slice-not-required`: internal-only change"


def review_section(
    declarations: str,
    *,
    base_sha: str = "",
    head_sha: str = "",
    extra_fields: str = "",
) -> str:
    return (
        "## 子智能体审查\n\n"
        f"{declarations}\n\n"
        f"Base SHA{FULLWIDTH_COLON}{base_sha}\n\n"
        f"Head SHA{FULLWIDTH_COLON}{head_sha}\n"
        f"{extra_fields}\n\n"
        "## CURRENT_STATUS新鲜度"
    )


def test_status_update_declaration_requires_current_status_change() -> None:
    errors = validate_status_declaration(REQUIRED, {"apps/api/main.py"})

    assert errors == ["PR declares status-update-required but does not change CURRENT_STATUS.md"]


def test_status_update_declaration_accepts_current_status_change() -> None:
    errors = validate_status_declaration(REQUIRED, {"CURRENT_STATUS.md"})

    assert errors == []


def test_no_status_update_declaration_rejects_current_status_change() -> None:
    errors = validate_status_declaration(NOT_REQUIRED, {"CURRENT_STATUS.md"})

    assert errors == ["PR changes CURRENT_STATUS.md but declares status-update-not-required"]


def test_status_declaration_requires_exactly_one_choice() -> None:
    assert validate_status_declaration("", set()) == [
        "PR must select exactly one CURRENT_STATUS freshness declaration"
    ]
    assert validate_status_declaration(f"{REQUIRED}\n{NOT_REQUIRED}", set()) == [
        "PR must select exactly one CURRENT_STATUS freshness declaration"
    ]


def vertical_section(declarations: str, fields: str = "") -> str:
    return f"## 纵向切片交付\n\n{declarations}\n\n{fields}\n\n## 子智能体审查"


def test_vertical_slice_declaration_is_required_for_current_prs() -> None:
    assert validate_vertical_slice_declaration(
        "legacy body", {"docs/README.md"}, required=True
    ) == ["PR must select exactly one vertical slice declaration"]


def test_vertical_slice_rejects_opt_out_for_real_production_boundaries() -> None:
    body = vertical_section(f"{VERTICAL_REQUIRED_UNCHECKED}\n{VERTICAL_NOT_REQUIRED}")
    paths = {
        "apps/api/main.py",
        "apps/api/assets/project_router.py",
        "apps/api/projects/router.py",
        "apps/api/node_execution/router.py",
        "apps/web/src/pages/HomePage.tsx",
        "apps/web/src/shared/api/client.ts",
        "contracts/api-surface.openapi.yaml",
        "contracts/delivery-slices/211-r1.yaml",
    }

    for path in paths:
        assert validate_vertical_slice_declaration(body, {path}, required=True) == [
            "PR changes a production delivery boundary but declares vertical-slice-not-required"
        ]


def test_vertical_slice_detects_nonstandard_router_file_from_source(tmp_path) -> None:
    route_file = tmp_path / "apps/api/custom/http.py"
    route_file.parent.mkdir(parents=True)
    route_file.write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n",
        encoding="utf-8",
    )
    body = vertical_section(f"{VERTICAL_REQUIRED_UNCHECKED}\n{VERTICAL_NOT_REQUIRED}")

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/custom/http.py"},
        required=True,
        repo_root=tmp_path,
    ) == ["PR changes a production delivery boundary but declares vertical-slice-not-required"]


def test_vertical_slice_requires_all_concrete_delivery_fields() -> None:
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: pending\n",
    )

    assert validate_vertical_slice_declaration(
        body, {"apps/api/artifacts/router.py"}, required=True
    ) == [
        "vertical slice field Backend tests must be concrete",
        "vertical slice section must contain exactly one Real API Playwright field",
    ]


def _write_vertical_slice_fixture(tmp_path) -> None:
    schema = tmp_path / "contracts/delivery-slice.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text(
        (Path(__file__).resolve().parents[2] / "contracts/delivery-slice.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    contract = tmp_path / "contracts/api-surface.openapi.yaml"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        "openapi: 3.1.0\n"
        "info: {title: test, version: 1.0.0}\n"
        "paths:\n"
        "  /projects:\n"
        "    get: {operationId: listProjects, responses: {'200': {description: ok}}}\n"
        "    post: {operationId: createProject, responses: {'200': {description: ok}}}\n",
        encoding="utf-8",
    )
    runtime_app = tmp_path / "apps/web/src/app/RuntimeApp.tsx"
    runtime_app.parent.mkdir(parents=True)
    runtime_app.write_text(
        '<Route element={<LoginPage />} path="/login" />\n'
        '<Route element={<AppShell />} path="/app">\n'
        '  <Route element={<ProjectsPage />} path="projects" />\n'
        '  <Route element={<NewProjectPage />} path="projects/new" />\n'
        "</Route>\n",
        encoding="utf-8",
    )
    models = tmp_path / "apps/api/projects/models.py"
    models.parent.mkdir(parents=True)
    models.write_text(
        "from apps.api.database import Base\n\n"
        'class Project(Base):\n    __tablename__ = "projects"\n',
        encoding="utf-8",
    )
    backend_test = tmp_path / "tests/integration/test_project_api.py"
    backend_test.parent.mkdir(parents=True)
    backend_test.write_text(
        "def test_create_project():\n    pass\n",
        encoding="utf-8",
    )
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.parent.mkdir(parents=True)
    browser_test.write_text(
        'import { test } from "@playwright/test";\n'
        'import { observeApiRequests, expectObservedApi } from "./support/observedApi";\n'
        'test("creates_project", async ({ page }) => {\n'
        "  const observed = observeApiRequests(page);\n"
        '  await page.goto("/app/projects");\n'
        '  await page.goto("/app/projects/new");\n'
        "  expectObservedApi(observed, [\n"
        '    { method: "GET", path: "/projects" },\n'
        '    { method: "POST", path: "/projects" },\n'
        "  ]);\n"
        "});\n",
        encoding="utf-8",
    )
    real_api_config = tmp_path / "apps/web/playwright.real-api.config.ts"
    real_api_config.write_text(
        'export default defineConfig({ testDir: "./e2e/real-api", '
        'use: { baseURL: "http://127.0.0.1:4177" }, '
        'webServer: { env: { VITE_API_MODE: "real", '
        'VITE_API_BASE_URL: "/api/v2", '
        'VITE_REAL_API_PROXY_TARGET: "http://127.0.0.1:8000" } } });\n',
        encoding="utf-8",
    )
    package_json = tmp_path / "apps/web/package.json"
    package_json.write_text(
        '{"scripts":{"test:e2e:real-api":'
        '"playwright test --config=playwright.real-api.config.ts"}}',
        encoding="utf-8",
    )
    real_api_workflow = tmp_path / ".github/workflows/r1-real-api.yml"
    real_api_workflow.parent.mkdir(parents=True)
    real_api_workflow.write_text(
        "on:\n"
        "  pull_request:\n"
        "    paths:\n"
        "      - contracts/delivery-slice.schema.json\n"
        "      - contracts/delivery-slices/**\n"
        "      - scripts/run_delivery_slice_tests.py\n"
        "      - tests/integration/**\n"
        "  push:\n"
        "    paths:\n"
        "      - contracts/delivery-slice.schema.json\n"
        "      - contracts/delivery-slices/**\n"
        "      - scripts/run_delivery_slice_tests.py\n"
        "      - tests/integration/**\n"
        "jobs:\n"
        "  real-api:\n"
        "    services:\n"
        "      postgres: {image: postgres:16}\n"
        "      redis: {image: redis:7}\n"
        "    steps:\n"
        "      - run: alembic upgrade head\n"
        "      - run: |\n"
        '          value="$(openssl rand -hex 32)"\n'
        '          echo "::add-mask::$value"\n'
        '          echo "SHANHAI_R1_ACCESS_CODE=$value" >> "$GITHUB_ENV"\n'
        "      - run: pnpm --filter @shanhaiedu/web exec playwright install chromium\n"
        "      - run: uvicorn apps.api.main:app &\n"
        "      - run: pnpm --filter @shanhaiedu/web test:e2e:real-api\n"
        "      - run: python scripts/run_delivery_slice_tests.py\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "contracts/delivery-slices/211-projects.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "schema_version: 1\n"
        "issue: 211\n"
        "rows:\n"
        "  - page_route: /app/projects\n"
        "    navigation_path: /app/projects\n"
        "    api_requests:\n"
        "      - operation_id: listProjects\n"
        "        method: GET\n"
        "        path: /projects\n"
        "    formal_facts: [Project]\n"
        "    backend_tests: [tests/integration/test_project_api.py::test_create_project]\n"
        "    real_api_playwright: "
        "[apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project]\n"
        "  - page_route: /app/projects/new\n"
        "    navigation_path: /app/projects/new\n"
        "    api_requests:\n"
        "      - operation_id: createProject\n"
        "        method: POST\n"
        "        path: /projects\n"
        "    formal_facts: [Project]\n"
        "    backend_tests: [tests/integration/test_project_api.py::test_create_project]\n"
        "    real_api_playwright: "
        "[apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project]\n",
        encoding="utf-8",
    )


def test_vertical_slice_accepts_complete_delivery_matrix(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n",
    )

    assert (
        validate_vertical_slice_declaration(
            body,
            {"contracts/api-surface.openapi.yaml"},
            required=True,
            repo_root=tmp_path,
        )
        == []
    )


def test_vertical_slice_accepts_changed_manifest_binding_one_slice(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = "Closes #211\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    assert (
        validate_vertical_slice_declaration(
            body,
            {
                "contracts/api-surface.openapi.yaml",
                "contracts/delivery-slices/211-projects.yaml",
            },
            required=True,
            repo_root=tmp_path,
            base_sha=BASE_SHA,
        )
        == []
    )


def test_vertical_slice_rejects_manifest_not_changed_or_bound_to_same_issue(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = "Closes #210\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"contracts/api-surface.openapi.yaml"},
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    ) == ["vertical slice Delivery manifest must be changed by this pull request"]

    errors = validate_vertical_slice_declaration(
        body,
        {
            "contracts/api-surface.openapi.yaml",
            "contracts/delivery-slices/211-projects.yaml",
        },
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    )
    assert "vertical slice Delivery manifest issue must match a Closes #<issue>" in errors


def test_vertical_slice_rejects_manifest_union_and_openapi_mismatch(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    manifest = tmp_path / "contracts/delivery-slices/211-projects.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("method: GET", "method: DELETE")
        .replace("page_route: /app/projects/new", "page_route: /app/projects"),
        encoding="utf-8",
    )
    body = "Closes #211\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    errors = validate_vertical_slice_declaration(
        body,
        {
            "contracts/api-surface.openapi.yaml",
            "contracts/delivery-slices/211-projects.yaml",
        },
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    )

    assert (
        "vertical slice Delivery manifest row 1 api_request does not match "
        "active OpenAPI: listProjects"
    ) in errors
    assert (
        "vertical slice Delivery manifest Page routes union does not match the PR declaration"
    ) in errors


def test_vertical_slice_rejects_manifest_schema_extra_properties(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    manifest = tmp_path / "contracts/delivery-slices/211-projects.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("issue: 211\n", "issue: 211\nunexpected_root: true\n")
        .replace(
            "  - page_route: /app/projects\n",
            "  - page_route: /app/projects\n    unexpected_row: true\n",
            1,
        ),
        encoding="utf-8",
    )
    body = "Closes #211\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    errors = validate_vertical_slice_declaration(
        body,
        {
            "contracts/api-surface.openapi.yaml",
            "contracts/delivery-slices/211-projects.yaml",
        },
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    )

    assert any(
        error.startswith("vertical slice Delivery manifest violates its JSON Schema")
        for error in errors
    )


def test_vertical_slice_rejects_navigation_path_mismatch(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    manifest = tmp_path / "contracts/delivery-slices/211-projects.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "    navigation_path: /app/projects\n",
            "    navigation_path: /app/projects/new\n",
            1,
        ),
        encoding="utf-8",
    )
    body = "Closes #211\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    errors = validate_vertical_slice_declaration(
        body,
        {
            "contracts/api-surface.openapi.yaml",
            "contracts/delivery-slices/211-projects.yaml",
        },
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    )

    assert (
        "vertical slice Delivery manifest row 1 navigation_path does not match page_route"
    ) in errors


def test_vertical_slice_checks_only_selected_playwright_test_body(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.write_text(
        'import { test } from "@playwright/test";\n'
        "function unusedEvidence(page: any) {\n"
        "  const observed = observeApiRequests(page);\n"
        '  page.goto("/app/projects");\n'
        '  page.goto("/app/projects/new");\n'
        "  expectObservedApi(observed, [\n"
        '    { method: "GET", path: "/projects" },\n'
        '    { method: "POST", path: "/projects" },\n'
        "  ]);\n"
        "}\n"
        'test("creates_project", async () => {});\n',
        encoding="utf-8",
    )
    body = "Closes #211\n\n" + vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project`\n"
        "Delivery manifest: contracts/delivery-slices/211-projects.yaml\n",
    )

    errors = validate_vertical_slice_declaration(
        body,
        {
            "contracts/api-surface.openapi.yaml",
            "contracts/delivery-slices/211-projects.yaml",
        },
        required=True,
        repo_root=tmp_path,
        base_sha=BASE_SHA,
    )

    assert any("does not navigate to navigation_path" in error for error in errors)
    assert any("must observe and assert real API requests" in error for error in errors)
    assert any("does not assert GET /projects" in error for error in errors)
    assert any("does not assert POST /projects" in error for error in errors)


def test_vertical_slice_rejects_unknown_operation_and_missing_test_files(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: `fakeOperation`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/missing.py::test_missing`\n"
        "Real API Playwright: `apps/web/e2e/real-api/missing.spec.ts::missing`\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares unknown active operationIds: fakeOperation",
        "vertical slice declares missing Backend tests file: tests/integration/missing.py",
        "vertical slice declares missing Real API Playwright file: "
        "apps/web/e2e/real-api/missing.spec.ts",
    ]


def test_vertical_slice_rejects_empty_delimited_fields(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: , ; \N{FULLWIDTH COMMA}\n"
        "Active operationIds: , ; \N{FULLWIDTH COMMA}\n"
        "Formal facts: , ; \N{FULLWIDTH COMMA}\n"
        "Backend tests: , ; \N{FULLWIDTH COMMA}\n"
        "Real API Playwright: , ; \N{FULLWIDTH COMMA}\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"contracts/api-surface.openapi.yaml"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice field Page routes must declare at least one value",
        "vertical slice field Active operationIds must declare at least one value",
        "vertical slice field Formal facts must declare at least one value",
        "vertical slice field Backend tests must declare at least one value",
        "vertical slice field Real API Playwright must declare at least one value",
    ]


def test_vertical_slice_rejects_invalid_page_route_and_operation_id(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: projects, /app/projects\n"
        "Active operationIds: listProjects, invalid operation\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"contracts/api-surface.openapi.yaml"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares invalid Page routes: projects",
        "vertical slice declares invalid active operationIds: invalid operation",
    ]


def test_vertical_slice_rejects_page_route_missing_from_runtime_router(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/login\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/app/RuntimeApp.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares Page routes absent from RuntimeApp: /app/login"]


def test_vertical_slice_rejects_invalid_formal_fact_name(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project, anything goes\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares invalid Formal facts: anything goes"]


def test_vertical_slice_rejects_formal_fact_missing_from_runtime_models(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project, Banana\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares Formal facts absent from persisted model classes: Banana"]


def test_vertical_slice_rejects_service_class_as_formal_fact(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    service = tmp_path / "apps/api/projects/service.py"
    service.write_text("class ProjectService:\n    pass\n", encoding="utf-8")
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: ProjectService\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares Formal facts absent from persisted model classes: ProjectService"
    ]


def test_vertical_slice_rejects_pydantic_class_in_models_module_as_formal_fact(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    models = tmp_path / "apps/api/model_gateway/models.py"
    models.parent.mkdir(parents=True)
    models.write_text(
        "from pydantic import BaseModel\n\n"
        "class Box(BaseModel):\n"
        '    __tablename__ = "boxes"\n'
        "    value: str\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Box\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares Formal facts absent from persisted model classes: Box"]


def test_vertical_slice_rejects_nested_database_model_as_formal_fact(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    models = tmp_path / "apps/api/projects/models.py"
    models.write_text(
        "from apps.api.database import Base\n\n"
        "def build_model():\n"
        "    class HiddenProject(Base):\n"
        '        __tablename__ = "hidden_projects"\n'
        "    return HiddenProject\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: HiddenProject\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares Formal facts absent from persisted model classes: HiddenProject"]


def test_vertical_slice_ignores_declarations_inside_fenced_code(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = (
        "## 说明\n\n"
        "```markdown\n"
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}\n"
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n"
        "```\n"
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["PR must select exactly one vertical slice declaration"]


def test_vertical_slice_ignores_tab_indented_markdown_code(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = f"\t## 纵向切片交付\n\t{VERTICAL_REQUIRED}\n\tPage routes: /app/projects\n"

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["PR must select exactly one vertical slice declaration"]


def test_vertical_slice_requires_declaration_inside_exact_section(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = (
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}\n"
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n"
        "\n## 说明\n"
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["PR must contain exactly one vertical slice delivery section"]


def test_vertical_slice_ignores_operation_id_inside_path_extension(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    contract = tmp_path / "contracts/api-surface.openapi.yaml"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(
            "  /projects:\n",
            "  /projects:\n    x-test-metadata:\n      operationId: fakeOperation\n",
        ),
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: fakeOperation\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"contracts/api-surface.openapi.yaml"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares unknown active operationIds: fakeOperation"]


def test_vertical_slice_rejects_repository_escape_in_test_path(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    outside = tmp_path.parent / "outside_test.py"
    outside.write_text("def test_outside():\n    pass\n", encoding="utf-8")
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: ../outside_test.py::test_outside\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares invalid Backend tests path: ../outside_test.py"]


def test_vertical_slice_rejects_wrong_test_kind_and_missing_selectors(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    wrong_backend = tmp_path / "docs/test_project_api.py"
    wrong_backend.parent.mkdir(parents=True)
    wrong_backend.write_text("def test_create_project():\n    pass\n", encoding="utf-8")
    wrong_browser = tmp_path / "apps/web/src/project.spec.ts"
    wrong_browser.parent.mkdir(parents=True, exist_ok=True)
    wrong_browser.write_text(
        'import { test } from "@playwright/test";\ntest("creates_project", async () => {});\n',
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: docs/test_project_api.py\n"
        "Real API Playwright: apps/web/src/project.spec.ts\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice Backend tests must use tests/integration/**/*.py: docs/test_project_api.py",
        "vertical slice Backend tests must include an exact ::test selector: "
        "docs/test_project_api.py",
        "vertical slice Real API Playwright must use "
        "apps/web/e2e/real-api/**/*.spec.ts or .spec.tsx: "
        "apps/web/src/project.spec.ts",
        "vertical slice Real API Playwright must include an exact ::test selector: "
        "apps/web/src/project.spec.ts",
    ]


def test_vertical_slice_rejects_missing_python_and_playwright_test_symbols(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_missing\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::missing_flow\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares missing Backend tests selector: "
        "tests/integration/test_project_api.py::test_missing",
        "vertical slice declares missing Real API Playwright selector: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::missing_flow",
    ]


def test_vertical_slice_rejects_module_skipped_python_selector(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    backend_test = tmp_path / "tests/integration/test_project_api.py"
    backend_test.write_text(
        "import pytest\n\n"
        'pytestmark = pytest.mark.skip(reason="not executable")\n\n'
        "def test_create_project():\n"
        "    pass\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares missing Backend tests selector: "
        "tests/integration/test_project_api.py::test_create_project"
    ]


def test_vertical_slice_rejects_class_xfailed_python_selector(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    backend_test = tmp_path / "tests/integration/test_project_api.py"
    backend_test.write_text(
        "import pytest\n\n"
        '@pytest.mark.xfail(reason="not executable")\n'
        "class TestProjects:\n"
        "    def test_create_project(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::TestProjects::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares missing Backend tests selector: "
        "tests/integration/test_project_api.py::TestProjects::test_create_project"
    ]


def test_vertical_slice_rejects_intercepted_playwright_as_real_api_evidence(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.write_text(
        'import { test } from "@playwright/test";\n'
        'import { installRuntimeApi } from "../runtime/support/runtimeApi";\n'
        'test("creates_project", async ({ page }) => { await installRuntimeApi(page); });\n',
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice Real API Playwright uses request interception or test API fixtures: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    ]


def test_vertical_slice_rejects_skipped_playwright_selector(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.write_text(
        'import { test } from "@playwright/test";\ntest.skip("creates_project", async () => {});\n',
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares missing Real API Playwright selector: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project"
    ]


def test_vertical_slice_rejects_interception_in_imported_playwright_helper(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.write_text(
        'import { installApi } from "./support/api";\n'
        'import { test } from "@playwright/test";\n'
        'test("creates_project", async ({ page }) => installApi(page));\n',
        encoding="utf-8",
    )
    helper = browser_test.parent / "support/api.ts"
    helper.parent.mkdir()
    helper.write_text(
        "export async function installApi(page: { route: Function }) {\n"
        '  await page.route("**/api/**", () => undefined);\n'
        "}\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice Real API Playwright uses request interception or "
        "test API fixtures: apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    ]


def test_vertical_slice_rejects_computed_interception_in_external_js_helper(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    browser_test = tmp_path / "apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    browser_test.write_text(
        'import { installApi } from "../support/external-api.mjs";\n'
        'import { test } from "@playwright/test";\n'
        'test("creates_project", async ({ page }) => installApi(page));\n',
        encoding="utf-8",
    )
    helper = tmp_path / "apps/web/e2e/support/external-api.mjs"
    helper.parent.mkdir(parents=True)
    helper.write_text(
        "export async function installApi(browserPage) {\n"
        '  await browserPage["route"]("**/api/**", () => undefined);\n'
        "}\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice Real API Playwright uses request interception or "
        "test API fixtures: apps/web/e2e/real-api/r1-teacher-flow.spec.ts"
    ]


def test_vertical_slice_requires_real_api_playwright_harness(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    (tmp_path / "apps/web/playwright.real-api.config.ts").unlink()
    (tmp_path / "apps/web/package.json").write_text('{"scripts":{}}', encoding="utf-8")
    (tmp_path / ".github/workflows/r1-real-api.yml").unlink()
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice real API Playwright config is missing: "
        "apps/web/playwright.real-api.config.ts",
        "vertical slice real API Playwright package script is missing: test:e2e:real-api",
        "vertical slice real API Playwright CI workflow is missing: "
        ".github/workflows/r1-real-api.yml",
    ]


def test_vertical_slice_rejects_comment_only_real_api_harness(tmp_path: Path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    config = tmp_path / "apps/web/playwright.real-api.config.ts"
    config.write_text(
        'const unused = defineConfig({ testDir: "./e2e/real-api", '
        'webServer: { env: { VITE_API_MODE: "real", '
        'VITE_API_BASE_URL: "/api/v2", '
        'VITE_REAL_API_PROXY_TARGET: "http://127.0.0.1:8000" } } });\n'
        "export default {};\n",
        encoding="utf-8",
    )
    workflow = tmp_path / ".github/workflows/r1-real-api.yml"
    workflow.write_text(
        "jobs:\n"
        "  real-api:\n"
        "    steps:\n"
        "      - run: echo postgres redis apps.api.main:app test:e2e:real-api\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice real API Playwright config does not enforce the "
        "real-api directory and real mode",
        "vertical slice real API Playwright CI workflow must start "
        "PostgreSQL, Redis and FastAPI and run test:e2e:real-api",
    ]


def test_vertical_slice_requires_semantic_workflow_commands_and_triggers(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    workflow = tmp_path / ".github/workflows/r1-real-api.yml"
    valid_source = workflow.read_text(encoding="utf-8")
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )
    invalid_variants = (
        valid_source.replace(
            "pnpm --filter @shanhaiedu/web exec playwright install chromium",
            "echo playwright install chromium",
        ),
        valid_source.replace('echo "::add-mask::$value"\n', ""),
        valid_source.replace("      - tests/integration/**\n", "", 1),
    )

    for invalid_source in invalid_variants:
        workflow.write_text(invalid_source, encoding="utf-8")
        errors = validate_vertical_slice_declaration(
            body,
            {"apps/web/src/pages/ProjectsPage.tsx"},
            required=True,
            repo_root=tmp_path,
        )
        assert (
            "vertical slice real API Playwright CI workflow must start "
            "PostgreSQL, Redis and FastAPI and run test:e2e:real-api"
        ) in errors


def test_vertical_slice_rejects_commented_or_unavailable_runtime_routes(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    runtime_app = tmp_path / "apps/web/src/app/RuntimeApp.tsx"
    runtime_app.write_text(
        '<Route path="/app">\n'
        '  {/* <Route element={<ProjectsPage />} path="fake" /> */}\n'
        '  <Route element={<ProjectsPage />} path="projects" />\n'
        '  <Route element={<RuntimeUnavailablePage />} path="creation/*" />\n'
        "</Route>\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/fake, /app/creation/*\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/pages/ProjectsPage.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == ["vertical slice declares Page routes absent from RuntimeApp: /app/creation/*, /app/fake"]


def test_vertical_slice_rejects_string_redirect_and_elementless_routes(
    tmp_path: Path,
) -> None:
    _write_vertical_slice_fixture(tmp_path)
    runtime_app = tmp_path / "apps/web/src/app/RuntimeApp.tsx"
    runtime_app.write_text(
        "const example = '<Route element={<Fake />} path=\"fake-string\" />';\n"
        '<Route element={<AppShell />} path="/app">\n'
        '  <Route path="elementless" />\n'
        '  <Route path="redirect"><Navigate to="/app" /></Route>\n'
        '  <Route Component={ProjectsPage} path="good" />\n'
        "</Route>\n",
        encoding="utf-8",
    )
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/fake-string, /app/elementless, /app/redirect, /app/good\n"
        "Active operationIds: listProjects\n"
        "Formal facts: Project\n"
        "Backend tests: tests/integration/test_project_api.py::test_create_project\n"
        "Real API Playwright: "
        "apps/web/e2e/real-api/r1-teacher-flow.spec.ts::creates_project\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/web/src/app/RuntimeApp.tsx"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares Page routes absent from RuntimeApp: "
        "/app/elementless, /app/fake-string, /app/redirect"
    ]


def test_pull_request_template_contains_vertical_slice_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative_path in (
        ".github/pull_request_template.md",
        "docs/frontend/templates/pull-request-template.md",
    ):
        template = (root / relative_path).read_text(encoding="utf-8")

        assert "## 纵向切片交付" in template
        assert "`vertical-slice-required`" in template
        assert "`vertical-slice-not-required`" in template
        for label in (
            "Page routes",
            "Active operationIds",
            "Formal facts",
            "Backend tests",
            "Real API Playwright",
            "Delivery manifest",
        ):
            assert f"{label}\N{FULLWIDTH COLON}" in template


def test_vertical_slice_opt_out_accepts_non_boundary_change() -> None:
    body = vertical_section(f"{VERTICAL_REQUIRED_UNCHECKED}\n{VERTICAL_NOT_REQUIRED}")

    assert (
        validate_vertical_slice_declaration(
            body, {"docs/governance/DELIVERY_ROADMAP.md"}, required=True
        )
        == []
    )


def test_vertical_slice_opt_out_still_requires_repository_real_api_harness(
    tmp_path: Path,
) -> None:
    body = vertical_section(f"{VERTICAL_REQUIRED_UNCHECKED}\n{VERTICAL_NOT_REQUIRED}")

    assert validate_vertical_slice_declaration(
        body,
        {"docs/governance/DELIVERY_ROADMAP.md"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice real API Playwright config is missing: "
        "apps/web/playwright.real-api.config.ts",
        "vertical slice real API Playwright package script is missing: test:e2e:real-api",
        "vertical slice real API Playwright CI workflow is missing: "
        ".github/workflows/r1-real-api.yml",
    ]


def test_review_declaration_keeps_legacy_pr_body_compatible() -> None:
    assert validate_review_declaration("legacy PR body", BASE_SHA, HEAD_SHA) == []


def test_review_declaration_requires_exactly_one_choice_when_present() -> None:
    assert validate_review_declaration(
        review_section(f"{PENDING_UNCHECKED}\n{APPROVED_UNCHECKED}"), BASE_SHA, HEAD_SHA
    ) == ["PR must select exactly one subagent review declaration"]
    assert validate_review_declaration(
        review_section(f"{PENDING}\n{APPROVED}"), BASE_SHA, HEAD_SHA
    ) == ["PR must select exactly one subagent review declaration"]


def test_pending_review_declaration_allows_empty_sha_fields() -> None:
    body = review_section(f"{PENDING}\n{APPROVED_UNCHECKED}")

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == []


def test_approved_review_declaration_requires_full_sha_fields() -> None:
    body = review_section(
        f"{PENDING_UNCHECKED}\n{APPROVED}",
        base_sha="1234567",
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == [
        "subagent-review-approved requires a full 40-character Base SHA",
        "subagent-review-approved requires a full 40-character Head SHA",
    ]


def test_approved_review_declaration_requires_matching_sha_fields() -> None:
    body = review_section(
        f"{PENDING_UNCHECKED}\n{APPROVED}",
        base_sha="3" * 40,
        head_sha="4" * 40,
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == [
        "subagent review Base SHA does not match the pull request base SHA",
        "subagent review Head SHA does not match the pull request head SHA",
    ]


def test_approved_review_declaration_accepts_exact_sha_fields() -> None:
    body = review_section(
        f"{PENDING_UNCHECKED}\n{APPROVED}",
        base_sha=f"`{BASE_SHA}`",
        head_sha=f"`{HEAD_SHA}`",
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == []


def test_review_declaration_requires_block_for_current_prs() -> None:
    assert validate_review_declaration(
        "PR body without review block",
        BASE_SHA,
        HEAD_SHA,
        required=True,
    ) == ["PR must contain exactly one subagent review section"]


def test_review_declaration_rejects_pending_for_ready_pr() -> None:
    body = review_section(f"{PENDING}\n{APPROVED_UNCHECKED}")

    assert validate_review_declaration(
        body,
        BASE_SHA,
        HEAD_SHA,
        required=True,
        is_draft=False,
    ) == ["non-draft PR must select subagent-review-approved"]


def test_review_declaration_rejects_duplicate_sha_fields() -> None:
    body = review_section(
        f"{PENDING_UNCHECKED}\n{APPROVED}",
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        extra_fields=f"\nBase SHA{FULLWIDTH_COLON}{'3' * 40}",
    )

    assert validate_review_declaration(
        body,
        BASE_SHA,
        HEAD_SHA,
        required=True,
        is_draft=False,
    ) == ["subagent review section must contain exactly one Base SHA field"]


def test_review_declaration_rejects_duplicate_review_sections() -> None:
    section = review_section(f"{PENDING}\n{APPROVED_UNCHECKED}")

    assert validate_review_declaration(
        f"{section}\n\n{section}",
        BASE_SHA,
        HEAD_SHA,
        required=True,
    ) == ["PR must contain exactly one subagent review section"]


def test_size_declaration_keeps_legacy_pr_body_compatible() -> None:
    assert validate_size_declaration("legacy PR body", 50, 2000, 0) == []


def test_size_declaration_requires_block_for_current_prs() -> None:
    assert validate_size_declaration("PR body without size block", 1, 1, 0, required=True) == [
        "PR must select exactly one pull request size declaration"
    ]


def test_size_declaration_requires_exactly_one_choice_when_present() -> None:
    assert validate_size_declaration(f"{SIZE_WITHIN_UNCHECKED}\n{SIZE_MAP_UNCHECKED}", 1, 1, 0) == [
        "PR must select exactly one pull request size declaration"
    ]
    assert validate_size_declaration(f"{SIZE_WITHIN}\n{SIZE_MAP_REQUIRED}", 1, 1, 0) == [
        "PR must select exactly one pull request size declaration"
    ]


def test_size_declaration_requires_review_map_above_file_limit() -> None:
    assert validate_size_declaration(f"{SIZE_WITHIN}\n{SIZE_MAP_UNCHECKED}", 21, 100, 0) == [
        "PR exceeds the raw size trigger but does not require a review map"
    ]


def test_size_declaration_requires_review_map_above_net_line_limit() -> None:
    assert validate_size_declaration(f"{SIZE_WITHIN}\n{SIZE_MAP_UNCHECKED}", 10, 1001, 200) == [
        "PR exceeds the raw size trigger but does not require a review map"
    ]


def test_size_declaration_accepts_review_map_above_raw_limit() -> None:
    assert (
        validate_size_declaration(f"{SIZE_WITHIN_UNCHECKED}\n{SIZE_MAP_REQUIRED}", 51, 1666, 471)
        == []
    )


def test_size_declaration_rejects_unneeded_review_map_claim() -> None:
    assert validate_size_declaration(
        f"{SIZE_WITHIN_UNCHECKED}\n{SIZE_MAP_REQUIRED}", 20, 900, 100
    ) == ["PR declares a required review map but does not exceed the raw size trigger"]


def test_size_declaration_requires_review_map_for_binary_diff() -> None:
    assert validate_size_declaration(
        f"{SIZE_WITHIN}\n{SIZE_MAP_UNCHECKED}",
        1,
        0,
        0,
        binary_file_count=1,
        required=True,
    ) == ["PR exceeds the raw size trigger but does not require a review map"]


def test_size_declaration_accepts_pure_rename_within_limit() -> None:
    assert (
        validate_size_declaration(
            f"{SIZE_WITHIN}\n{SIZE_MAP_UNCHECKED}",
            1,
            0,
            0,
            binary_file_count=0,
            required=True,
        )
        == []
    )


def test_parse_numstat_counts_binary_and_preserves_text_rename() -> None:
    output = "4\t1\tmodule.py\n-\t-\tasset.zip\n0\t0\told.py => new.py\n"

    assert parse_numstat(output) == (4, 1, 1)
