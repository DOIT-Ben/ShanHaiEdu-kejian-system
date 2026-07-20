"""Pure compilation of published model-output persistence declarations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from apps.api.artifacts.domain import ArtifactRelationType
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    ArtifactWriteResult,
    CreationPackageSpec,
    FrozenSnapshotRefs,
    GeneratedArtifactRelation,
    GeneratedArtifactWrite,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_authorization import (
    validate_package_contract,
    validate_reference_asset_authorization,
    validate_target_slot_authorization,
)
from apps.api.runtime_boundary.projection_package import (
    OutputProjectionPlan,
    materialize_creation_package,
)
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    require_json_mapping,
    require_mapping,
    require_text,
    require_text_sequence,
    resolve_projection,
    runtime_document,
    validate_artifact_declaration,
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
    artifact_write = _compile_artifact_write(
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
    return OutputProjectionPlan(
        artifact_write=artifact_write,
        package_declaration=package,
        output=output,
        execution=execution,
        snapshots=snapshots,
        request_id=validated_request_id,
        runtime_values=normalized_runtime_values,
        target_slot_authorization=normalized_authorization,
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


def _compile_artifact_write(
    *,
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
    snapshots: FrozenSnapshotRefs,
    binding: Mapping[str, Any],
    artifact: Mapping[str, Any],
    output: Mapping[str, Any],
    upstream_artifacts: Mapping[str, ArtifactContextVersion],
    request_id: str,
    runtime_values: Mapping[str, Any] | None,
) -> GeneratedArtifactWrite:
    validate_artifact_declaration(binding, artifact)
    _validate_content_definition_ref(definition, artifact)
    runtime = runtime_document(execution, runtime_values)
    content = require_json_mapping(
        resolve_projection(artifact.get("content"), output=output, item=None, runtime=runtime),
        "OUTPUT_PROJECTION_CONTENT_TYPE_INVALID",
    )
    relations = _compile_relations(
        artifact.get("relations"),
        output=output,
        runtime=runtime,
        upstream_artifacts=upstream_artifacts,
        allowed_source_bindings=require_text_sequence(
            binding.get("input_contract_refs"),
            "OUTPUT_PROJECTION_INPUT_CONTRACTS_INVALID",
        ),
    )
    identity = require_mapping(artifact.get("identity"), "OUTPUT_PROJECTION_IDENTITY_INVALID")
    return GeneratedArtifactWrite(
        project_id=execution.project_id,
        lesson_unit_id=execution.lesson_unit_id,
        node_run_id=execution.node_run_id,
        context_snapshot_id=snapshots.context_snapshot_id,
        prompt_snapshot_id=snapshots.prompt_snapshot_id,
        artifact_key=_compile_artifact_key(identity, execution),
        artifact_type=require_text(artifact.get("artifact_type"), "artifact_type", 80),
        branch_key=require_text(artifact.get("branch_key"), "branch_key", 80),
        content_definition_version_id=definition.content_definition_version_id,
        content=content,
        request_id=request_id,
        relations=relations,
    )


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


def _validate_content_definition_ref(
    definition: RuntimeNodeDefinition, artifact: Mapping[str, Any]
) -> None:
    if not isinstance(cast(object, definition.content_definition_version_id), UUID):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_CONTENT_DEFINITION_INVALID",
            "resolved content definition version ID is invalid",
        )
    provenance_release = definition.content_definition_release_id
    provenance_item = definition.content_definition_item_key
    if provenance_release is None or provenance_item is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_CONTENT_DEFINITION_PROVENANCE_MISSING",
            "resolved content definition is missing release/item provenance",
        )
    if provenance_release != definition.content_release_id:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_CONTENT_DEFINITION_PROVENANCE_INVALID",
            "content definition provenance is bound to another release",
        )
    reference = require_mapping(
        artifact.get("content_definition_ref"),
        "OUTPUT_PROJECTION_CONTENT_DEFINITION_INVALID",
    )
    template = require_mapping(definition.generation_template, "GENERATION_TEMPLATE_INVALID")
    template_spec = require_mapping(template.get("spec", template), "GENERATION_TEMPLATE_INVALID")
    output_ref = require_mapping(
        template_spec.get("output_definition_ref"),
        "GENERATION_TEMPLATE_OUTPUT_REF_INVALID",
    )
    if (
        reference.get("kind") != "content_definition"
        or output_ref.get("kind") != "content_definition"
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_CONTENT_DEFINITION_INVALID",
            "output persistence must resolve a content definition",
        )
    if (
        reference.get("item_key") != output_ref.get("item_key")
        or provenance_item != output_ref.get("item_key")
        or template_spec.get("template_key") != definition.generation_template_key
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_CONTENT_DEFINITION_MISMATCH",
            "artifact persistence points to a different output definition",
        )


def _compile_artifact_key(identity: Mapping[str, Any], execution: WorkflowExecutionContext) -> str:
    strategy = identity.get("strategy")
    if strategy == "project_singleton":
        key = identity.get("artifact_key")
    elif strategy == "lesson_unit_singleton":
        lesson_key = require_text(execution.lesson_key, "lesson_key", 120)
        prefix = require_text(identity.get("artifact_key_prefix"), "artifact_key_prefix", 120)
        key = f"{prefix}:{lesson_key}"
    else:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_IDENTITY_INVALID",
            "artifact identity strategy is unsupported",
        )
    return require_text(key, "artifact_key", 160)


def _compile_relations(
    raw_relations: object,
    *,
    output: Mapping[str, Any],
    runtime: Mapping[str, Any],
    upstream_artifacts: Mapping[str, ArtifactContextVersion],
    allowed_source_bindings: tuple[str, ...],
) -> tuple[GeneratedArtifactRelation, ...]:
    if not isinstance(raw_relations, Sequence) or isinstance(
        raw_relations, (str, bytes, bytearray)
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RELATIONS_INVALID",
            "artifact relations must be an array",
        )
    compiled: list[GeneratedArtifactRelation] = []
    identities: set[tuple[str, str]] = set()
    for raw in cast(Sequence[object], raw_relations):
        relation = _compile_relation(
            raw,
            output=output,
            runtime=runtime,
            upstream_artifacts=upstream_artifacts,
            allowed_source_bindings=allowed_source_bindings,
        )
        source = require_mapping(raw, "OUTPUT_PROJECTION_RELATION_INVALID").get("source_binding")
        identity = (cast(str, source), relation.binding_key)
        if identity in identities:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_RELATION_DUPLICATE",
                "artifact relation declaration is duplicated",
            )
        identities.add(identity)
        compiled.append(relation)
    return tuple(compiled)


def _compile_relation(
    raw: object,
    *,
    output: Mapping[str, Any],
    runtime: Mapping[str, Any],
    upstream_artifacts: Mapping[str, ArtifactContextVersion],
    allowed_source_bindings: tuple[str, ...],
) -> GeneratedArtifactRelation:
    declaration = require_mapping(raw, "OUTPUT_PROJECTION_RELATION_INVALID")
    source = declaration.get("source_binding")
    if (
        not isinstance(source, str)
        or source not in allowed_source_bindings
        or source not in upstream_artifacts
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RELATION_SOURCE_MISSING",
            "relation source binding is not present in runtime context",
        )
    upstream_id = cast(object, upstream_artifacts[source].artifact_version_id)
    if not isinstance(upstream_id, UUID):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RELATION_SOURCE_INVALID",
            "relation source version ID is invalid",
        )
    try:
        relation_type = ArtifactRelationType(cast(str, declaration.get("relation_type")))
    except (TypeError, ValueError) as exc:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RELATION_TYPE_INVALID",
            "relation type is unsupported",
        ) from exc
    if relation_type is ArtifactRelationType.SUPERSEDES:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RELATION_TYPE_INVALID",
            "generated output cannot declare supersedes",
        )
    return GeneratedArtifactRelation(
        from_artifact_version_id=upstream_id,
        relation_type=relation_type,
        binding_key=require_text(declaration.get("binding_key"), "binding_key", 160),
        impact_scope=_compile_impact_scope(
            declaration.get("impact_scope"), output=output, runtime=runtime
        ),
    )


def _compile_impact_scope(
    raw: object,
    *,
    output: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    declaration = require_mapping(raw, "OUTPUT_PROJECTION_IMPACT_SCOPE_INVALID")
    if declaration == {"mode": "all"}:
        return {"mode": "all"}
    expected_keys = {"source": "runtime", "pointer": "/lesson_key"}
    if (
        declaration.get("mode") != "keyed"
        or declaration.get("selector") != "lesson_key"
        or set(declaration) != {"mode", "selector", "keys"}
        or declaration.get("keys") != expected_keys
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_IMPACT_SCOPE_INVALID",
            "keyed impact scope must use the trusted runtime lesson_key",
        )
    key = resolve_projection(declaration["keys"], output=output, item=None, runtime=runtime)
    if type(key) is not str or not key.strip() or key != runtime.get("lesson_key"):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_IMPACT_SCOPE_INVALID",
            "keyed impact scope must resolve to the current lesson_key",
        )
    return {"mode": "keyed", "selector": "lesson_key", "keys": [key]}
