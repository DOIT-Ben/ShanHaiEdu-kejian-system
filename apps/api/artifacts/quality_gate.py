"""Resolve and enforce the published exact quality gate for artifact approval."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifact_quality.approval_port import (
    ArtifactQualityApprovalEvidenceReader,
    QualityApprovalEvidence,
)
from apps.api.artifact_quality.binding import (
    QualityReportBindingError,
    canonical_validator_refs,
    resolve_quality_report_binding,
    validator_set_payload,
)
from apps.api.artifact_quality.contracts import QualitySourceType, ValidatorRef
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.assets.approval_port import LinkedFileApprovalReader
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.workflows.approval_port import WorkflowApprovalReader
from workflow.definition import WorkflowDefinitionError
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY, RegisteredWorkflow


class ArtifactQualityGateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DeclaredArtifactQualityGate:
    validate_node_key: str
    validator_refs: tuple[ValidatorRef, ...]
    validator_set_hash: str
    accepted_conclusions: tuple[str, ...]
    source_binding: str


@dataclass(frozen=True, slots=True)
class ApprovalQualitySource:
    source_type: QualitySourceType
    version_id: UUID
    content_hash: str


def resolve_declared_quality_gate(
    registered: RegisteredWorkflow,
    content_definition_key: str,
) -> DeclaredArtifactQualityGate | None:
    """Resolve only immutable v2 declarations; legacy bindings fail closed."""
    if not registered.supports_output_projection:
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_UNDECLARED",
            "the fixed workflow has no versioned artifact quality declaration",
        )
    output = registered.output_definition_index.get(content_definition_key)
    if output is None:
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_UNDECLARED",
            "the artifact output has no versioned quality declaration",
        )
    if output.quality_requirement_mode == "none":
        return None
    if (
        output.quality_requirement_mode != "reports"
        or output.quality_validate_node_key is None
        or output.quality_gate_node_key is None
        or output.quality_source_binding not in {"artifact", "linked_file_asset"}
        or not output.quality_report_refs
        or not output.quality_validator_refs
    ):
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_INVALID",
            "the fixed workflow artifact quality declaration is incomplete",
        )
    try:
        report_binding = resolve_quality_report_binding(
            registered,
            output.quality_validate_node_key,
        )
    except QualityReportBindingError as exc:
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_INVALID",
            "the fixed quality report binding is invalid",
        ) from exc
    declared_refs = canonical_validator_refs(
        tuple(ValidatorRef(*identity) for identity in output.quality_validator_refs)
    )
    if declared_refs != report_binding.validator_refs or report_binding.validator_set_hash == "":
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_INVALID",
            "the fixed workflow artifact quality declaration is inconsistent",
        )
    accepted = _accepted_conclusions(registered, output.quality_gate_node_key)
    return DeclaredArtifactQualityGate(
        validate_node_key=output.quality_validate_node_key,
        validator_refs=report_binding.validator_refs,
        validator_set_hash=report_binding.validator_set_hash,
        accepted_conclusions=accepted,
        source_binding=output.quality_source_binding,
    )


class ArtifactQualityApprovalGuard:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._actor = actor
        self._reports = ArtifactQualityApprovalEvidenceReader(session, actor)
        self._linked_files = LinkedFileApprovalReader(session, actor)
        self._definitions = ContentDefinitionApprovalReader(session)
        self._workflows = WorkflowApprovalReader(session)

    def require_evidence(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        *,
        content_release_id: UUID,
        workflow_definition_version_id: UUID,
    ) -> dict[str, str]:
        definition_key = self._definitions.definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=content_release_id,
        )
        if definition_key is None:
            raise self._invalid_gate("the artifact content definition is outside its fixed release")
        graph = self._workflows.published_graph(
            workflow_definition_version_id,
        )
        if graph is None:
            raise self._invalid_gate("the fixed workflow definition is unavailable")
        try:
            registered = BUILTIN_WORKFLOW_REGISTRY.load(graph)
            gate = resolve_declared_quality_gate(registered, definition_key)
        except (ArtifactQualityGateError, WorkflowDefinitionError, TypeError) as exc:
            raise self._invalid_gate(str(exc)) from exc
        if gate is None:
            return {}
        source = self._approval_source(artifact, version, gate)
        report = self._reports.find_exact(
            project_id=artifact.project_id,
            source_type=source.source_type,
            source_version_id=source.version_id,
            workflow_definition_version_id=workflow_definition_version_id,
            validator_set_hash=gate.validator_set_hash,
        )
        if report is None:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_QUALITY_REQUIRED",
                message="The current submitted artifact version has no exact quality report.",
            )
        if report.conclusion not in gate.accepted_conclusions:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_QUALITY_FAILED",
                message="The current submitted artifact version did not pass its quality gate.",
            )
        self._require_exact_report(
            report,
            artifact=artifact,
            version=version,
            source=source,
            content_release_id=content_release_id,
            workflow_definition_version_id=workflow_definition_version_id,
            gate=gate,
        )
        evidence = {
            "report_id": str(report.report_id),
            "evidence_hash": report.evidence_hash,
        }
        if source.source_type == "asset":
            evidence.update(
                source_type="asset",
                source_file_asset_version_id=str(source.version_id),
                source_content_hash=source.content_hash,
            )
        return evidence

    def _require_exact_report(
        self,
        report: QualityApprovalEvidence,
        *,
        artifact: Artifact,
        version: ArtifactVersion,
        source: ApprovalQualitySource,
        content_release_id: UUID,
        workflow_definition_version_id: UUID,
        gate: DeclaredArtifactQualityGate,
    ) -> None:
        node = self._workflows.validate_node_fact(report.validate_node_run_id)
        if node is None:
            raise _invalid_report()
        if (
            report.organization_id != self._actor.organization_id
            or report.organization_id != artifact.organization_id
            or report.project_id != artifact.project_id
            or report.lesson_unit_id != artifact.lesson_unit_id
            or report.source_type != source.source_type
            or report.source_artifact_version_id
            != (version.id if source.source_type == "artifact" else None)
            or report.source_file_asset_version_id
            != (source.version_id if source.source_type == "asset" else None)
            or report.source_content_hash != source.content_hash
            or report.content_release_id != content_release_id
            or report.workflow_definition_version_id != workflow_definition_version_id
            or report.validator_set_hash != gate.validator_set_hash
            or report.validator_set
            != tuple(dict(item) for item in validator_set_payload(gate.validator_refs))
            or node.organization_id != self._actor.organization_id
            or node.node_key != gate.validate_node_key
            or node.status != NodeStatus.APPROVED.value
            or node.project_id != artifact.project_id
            or node.lesson_unit_id != artifact.lesson_unit_id
            or node.content_release_id != content_release_id
            or node.workflow_definition_version_id != workflow_definition_version_id
        ):
            raise _invalid_report()

    def _approval_source(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        gate: DeclaredArtifactQualityGate,
    ) -> ApprovalQualitySource:
        if gate.source_binding == "artifact":
            return ApprovalQualitySource(
                source_type="artifact",
                version_id=version.id,
                content_hash=version.content_hash,
            )
        file_version_id = _uuid_value(version.content_json.get("file_asset_version_id"))
        fact = self._linked_files.current_pptx(
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
            file_asset_version_id=file_version_id,
        )
        if fact is None or (
            version.content_json.get("mime_type") != fact.mime_type
            or version.content_json.get("size_bytes") != fact.size_bytes
            or version.content_json.get("sha256") != fact.sha256
            or version.content_json.get("page_count") != fact.page_count
        ):
            raise _invalid_report()
        return ApprovalQualitySource(
            source_type="asset",
            version_id=fact.file_asset_version_id,
            content_hash=fact.sha256,
        )

    @staticmethod
    def _invalid_gate(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="ARTIFACT_QUALITY_GATE_INVALID",
            message=f"The artifact quality gate is invalid: {message}.",
        )

def _accepted_conclusions(
    registered: RegisteredWorkflow,
    gate_node_key: str,
) -> tuple[str, ...]:
    gate_node = registered.node_by_key.get(gate_node_key)
    requirement = gate_node.binding.get("quality_requirement") if gate_node is not None else None
    if not isinstance(requirement, Mapping):
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_INVALID",
            "the fixed human gate has no quality requirement",
        )
    values = cast(Mapping[str, Any], requirement)
    accepted = values.get("accepted_conclusions")
    if accepted != ["passed"] and accepted != ("passed",):
        raise ArtifactQualityGateError(
            "ARTIFACT_QUALITY_GATE_INVALID",
            "the fixed human gate has an unsupported accepted conclusion",
        )
    return ("passed",)


def _uuid_value(value: object) -> UUID:
    try:
        if type(value) is not str:
            raise ValueError("UUID text is required")
        return UUID(value)
    except ValueError as exc:
        raise _invalid_report() from exc


def _invalid_report() -> ApiError:
    return ApiError(
        status_code=409,
        code="ARTIFACT_QUALITY_REPORT_INVALID",
        message="The artifact quality report does not match the fixed approval context.",
    )
