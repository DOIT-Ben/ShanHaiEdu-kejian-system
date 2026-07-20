"""Pure compilation of published model-output persistence declarations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    ArtifactWriteResult,
    CreationPackageSpec,
    FrozenSnapshotRefs,
    GeneratedArtifactWrite,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_artifact import compile_artifact_write
from apps.api.runtime_boundary.projection_authorization import (
    validate_package_contract,
    validate_reference_asset_authorization,
    validate_target_slot_authorization,
)
from apps.api.runtime_boundary.projection_package import (
    OutputProjectionPlan,
    build_output_projection_plan,
    materialize_creation_package,
)
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    require_json_mapping,
    require_mapping,
    require_text,
    validate_resolved_binding,
    validate_scope_context,
)

ProjectionCompilationError = OutputProjectionError


def compile_output_projection(
    *,
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
    snapshots: FrozenSnapshotRefs,
    validated_output: Mapping[str, Any],
    upstream_artifacts: Mapping[str, ArtifactContextVersion],
    request_id: str,
    runtime_values: Mapping[str, Any] | None = None,
    target_slot_authorization: TargetSlotAuthorization | None = None,
    reference_asset_authorization: ReferenceAssetAuthorization | None = None,
) -> OutputProjectionPlan:
    """Compile immutable Artifact and optional phase-two package inputs."""

    binding = require_mapping(definition.node_binding, "NODE_BINDING_INVALID")
    _require_model_generation_binding(definition, binding)
    _validate_execution_context(definition, execution, binding)
    output = require_json_mapping(validated_output, "OUTPUT_PROJECTION_OUTPUT_INVALID")
    artifact, package = _persistence_declarations(binding)
    normalized_authorization = validate_target_slot_authorization(
        target_slot_authorization,
        definition=definition,
        execution=execution,
        required=False,
    )
    normalized_asset_authorization = validate_reference_asset_authorization(
        reference_asset_authorization,
        definition=definition,
        execution=execution,
    )
    normalized_runtime_values = _normalize_runtime_values(
        runtime_values,
        normalized_asset_authorization,
    )
    validate_package_contract(binding, package)
    validated_request_id = require_text(request_id, "request_id", 256)
    artifact_write = compile_artifact_write(
        definition=definition,
        execution=execution,
        snapshots=snapshots,
        binding=binding,
        artifact=artifact,
        output=output,
        upstream_artifacts=upstream_artifacts,
        request_id=validated_request_id,
        runtime_values=normalized_runtime_values,
    )
    return build_output_projection_plan(
        definition=definition,
        artifact_write=artifact_write,
        package_declaration=package,
        output=output,
        execution=execution,
        snapshots=snapshots,
        request_id=validated_request_id,
        runtime_values=normalized_runtime_values,
        target_slot_authorization=normalized_authorization,
        reference_asset_authorization=normalized_asset_authorization,
    )


def _normalize_runtime_values(
    values: Mapping[str, Any] | None,
    authorization: ReferenceAssetAuthorization | None,
) -> Mapping[str, Any]:
    raw = dict(
        require_json_mapping(
            values or {},
            "OUTPUT_PROJECTION_RUNTIME_CONTEXT_INVALID",
        )
    )
    supplied = raw.pop("reference_assets", None)
    legacy = raw.pop("reference_asset_version_ids", None)
    if legacy is not None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "reference assets require a trusted authorization DTO",
        )
    if supplied is not None and authorization is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "reference assets require a trusted authorization DTO",
        )
    if authorization is not None:
        authorized = [
            {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
            for asset in authorization.assets
        ]
        if supplied is not None and supplied != authorized:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
                "runtime reference assets do not match the trusted authorization set",
            )
        raw["reference_assets"] = authorized
    return raw


def compile_generated_artifact(**kwargs: Any) -> GeneratedArtifactWrite:
    """Return only the phase-one Artifact write DTO."""

    return compile_output_projection(**kwargs).artifact_write


def compile_creation_package(
    *, artifact_result: ArtifactWriteResult, **kwargs: Any
) -> CreationPackageSpec | None:
    """Compile both phases when an Artifact write result is already available."""

    return materialize_creation_package(
        compile_output_projection(**kwargs), artifact_result=artifact_result
    )


def _require_model_generation_binding(
    definition: RuntimeNodeDefinition, binding: Mapping[str, Any]
) -> None:
    if (
        binding.get("execution_kind") != "model_generation"
        or definition.execution_kind != "model_generation"
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_EXECUTION_KIND_INVALID",
            "only model_generation nodes can emit an output projection",
        )


def _persistence_declarations(
    binding: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any] | None]:
    persistence = require_mapping(
        binding.get("output_persistence"),
        "OUTPUT_PROJECTION_DECLARATION_MISSING",
    )
    artifact = require_mapping(
        persistence.get("artifact"),
        "OUTPUT_PROJECTION_ARTIFACT_DECLARATION_INVALID",
    )
    package = persistence.get("creation_package")
    if package is None:
        return artifact, None
    return artifact, require_mapping(package, "OUTPUT_PROJECTION_PACKAGE_DECLARATION_INVALID")


def _validate_execution_context(
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
    binding: Mapping[str, Any],
) -> None:
    validate_resolved_binding(definition, binding)
    for actual, expected, code, message in (
        (
            execution.node_key,
            definition.node_key,
            "OUTPUT_PROJECTION_NODE_MISMATCH",
            "runtime node does not match the published binding",
        ),
        (
            execution.content_release_id,
            definition.content_release_id,
            "OUTPUT_PROJECTION_RELEASE_MISMATCH",
            "runtime content release does not match the published binding",
        ),
        (
            execution.workflow_definition_version_id,
            definition.workflow_definition_version_id,
            "OUTPUT_PROJECTION_WORKFLOW_MISMATCH",
            "runtime workflow version does not match the published binding",
        ),
    ):
        if actual != expected:
            raise OutputProjectionError(code, message)
    if execution.branch_key != binding.get("branch_key"):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_BRANCH_MISMATCH",
            "runtime branch does not match the published binding",
        )
    validate_scope_context(execution, binding.get("execution_scope"))
