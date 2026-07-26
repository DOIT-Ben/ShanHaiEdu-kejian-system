from __future__ import annotations

import pytest

from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from scripts.r1_provider_acceptance import (
    R1AcceptanceLocator,
    R1ProviderAcceptanceError,
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
