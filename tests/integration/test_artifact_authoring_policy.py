from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import select

from apps.api.artifacts.authoring_provision import (
    ArtifactAuthoringProvisionPort,
    GeneratedDraftRequest,
    RepeatableItemProvision,
)
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.content_runtime.registry import BUILTIN_CONTENT_DEFINITION_VERSION_ID
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import system_actor
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from tests.fakes.identity import seed_test_actor
from tests.integration.test_node_execution_runtime import _seed_runtime

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_seed_mutation_fails_closed(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = _create_project(session, actor, "Legacy authoring")

        with pytest.raises(ApiError) as caught:
            ArtifactService(session, actor).create(
                project.id,
                artifact_key="legacy",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                content_definition_version_id=BUILTIN_CONTENT_DEFINITION_VERSION_ID,
                draft_branch="main",
                initial_content={"title": "Blocked"},
                request_id="issue-131-legacy",
            )

        assert caught.value.code == "AUTHORING_POLICY_UNAVAILABLE"


def test_current_policy_allows_editable_fields_and_rejects_locked_fields(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, project, definition = _seed_current_project(session)
        service = ArtifactService(session, actor)

        artifact = service.create(
            project.id,
            artifact_key="editable",
            artifact_type="lesson_division",
            branch_key="project",
            content_definition_version_id=definition.id,
            draft_branch="main",
            initial_content={"lesson_count": 2},
            request_id="issue-131-editable",
        )
        assert artifact.id is not None

        with pytest.raises(ApiError) as caught:
            service.create(
                project.id,
                artifact_key="locked",
                artifact_type="lesson_division",
                branch_key="project",
                content_definition_version_id=definition.id,
                draft_branch="main",
                initial_content={"division_key": "forged", "lesson_count": 2},
                request_id="issue-131-locked",
            )

        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"
        assert caught.value.details == {"paths": ["division_key"]}


def test_save_uses_exact_immutable_version_as_authoring_baseline(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, project, definition = _seed_current_project(session)
        service = ArtifactService(session, actor)
        artifact = service.create(
            project.id,
            artifact_key="baseline",
            artifact_type="lesson_division",
            branch_key="project",
            content_definition_version_id=definition.id,
            draft_branch="main",
            initial_content={"lesson_count": 2},
            request_id="issue-131-baseline",
        )
        draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
        assert draft is not None
        baseline_content = {"division_key": "stable", "lesson_count": 2}
        baseline = ArtifactVersion(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            artifact_id=artifact.id,
            version_no=1,
            content_json=baseline_content,
            content_hash=canonical_content_hash(baseline_content),
            render_summary_json={},
            source_kind="model",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=actor.principal_id,
        )
        session.add(baseline)
        session.flush()
        draft.based_on_version_id = baseline.id
        session.flush()

        saved = service.save_draft(
            artifact.id,
            "main",
            expected_lock_version=draft.lock_version,
            content={"division_key": "stable", "lesson_count": 3},
            request_id="issue-131-save",
        )
        assert saved.content_json["lesson_count"] == 3

        with pytest.raises(ApiError) as caught:
            service.save_draft(
                artifact.id,
                "main",
                expected_lock_version=saved.lock_version,
                content={"division_key": "changed", "lesson_count": 3},
                request_id="issue-131-save-locked",
            )
        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"


def test_submit_rechecks_authoring_policy_for_dirty_draft(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, project, definition = _seed_current_project(session)
        artifact = ArtifactService(session, actor).create(
            project.id,
            artifact_key="dirty-submit",
            artifact_type="lesson_division",
            branch_key="project",
            content_definition_version_id=definition.id,
            draft_branch="main",
            initial_content={"lesson_count": 2},
            request_id="issue-131-dirty",
        )
        draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
        assert draft is not None
        draft.content_json = {"division_key": "forged", "lesson_count": 2}
        session.flush()

        with pytest.raises(ApiError) as caught:
            ArtifactService(session, actor).submit(
                artifact.id,
                "main",
                expected_lock_version=draft.lock_version,
                source_kind="manual",
                request_id="issue-131-dirty-submit",
            )
        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"


def test_system_actor_does_not_bypass_authoring_guard(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, project, definition = _seed_current_project(session)
        privileged = system_actor(actor.organization_id)

        with pytest.raises(ApiError) as caught:
            ArtifactService(session, privileged).create(
                project.id,
                artifact_key="system-forgery",
                artifact_type="lesson_division",
                branch_key="project",
                content_definition_version_id=definition.id,
                draft_branch="main",
                initial_content={"division_key": "forged", "lesson_count": 2},
                request_id="issue-131-system",
            )
        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"


async def test_generated_version_opens_an_exact_idempotent_authoring_draft(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    result = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(seeded.output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(seeded.node_run_id, request_id="issue-131-open-generated")

    with factory() as session, session.begin():
        version = session.get(ArtifactVersion, result.artifact_version_id)
        assert version is not None
        port = ArtifactAuthoringProvisionPort(
            session,
            system_actor(seeded.actor.organization_id),
        )
        with pytest.raises(ApiError) as user_denied:
            ArtifactAuthoringProvisionPort(session, seeded.actor).open_generated_draft(
                GeneratedDraftRequest(
                    artifact_id=version.artifact_id,
                    artifact_version_id=version.id,
                    expected_content_hash=version.content_hash,
                    draft_branch="main",
                )
            )
        assert user_denied.value.code == "PERMISSION_DENIED"
        with pytest.raises(ApiError) as wrong_hash:
            port.open_generated_draft(
                GeneratedDraftRequest(
                    artifact_id=version.artifact_id,
                    artifact_version_id=version.id,
                    expected_content_hash="0" * 64,
                    draft_branch="main",
                )
            )
        assert wrong_hash.value.code == "AUTHORING_PROVISION_CONFLICT"
        request = GeneratedDraftRequest(
            artifact_id=version.artifact_id,
            artifact_version_id=version.id,
            expected_content_hash=version.content_hash,
            draft_branch="main",
        )
        first = port.open_generated_draft(request)
        replay = port.open_generated_draft(request)
        assert replay.id == first.id
        assert first.based_on_version_id == version.id
        assert first.content_json == version.content_json


async def test_locked_repeatable_item_requires_exact_server_provision(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    result = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(seeded.output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(seeded.node_run_id, request_id="issue-131-provision")

    with factory() as session, session.begin():
        version = session.get(ArtifactVersion, result.artifact_version_id)
        assert version is not None
        system = system_actor(seeded.actor.organization_id)
        port = ArtifactAuthoringProvisionPort(session, system)
        draft = port.open_generated_draft(
            GeneratedDraftRequest(
                artifact_id=version.artifact_id,
                artifact_version_id=version.id,
                expected_content_hash=version.content_hash,
                draft_branch="main",
            )
        )
        candidate = deepcopy(version.content_json)
        new_item = deepcopy(candidate["lesson_units"][0])
        new_item["lesson_unit_key"] = "LESSON-NEW"
        new_item["position"] = len(candidate["lesson_units"]) + 1
        new_item["title"] = "Provisioned lesson"
        candidate["lesson_units"].append(new_item)
        candidate["lesson_count"] = len(candidate["lesson_units"])

        with pytest.raises(ApiError) as caught:
            ArtifactService(session, seeded.actor).save_draft(
                version.artifact_id,
                "main",
                expected_lock_version=draft.lock_version,
                content=candidate,
                request_id="issue-131-user-add",
            )
        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"

        editable = deepcopy(version.content_json)
        editable["lesson_count"] = len(editable["lesson_units"]) + 1
        saved = ArtifactService(session, seeded.actor).save_draft(
            version.artifact_id,
            "main",
            expected_lock_version=draft.lock_version,
            content=editable,
            request_id="issue-131-count",
        )
        request = RepeatableItemProvision(
            artifact_id=version.artifact_id,
            draft_id=saved.id,
            based_on_version_id=version.id,
            baseline_content_hash=version.content_hash,
            expected_lock_version=saved.lock_version,
            field_path=("lesson_units",),
            item=new_item,
        )
        provisioned = port.provision_repeatable_item(request)
        assert provisioned.validation_report_json["valid"] is True
        assert provisioned.content_json["lesson_units"][-1]["lesson_unit_key"] == "LESSON-NEW"
        with pytest.raises(ApiError) as stale_lock:
            port.provision_repeatable_item(request)
        assert stale_lock.value.code == "AUTHORING_PROVISION_CONFLICT"
        assert len(provisioned.content_json["lesson_units"]) == len(candidate["lesson_units"])


def _seed_current_project(session):
    actor = seed_test_actor(session)
    source = load_builtin_courseware_release(ROOT)
    result = ContentReleasePublisher(session).publish(source, published_by=actor.principal_id)
    project = _create_project(session, actor, "Current authoring")
    definition = session.scalar(
        select(ContentDefinitionVersion).where(
            ContentDefinitionVersion.content_package_version_id
            == result.content_package_version_id,
            ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
        )
    )
    assert definition is not None
    return actor, project, definition


def _create_project(session, actor, title: str):
    return ProjectRepository(session, actor).create(
        CreateProjectRequest(title=title, knowledge_point="One half")
    )
