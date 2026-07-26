#!/usr/bin/env python3
"""Emit a redacted receipt for one controlled real-Provider R1 golden project."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.intro_selections.models import IntroSelection
from apps.api.jobs.models import GenerationJob
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.projects.models import Project
from apps.api.settings import Settings, get_settings

APPROVED_NODES = {
    "lesson_division": "lesson.division.generate",
    "lesson_plan": "lesson_plan.generate",
    "intro_option_set": "intro.generate_options",
}
FAKE_PROVIDER_NAMES = frozenset(
    {
        "deterministic-fake",
        "fake",
        "r1-rescue-deterministic",
        "test",
    }
)


class R1ProviderAcceptanceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class R1AcceptanceLocator(_StrictModel):
    project_id: UUID
    lesson_unit_id: UUID
    isolation_lesson_unit_id: UUID
    lesson_division_project_id: UUID


class ProviderEvidence(_StrictModel):
    name: str = Field(min_length=1, max_length=80)
    configured_model: str = Field(min_length=1, max_length=160)


class ArtifactEvidence(_StrictModel):
    kind: Literal["lesson_division", "lesson_plan", "intro_option_set"]
    project_id: UUID
    lesson_unit_id: UUID | None
    artifact_id: UUID
    generated_version_id: UUID
    approved_version_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_report_id: UUID
    quality_evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID


class JobEvidence(_StrictModel):
    job_id: UUID
    project_id: UUID
    lesson_unit_id: UUID | None
    node_run_id: UUID
    node_key: Literal[
        "lesson.division.generate",
        "lesson_plan.generate",
        "intro.generate_options",
    ]
    result_artifact_version_id: UUID
    status: Literal["succeeded"]


class UsageEvidence(_StrictModel):
    input_units: dict[str, NonNegativeInt]
    output_units: dict[str, NonNegativeInt]
    actual_cost: Decimal | None
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class AttemptEvidence(_StrictModel):
    attempt_id: UUID
    project_id: UUID
    generation_job_id: UUID
    node_run_id: UUID
    capability: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=80)
    configured_model: str = Field(min_length=1, max_length=160)
    actual_model: str = Field(min_length=1, max_length=160)
    request_id: str = Field(min_length=1, max_length=160)
    provider_request_id: str = Field(min_length=1, max_length=255)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    latency_ms: int = Field(ge=0)
    usage: UsageEvidence


class SelectionEvidence(_StrictModel):
    selection_id: UUID
    artifact_version_id: UUID
    source_approval_id: UUID
    option_key: str = Field(min_length=1, max_length=80)


class IsolationEvidence(_StrictModel):
    lesson_unit_id: UUID
    lesson_plan_artifact_id: UUID
    lesson_plan_version_id: UUID
    lesson_plan_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lesson_plan_job_id: UUID
    lesson_plan_node_run_id: UUID
    intro_artifact_count: Literal[0]
    intro_job_count: Literal[0]


class R1ProviderAcceptanceReceipt(_StrictModel):
    schema_version: Literal[1] = 1
    conclusion: Literal["passed"] = "passed"
    utc: datetime
    project_id: UUID
    lesson_division_project_id: UUID
    lesson_unit_id: UUID
    isolation_lesson_unit_id: UUID
    provider: ProviderEvidence
    artifacts: list[ArtifactEvidence] = Field(min_length=3, max_length=3)
    jobs: list[JobEvidence] = Field(min_length=4, max_length=4)
    attempts: list[AttemptEvidence] = Field(min_length=4, max_length=4)
    selection: SelectionEvidence
    isolation: IsolationEvidence


def validate_controlled_real_provider(
    *,
    actual_provider: str,
    expected_provider: str,
    provider_request_id: str,
) -> None:
    normalized = actual_provider.strip().lower()
    if normalized in FAKE_PROVIDER_NAMES or normalized.startswith(("fake-", "test-")):
        raise R1ProviderAcceptanceError("R1_PROVIDER_EVIDENCE_NOT_REAL")
    if provider_request_id.strip().lower().startswith("fake:"):
        raise R1ProviderAcceptanceError("R1_PROVIDER_EVIDENCE_NOT_REAL")
    if actual_provider != expected_provider:
        raise R1ProviderAcceptanceError("R1_PROVIDER_ROUTE_MISMATCH")


def load_locator(path: Path) -> R1AcceptanceLocator:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return R1AcceptanceLocator.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_LOCATOR_INVALID") from error


def build_receipt(
    session: Session,
    locator: R1AcceptanceLocator,
    *,
    expected_provider: str,
    configured_model: str,
) -> R1ProviderAcceptanceReceipt:
    project = session.get(Project, locator.project_id)
    lesson_division_project = session.get(Project, locator.lesson_division_project_id)
    lesson = session.get(LessonUnit, locator.lesson_unit_id)
    isolation_lesson = session.get(LessonUnit, locator.isolation_lesson_unit_id)
    if project is None or lesson_division_project is None:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_PROJECT_NOT_FOUND")
    if lesson_division_project.organization_id != project.organization_id:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_PROJECT_SCOPE_INVALID")
    if not _lesson_matches(project, lesson) or not _lesson_matches(project, isolation_lesson):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_LESSON_SCOPE_INVALID")
    if lesson is None or isolation_lesson is None or lesson.id == isolation_lesson.id:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_LESSON_SCOPE_INVALID")

    artifact_evidence: list[ArtifactEvidence] = []
    job_evidence: list[JobEvidence] = []
    attempt_evidence: list[AttemptEvidence] = []
    approval_by_kind: dict[str, Approval] = {}
    artifact_by_kind: dict[str, ArtifactEvidence] = {}
    required_facts = (
        (
            "lesson_division",
            lesson_division_project.id,
            None,
            "lesson_division",
            APPROVED_NODES["lesson_division"],
        ),
        (
            "lesson_plan",
            project.id,
            lesson.id,
            "lesson_plan",
            APPROVED_NODES["lesson_plan"],
        ),
        (
            "intro_option_set",
            project.id,
            lesson.id,
            "intro_option_set",
            APPROVED_NODES["intro_option_set"],
        ),
    )
    for kind, fact_project_id, fact_lesson_id, artifact_type, node_key in required_facts:
        artifact, job = _exact_artifact_and_job(
            session,
            project_id=fact_project_id,
            lesson_unit_id=fact_lesson_id,
            artifact_type=artifact_type,
            node_key=node_key,
        )
        artifact_fact, approval = _artifact_evidence(session, artifact, job, kind=kind)
        artifact_evidence.append(artifact_fact)
        artifact_by_kind[kind] = artifact_fact
        approval_by_kind[kind] = approval
        job_evidence.append(_job_evidence(job, node_key=node_key))
        attempt_evidence.append(
            _attempt_evidence(
                session,
                job,
                expected_provider=expected_provider,
                configured_model=configured_model,
            )
        )

    isolation_artifact, isolation_job = _exact_artifact_and_job(
        session,
        project_id=project.id,
        lesson_unit_id=isolation_lesson.id,
        artifact_type="lesson_plan",
        node_key=APPROVED_NODES["lesson_plan"],
    )
    job_evidence.append(_job_evidence(isolation_job, node_key=APPROVED_NODES["lesson_plan"]))
    attempt_evidence.append(
        _attempt_evidence(
            session,
            isolation_job,
            expected_provider=expected_provider,
            configured_model=configured_model,
        )
    )

    selection = _selection_evidence(
        session,
        project_id=project.id,
        lesson_unit_id=lesson.id,
        artifact=artifact_by_kind["intro_option_set"],
        approval=approval_by_kind["intro_option_set"],
    )
    isolation = _isolation_evidence(
        session,
        project.id,
        isolation_lesson.id,
        artifact=isolation_artifact,
        job=isolation_job,
    )
    return R1ProviderAcceptanceReceipt(
        utc=datetime.now(UTC),
        project_id=project.id,
        lesson_division_project_id=lesson_division_project.id,
        lesson_unit_id=lesson.id,
        isolation_lesson_unit_id=isolation_lesson.id,
        provider=ProviderEvidence(name=expected_provider, configured_model=configured_model),
        artifacts=artifact_evidence,
        jobs=job_evidence,
        attempts=attempt_evidence,
        selection=selection,
        isolation=isolation,
    )


def _lesson_matches(project: Project, lesson: LessonUnit | None) -> bool:
    return bool(
        lesson is not None
        and lesson.organization_id == project.organization_id
        and lesson.project_id == project.id
        and lesson.status == "active"
    )


def _exact_artifact_and_job(
    session: Session,
    *,
    project_id: UUID,
    lesson_unit_id: UUID | None,
    artifact_type: str,
    node_key: str,
) -> tuple[Artifact, GenerationJob]:
    artifact_lesson_scope = (
        Artifact.lesson_unit_id.is_(None)
        if lesson_unit_id is None
        else Artifact.lesson_unit_id == lesson_unit_id
    )
    job_lesson_scope = (
        GenerationJob.lesson_unit_id.is_(None)
        if lesson_unit_id is None
        else GenerationJob.lesson_unit_id == lesson_unit_id
    )
    artifacts = list(
        session.scalars(
            select(Artifact).where(
                Artifact.project_id == project_id,
                artifact_lesson_scope,
                Artifact.artifact_type == artifact_type,
                Artifact.deleted_at.is_(None),
            )
        )
    )
    jobs = list(
        session.scalars(
            select(GenerationJob).where(
                GenerationJob.project_id == project_id,
                job_lesson_scope,
                GenerationJob.workflow_node_key == node_key,
                GenerationJob.status == "succeeded",
                GenerationJob.deleted_at.is_(None),
            )
        )
    )
    if len(artifacts) != 1 or len(jobs) != 1:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_EXACT_FACT_CARDINALITY_INVALID")
    return artifacts[0], jobs[0]


def _artifact_evidence(
    session: Session,
    artifact: Artifact,
    job: GenerationJob,
    *,
    kind: str,
) -> tuple[ArtifactEvidence, Approval]:
    if (
        job.project_id is None
        or artifact.organization_id != job.organization_id
        or artifact.project_id != job.project_id
        or artifact.lesson_unit_id != job.lesson_unit_id
    ):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ARTIFACT_SCOPE_INVALID")
    generated = session.get(ArtifactVersion, job.result_artifact_version_id)
    approved = session.get(ArtifactVersion, artifact.current_approved_version_id)
    if generated is None or approved is None or generated.artifact_id != artifact.id:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ARTIFACT_LINEAGE_INVALID")
    if approved.artifact_id != artifact.id:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ARTIFACT_LINEAGE_INVALID")
    report = session.scalar(
        select(ArtifactQualityReport)
        .where(
            ArtifactQualityReport.source_artifact_version_id == approved.id,
            ArtifactQualityReport.conclusion == "passed",
        )
        .order_by(ArtifactQualityReport.created_at.desc())
        .limit(1)
    )
    approval = session.scalar(
        select(Approval)
        .where(Approval.artifact_version_id == approved.id, Approval.action == "approve")
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    if report is None or approval is None:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_APPROVAL_EVIDENCE_MISSING")
    return (
        ArtifactEvidence(
            kind=kind,  # type: ignore[arg-type]
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
            artifact_id=artifact.id,
            generated_version_id=generated.id,
            approved_version_id=approved.id,
            content_hash=approved.content_hash,
            quality_report_id=report.id,
            quality_evidence_hash=report.evidence_hash,
            approval_id=approval.id,
        ),
        approval,
    )


def _job_evidence(job: GenerationJob, *, node_key: str) -> JobEvidence:
    if job.project_id is None or job.node_run_id is None or job.result_artifact_version_id is None:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_JOB_LINEAGE_INVALID")
    return JobEvidence(
        job_id=job.id,
        project_id=job.project_id,
        lesson_unit_id=job.lesson_unit_id,
        node_run_id=job.node_run_id,
        node_key=node_key,  # type: ignore[arg-type]
        result_artifact_version_id=job.result_artifact_version_id,
        status="succeeded",
    )


def _attempt_evidence(
    session: Session,
    job: GenerationJob,
    *,
    expected_provider: str,
    configured_model: str,
) -> AttemptEvidence:
    attempts = list(
        session.scalars(
            select(GenerationAttempt).where(
                GenerationAttempt.generation_job_id == job.id,
                GenerationAttempt.status == "succeeded",
            )
        )
    )
    if len(attempts) != 1:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ATTEMPT_CARDINALITY_INVALID")
    attempt = attempts[0]
    usage = session.scalar(
        select(UsageRecord).where(UsageRecord.generation_attempt_id == attempt.id)
    )
    if (
        usage is None
        or usage.provider_model is None
        or attempt.provider_name is None
        or attempt.provider_model is None
        or attempt.provider_request_id is None
        or attempt.latency_ms is None
        or job.node_run_id is None
    ):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ATTEMPT_EVIDENCE_MISSING")
    if (
        attempt.organization_id != job.organization_id
        or attempt.project_id != job.project_id
        or attempt.node_run_id != job.node_run_id
        or usage.organization_id != attempt.organization_id
        or usage.project_id != attempt.project_id
        or usage.node_run_id != attempt.node_run_id
        or usage.capability != attempt.capability
        or usage.provider_name != attempt.provider_name
    ):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_ATTEMPT_LINEAGE_INVALID")
    validate_controlled_real_provider(
        actual_provider=attempt.provider_name,
        expected_provider=expected_provider,
        provider_request_id=attempt.provider_request_id,
    )
    if attempt.provider_model != configured_model:
        raise R1ProviderAcceptanceError("R1_PROVIDER_MODEL_MISMATCH")
    return AttemptEvidence(
        attempt_id=attempt.id,
        project_id=attempt.project_id,
        generation_job_id=job.id,
        node_run_id=job.node_run_id,
        capability=attempt.capability,
        provider=attempt.provider_name,
        configured_model=attempt.provider_model,
        actual_model=usage.provider_model,
        request_id=attempt.request_id,
        provider_request_id=attempt.provider_request_id,
        request_hash=attempt.request_hash,
        latency_ms=attempt.latency_ms,
        usage=UsageEvidence(
            input_units=usage.input_units_json,
            output_units=usage.output_units_json,
            actual_cost=usage.actual_cost,
            currency=usage.currency,
        ),
    )


def _selection_evidence(
    session: Session,
    *,
    project_id: UUID,
    lesson_unit_id: UUID,
    artifact: ArtifactEvidence,
    approval: Approval,
) -> SelectionEvidence:
    selection = session.scalar(
        select(IntroSelection).where(
            IntroSelection.project_id == project_id,
            IntroSelection.lesson_unit_id == lesson_unit_id,
            IntroSelection.active.is_(True),
        )
    )
    if (
        selection is None
        or selection.artifact_version_id != artifact.approved_version_id
        or selection.source_approval_id != approval.id
    ):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_SELECTION_INVALID")
    return SelectionEvidence(
        selection_id=selection.id,
        artifact_version_id=selection.artifact_version_id,
        source_approval_id=selection.source_approval_id,
        option_key=selection.option_key,
    )


def _isolation_evidence(
    session: Session,
    project_id: UUID,
    lesson_unit_id: UUID,
    *,
    artifact: Artifact,
    job: GenerationJob,
) -> IsolationEvidence:
    intro_artifact_count = session.scalar(
        select(func.count())
        .select_from(Artifact)
        .where(
            Artifact.project_id == project_id,
            Artifact.lesson_unit_id == lesson_unit_id,
            Artifact.artifact_type == "intro_option_set",
            Artifact.deleted_at.is_(None),
        )
    )
    intro_job_count = session.scalar(
        select(func.count())
        .select_from(GenerationJob)
        .where(
            GenerationJob.project_id == project_id,
            GenerationJob.lesson_unit_id == lesson_unit_id,
            GenerationJob.workflow_node_key == APPROVED_NODES["intro_option_set"],
            GenerationJob.deleted_at.is_(None),
        )
    )
    generated = session.get(ArtifactVersion, job.result_artifact_version_id)
    if (
        artifact.project_id != project_id
        or artifact.lesson_unit_id != lesson_unit_id
        or job.project_id != project_id
        or job.lesson_unit_id != lesson_unit_id
        or job.node_run_id is None
        or generated is None
        or generated.artifact_id != artifact.id
    ):
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_LESSON_ISOLATION_FAILED")
    if intro_artifact_count != 0 or intro_job_count != 0:
        raise R1ProviderAcceptanceError("R1_ACCEPTANCE_LESSON_ISOLATION_FAILED")
    return IsolationEvidence(
        lesson_unit_id=lesson_unit_id,
        lesson_plan_artifact_id=artifact.id,
        lesson_plan_version_id=generated.id,
        lesson_plan_content_hash=generated.content_hash,
        lesson_plan_job_id=job.id,
        lesson_plan_node_run_id=job.node_run_id,
        intro_artifact_count=0,
        intro_job_count=0,
    )


def _failure(code: str) -> str:
    return json.dumps(
        {
            "conclusion": "failed",
            "utc": datetime.now(UTC).isoformat(),
            "error_code": code,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def controlled_real_provider_configured(settings: Settings) -> bool:
    secret = os.environ.get(settings.text_provider_secret_env)
    return bool(
        settings.database_url is not None
        and settings.text_provider_name
        and settings.text_provider_base_url
        and settings.text_provider_model
        and secret
        and secret.strip()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a redacted R1 real-Provider receipt")
    parser.add_argument("--locator", required=True, type=Path)
    parser.add_argument("--real", action="store_true")
    args = parser.parse_args()
    if not args.real:
        parser.error("r1-provider-acceptance requires --real")

    settings = get_settings()
    database_url = settings.database_url
    expected_provider = settings.text_provider_name
    configured_model = settings.text_provider_model
    if (
        not controlled_real_provider_configured(settings)
        or database_url is None
        or expected_provider is None
        or configured_model is None
    ):
        print(_failure("R1_PROVIDER_ACCEPTANCE_CONFIG_MISSING"))
        return 1
    try:
        locator = load_locator(args.locator)
        engine = build_engine(database_url.get_secret_value())
        try:
            with build_session_factory(engine)() as session:
                receipt = build_receipt(
                    session,
                    locator,
                    expected_provider=expected_provider,
                    configured_model=configured_model,
                )
        finally:
            engine.dispose()
    except R1ProviderAcceptanceError as error:
        print(_failure(error.code))
        return 1
    print(receipt.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
