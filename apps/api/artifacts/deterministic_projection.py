"""Narrow output projection used by trusted deterministic executors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.domain import ArtifactRelationType
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.content_runtime.deterministic_port import DeterministicNodeDefinition
from apps.api.identity.context import ActorContext
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    require_mapping,
    require_text,
    validate_artifact_declaration,
)


class DeterministicProjectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def compile_deterministic_identity(
    definition: DeterministicNodeDefinition,
    execution: WorkflowExecutionContext,
) -> tuple[str, str, str]:
    try:
        binding = require_mapping(definition.node_binding, "PPT_RUNTIME_BINDING_INVALID")
        persistence = require_mapping(
            binding.get("output_persistence"),
            "PPT_RUNTIME_OUTPUT_PERSISTENCE_INVALID",
        )
        artifact = require_mapping(
            persistence.get("artifact"),
            "PPT_RUNTIME_OUTPUT_PERSISTENCE_INVALID",
        )
        validate_artifact_declaration(binding, artifact)
        _require_output_definition(definition, artifact)
        identity = require_mapping(
            artifact.get("identity"),
            "PPT_RUNTIME_ARTIFACT_IDENTITY_INVALID",
        )
        if identity.get("strategy") != "lesson_unit_singleton":
            raise _error(
                "PPT_RUNTIME_ARTIFACT_IDENTITY_INVALID",
                "the PPT artifact identity must be lesson-scoped",
            )
        prefix = require_text(identity.get("artifact_key_prefix"), "artifact_key_prefix", 79)
        lesson_key = require_text(execution.lesson_key, "lesson_key", 80)
        return (
            f"{prefix}:{lesson_key}",
            require_text(artifact.get("artifact_type"), "artifact_type", 80),
            require_text(artifact.get("branch_key"), "branch_key", 80),
        )
    except OutputProjectionError as exc:
        raise _error(exc.code, str(exc)) from exc


def persist_deterministic_relations(
    session: Session,
    actor: ActorContext,
    definition: DeterministicNodeDefinition,
    execution: WorkflowExecutionContext,
    inputs: Mapping[str, ArtifactContextVersion],
    target_version_id: UUID,
) -> None:
    persistence = _mapping(definition.node_binding.get("output_persistence"))
    artifact = _mapping(persistence.get("artifact"))
    raw = artifact.get("relations")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise _error("PPT_RUNTIME_RELATIONS_INVALID", "artifact relations are invalid")
    service = ArtifactRelationService(session, actor)
    for item in cast(Sequence[object], raw):
        relation = _mapping(item)
        source_ref = relation.get("source_binding")
        source = inputs.get(source_ref) if isinstance(source_ref, str) else None
        if source is None or source.project_id != execution.project_id:
            raise _error(
                "PPT_RUNTIME_RELATION_SOURCE_INVALID",
                "an exact deterministic relation source is missing",
            )
        try:
            relation_type = ArtifactRelationType(cast(str, relation.get("relation_type")))
        except (TypeError, ValueError) as exc:
            raise _error(
                "PPT_RUNTIME_RELATIONS_INVALID",
                "a deterministic relation type is invalid",
            ) from exc
        service.add(
            from_version_id=source.artifact_version_id,
            to_version_id=target_version_id,
            relation_type=relation_type.value,
            binding_key=_text(relation.get("binding_key")),
            impact_scope=dict(_mapping(relation.get("impact_scope"))),
        )


def _require_output_definition(
    definition: DeterministicNodeDefinition,
    artifact: Mapping[str, Any],
) -> None:
    reference = require_mapping(
        artifact.get("content_definition_ref"),
        "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
    )
    if reference != {
        "item_key": definition.content_definition_key,
        "kind": "content_definition",
    }:
        raise _error(
            "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
            "the deterministic artifact points to another output definition",
        )


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error("PPT_RUNTIME_BINDING_INVALID", "a deterministic binding is invalid")
    return cast(Mapping[str, Any], value)


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise _error("PPT_RUNTIME_BINDING_INVALID", "a deterministic binding text is invalid")
    return value


def _error(code: str, message: str) -> DeterministicProjectionError:
    return DeterministicProjectionError(code, message)
