from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from apps.api.node_execution.contracts import NodeExecutionError
from apps.api.node_execution.materials import collect_upstream_artifacts
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext

PROJECT_ID = UUID("10000000-0000-4000-8000-000000000001")
LESSON_UNIT_ID = UUID("10000000-0000-4000-8000-000000000002")
VERSION_ID = UUID("10000000-0000-4000-8000-000000000003")


class ArtifactPortStub:
    def __init__(self, values: dict[str, tuple[ArtifactContextVersion, ...]]) -> None:
        self.values = values

    def list_context_versions(
        self, execution: WorkflowExecutionContext, source: str
    ) -> tuple[ArtifactContextVersion, ...]:
        return self.values.get(source, ())


def execution() -> WorkflowExecutionContext:
    return WorkflowExecutionContext(
        organization_id=UUID("10000000-0000-4000-8000-000000000010"),
        project_id=PROJECT_ID,
        workflow_run_id=UUID("10000000-0000-4000-8000-000000000011"),
        node_run_id=UUID("10000000-0000-4000-8000-000000000012"),
        content_release_id=UUID("10000000-0000-4000-8000-000000000013"),
        workflow_definition_version_id=UUID("10000000-0000-4000-8000-000000000014"),
        node_key="intro.generate_options",
        branch_key="intro_options",
        lesson_key="lesson-01",
        lesson_unit_id=LESSON_UNIT_ID,
        status="ready",
    )


def source() -> ArtifactContextVersion:
    return ArtifactContextVersion(
        project_id=PROJECT_ID,
        lesson_unit_id=LESSON_UNIT_ID,
        artifact_version_id=VERSION_ID,
        contract_ref="artifact:intro_option_set_source",
        artifact_type="intro_option_set",
        content={"option_set_key": "existing"},
        content_hash="a" * 64,
    )


def test_optional_artifact_input_may_be_absent_or_resolve_exactly_once() -> None:
    binding = {
        "input_contract_refs": ["artifact:intro_option_set_source"],
        "optional_input_contract_refs": ["artifact:intro_option_set_source"],
    }

    assert collect_upstream_artifacts(ArtifactPortStub({}), execution(), binding) == {}
    assert collect_upstream_artifacts(
        ArtifactPortStub({"artifact:intro_option_set_source": (source(),)}),
        execution(),
        binding,
    ) == {"artifact:intro_option_set_source": source()}


def test_required_artifact_input_cannot_be_absent() -> None:
    with pytest.raises(NodeExecutionError) as caught:
        collect_upstream_artifacts(
            ArtifactPortStub({}),
            execution(),
            {"input_contract_refs": ["artifact:intro_option_set_source"]},
        )

    assert caught.value.code == "NODE_EXECUTION_INPUT_CONTRACT_MISSING"


def test_artifact_input_cannot_resolve_to_multiple_versions() -> None:
    with pytest.raises(NodeExecutionError) as caught:
        collect_upstream_artifacts(
            ArtifactPortStub({"artifact:intro_option_set_source": (source(), source())}),
            execution(),
            {
                "input_contract_refs": ["artifact:intro_option_set_source"],
                "optional_input_contract_refs": ["artifact:intro_option_set_source"],
            },
        )

    assert caught.value.code == "NODE_EXECUTION_INPUT_CONTRACT_AMBIGUOUS"


def test_optional_inputs_must_be_a_subset_of_declared_inputs() -> None:
    with pytest.raises(NodeExecutionError) as caught:
        collect_upstream_artifacts(
            ArtifactPortStub({}),
            execution(),
            {
                "input_contract_refs": ["approval:lesson_division"],
                "optional_input_contract_refs": ["artifact:intro_option_set_source"],
            },
        )

    assert caught.value.code == "NODE_EXECUTION_OPTIONAL_INPUT_INVALID"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", UUID("20000000-0000-4000-8000-000000000001")),
        ("lesson_unit_id", UUID("20000000-0000-4000-8000-000000000002")),
        ("contract_ref", "artifact:foreign"),
    ],
)
def test_present_optional_input_must_match_fixed_provenance(field: str, value: object) -> None:
    mismatched = replace(source(), **{field: value})
    with pytest.raises(NodeExecutionError) as caught:
        collect_upstream_artifacts(
            ArtifactPortStub({"artifact:intro_option_set_source": (mismatched,)}),
            execution(),
            {
                "input_contract_refs": ["artifact:intro_option_set_source"],
                "optional_input_contract_refs": ["artifact:intro_option_set_source"],
            },
        )

    assert caught.value.code == "NODE_EXECUTION_INPUT_CONTRACT_MISMATCH"
