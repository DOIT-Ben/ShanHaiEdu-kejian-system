"""SQLAlchemy transaction owner for artifact quality validation."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.binding import (
    QualityReportBinding,
    resolve_quality_report_binding,
    validator_set_payload,
)
from apps.api.artifact_quality.contracts import (
    ArtifactQualityReportResult,
    ArtifactQualityTransaction,
    ArtifactQualityTransactionFactory,
    QualityConclusion,
    QualitySource,
    QualityValidationContext,
    ValidatorOutcome,
)
from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.payloads import canonical_hash, plain_json
from apps.api.artifact_quality.repository import ArtifactQualityReportRepository
from apps.api.artifact_quality.source_resolver import resolve_quality_source
from apps.api.artifact_quality.supporting_inputs import resolve_quality_supporting_inputs
from apps.api.artifacts.quality_port import SqlAlchemyArtifactQualitySourcePort
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from apps.api.workflows.quality_port import SqlAlchemyQualityWorkflowPort
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


class ArtifactQualityTransactionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyArtifactQualityTransactionFactory(ArtifactQualityTransactionFactory):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        actor: ActorContext,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._actor = actor
        self._fault_injector = fault_injector or _ignore_fault_stage

    @contextmanager
    def begin(self) -> Generator[ArtifactQualityTransaction]:
        session = self._session_factory()
        try:
            with session.begin():
                yield SqlAlchemyArtifactQualityTransaction(
                    session,
                    self._actor,
                    fault_injector=self._fault_injector,
                )
        finally:
            session.close()


class SqlAlchemyArtifactQualityTransaction(ArtifactQualityTransaction):
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        fault_injector: Callable[[str], None],
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = SqlAlchemyWorkflowExecutionPort(session, actor)
        self._quality_workflow = SqlAlchemyQualityWorkflowPort(session, actor)
        self._artifact_sources = SqlAlchemyArtifactQualitySourcePort(session, actor)
        self._asset_sources = SqlAlchemyAssetQualitySourcePort(session, actor)
        self._reports = ArtifactQualityReportRepository(session, actor)
        self._fault_injector = fault_injector

    def prepare(self, node_run_id: UUID) -> QualityValidationContext:
        execution = self._workflow.require_context(
            node_run_id,
            for_update=True,
            lock_run=False,
        )
        registered = BUILTIN_WORKFLOW_REGISTRY.load(
            dict(self._workflow.published_graph(execution.workflow_definition_version_id))
        )
        binding = resolve_quality_report_binding(registered, execution.node_key)
        source_input = self._quality_workflow.require_source_input(
            node_run_id,
            binding.source_input_ref,
        )
        source = resolve_quality_source(
            execution,
            binding,
            source_input,
            self._artifact_sources,
            self._asset_sources,
        )
        if source.content_hash != source_input.content_hash:
            raise ArtifactQualityTransactionError(
                "QUALITY_SOURCE_HASH_MISMATCH",
                "the frozen source hash does not match the exact artifact version",
            )
        supporting_inputs = self._resolve_supporting_inputs(execution, binding, node_run_id)
        existing = self._reports.get_for_node(node_run_id)
        result = None if existing is None else _report_result(existing)
        if existing is not None:
            self._require_same_fixed_identity(
                existing,
                execution,
                source,
                source.content_hash,
                binding,
            )
        else:
            self._workflow.start(node_run_id)
        return QualityValidationContext(
            organization_id=execution.organization_id,
            project_id=execution.project_id,
            lesson_unit_id=execution.lesson_unit_id,
            content_release_id=execution.content_release_id,
            workflow_definition_version_id=execution.workflow_definition_version_id,
            node_run_id=node_run_id,
            source_type=source.source_type,
            source_id=source.source_id,
            source_version_id=source.source_version_id,
            source_content_hash=source.content_hash,
            source_content=source.content,
            validator_refs=binding.validator_refs,
            validator_set_hash=binding.validator_set_hash,
            supporting_inputs=supporting_inputs,
            existing_result=result,
        )

    def _resolve_supporting_inputs(
        self,
        execution: WorkflowExecutionContext,
        binding: QualityReportBinding,
        node_run_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        return resolve_quality_supporting_inputs(
            execution,
            binding,
            node_run_id,
            self._quality_workflow,
            self._artifact_sources,
            self._asset_sources,
        )

    def complete(
        self,
        context: QualityValidationContext,
        *,
        conclusion: QualityConclusion,
        outcomes: tuple[ValidatorOutcome, ...],
    ) -> ArtifactQualityReportResult:
        expected_conclusion: QualityConclusion = (
            "passed" if all(outcome.passed for outcome in outcomes) else "failed"
        )
        if conclusion != expected_conclusion:
            raise ArtifactQualityTransactionError(
                "QUALITY_CONCLUSION_MISMATCH",
                "quality conclusion does not match validator outcomes",
            )
        findings, evidence_hash = _validated_outcome_payload(context, outcomes)
        self._lock_identity(context)
        existing = self._reports.get_exact(
            project_id=context.project_id,
            source_type=context.source_type,
            source_version_id=context.source_version_id,
            workflow_definition_version_id=context.workflow_definition_version_id,
            validator_set_hash=context.validator_set_hash,
        )
        if existing is not None:
            return self._replay_or_conflict(existing, context, conclusion, findings, evidence_hash)
        report = ArtifactQualityReport(
            id=new_uuid7(),
            organization_id=context.organization_id,
            project_id=context.project_id,
            lesson_unit_id=context.lesson_unit_id,
            source_type=context.source_type,
            source_artifact_version_id=(
                context.source_version_id if context.source_type == "artifact" else None
            ),
            source_file_asset_version_id=(
                context.source_version_id if context.source_type == "asset" else None
            ),
            source_content_hash=context.source_content_hash,
            content_release_id=context.content_release_id,
            workflow_definition_version_id=context.workflow_definition_version_id,
            validate_node_run_id=context.node_run_id,
            validator_set_json=validator_set_payload(context.validator_refs),
            validator_set_hash=context.validator_set_hash,
            conclusion=conclusion,
            findings_json=findings,
            evidence_hash=evidence_hash,
            created_by=self._actor.principal_id,
        )
        self._session.add(report)
        self._session.flush()
        self._fault_injector("after_report")
        self._quality_workflow.complete(context.node_run_id, passed=conclusion == "passed")
        self._fault_injector("after_terminal")
        self._append_event(report)
        self._fault_injector("after_event")
        return _report_result(report)

    def fail_technical(self, context: QualityValidationContext, *, code: str) -> None:
        self._workflow.terminalize(context.node_run_id, code=code, cancelled=False)
        self._fault_injector("after_terminal")
        EventWriter(self._session, context.organization_id).append(
            project_id=context.project_id,
            event_type="artifact.quality_validation.technical_failed",
            resource=EventResource(type="node_run", id=context.node_run_id),
            payload={
                "source_type": context.source_type,
                "source_version_id": str(context.source_version_id),
                "workflow_definition_version_id": str(context.workflow_definition_version_id),
                "validator_set_hash": context.validator_set_hash,
                "error_code": code,
            },
            request_id=None,
        )
        self._fault_injector("after_event")

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> None:
        routing = self._quality_workflow.fail_prepare(node_run_id, code=code)
        if routing is None:
            return
        self._fault_injector("after_terminal")
        EventWriter(self._session, routing.organization_id).append(
            project_id=routing.project_id,
            event_type="artifact.quality_validation.technical_failed",
            resource=EventResource(type="node_run", id=node_run_id),
            payload={
                "content_release_id": str(routing.content_release_id),
                "workflow_definition_version_id": str(routing.workflow_definition_version_id),
                "error_code": code,
                "failure_stage": "prepare",
            },
            request_id=None,
        )
        self._fault_injector("after_event")

    def _lock_identity(self, context: QualityValidationContext) -> None:
        identity = ":".join(
            (
                context.source_type,
                str(context.source_version_id),
                str(context.workflow_definition_version_id),
                context.validator_set_hash,
            )
        )
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": identity},
        )

    @staticmethod
    def _require_same_fixed_identity(
        existing: ArtifactQualityReport,
        execution: WorkflowExecutionContext,
        source: QualitySource,
        source_hash: str,
        binding: QualityReportBinding,
    ) -> None:
        if (
            existing.organization_id != execution.organization_id
            or existing.project_id != execution.project_id
            or existing.lesson_unit_id != execution.lesson_unit_id
            or existing.content_release_id != execution.content_release_id
            or existing.workflow_definition_version_id != execution.workflow_definition_version_id
            or existing.source_type != source.source_type
            or _source_version_id(existing) != source.source_version_id
            or existing.source_content_hash != source_hash
            or existing.validator_set_hash != binding.validator_set_hash
            or existing.validator_set_json != validator_set_payload(binding.validator_refs)
        ):
            raise ArtifactQualityTransactionError(
                "QUALITY_REPORT_IDEMPOTENCY_CONFLICT",
                "the validate node already owns another quality report identity",
            )

    @staticmethod
    def _replay_or_conflict(
        existing: ArtifactQualityReport,
        context: QualityValidationContext,
        conclusion: QualityConclusion,
        findings: list[dict[str, Any]],
        evidence_hash: str,
    ) -> ArtifactQualityReportResult:
        if (
            existing.validate_node_run_id == context.node_run_id
            and existing.source_type == context.source_type
            and _source_version_id(existing) == context.source_version_id
            and existing.source_content_hash == context.source_content_hash
            and existing.content_release_id == context.content_release_id
            and existing.conclusion == conclusion
            and existing.findings_json == findings
            and existing.evidence_hash == evidence_hash
        ):
            return _report_result(existing)
        raise ArtifactQualityTransactionError(
            "QUALITY_REPORT_IDEMPOTENCY_CONFLICT",
            "the quality report identity already has another payload",
        )

    def _append_event(self, report: ArtifactQualityReport) -> None:
        EventWriter(self._session, report.organization_id).append(
            project_id=report.project_id,
            event_type=f"artifact.quality_report.{report.conclusion}",
            resource=EventResource(type="artifact_quality_report", id=report.id),
            payload={
                "source_type": report.source_type,
                "source_version_id": str(_source_version_id(report)),
                "source_content_hash": report.source_content_hash,
                "content_release_id": str(report.content_release_id),
                "workflow_definition_version_id": str(report.workflow_definition_version_id),
                "validate_node_run_id": str(report.validate_node_run_id),
                "validator_set_hash": report.validator_set_hash,
                "conclusion": report.conclusion,
                "evidence_hash": report.evidence_hash,
            },
            request_id=None,
        )


def _validated_outcome_payload(
    context: QualityValidationContext,
    outcomes: tuple[ValidatorOutcome, ...],
) -> tuple[list[dict[str, Any]], str]:
    if tuple(outcome.validator for outcome in outcomes) != context.validator_refs:
        raise ArtifactQualityTransactionError(
            "QUALITY_VALIDATOR_SET_MISMATCH",
            "validator outcomes do not match the fixed validator set",
        )
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for outcome in outcomes:
        validator = asdict(outcome.validator)
        findings.extend(
            {"validator": validator, "finding": plain_json(item)} for item in outcome.findings
        )
        evidence.append({"validator": validator, "evidence": plain_json(outcome.evidence)})
    return findings, canonical_hash(evidence)


def _report_result(report: ArtifactQualityReport) -> ArtifactQualityReportResult:
    return ArtifactQualityReportResult(
        report_id=report.id,
        node_run_id=report.validate_node_run_id,
        conclusion=cast(QualityConclusion, report.conclusion),
    )


def _source_version_id(report: ArtifactQualityReport) -> UUID:
    value = (
        report.source_artifact_version_id
        if report.source_type == "artifact"
        else report.source_file_asset_version_id
    )
    if value is None:
        raise ArtifactQualityTransactionError(
            "QUALITY_REPORT_SOURCE_INVALID",
            "the persisted quality report has no exact source version",
        )
    return value


def _ignore_fault_stage(_stage: str) -> None:
    return None
