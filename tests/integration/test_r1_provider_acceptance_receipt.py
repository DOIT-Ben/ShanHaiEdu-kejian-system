from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from scripts.r1_provider_acceptance import (
    R1AcceptanceLocator,
    R1ProviderAcceptanceError,
    _attempt_evidence,  # pyright: ignore[reportPrivateUsage]
    _exact_artifact_and_job,  # pyright: ignore[reportPrivateUsage]
    build_receipt,
)
from tests.integration.intro_selection_support import prepare_approved_option_set


async def test_receipt_fails_closed_without_exact_generation_jobs_and_attempts(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    prepared = await prepare_approved_option_set(factory)
    isolation_lesson_id = new_uuid7()
    try:
        with factory() as session, session.begin():
            source = session.get(LessonUnit, prepared.lesson_unit_id)
            assert source is not None
            session.add(
                LessonUnit(
                    id=isolation_lesson_id,
                    organization_id=source.organization_id,
                    project_id=source.project_id,
                    lesson_key="R1-PROVIDER-ISOLATION-002",
                    position=2,
                    title="R1 Provider isolation",
                    scope_summary="Exact isolation fact for the acceptance receipt.",
                    objective_summary="No generated artifacts or jobs may cross into this lesson.",
                    estimated_minutes=40,
                    source_division_version_id=source.source_division_version_id,
                    status="active",
                    created_by=prepared.actor.principal_id,
                    updated_by=prepared.actor.principal_id,
                )
            )

        with factory() as session, pytest.raises(R1ProviderAcceptanceError) as captured:
            build_receipt(
                session,
                R1AcceptanceLocator(
                    project_id=prepared.project_id,
                    lesson_unit_id=prepared.lesson_unit_id,
                    isolation_lesson_unit_id=isolation_lesson_id,
                    lesson_division_project_id=prepared.project_id,
                ),
                expected_provider="controlled-provider",
                configured_model="controlled-model",
            )

        assert captured.value.code == "R1_ACCEPTANCE_EXACT_FACT_CARDINALITY_INVALID"
    finally:
        engine.dispose()


async def test_receipt_rejects_an_extra_failed_job_in_the_exact_scope(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    prepared = await prepare_approved_option_set(factory)
    try:
        with factory() as session, session.begin():
            for status in ("succeeded", "failed"):
                session.add(
                    GenerationJob(
                        id=new_uuid7(),
                        organization_id=prepared.actor.organization_id,
                        project_id=prepared.project_id,
                        lesson_unit_id=prepared.lesson_unit_id,
                        workflow_node_key="intro.generate_options",
                        result_artifact_version_id=(
                            prepared.version_id if status == "succeeded" else None
                        ),
                        job_type="workflow.node",
                        status=status,
                        progress_percent=100,
                        error_code=None if status == "succeeded" else "MODEL_TIMEOUT",
                        priority=100,
                        created_by=prepared.actor.principal_id,
                        updated_by=prepared.actor.principal_id,
                    )
                )

        with factory() as session, pytest.raises(R1ProviderAcceptanceError) as captured:
            _exact_artifact_and_job(
                session,
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
                artifact_type="intro_option_set",
                node_key="intro.generate_options",
            )

        assert captured.value.code == "R1_ACCEPTANCE_EXACT_FACT_CARDINALITY_INVALID"
    finally:
        engine.dispose()


async def test_receipt_rejects_an_extra_failed_attempt_for_an_exact_job(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    prepared = await prepare_approved_option_set(factory)
    now = datetime.now(UTC)
    job_id = new_uuid7()
    try:
        with factory() as session, session.begin():
            session.add(
                GenerationJob(
                    id=job_id,
                    organization_id=prepared.actor.organization_id,
                    project_id=prepared.project_id,
                    node_run_id=prepared.select_node_run_id,
                    lesson_unit_id=prepared.lesson_unit_id,
                    workflow_node_key="intro.generate_options",
                    result_artifact_version_id=prepared.version_id,
                    job_type="workflow.node",
                    status="succeeded",
                    progress_percent=100,
                    priority=100,
                    created_by=prepared.actor.principal_id,
                    updated_by=prepared.actor.principal_id,
                )
            )
            for attempt_no, status in ((1, "succeeded"), (2, "failed")):
                attempt_id = new_uuid7()
                request_id = f"receipt-attempt-{attempt_no}-{attempt_id}"
                session.add(
                    GenerationAttempt(
                        id=attempt_id,
                        organization_id=prepared.actor.organization_id,
                        project_id=prepared.project_id,
                        node_run_id=prepared.select_node_run_id,
                        generation_job_id=job_id,
                        attempt_no=attempt_no,
                        request_id=request_id,
                        capability="text.structured.creative_education",
                        operation_kind="text_generate",
                        provider_name="controlled-provider",
                        provider_model="controlled-model",
                        route_reason="configured_primary",
                        status=status,
                        request_hash=f"{attempt_no}" * 64,
                        provider_request_id=f"provider-{request_id}",
                        submitted_at=now,
                        finished_at=now,
                        error_code=None if status == "succeeded" else "MODEL_TIMEOUT",
                        error_details_json={},
                        latency_ms=100,
                    )
                )
                session.add(
                    UsageRecord(
                        id=new_uuid7(),
                        organization_id=prepared.actor.organization_id,
                        user_id=prepared.actor.user_id,
                        project_id=prepared.project_id,
                        node_run_id=prepared.select_node_run_id,
                        generation_attempt_id=attempt_id,
                        capability="text.structured.creative_education",
                        provider_name="controlled-provider",
                        provider_model="controlled-model",
                        input_units_json={"prompt_tokens": 10},
                        output_units_json={"completion_tokens": 20, "total_tokens": 30},
                        pricing_version=None,
                        estimated_cost=Decimal("0.001"),
                        actual_cost=Decimal("0.001"),
                        currency="USD",
                        latency_ms=100,
                    )
                )

        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job is not None
            with pytest.raises(R1ProviderAcceptanceError) as captured:
                _attempt_evidence(
                    session,
                    job,
                    expected_provider="controlled-provider",
                    configured_model="controlled-model",
                )

        assert captured.value.code == "R1_ACCEPTANCE_ATTEMPT_CARDINALITY_INVALID"
    finally:
        engine.dispose()
