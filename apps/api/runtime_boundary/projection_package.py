"""Creation-package materialization for compiled runtime output projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import InitVar, dataclass
from typing import Any, cast
from uuid import UUID

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.runtime_boundary.creation_package_contracts import MAX_PACKAGE_ITEMS
from apps.api.runtime_boundary.ports import (
    ArtifactWriteResult,
    CreationPackageItemSpec,
    CreationPackageSpec,
    FrozenSnapshotRefs,
    GeneratedArtifactWrite,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_authorization import (
    validate_reference_asset_projection,
)
from apps.api.runtime_boundary.projection_package_items import (
    compile_package_items,
    public_target_rules,
    require_target_rules,
)
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    freeze_json_mapping,
    plain_json_value,
    require_mapping,
    require_text,
    resolve_json_pointer,
    runtime_document,
)

_OUTPUT_PROJECTION_COMPILER_TOKEN = object()


@dataclass(frozen=True, slots=True)
class OutputProjectionPlan:
    """Artifact DTO plus the immutable declaration needed for phase two."""

    definition: RuntimeNodeDefinition
    artifact_write: GeneratedArtifactWrite
    package_declaration: Mapping[str, Any] | None
    output: Mapping[str, Any]
    execution: WorkflowExecutionContext
    snapshots: FrozenSnapshotRefs
    request_id: str
    runtime_values: Mapping[str, Any]
    target_slot_authorization: TargetSlotAuthorization | None = None
    reference_asset_authorization: ReferenceAssetAuthorization | None = None
    _compiler_token: InitVar[object | None] = None

    def __post_init__(self, _compiler_token: object | None) -> None:
        _validate_plan_provenance(self)
        if self.package_declaration is not None:
            validate_reference_asset_projection(self.package_declaration)
            object.__setattr__(
                self,
                "package_declaration",
                freeze_json_mapping(self.package_declaration),
            )
        if _compiler_token is not _OUTPUT_PROJECTION_COMPILER_TOKEN:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_PLAN_UNTRUSTED",
                "projection plans must be created by the output compiler",
            )
        object.__setattr__(self, "output", freeze_json_mapping(self.output))
        object.__setattr__(self, "runtime_values", freeze_json_mapping(self.runtime_values))


def build_output_projection_plan(
    *,
    definition: RuntimeNodeDefinition,
    artifact_write: GeneratedArtifactWrite,
    package_declaration: Mapping[str, Any] | None,
    output: Mapping[str, Any],
    execution: WorkflowExecutionContext,
    snapshots: FrozenSnapshotRefs,
    request_id: str,
    runtime_values: Mapping[str, Any],
    target_slot_authorization: TargetSlotAuthorization | None,
    reference_asset_authorization: ReferenceAssetAuthorization | None,
) -> OutputProjectionPlan:
    """Create a phase-two plan from the trusted compiler boundary only."""

    return OutputProjectionPlan(
        definition=definition,
        artifact_write=artifact_write,
        package_declaration=package_declaration,
        output=output,
        execution=execution,
        snapshots=snapshots,
        request_id=request_id,
        runtime_values=runtime_values,
        target_slot_authorization=target_slot_authorization,
        reference_asset_authorization=reference_asset_authorization,
        _compiler_token=_OUTPUT_PROJECTION_COMPILER_TOKEN,
    )


def _validate_plan_provenance(plan: OutputProjectionPlan) -> None:
    write = plan.artifact_write
    execution = plan.execution
    snapshots = plan.snapshots
    definition = plan.definition
    if (
        definition.content_release_id != execution.content_release_id
        or definition.workflow_definition_version_id != execution.workflow_definition_version_id
        or definition.node_key != execution.node_key
        or definition.content_definition_version_id != write.content_definition_version_id
        or write.project_id != execution.project_id
        or write.node_run_id != execution.node_run_id
        or write.lesson_unit_id != execution.lesson_unit_id
        or write.context_snapshot_id != snapshots.context_snapshot_id
        or write.prompt_snapshot_id != snapshots.prompt_snapshot_id
        or write.request_id != plan.request_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PLAN_PROVENANCE_INVALID",
            "projection plan artifact provenance does not match its execution",
        )
    binding = require_mapping(definition.node_binding, "NODE_BINDING_INVALID")
    persistence = require_mapping(
        binding.get("output_persistence"),
        "OUTPUT_PROJECTION_DECLARATION_MISSING",
    )
    expected_package = persistence.get("creation_package")
    if expected_package != plan.package_declaration:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PLAN_DECLARATION_MISMATCH",
            "projection plan package declaration differs from the published binding",
        )
    if expected_package is not None and _projection_content_hash(
        plan.output
    ) != _projection_content_hash(write.content):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PLAN_CONTENT_MISMATCH",
            "package projection output differs from its source Artifact content",
        )
    target_authorization = plan.target_slot_authorization
    if target_authorization is not None and (
        target_authorization.content_release_id != execution.content_release_id
        or target_authorization.workflow_definition_version_id
        != execution.workflow_definition_version_id
        or target_authorization.project_id != execution.project_id
        or target_authorization.node_key != execution.node_key
        or target_authorization.branch_key != execution.branch_key
        or target_authorization.lesson_unit_id != execution.lesson_unit_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOTS_MISMATCH",
            "projection plan target-slot authorization does not match its execution",
        )
    _validate_plan_reference_assets(plan)


def _validate_plan_reference_assets(plan: OutputProjectionPlan) -> None:
    authorization = plan.reference_asset_authorization
    supplied = plan.runtime_values.get("reference_assets")
    if authorization is None:
        if supplied is not None:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
                "projection plan contains reference assets without authorization",
            )
        return
    execution = plan.execution
    if (
        authorization.content_release_id != execution.content_release_id
        or authorization.workflow_definition_version_id != execution.workflow_definition_version_id
        or authorization.project_id != execution.project_id
        or authorization.node_key != execution.node_key
        or authorization.branch_key != execution.branch_key
        or authorization.lesson_unit_id != execution.lesson_unit_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "projection plan reference authorization does not match its execution",
        )
    expected = tuple(
        {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
        for asset in authorization.assets
    )
    try:
        actual = tuple(cast(Sequence[object], supplied))
    except TypeError as exc:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "projection plan reference assets do not match their authorization",
        ) from exc
    if actual != expected:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "projection plan reference assets do not match their authorization",
        )


def materialize_creation_package(
    plan: OutputProjectionPlan,
    *,
    artifact_result: ArtifactWriteResult,
) -> CreationPackageSpec | None:
    """Materialize a package after ArtifactPort returns its version ID."""

    declaration = plan.package_declaration
    if declaration is None:
        return None
    artifact_version_id = _require_artifact_write_result(plan, artifact_result)
    package_type = _require_package_type(declaration.get("package_type"))
    package_key = _compile_package_key(declaration.get("package_key"), artifact_version_id)
    source_content = plan.artifact_write.content
    raw_items = _resolve_package_items(declaration, source_content)
    mapping = require_mapping(
        declaration.get("item_mapping"),
        "OUTPUT_PROJECTION_ITEM_MAPPING_INVALID",
    )
    target_rules = require_target_rules(declaration.get("target_rules"))
    authorization = plan.target_slot_authorization
    if authorization is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOTS_MISSING",
            "package materialization requires an authorized target-slot set",
        )
    runtime = runtime_document(plan.execution, plan.runtime_values)
    items = compile_package_items(
        raw_items,
        mapping=mapping,
        output=source_content,
        runtime=runtime,
        target_rules=target_rules,
        allowed_target_slots=authorization.slots,
    )
    return _build_package_spec(
        plan,
        artifact_version_id=artifact_version_id,
        package_type=package_type,
        package_key=package_key,
        items=items,
        target_rules=public_target_rules(target_rules),
    )


def _require_artifact_write_result(
    plan: OutputProjectionPlan,
    result: ArtifactWriteResult,
) -> UUID:
    value = cast(object, result.artifact_version_id)
    if not isinstance(value, UUID):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ARTIFACT_RESULT_INVALID",
            "artifact result version ID is invalid",
        )
    write = plan.artifact_write
    expected = (
        (result.project_id, write.project_id),
        (result.node_run_id, write.node_run_id),
        (result.context_snapshot_id, write.context_snapshot_id),
        (result.prompt_snapshot_id, write.prompt_snapshot_id),
        (result.artifact_key, write.artifact_key),
        (result.artifact_type, write.artifact_type),
        (result.branch_key, write.branch_key),
        (
            result.content_definition_version_id,
            write.content_definition_version_id,
        ),
    )
    if (
        any(actual != required for actual, required in expected)
        or result.lesson_unit_id != write.lesson_unit_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ARTIFACT_RESULT_MISMATCH",
            "artifact result does not belong to the compiled write",
        )
    if result.content_hash != _projection_content_hash(write.content):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ARTIFACT_RESULT_MISMATCH",
            "artifact result content hash does not match the compiled write",
        )
    return value


def _projection_content_hash(value: Mapping[str, Any]) -> str:
    normalized = plain_json_value(value)
    if not isinstance(normalized, Mapping):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_JSON_INVALID",
            "projection content must be a JSON object",
        )
    return canonical_content_hash(cast(Mapping[str, Any], normalized))


def _require_package_type(value: object) -> str:
    package_type = require_text(value, "package_type", 20)
    if package_type not in {"image", "video", "presentation"}:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_TYPE_INVALID",
            "creation package type is unsupported",
        )
    return package_type


def _compile_package_key(raw: object, artifact_version_id: UUID) -> str:
    declaration = require_mapping(raw, "OUTPUT_PROJECTION_PACKAGE_KEY_INVALID")
    if declaration.get("strategy") != "source_artifact_version":
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_KEY_INVALID",
            "package key strategy is unsupported",
        )
    prefix = require_text(declaration.get("prefix"), "package key prefix", 120)
    return require_text(f"{prefix}:{artifact_version_id}", "package_key", 180)


def _resolve_package_items(
    declaration: Mapping[str, Any], output: Mapping[str, Any]
) -> tuple[object, ...]:
    pointer = declaration.get("items_pointer")
    if not isinstance(pointer, str):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            "package items_pointer must be a string",
        )
    raw_items = resolve_json_pointer(output, pointer, source="output")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ITEMS_TYPE_INVALID",
            "package items projection must resolve to an array",
        )
    values = tuple(cast(Sequence[object], raw_items))
    if not values or len(values) > MAX_PACKAGE_ITEMS:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ITEMS_INVALID",
            "package items must contain between one and one hundred entries",
        )
    return values


def _build_package_spec(
    plan: OutputProjectionPlan,
    *,
    artifact_version_id: UUID,
    package_type: str,
    package_key: str,
    items: tuple[CreationPackageItemSpec, ...],
    target_rules: Mapping[str, Any],
) -> CreationPackageSpec:
    return CreationPackageSpec(
        project_id=plan.execution.project_id,
        workflow_run_id=plan.execution.workflow_run_id,
        node_run_id=plan.execution.node_run_id,
        lesson_unit_id=plan.execution.lesson_unit_id,
        artifact_version_id=artifact_version_id,
        context_snapshot_id=plan.snapshots.context_snapshot_id,
        prompt_snapshot_id=plan.snapshots.prompt_snapshot_id,
        package_key=package_key,
        package_type=package_type,
        items=items,
        target_rules=target_rules,
        request_id=plan.request_id,
    )
