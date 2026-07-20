from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from apps.api.artifacts.domain import (
    ArtifactInvariantError,
    ArtifactRelationType,
    canonical_content_hash,
)
from apps.api.runtime_boundary.output_projection import (
    OutputProjectionError,
    compile_output_projection,
    materialize_creation_package,
)
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    ArtifactWriteResult,
    CreationPackageReferenceAssetSpec,
    FrozenSnapshotRefs,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_package import OutputProjectionPlan

RELEASE_ID = UUID("10000000-0000-4000-8000-000000000001")
WORKFLOW_ID = UUID("10000000-0000-4000-8000-000000000002")
CONTENT_DEFINITION_ID = UUID("10000000-0000-4000-8000-000000000003")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000004")
WORKFLOW_RUN_ID = UUID("10000000-0000-4000-8000-000000000005")
NODE_RUN_ID = UUID("10000000-0000-4000-8000-000000000006")
LESSON_UNIT_ID = UUID("10000000-0000-4000-8000-000000000007")
CONTEXT_SNAPSHOT_ID = UUID("10000000-0000-4000-8000-000000000008")
PROMPT_SNAPSHOT_ID = UUID("10000000-0000-4000-8000-000000000009")
UPSTREAM_VERSION_ID = UUID("10000000-0000-4000-8000-000000000010")
ARTIFACT_ID = UUID("10000000-0000-4000-8000-000000000011")
ARTIFACT_VERSION_ID = UUID("10000000-0000-4000-8000-000000000012")
FOREIGN_PROJECT_ID = UUID("10000000-0000-4000-8000-000000000099")


def _binding(*, scope: str = "lesson_unit", package: bool = False) -> dict[str, Any]:
    lesson = scope == "lesson_unit"
    branch = "ppt" if lesson else "lesson_division"
    identity = (
        {"strategy": "lesson_unit_singleton", "artifact_key_prefix": "ppt-body-prompts"}
        if lesson
        else {"strategy": "project_singleton", "artifact_key": "lesson-division"}
    )
    impact_scope: dict[str, Any] = (
        {
            "mode": "keyed",
            "selector": "lesson_key",
            "keys": {"source": "runtime", "pointer": "/lesson_key"},
        }
        if lesson
        else {"mode": "all"}
    )
    persistence: dict[str, Any] = {
        "artifact": {
            "identity": identity,
            "artifact_type": "ppt_body_asset_prompt_package" if lesson else "lesson_division",
            "branch_key": branch if lesson else "project",
            "content_definition_ref": {
                "item_key": "example.generate.output",
                "kind": "content_definition",
            },
            "content": {"source": "output", "pointer": ""},
            "relations": [
                {
                    "source_binding": "approval:source",
                    "relation_type": "derives_from",
                    "binding_key": "upstream.approval.source",
                    "impact_scope": impact_scope,
                }
            ],
        }
    }
    if package:
        persistence["creation_package"] = _package_declaration()
    return {
        "node_key": "example.generate",
        "execution_kind": "model_generation",
        "execution_scope": scope,
        "branch_key": branch,
        "generation_template_ref": {
            "item_key": "example.generate",
            "kind": "generation_template",
        },
        "input_contract_refs": ["approval:source"],
        "output_contract_refs": ["package:creation_image" if package else "artifact:example"],
        "output_persistence": persistence,
    }


def _package_declaration() -> dict[str, Any]:
    return {
        "package_type": "image",
        "package_key": {"strategy": "source_artifact_version", "prefix": "ppt-body"},
        "items_pointer": "/items",
        "item_mapping": {
            "item_key": {"source": "item", "pointer": "/key"},
            "position": {"source": "intrinsic", "name": "item_position"},
            "title": {"source": "item", "pointer": "/title"},
            "business_prompt": {"source": "item", "pointer": "/business_prompt"},
            "reference_assets": {"source": "runtime", "pointer": "/reference_assets"},
            "output_spec": {"source": "item", "pointer": "/output_spec"},
            "target_slot": {"source": "item", "pointer": "/target_slot"},
            "consistency_key": {"source": "item", "pointer": "/consistency_key"},
        },
        "target_rules": {
            "replace_modes": ["reject_if_occupied", "replace_active"],
            "allow_download": True,
            "target_slot_prefix": "ppt.",
        },
    }


def _definition(binding: dict[str, Any]) -> RuntimeNodeDefinition:
    return RuntimeNodeDefinition(
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="example.generate",
        execution_kind="model_generation",
        generation_template_key="example.generate",
        generation_template={
            "spec": {
                "template_key": "example.generate",
                "output_definition_ref": {
                    "item_key": "example.generate.output",
                    "kind": "content_definition",
                },
            }
        },
        node_binding=binding,
        content_definition_version_id=CONTENT_DEFINITION_ID,
        content_definition_release_id=RELEASE_ID,
        content_definition_item_key="example.generate.output",
    )


def _execution(*, scope: str = "lesson_unit") -> WorkflowExecutionContext:
    lesson = scope == "lesson_unit"
    return WorkflowExecutionContext(
        organization_id=UUID("10000000-0000-4000-8000-000000000020"),
        project_id=PROJECT_ID,
        workflow_run_id=WORKFLOW_RUN_ID,
        node_run_id=NODE_RUN_ID,
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="example.generate",
        branch_key="ppt" if lesson else "lesson_division",
        lesson_key="LESSON-001" if lesson else None,
        lesson_unit_id=LESSON_UNIT_ID if lesson else None,
        status="running",
    )


def _snapshots() -> FrozenSnapshotRefs:
    return FrozenSnapshotRefs(
        context_snapshot_id=CONTEXT_SNAPSHOT_ID,
        prompt_snapshot_id=PROMPT_SNAPSHOT_ID,
        context_hash="context-hash",
        prompt_hash="prompt-hash",
    )


def _upstream(execution: WorkflowExecutionContext) -> dict[str, ArtifactContextVersion]:
    return {
        "approval:source": ArtifactContextVersion(
            project_id=execution.project_id,
            lesson_unit_id=execution.lesson_unit_id,
            artifact_version_id=UPSTREAM_VERSION_ID,
            contract_ref="approval:source",
            artifact_type="source",
            content={},
            content_hash="a" * 64,
        )
    }


def _output() -> dict[str, Any]:
    return {
        "summary": {"points": ["one"]},
        "items": [
            {
                "key": "visual-01",
                "title": "First visual",
                "business_prompt": "Draw the first classroom visual.",
                "output_spec": {"aspect_ratio": "16:9"},
                "target_slot": "ppt.page-01.main-visual",
                "consistency_key": "style-main",
            },
            {
                "key": "visual-02",
                "title": "Second visual",
                "business_prompt": "Draw the second classroom visual.",
                "output_spec": {"aspect_ratio": "16:9"},
                "target_slot": "ppt.page-02.main-visual",
                "consistency_key": None,
            },
        ],
    }


def _compile(
    binding: dict[str, Any],
    *,
    scope: str = "lesson_unit",
    output: dict[str, Any] | None = None,
    execution: WorkflowExecutionContext | None = None,
    runtime_values: dict[str, Any] | None = None,
    target_slot_authorization: TargetSlotAuthorization | None = None,
    reference_asset_authorization: ReferenceAssetAuthorization | None = None,
    upstream_artifacts: dict[str, ArtifactContextVersion] | None = None,
) -> OutputProjectionPlan:
    resolved_execution = execution or _execution(scope=scope)
    return compile_output_projection(
        definition=_definition(binding),
        execution=resolved_execution,
        snapshots=_snapshots(),
        validated_output=output or _output(),
        upstream_artifacts=(
            upstream_artifacts if upstream_artifacts is not None else _upstream(resolved_execution)
        ),
        request_id="request-130",
        runtime_values=runtime_values,
        target_slot_authorization=target_slot_authorization
        if target_slot_authorization is not None
        else (
            _target_slot_authorization()
            if binding.get("output_persistence", {}).get("creation_package")
            else None
        ),
        reference_asset_authorization=(
            reference_asset_authorization
            if reference_asset_authorization is not None
            else (
                _reference_asset_authorization(())
                if binding.get("output_persistence", {}).get("creation_package")
                else None
            )
        ),
    )


def _artifact_result(plan: OutputProjectionPlan) -> ArtifactWriteResult:
    write = plan.artifact_write
    return ArtifactWriteResult(
        artifact_id=ARTIFACT_ID,
        artifact_version_id=ARTIFACT_VERSION_ID,
        content_hash=canonical_content_hash(write.content),
        project_id=write.project_id,
        node_run_id=write.node_run_id,
        context_snapshot_id=write.context_snapshot_id,
        prompt_snapshot_id=write.prompt_snapshot_id,
        artifact_key=write.artifact_key,
        artifact_type=write.artifact_type,
        branch_key=write.branch_key,
        lesson_unit_id=write.lesson_unit_id,
        content_definition_version_id=write.content_definition_version_id,
    )


def _reference_asset_authorization(
    assets: tuple[tuple[str, str], ...],
) -> ReferenceAssetAuthorization:
    return ReferenceAssetAuthorization(
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        project_id=PROJECT_ID,
        node_key="example.generate",
        branch_key="ppt",
        lesson_unit_id=LESSON_UNIT_ID,
        assets=tuple(
            CreationPackageReferenceAssetSpec(
                asset_version_id=UUID(asset_id),
                role=role,
            )
            for asset_id, role in assets
        ),
    )


def _target_slot_authorization(
    *,
    project_id: UUID = PROJECT_ID,
    slots: tuple[str, ...] = (
        "ppt.page-01.main-visual",
        "ppt.page-02.main-visual",
    ),
) -> TargetSlotAuthorization:
    return TargetSlotAuthorization(
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        project_id=project_id,
        node_key="example.generate",
        branch_key="ppt",
        lesson_unit_id=LESSON_UNIT_ID,
        slots=slots,
    )


def test_compiles_project_singleton_artifact_with_all_scope() -> None:
    output = _output()
    plan = _compile(_binding(scope="project"), scope="project", output=output)

    assert plan.artifact_write.artifact_key == "lesson-division"
    assert plan.artifact_write.branch_key == "project"
    assert plan.artifact_write.lesson_unit_id is None
    assert plan.artifact_write.content_definition_version_id == CONTENT_DEFINITION_ID
    assert plan.artifact_write.relations[0].impact_scope == {"mode": "all"}
    output["summary"]["points"].append("mutated")
    assert plan.artifact_write.content["summary"]["points"] == ("one",)
    assert plan.output["summary"]["points"] == ("one",)


def test_compiles_lesson_identity_and_trusted_keyed_relation() -> None:
    plan = _compile(_binding())

    assert plan.artifact_write.artifact_key == "ppt-body-prompts:LESSON-001"
    assert plan.artifact_write.lesson_unit_id == LESSON_UNIT_ID
    relation = plan.artifact_write.relations[0]
    assert relation.from_artifact_version_id == UPSTREAM_VERSION_ID
    assert relation.relation_type is ArtifactRelationType.DERIVES_FROM
    assert relation.impact_scope == {
        "mode": "keyed",
        "selector": "lesson_key",
        "keys": ("LESSON-001",),
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("node_key", "other.node", "OUTPUT_PROJECTION_NODE_MISMATCH"),
        ("content_release_id", ARTIFACT_ID, "OUTPUT_PROJECTION_RELEASE_MISMATCH"),
        (
            "workflow_definition_version_id",
            ARTIFACT_ID,
            "OUTPUT_PROJECTION_WORKFLOW_MISMATCH",
        ),
        ("branch_key", "video", "OUTPUT_PROJECTION_BRANCH_MISMATCH"),
        ("lesson_key", None, "OUTPUT_PROJECTION_SCOPE_MISSING"),
        ("lesson_unit_id", None, "OUTPUT_PROJECTION_SCOPE_MISSING"),
    ],
)
def test_rejects_execution_context_mismatches(field: str, value: object, code: str) -> None:
    execution = replace(_execution(), **{field: value})
    with pytest.raises(OutputProjectionError) as caught:
        _compile(_binding(), execution=execution)
    assert caught.value.code == code


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("identity", "OUTPUT_PROJECTION_IDENTITY_SCOPE_MISMATCH"),
        ("artifact_branch", "OUTPUT_PROJECTION_ARTIFACT_BRANCH_MISMATCH"),
        ("content_ref", "OUTPUT_PROJECTION_CONTENT_DEFINITION_MISMATCH"),
        ("content_source", "OUTPUT_PROJECTION_CONTENT_SOURCE_INVALID"),
    ],
)
def test_rejects_published_artifact_mismatches(mutation: str, code: str) -> None:
    binding = _binding()
    artifact = binding["output_persistence"]["artifact"]
    if mutation == "identity":
        artifact["identity"] = {"strategy": "project_singleton", "artifact_key": "wrong"}
    elif mutation == "artifact_branch":
        artifact["branch_key"] = "project"
    elif mutation == "content_ref":
        artifact["content_definition_ref"]["item_key"] = "other.output"
    else:
        artifact["content"] = {"source": "constant", "value": {}}
    with pytest.raises(OutputProjectionError) as caught:
        _compile(binding)
    assert caught.value.code == code


def test_rejects_missing_content_definition_provenance() -> None:
    definition = _definition(_binding())
    definition = replace(
        definition,
        content_definition_release_id=None,
        content_definition_item_key=None,
    )
    with pytest.raises(OutputProjectionError) as caught:
        compile_output_projection(
            definition=definition,
            execution=_execution(),
            snapshots=_snapshots(),
            validated_output=_output(),
            upstream_artifacts=_upstream(_execution()),
            request_id="request-130",
        )
    assert caught.value.code == "OUTPUT_PROJECTION_CONTENT_DEFINITION_PROVENANCE_MISSING"


def test_rejects_unknown_superseding_and_untrusted_relations() -> None:
    for mutation, code in (
        ("unknown", "OUTPUT_PROJECTION_RELATION_SOURCE_MISSING"),
        ("supersedes", "OUTPUT_PROJECTION_RELATION_TYPE_INVALID"),
        ("untrusted_keys", "OUTPUT_PROJECTION_IMPACT_SCOPE_INVALID"),
    ):
        binding = _binding()
        relation = binding["output_persistence"]["artifact"]["relations"][0]
        if mutation == "unknown":
            relation["source_binding"] = "approval:unknown"
        elif mutation == "supersedes":
            relation["relation_type"] = "supersedes"
        else:
            relation["impact_scope"]["keys"] = {
                "source": "output",
                "pointer": "/summary/points",
            }
        with pytest.raises(OutputProjectionError) as caught:
            _compile(binding)
        assert caught.value.code == code


@pytest.mark.parametrize("pointer", ["relative", "/bad~2", "/#", "/*", "/..", "/items/01"])
def test_rejects_unsafe_or_noncanonical_projection_pointers(pointer: str) -> None:
    binding = _binding(package=True)
    binding["output_persistence"]["creation_package"]["item_mapping"]["title"][
        "pointer"
    ] = pointer
    plan = _compile(binding)
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(plan, artifact_result=_artifact_result(plan))
    assert caught.value.code.startswith("OUTPUT_PROJECTION_POINTER_")


def test_runtime_values_cannot_override_trusted_execution_roots() -> None:
    with pytest.raises(OutputProjectionError) as caught:
        _compile(_binding(), runtime_values={"lesson_key": "LESSON-999"})
    assert caught.value.code == "OUTPUT_PROJECTION_RUNTIME_CONTEXT_INVALID"


def test_runtime_projection_cannot_expose_project_or_workflow_ids() -> None:
    binding = _binding(package=True)
    binding["output_persistence"]["creation_package"]["item_mapping"]["title"] = {
        "source": "runtime",
        "pointer": "/project_id",
    }
    plan = _compile(binding)
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(plan, artifact_result=_artifact_result(plan))
    assert caught.value.code == "OUTPUT_PROJECTION_RUNTIME_POINTER_INVALID"


def test_materializes_creation_package_after_artifact_persistence() -> None:
    binding = _binding(package=True)
    output = _output()
    plan = _compile(binding, output=output)
    output["items"][0]["title"] = "mutated"
    binding["output_persistence"]["creation_package"]["items_pointer"] = "/missing"
    package = materialize_creation_package(
        plan,
        artifact_result=_artifact_result(plan),
    )

    assert package is not None
    assert package.package_key == f"ppt-body:{ARTIFACT_VERSION_ID}"
    assert package.artifact_version_id == ARTIFACT_VERSION_ID
    assert package.context_snapshot_id == CONTEXT_SNAPSHOT_ID
    assert package.prompt_snapshot_id == PROMPT_SNAPSHOT_ID
    assert package.target_slots == (
        "ppt.page-01.main-visual",
        "ppt.page-02.main-visual",
    )
    assert package.items[0].position == 1
    assert package.items[0].title == "First visual"
    assert package.items[0].prompt == {}
    assert package.items[0].output_spec["aspect_ratio"] == "16:9"
    assert package.target_rules == {
        "replace_modes": ("reject_if_occupied", "replace_active"),
        "allow_download": True,
    }


@pytest.mark.parametrize("duplicate", ["key", "position", "slot"])
def test_rejects_duplicate_creation_package_coordinates(duplicate: str) -> None:
    binding = _binding(package=True)
    output = _output()
    if duplicate == "key":
        output["items"][1]["key"] = output["items"][0]["key"]
    elif duplicate == "position":
        mapping = binding["output_persistence"]["creation_package"]["item_mapping"]
        mapping["position"] = {"source": "constant", "value": 1}
    else:
        output["items"][1]["target_slot"] = output["items"][0]["target_slot"]
    plan = _compile(binding, output=output)
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(
            plan,
            artifact_result=_artifact_result(plan),
        )
    assert caught.value.code == "OUTPUT_PROJECTION_PACKAGE_DUPLICATE"


def test_rejects_target_slots_outside_declared_namespace() -> None:
    output = _output()
    output["items"][0]["target_slot"] = "ppt.admin.delete"
    plan = _compile(_binding(package=True), output=output)
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(
            plan,
            artifact_result=_artifact_result(plan),
        )
    assert caught.value.code == "OUTPUT_PROJECTION_TARGET_SLOT_UNAUTHORIZED"


def test_rejects_target_slot_prefix_that_cannot_have_a_valid_suffix() -> None:
    binding = _binding(package=True)
    binding["output_persistence"]["creation_package"]["target_rules"][
        "target_slot_prefix"
    ] = f"{'a' * 159}."

    plan = _compile(binding)
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(plan, artifact_result=_artifact_result(plan))
    assert caught.value.code == "OUTPUT_PROJECTION_TARGET_RULES_INVALID"


def test_nonempty_reference_assets_require_trusted_runtime_authorization() -> None:
    asset_id = "10000000-0000-4000-8000-000000000013"
    with pytest.raises(OutputProjectionError) as caught:
        _compile(
            _binding(package=True),
            runtime_values={"reference_assets": [{"asset_version_id": asset_id, "role": "style"}]},
        )
    assert caught.value.code == "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED"

    plan = _compile(
        _binding(package=True),
        reference_asset_authorization=_reference_asset_authorization(((asset_id, "style"),)),
    )
    package = materialize_creation_package(
        plan,
        artifact_result=_artifact_result(plan),
    )
    assert package is not None
    assert package.items[0].reference_assets[0].asset_version_id == UUID(asset_id)


def test_legacy_reference_asset_version_ids_are_rejected() -> None:
    asset_id = "10000000-0000-4000-8000-000000000013"

    with pytest.raises(OutputProjectionError) as caught:
        _compile(
            _binding(package=True),
            runtime_values={"reference_asset_version_ids": [asset_id]},
        )

    assert caught.value.code == "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED"


def test_phase_two_rejects_tampered_reference_asset_values() -> None:
    plan = _compile(_binding(package=True))
    tampered = {
        "reference_assets": [
            {
                "asset_version_id": "10000000-0000-4000-8000-000000000099",
                "role": "foreign",
            }
        ]
    }

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, runtime_values=tampered)
    assert caught.value.code == "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED"


def test_reference_asset_authorization_requires_the_same_role() -> None:
    asset_id = "10000000-0000-4000-8000-000000000013"
    plan = _compile(
        _binding(package=True),
        reference_asset_authorization=_reference_asset_authorization(((asset_id, "style"),)),
    )
    tampered = {
        "reference_assets": [
            {
                "asset_version_id": asset_id,
                "role": "character",
            }
        ]
    }

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, runtime_values=tampered)

    assert caught.value.code == "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED"


def test_reference_asset_uuid_cannot_be_reused_with_a_different_role() -> None:
    asset_id = "10000000-0000-4000-8000-000000000013"
    with pytest.raises(ArtifactInvariantError, match="IDs must be unique"):
        _reference_asset_authorization(
            (
                (asset_id, "style"),
                (asset_id, "character"),
            )
        )


def test_rejects_more_than_twenty_authorized_reference_assets() -> None:
    assets = tuple((str(UUID(int=index + 1)), "style") for index in range(21))
    with pytest.raises(ArtifactInvariantError, match="authorization entries"):
        _reference_asset_authorization(assets)


def test_package_requires_an_authorized_target_slot_set() -> None:
    plan = compile_output_projection(
        definition=_definition(_binding(package=True)),
        execution=_execution(),
        snapshots=_snapshots(),
        validated_output=_output(),
        upstream_artifacts=_upstream(_execution()),
        request_id="request-130",
    )
    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(
            plan,
            artifact_result=_artifact_result(plan),
        )
    assert caught.value.code == "OUTPUT_PROJECTION_TARGET_SLOTS_MISSING"


def test_rejects_target_slot_authorization_from_another_project() -> None:
    with pytest.raises(OutputProjectionError) as caught:
        _compile(
            _binding(package=True),
            target_slot_authorization=_target_slot_authorization(project_id=FOREIGN_PROJECT_ID),
        )
    assert caught.value.code == "OUTPUT_PROJECTION_TARGET_SLOTS_MISMATCH"


def test_rejects_noncanonical_semantic_target_slot() -> None:
    output = _output()
    output["items"][0]["target_slot"] = "ppt.PAGE-01.main-visual"
    plan = _compile(_binding(package=True), output=output)

    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(plan, artifact_result=_artifact_result(plan))
    assert caught.value.code == "OUTPUT_PROJECTION_TARGET_SLOT_UNAUTHORIZED"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("project_id", FOREIGN_PROJECT_ID),
        ("node_run_id", UPSTREAM_VERSION_ID),
        ("context_snapshot_id", UPSTREAM_VERSION_ID),
        ("prompt_snapshot_id", UPSTREAM_VERSION_ID),
        ("artifact_key", "foreign-artifact"),
        ("artifact_type", "foreign-artifact"),
        ("branch_key", "video"),
        ("lesson_unit_id", None),
        ("content_definition_version_id", UPSTREAM_VERSION_ID),
        ("content_hash", "f" * 64),
    ),
)
def test_rejects_artifact_result_provenance_mismatch(field: str, value: object) -> None:
    plan = _compile(_binding(package=True))
    foreign_result = replace(
        _artifact_result(plan),
        **{field: value},
    )

    with pytest.raises(OutputProjectionError) as caught:
        materialize_creation_package(plan, artifact_result=foreign_result)
    assert caught.value.code == "OUTPUT_PROJECTION_ARTIFACT_RESULT_MISMATCH"


@pytest.mark.parametrize("field", ["project_id", "lesson_unit_id", "contract_ref"])
def test_rejects_relation_source_with_foreign_provenance(field: str) -> None:
    execution = _execution()
    upstream = _upstream(execution)
    replacement: object = "approval:foreign" if field == "contract_ref" else FOREIGN_PROJECT_ID
    upstream["approval:source"] = replace(
        upstream["approval:source"],
        **{field: replacement},
    )

    with pytest.raises(OutputProjectionError) as caught:
        _compile(_binding(), execution=execution, upstream_artifacts=upstream)
    assert caught.value.code == "OUTPUT_PROJECTION_RELATION_SOURCE_MISMATCH"


@pytest.mark.parametrize(
    "reference_assets",
    [
        {
            "source": "constant",
            "value": [
                {
                    "asset_version_id": "10000000-0000-4000-8000-000000000013",
                    "role": "style",
                }
            ],
        },
        {"source": "item", "pointer": "/reference_assets"},
    ],
)
def test_rejects_untrusted_reference_asset_projection_source(
    reference_assets: dict[str, object],
) -> None:
    binding = _binding(package=True)
    mapping = binding["output_persistence"]["creation_package"]["item_mapping"]
    mapping["reference_assets"] = reference_assets

    with pytest.raises(OutputProjectionError) as caught:
        _compile(binding)
    assert caught.value.code == "OUTPUT_PROJECTION_REFERENCE_ASSET_SOURCE_INVALID"


@pytest.mark.parametrize(
    "reference_assets",
    [
        {
            "source": "constant",
            "value": [
                {
                    "asset_version_id": "10000000-0000-4000-8000-000000000013",
                    "role": "style",
                }
            ],
        },
        {"source": "item", "pointer": "/reference_assets"},
    ],
)
def test_phase_two_rejects_tampered_reference_asset_projection_source(
    reference_assets: dict[str, object],
) -> None:
    plan = _compile(_binding(package=True))
    declaration = dict(plan.package_declaration or {})
    mapping = dict(declaration["item_mapping"])
    mapping["reference_assets"] = reference_assets
    declaration["item_mapping"] = mapping

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, package_declaration=declaration)
    assert caught.value.code == "OUTPUT_PROJECTION_PLAN_DECLARATION_MISMATCH"


@pytest.mark.parametrize(
    "mutation",
    ["missing", "package_type", "package_key", "item_mapping", "target_rules"],
)
def test_phase_two_rejects_any_tampered_package_declaration(mutation: str) -> None:
    plan = _compile(_binding(package=True))
    declaration: dict[str, Any] | None = _package_declaration()
    if mutation == "missing":
        declaration = None
    elif mutation == "package_type":
        declaration["package_type"] = "video"
    elif mutation == "package_key":
        declaration["package_key"] = {
            "strategy": "source_artifact_version",
            "prefix": "tampered",
        }
    elif mutation == "item_mapping":
        declaration["item_mapping"]["title"] = {
            "source": "item",
            "pointer": "/business_prompt",
        }
    else:
        declaration["target_rules"]["allow_download"] = False

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, package_declaration=declaration)
    assert caught.value.code == "OUTPUT_PROJECTION_PLAN_DECLARATION_MISMATCH"


def test_phase_two_rejects_output_that_differs_from_source_artifact() -> None:
    plan = _compile(_binding(package=True))

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, output={"items": []})
    assert caught.value.code == "OUTPUT_PROJECTION_PLAN_CONTENT_MISMATCH"


def test_phase_two_rejects_tampered_request_id() -> None:
    plan = _compile(_binding(package=True))

    with pytest.raises(OutputProjectionError) as caught:
        replace(plan, request_id="request-forged")
    assert caught.value.code == "OUTPUT_PROJECTION_PLAN_PROVENANCE_INVALID"


def test_phase_two_rejects_simultaneous_definition_and_declaration_replacement() -> None:
    plan = _compile(_binding(package=True))
    forged_binding = _binding(package=True)
    forged_binding["output_persistence"]["creation_package"]["package_type"] = "video"
    forged_definition = _definition(forged_binding)
    forged_declaration = forged_definition.node_binding["output_persistence"][
        "creation_package"
    ]

    with pytest.raises(OutputProjectionError) as caught:
        replace(
            plan,
            definition=forged_definition,
            package_declaration=forged_declaration,
        )
    assert caught.value.code == "OUTPUT_PROJECTION_PLAN_UNTRUSTED"


@pytest.mark.parametrize(
    ("package", "outputs", "code"),
    [
        (True, ["package:first", "package:second"], "OUTPUT_PROJECTION_PACKAGE_OUTPUT_MISMATCH"),
        (False, ["package:missing"], "OUTPUT_PROJECTION_PACKAGE_DECLARATION_MISSING"),
    ],
)
def test_package_declaration_matches_exactly_one_package_output(
    package: bool, outputs: list[str], code: str
) -> None:
    binding = _binding(package=package)
    binding["output_contract_refs"] = outputs
    with pytest.raises(OutputProjectionError) as caught:
        _compile(
            binding,
            target_slot_authorization=_target_slot_authorization(
                slots=("ppt.page-01.main-visual",)
            ),
        )
    assert caught.value.code == code


def test_node_without_package_returns_none_after_artifact_persistence() -> None:
    plan = _compile(_binding())
    package = materialize_creation_package(
        plan,
        artifact_result=_artifact_result(plan),
    )
    assert package is None
