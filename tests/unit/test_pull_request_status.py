from __future__ import annotations

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
        "apps/api/projects/router.py",
        "apps/api/node_execution/router.py",
        "apps/web/src/pages/HomePage.tsx",
        "apps/web/src/shared/api/client.ts",
        "contracts/api-surface.openapi.yaml",
    }

    for path in paths:
        assert validate_vertical_slice_declaration(body, {path}, required=True) == [
            "PR changes a production delivery boundary but declares vertical-slice-not-required"
        ]


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
    contract = tmp_path / "contracts/api-surface.openapi.yaml"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        "openapi: 3.1.0\n"
        "info: {title: test, version: 1.0.0}\n"
        "paths:\n"
        "  /projects:\n"
        "    get: {operationId: listProjects, responses: {'200': {description: ok}}}\n"
        "    post: {operationId: createProject, responses: {'200': {description: ok}}}\n",
        encoding="utf-8",
    )
    backend_test = tmp_path / "tests/integration/test_project_api.py"
    backend_test.parent.mkdir(parents=True)
    backend_test.write_text("", encoding="utf-8")
    browser_test = tmp_path / "apps/web/e2e/r1-teacher-flow.spec.ts"
    browser_test.parent.mkdir(parents=True)
    browser_test.write_text("", encoding="utf-8")


def test_vertical_slice_accepts_complete_delivery_matrix(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects, /app/projects/new\n"
        "Active operationIds: `listProjects`, `createProject`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/test_project_api.py::test_create_project`\n"
        "Real API Playwright: "
        "`apps/web/e2e/r1-teacher-flow.spec.ts::creates_project`\n",
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


def test_vertical_slice_rejects_unknown_operation_and_missing_test_files(tmp_path) -> None:
    _write_vertical_slice_fixture(tmp_path)
    body = vertical_section(
        f"{VERTICAL_REQUIRED}\n{VERTICAL_NOT_REQUIRED_UNCHECKED}",
        "Page routes: /app/projects\n"
        "Active operationIds: `fakeOperation`\n"
        "Formal facts: Project\n"
        "Backend tests: `tests/integration/missing.py::test_missing`\n"
        "Real API Playwright: `apps/web/e2e/missing.spec.ts::missing`\n",
    )

    assert validate_vertical_slice_declaration(
        body,
        {"apps/api/projects/router.py"},
        required=True,
        repo_root=tmp_path,
    ) == [
        "vertical slice declares unknown active operationIds: fakeOperation",
        "vertical slice declares missing Backend tests file: tests/integration/missing.py",
        "vertical slice declares missing Real API Playwright file: apps/web/e2e/missing.spec.ts",
    ]


def test_vertical_slice_opt_out_accepts_non_boundary_change() -> None:
    body = vertical_section(f"{VERTICAL_REQUIRED_UNCHECKED}\n{VERTICAL_NOT_REQUIRED}")

    assert (
        validate_vertical_slice_declaration(
            body, {"docs/governance/DELIVERY_ROADMAP.md"}, required=True
        )
        == []
    )


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
