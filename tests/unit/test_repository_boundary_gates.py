from __future__ import annotations

import json
from pathlib import Path

from scripts.check_repository import (
    ROOT,
    check_cross_module_model_imports,
    check_python_size_limits,
    load_repository_governance_baseline,
    production_python_files,
)
from scripts.repository_governance import _find_cross_module_model_imports, _parse


def _baseline(path: Path, **overrides: object):
    payload: dict[str, object] = {
        "schema_version": 1,
        "cross_module_model_imports": [],
        "oversized_files": [],
        "oversized_functions": [],
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    errors: list[str] = []
    baseline = load_repository_governance_baseline(path, errors)
    assert errors == []
    assert baseline is not None
    return baseline


def _exception(**values: object) -> dict[str, object]:
    return {
        "owner": "area:api",
        "reason": "Existing orchestration boundary pending extraction.",
        "exit_issue": "#92",
        **values,
    }


def test_cross_module_model_gate_allows_exact_owned_exception(tmp_path: Path) -> None:
    source = tmp_path / "apps/api/artifacts/service.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from apps.api.artifacts.models import Artifact\n"
        "from apps.api.workflows.models import NodeRun\n",
        encoding="utf-8",
    )
    baseline = _baseline(
        tmp_path / "baseline.json",
        cross_module_model_imports=[
            _exception(
                source="apps/api/artifacts/service.py",
                target="apps.api.workflows.models",
                names=["NodeRun"],
            )
        ],
    )
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == []


def test_cross_module_model_gate_rejects_new_or_expanded_import(tmp_path: Path) -> None:
    source = tmp_path / "apps/api/artifacts/service.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from apps.api.workflows.models import NodeRun, WorkflowRun\n",
        encoding="utf-8",
    )
    baseline = _baseline(
        tmp_path / "baseline.json",
        cross_module_model_imports=[
            _exception(
                source="apps/api/artifacts/service.py",
                target="apps.api.workflows.models",
                names=["NodeRun"],
            )
        ],
    )
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == [
        "unauthorized cross-module ORM import: apps/api/artifacts/service.py -> "
        "apps.api.workflows.models [NodeRun, WorkflowRun]"
    ]


def test_cross_module_model_gate_resolves_relative_imports(tmp_path: Path) -> None:
    source = tmp_path / "apps/api/artifacts/service.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from ..workflows.models import NodeRun\n",
        encoding="utf-8",
    )
    baseline = _baseline(tmp_path / "baseline.json")
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == [
        "unauthorized cross-module ORM import: apps/api/artifacts/service.py -> "
        "apps.api.workflows.models [NodeRun]"
    ]


def test_cross_module_model_gate_rejects_package_level_model_aliases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps/api/artifacts/service.py"
    source.parent.mkdir(parents=True)
    (tmp_path / "apps/api/workflows").mkdir(parents=True)
    (tmp_path / "apps/api/workflows/models.py").write_text("", encoding="utf-8")
    (tmp_path / "apps/api/assets").mkdir(parents=True)
    (tmp_path / "apps/api/assets/project_models.py").write_text("", encoding="utf-8")
    source.write_text(
        "from apps.api.workflows import models as workflow_models\n"
        "from apps.api.assets import project_models\n",
        encoding="utf-8",
    )
    baseline = _baseline(tmp_path / "baseline.json")
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == [
        "unauthorized cross-module ORM import: apps/api/artifacts/service.py -> "
        "apps.api.assets.project_models [project_models]",
        "unauthorized cross-module ORM import: apps/api/artifacts/service.py -> "
        "apps.api.workflows.models [models]",
    ]


def test_cross_module_model_gate_rejects_relative_package_level_model_alias(
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps/api/artifacts/internal/service.py"
    source.parent.mkdir(parents=True)
    (tmp_path / "apps/api/workflows").mkdir(parents=True)
    (tmp_path / "apps/api/workflows/models.py").write_text("", encoding="utf-8")
    source.write_text(
        "from ...workflows import models as workflow_models\n",
        encoding="utf-8",
    )
    baseline = _baseline(tmp_path / "baseline.json")
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == [
        "unauthorized cross-module ORM import: apps/api/artifacts/internal/service.py -> "
        "apps.api.workflows.models [models]"
    ]


def test_package_level_non_orm_and_same_owner_model_imports_are_allowed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps/api/workflows/internal/service.py"
    source.parent.mkdir(parents=True)
    (tmp_path / "apps/api/workflows/models.py").write_text("", encoding="utf-8")
    source.write_text(
        "from apps.api.workflows import service\nfrom .. import models\n",
        encoding="utf-8",
    )
    baseline = _baseline(tmp_path / "baseline.json")
    errors: list[str] = []

    check_cross_module_model_imports([source], tmp_path, baseline, errors)

    assert errors == []


def test_parser_accepts_pep_695_type_alias_on_supported_or_fallback_python(
    tmp_path: Path,
) -> None:
    source = tmp_path / "module.py"
    source.write_text("type Identifier = str\nvalue: Identifier = 'ok'\n", encoding="utf-8")
    errors: list[str] = []

    tree = _parse(source, "module.py", errors)

    assert tree is not None
    assert errors == []


def test_parser_does_not_hide_non_pep_695_syntax_errors(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("type Identifier = str\ndef broken(\n", encoding="utf-8")
    errors: list[str] = []

    tree = _parse(source, "module.py", errors)

    assert tree is None
    assert len(errors) == 1
    assert errors[0].startswith("cannot parse Python source module.py:")


def test_parser_does_not_retry_when_first_error_is_not_a_type_alias(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("def broken(\ntype Identifier = str\n", encoding="utf-8")
    errors: list[str] = []

    tree = _parse(source, "module.py", errors)

    assert tree is None
    assert len(errors) == 1
    assert errors[0].startswith("cannot parse Python source module.py:")


def test_governance_baseline_requires_owner_reason_and_exit_issue(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cross_module_model_imports": [
                    {
                        "source": "apps/api/artifacts/service.py",
                        "target": "apps.api.workflows.models",
                        "names": ["NodeRun"],
                        "owner": "",
                        "reason": "",
                        "exit_issue": "later",
                    }
                ],
                "oversized_files": [],
                "oversized_functions": [],
            }
        ),
        encoding="utf-8",
    )
    errors: list[str] = []

    baseline = load_repository_governance_baseline(path, errors)

    assert baseline is None
    assert errors == [
        "invalid governance baseline cross_module_model_imports[0]: owner is required",
        "invalid governance baseline cross_module_model_imports[0]: reason is required",
        "invalid governance baseline cross_module_model_imports[0]: "
        "exit_issue must reference a GitHub issue",
    ]


def test_size_gate_reports_owned_exceptions_without_failing(tmp_path: Path, capsys) -> None:
    oversized_file = tmp_path / "apps/api/uploads/service.py"
    oversized_file.parent.mkdir(parents=True)
    oversized_file.write_text("\n".join(["value = 1"] * 401) + "\n", encoding="utf-8")
    long_function = tmp_path / "workers/task.py"
    long_function.parent.mkdir(parents=True)
    long_function.write_text(
        "def run():\n" + "".join("    value = 1\n" for _ in range(60)),
        encoding="utf-8",
    )
    baseline = _baseline(
        tmp_path / "baseline.json",
        oversized_files=[_exception(path="apps/api/uploads/service.py", line_count=401)],
        oversized_functions=[_exception(path="workers/task.py", qualname="run", line_count=61)],
    )
    errors: list[str] = []

    check_python_size_limits([oversized_file, long_function], tmp_path, baseline, errors)

    assert errors == []
    report = capsys.readouterr().err
    assert "oversized file: apps/api/uploads/service.py has 401 lines" in report
    assert "long function: workers/task.py::run has 61 lines" in report


def test_size_gate_rejects_unowned_trigger_and_owned_net_growth(tmp_path: Path) -> None:
    oversized_file = tmp_path / "apps/api/uploads/service.py"
    oversized_file.parent.mkdir(parents=True)
    oversized_file.write_text("\n".join(["value = 1"] * 402) + "\n", encoding="utf-8")
    new_long_function = tmp_path / "workers/new_task.py"
    new_long_function.parent.mkdir(parents=True)
    new_long_function.write_text(
        "def run():\n" + "".join("    value = 1\n" for _ in range(60)),
        encoding="utf-8",
    )
    baseline = _baseline(
        tmp_path / "baseline.json",
        oversized_files=[_exception(path="apps/api/uploads/service.py", line_count=401)],
    )
    errors: list[str] = []

    check_python_size_limits([oversized_file, new_long_function], tmp_path, baseline, errors)

    assert errors == [
        "oversized file grew beyond its owned baseline: "
        "apps/api/uploads/service.py has 402 lines (baseline 401)",
        "unowned long function: workers/new_task.py::run has 61 lines",
    ]


def test_live_size_baseline_is_exactly_three_files_and_twenty_two_functions(
    capsys,
) -> None:
    files = production_python_files(
        [*ROOT.joinpath("apps/api").rglob("*.py"), *ROOT.joinpath("workers").rglob("*.py")],
        ROOT,
    )
    errors: list[str] = []
    baseline = load_repository_governance_baseline(
        ROOT / "scripts/repository-governance-baseline.json", errors
    )
    assert baseline is not None

    check_python_size_limits(files, ROOT, baseline, errors)

    assert errors == []
    assert len(baseline.oversized_files) == 3
    assert len(baseline.oversized_functions) == 22
    report = capsys.readouterr().err
    assert report.count("warning: oversized file:") == 3
    assert report.count("warning: long function:") == 22


def test_live_orm_baseline_exactly_matches_detected_dependencies() -> None:
    files = production_python_files(
        [*ROOT.joinpath("apps/api").rglob("*.py"), *ROOT.joinpath("workers").rglob("*.py")],
        ROOT,
    )
    errors: list[str] = []
    baseline = load_repository_governance_baseline(
        ROOT / "scripts/repository-governance-baseline.json", errors
    )
    assert baseline is not None

    detected = _find_cross_module_model_imports(files, ROOT, errors)

    assert errors == []
    actual = {(item.source, item.target, item.names) for item in detected}
    expected = {(item.source, item.target, item.names) for item in baseline.model_imports}
    assert len(actual) == 48
    assert actual == expected
