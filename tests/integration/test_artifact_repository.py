from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.artifacts.models import ArtifactDraft, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.ids import new_uuid7
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from tests.fakes.content_runtime import ensure_test_authoring_definition
from tests.fakes.identity import seed_test_actor


def create_project(session, actor):
    return ProjectRepository(session, actor).create(
        CreateProjectRequest(title="Fractions", knowledge_point="One half")
    )


def test_active_draft_is_unique_and_autosave_uses_optimistic_lock(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            definition_id = ensure_test_authoring_definition(session, project.id)
            artifact = ArtifactService(session, actor).create(
                project.id,
                artifact_key="lesson-plan:lesson-01",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                content_definition_version_id=definition_id,
                draft_branch="main",
                initial_content={"title": "First"},
                request_id="req-create",
            )
            draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
            assert draft is not None
            initial_version = draft.lock_version

        with session.begin():
            saved = ArtifactService(session, actor).save_draft(
                artifact.id,
                "main",
                expected_lock_version=initial_version,
                content={"title": "Second"},
                request_id="req-save",
            )
        assert saved.lock_version == initial_version + 1
        assert saved.content_json == {"title": "Second"}

        with pytest.raises(ApiError) as conflict:
            with session.begin():
                ArtifactService(session, actor).save_draft(
                    artifact.id,
                    "main",
                    expected_lock_version=initial_version,
                    content={"title": "Stale edit"},
                    request_id="req-stale",
                )
        assert conflict.value.code == "EDIT_CONFLICT"
        assert session.scalar(select(func.count()).select_from(ArtifactDraft)) == 1

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                ArtifactDraft(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    artifact_id=artifact.id,
                    draft_branch="main",
                    content_json={},
                    validation_report_json={"valid": True, "errors": []},
                    based_on_version_id=None,
                    created_by=actor.principal_id,
                    updated_by=actor.principal_id,
                )
            )
            session.flush()


def test_submit_is_deterministic_and_artifact_version_is_database_immutable(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            definition_id = ensure_test_authoring_definition(session, project.id)
            artifact = ArtifactService(session, actor).create(
                project.id,
                artifact_key="lesson-plan:lesson-01",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                content_definition_version_id=definition_id,
                draft_branch="main",
                initial_content={"title": "Stable"},
                request_id="req-create",
            )
            draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
            assert draft is not None
            with pytest.raises(ApiError) as forged_source:
                ArtifactService(session, actor).submit(
                    artifact.id,
                    "main",
                    expected_lock_version=draft.lock_version,
                    source_kind="system",
                    request_id="req-forged-source",
                )
            assert forged_source.value.code == "PERMISSION_DENIED"
            first = ArtifactService(session, actor).submit(
                artifact.id,
                "main",
                expected_lock_version=draft.lock_version,
                source_kind="manual",
                request_id="req-submit-1",
            )

        with session.begin():
            replay = ArtifactService(session, actor).submit(
                artifact.id,
                "main",
                expected_lock_version=draft.lock_version,
                source_kind="manual",
                request_id="req-submit-2",
            )

        assert replay.id == first.id
        assert replay.version_no == 1
        assert replay.content_hash == first.content_hash
        assert session.scalar(select(func.count()).select_from(ArtifactVersion)) == 1

        with pytest.raises(DBAPIError), session.begin_nested():
            stored = session.get(ArtifactVersion, first.id)
            assert stored is not None
            stored.content_json = {"title": "Mutated"}
            session.flush()
