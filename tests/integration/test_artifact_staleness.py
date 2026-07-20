from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.models import ArtifactRelation
from apps.api.artifacts.service import ArtifactService
from apps.api.content_runtime.registry import BUILTIN_CONTENT_DEFINITION_VERSION_ID
from apps.api.creation.models import CreationPackage
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry
from apps.api.workflows.models import NodeRun
from apps.api.ids import new_uuid7
from tests.fakes.identity import seed_test_actor
from tests.integration.test_creation_lifecycle import seed_project_package


def create_approved(session, actor, project_id, key: str, content: dict[str, object]):
    service = ArtifactService(session, actor)
    artifact = service.create(
        project_id,
        artifact_key=key,
        artifact_type="test_content",
        branch_key="lesson_plan",
        content_definition_version_id=BUILTIN_CONTENT_DEFINITION_VERSION_ID,
        draft_branch="main",
        initial_content=content,
        request_id=f"req-create-{key}",
    )
    draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
    assert draft is not None
    version = service.submit(
        artifact.id,
        "main",
        expected_lock_version=draft.lock_version,
        source_kind="manual",
        request_id=f"req-submit-{key}",
    )
    service.review(
        version.id,
        action="approve",
        comment="approved",
        request_id=f"req-approve-{key}",
    )
    return artifact, version


def test_stale_propagates_only_along_real_relations_and_accept_stale_clears_it(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            upstream, upstream_v1 = create_approved(
                session, actor, project.id, "upstream", {"value": 1}
            )
            downstream, downstream_v1 = create_approved(
                session, actor, project.id, "downstream", {"value": "derived"}
            )
            unrelated, _ = create_approved(
                session, actor, project.id, "unrelated", {"value": "manual"}
            )
            ArtifactService(session, actor).add_relation(
                from_version_id=upstream_v1.id,
                to_version_id=downstream_v1.id,
                relation_type="derives_from",
                binding_key="lesson_scope",
                impact_scope={"mode": "all"},
            )
            package, _ = seed_project_package(
                session,
                actor,
                project,
                "lesson.01.image.downstream",
            )
            package_node = session.get(NodeRun, package.source_node_run_id)
            assert package_node is not None
            package_node.active_artifact_version_id = downstream_v1.id
            session.flush()
            draft = ArtifactRepository(session, actor).get_draft(upstream.id, "main")
            assert draft is not None
            saved = ArtifactService(session, actor).save_draft(
                upstream.id,
                "main",
                expected_lock_version=draft.lock_version,
                content={"value": 2},
                request_id="req-upstream-save",
            )
            upstream_v2 = ArtifactService(session, actor).submit(
                upstream.id,
                "main",
                expected_lock_version=saved.lock_version,
                source_kind="manual",
                request_id="req-upstream-submit-v2",
            )
            ArtifactService(session, actor).review(
                upstream_v2.id,
                action="approve",
                comment="new source",
                request_id="req-upstream-approve-v2",
            )

        session.refresh(downstream)
        session.refresh(unrelated)
        assert downstream.status == "stale"
        assert downstream.stale_reason_json == {
            "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
            "replaced_upstream_version_id": str(upstream_v1.id),
            "replacement_version_id": str(upstream_v2.id),
            "bindings": [
                {
                    "relation_type": "derives_from",
                    "binding_key": "lesson_scope",
                    "impact_scope": {"mode": "all"},
                }
            ],
        }
        assert unrelated.status == "approved"
        refreshed_package = session.get(CreationPackage, package.id)
        assert refreshed_package is not None
        assert refreshed_package.source_stale_at is not None
        stale_event = session.scalar(
            select(EventStreamEntry).where(
                EventStreamEntry.event_type == "workflow.downstream_stale.propagated"
            )
        )
        assert stale_event is not None
        assert stale_event.summary_json["payload"] == {
            "source_version_id": str(upstream_v2.id),
            "affected_resource_ids": [str(downstream.id)],
            "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
        }
        session.rollback()

        with session.begin():
            ArtifactService(session, actor).review(
                downstream_v1.id,
                action="accept_stale",
                comment="Teacher confirmed reuse",
                request_id="req-accept-stale",
            )
        session.refresh(downstream)
        assert downstream.status == "approved"
        assert downstream.stale_reason_json is None


def test_relation_cycle_and_cross_tenant_visibility_are_rejected(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        first, first_v = create_approved(session, actor, project.id, "first", {"value": 1})
        _second, second_v = create_approved(session, actor, project.id, "second", {"value": 2})
        service = ArtifactService(session, actor)
        service.add_relation(
            from_version_id=first_v.id,
            to_version_id=second_v.id,
            relation_type="references",
            binding_key="first-to-second",
            impact_scope={"mode": "all"},
        )
        with pytest.raises(ApiError) as cycle:
            service.add_relation(
                from_version_id=second_v.id,
                to_version_id=first_v.id,
                relation_type="references",
                binding_key="second-to-first",
                impact_scope={"mode": "all"},
            )
        assert cycle.value.code == "ARTIFACT_RELATION_CYCLE"

        foreign_actor = actor.__class__(
            organization_id=first.id,
            principal_id=actor.principal_id,
            user_id=None,
            actor_type="system",
        )
        assert ArtifactRepository(session, foreign_actor).get(first.id) is None


def test_relation_impact_scope_database_constraint_accepts_only_current_shapes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        _source, source_version = create_approved(
            session, actor, project.id, "scope-source", {"value": 1}
        )
        _target, target_version = create_approved(
            session, actor, project.id, "scope-target", {"value": 2}
        )
        service = ArtifactService(session, actor)
        service.add_relation(
            from_version_id=source_version.id,
            to_version_id=target_version.id,
            relation_type="references",
            binding_key="scope-all",
            impact_scope={"mode": "all"},
        )
        service.add_relation(
            from_version_id=source_version.id,
            to_version_id=target_version.id,
            relation_type="references",
            binding_key="scope-keyed",
            impact_scope={
                "mode": "keyed",
                "selector": "lesson_key",
                "keys": ["LESSON-001"],
            },
        )
        session.flush()

        invalid_scopes = [
            {},
            {"mode": "keyed", "selector": "lesson_key", "keys": []},
            {
                "mode": "keyed",
                "selector": "lesson_unit_key",
                "keys": ["LESSON-001"],
            },
            {
                "mode": "keyed",
                "selector": "lesson_key",
                "keys": ["LESSON-001"],
                "extra": True,
            },
            {"mode": "all", "extra": True},
        ]
        for index, impact_scope in enumerate(invalid_scopes):
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.add(
                        ArtifactRelation(
                            id=new_uuid7(),
                            organization_id=actor.organization_id,
                            from_artifact_version_id=source_version.id,
                            to_artifact_version_id=target_version.id,
                            relation_type="constrains",
                            binding_key=f"invalid-scope-{index}",
                            impact_scope_json=impact_scope,
                            created_by=actor.principal_id,
                        )
                    )
                    session.flush()


def test_revoking_an_upstream_approval_marks_real_downstream_stale(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        _upstream, upstream_version = create_approved(
            session, actor, project.id, "upstream-revoke", {"value": 1}
        )
        downstream, downstream_version = create_approved(
            session, actor, project.id, "downstream-revoke", {"value": "derived"}
        )
        service = ArtifactService(session, actor)
        service.add_relation(
            from_version_id=upstream_version.id,
            to_version_id=downstream_version.id,
            relation_type="derives_from",
            binding_key="revoked-source",
            impact_scope={"mode": "all"},
        )
        service.review(
            upstream_version.id,
            action="revoke",
            comment="Source approval is no longer valid",
            request_id="req-revoke-upstream",
        )

        assert downstream.status == "stale"
        assert downstream.stale_reason_json is not None
        assert downstream.stale_reason_json["reason_code"] == "UPSTREAM_APPROVAL_REVOKED"
        assert downstream.stale_reason_json["replacement_version_id"] is None
