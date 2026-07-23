from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from apps.api.artifacts.authoring_provision import ArtifactAuthoringProvisionPort
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import system_actor
from apps.api.ids import new_uuid7
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from tests.fakes.identity import seed_test_actor

ROOT = Path(__file__).resolve().parents[2]


def test_material_scope_reaches_approved_version_through_artifact_interfaces(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Numbers 1 to 5", knowledge_point="1 to 5")
        )
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id
                == published.content_package_version_id,
                ContentDefinitionVersion.definition_key == "material.scope_review.output",
            )
        )
        assert definition is not None

        service = ArtifactService(session, actor)
        artifact = service.create(
            project.id,
            artifact_key="material-scope",
            artifact_type="material_scope",
            branch_key="project",
            content_definition_version_id=definition.id,
            draft_branch="main",
            initial_content={
                "knowledge_point": "1 to 5",
                "knowledge_boundary": {
                    "allowed": ["Recognize and order the numbers 1 to 5"],
                    "forbidden": ["Addition and subtraction"],
                },
                "approved_evidence_keys": ["PAGE-3", "PAGE-4", "PAGE-5"],
                "duration_minutes": 40,
                "lesson_count_mode": "auto",
            },
            request_id="issue-118-material-scope-create",
        )
        draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
        assert draft is not None
        locked_fields = {
            "source_material_id": str(new_uuid7()),
            "material_parse_version_id": str(new_uuid7()),
            "page_start": 3,
            "page_end": 5,
        }

        with pytest.raises(ApiError) as user_denied:
            ArtifactAuthoringProvisionPort(session, actor).provision_initial_locked_fields(
                artifact_id=artifact.id,
                draft_branch="main",
                expected_lock_version=draft.lock_version,
                fields=locked_fields,
            )
        assert user_denied.value.code == "PERMISSION_DENIED"

        provisioned = ArtifactAuthoringProvisionPort(
            session,
            system_actor(actor.organization_id),
        ).provision_initial_locked_fields(
            artifact_id=artifact.id,
            draft_branch="main",
            expected_lock_version=draft.lock_version,
            fields=locked_fields,
        )
        assert provisioned.validation_report_json["valid"] is True

        version = service.submit(
            artifact.id,
            "main",
            expected_lock_version=provisioned.lock_version,
            source_kind="manual",
            request_id="issue-118-material-scope-submit",
        )
        approval = service.review(
            version.id,
            action="approve",
            comment="Approved material scope",
            request_id="issue-118-material-scope-approve",
        )

        assert approval.artifact_version_id == version.id
        assert version.content_json == {
            **draft.content_json,
            **locked_fields,
        }
        assert artifact.current_approved_version_id == version.id
        assert artifact.status == "approved"
