"""Fresh execution input compilation outside the transaction owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.assets.execution_port import SqlAlchemyAssetPort
from apps.api.content_runtime.runtime_port import (
    RuntimeNodeMaterials,
    SqlAlchemyRuntimeDefinitionReader,
)
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    FrozenSnapshotRefs,
    PromptSnapshotPort,
    ReferenceAssetAuthorization,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)

from .materials import collect_context_items, collect_upstream_artifacts
from .prompt_plan import CompiledNodePrompt, compile_node_prompt


@dataclass(frozen=True, slots=True)
class FreshNodeInputs:
    materials: RuntimeNodeMaterials
    compiled: CompiledNodePrompt
    snapshots: FrozenSnapshotRefs
    upstream: dict[str, ArtifactContextVersion]
    runtime_values: dict[str, Any]
    target_authorization: TargetSlotAuthorization | None
    reference_authorization: ReferenceAssetAuthorization | None
    frozen_reference_assets: tuple[dict[str, str], ...]


def compile_fresh_inputs(
    *,
    definitions: SqlAlchemyRuntimeDefinitionReader,
    artifacts: SqlAlchemyArtifactPort,
    assets: SqlAlchemyAssetPort,
    snapshots: PromptSnapshotPort,
    execution: WorkflowExecutionContext,
    node_run_id: UUID,
    model_request_id: str,
    user_id: UUID | None,
    artifact_selection: dict[str, UUID] | None = None,
) -> FreshNodeInputs:
    materials = definitions.resolve_materials(node_run_id)
    binding = materials.definition.node_binding
    upstream = collect_upstream_artifacts(
        artifacts,
        execution,
        binding,
        artifact_selection=artifact_selection,
    )
    context_items = collect_context_items(
        artifacts,
        assets,
        execution,
        binding,
        selected_upstream=upstream if artifact_selection is not None else None,
    )
    compiled = compile_node_prompt(
        definition=materials.definition,
        execution=execution,
        prompt_template=materials.prompt_template,
        output_schema=materials.output_schema,
        context_items=context_items,
        request_id=model_request_id,
        user_id=user_id,
    )
    frozen_snapshots = snapshots.freeze(
        node_run_id,
        context=compiled.context,
        prompt=compiled.prompt,
    )
    reference_auth = assets.freeze_reference_assets(materials.definition, execution)
    frozen_assets = tuple(
        {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
        for asset in (reference_auth.assets if reference_auth is not None else ())
    )
    return FreshNodeInputs(
        materials=materials,
        compiled=compiled,
        snapshots=frozen_snapshots,
        upstream=upstream,
        runtime_values={"reference_assets": list(frozen_assets)} if reference_auth else {},
        target_authorization=assets.authorize_target_slots(materials.definition, execution),
        reference_authorization=reference_auth,
        frozen_reference_assets=frozen_assets,
    )
