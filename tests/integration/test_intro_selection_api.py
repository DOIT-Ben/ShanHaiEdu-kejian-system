from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.authoring_provision import (
    ArtifactAuthoringProvisionPort,
    GeneratedDraftRequest,
)
from apps.api.artifacts.models import Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.models import Organization, ProjectMember
from apps.api.ids import new_uuid7
from apps.api.intro_selections.models import IntroSelection
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.integration.intro_selection_support import (
    ApprovedOptionSet,
    prepare_approved_option_set,
)


async def _approved_harness(
    database_url: str,
) -> tuple[httpx.ASGITransport, Engine, sessionmaker[Session], ApprovedOptionSet]:
    run_migration(database_url, "head")
    engine = build_engine(database_url)
    factory = build_session_factory(engine)
    prepared = await prepare_approved_option_set(factory)
    app = create_app(
        settings=Settings(_env_file=None, environment="test", database_url=database_url),
        session_factory=factory,
    )
    override_test_identity(app, prepared.actor)
    return httpx.ASGITransport(app=app), engine, factory, prepared


def _submit_pending_revision(
    factory: sessionmaker[Session], prepared: ApprovedOptionSet
) -> UUID:
    with factory() as session, session.begin():
        original = session.get(ArtifactVersion, prepared.version_id)
        assert original is not None
        ArtifactAuthoringProvisionPort(
            session,
            system_actor(prepared.actor.organization_id),
        ).open_generated_draft(
            GeneratedDraftRequest(
                artifact_id=prepared.artifact_id,
                artifact_version_id=prepared.version_id,
                expected_content_hash=original.content_hash,
                draft_branch="main",
            )
        )
    with factory() as session, session.begin():
        draft = session.scalar(
            select(ArtifactDraft).where(
                ArtifactDraft.artifact_id == prepared.artifact_id,
                ArtifactDraft.draft_branch == "main",
            )
        )
        assert draft is not None
        content = deepcopy(draft.content_json)
        content["options"][0]["title"] = "Pending teacher revision"
        service = ArtifactService(session, prepared.actor)
        saved = service.save_draft(
            prepared.artifact_id,
            "main",
            expected_lock_version=draft.lock_version,
            content=content,
            request_id="issue-129-save-pending",
        )
        return service.submit(
            prepared.artifact_id,
            "main",
            expected_lock_version=saved.lock_version,
            source_kind="manual",
            request_id="issue-129-submit-pending",
        ).id


def _selection_payload(
    prepared: ApprovedOptionSet,
    option_key: str | None = None,
) -> dict[str, str]:
    return {
        "artifact_version_id": str(prepared.version_id),
        "option_key": option_key or prepared.option_keys[0],
    }


def _assert_approved_with_pending(
    response: httpx.Response,
    prepared: ApprovedOptionSet,
    pending_version_id: UUID,
) -> None:
    assert response.status_code == 200, response.text
    assert_contract_response(response, operation_id="getLessonIntroOptions", status="200")
    data = response.json()["data"]
    assert data["artifact_id"] == str(prepared.artifact_id)
    assert data["current_approved_version_id"] == str(prepared.version_id)
    assert data["display_version"]["artifact_version_id"] == str(prepared.version_id)
    assert data["display_version"]["approval_status"] == "approved"
    assert data["display_version"]["selectable"] is True
    assert data["pending_version"]["artifact_version_id"] == str(pending_version_id)
    assert data["pending_version"]["approval_status"] == "pending_review"
    assert data["pending_version"]["selectable"] is False
    rendered = json.dumps(data)
    for private_field in (
        "generation_context_snapshot_id",
        "source_intro_option_version_refs",
        "option_set_id",
        "source_approval_id",
        "policy_evidence",
    ):
        assert private_field not in rendered


def _assert_public_selection(
    response: httpx.Response,
    prepared: ApprovedOptionSet,
) -> dict[str, object]:
    assert response.status_code == 201, response.text
    assert_contract_response(response, operation_id="selectLessonIntroOption", status="201")
    selection = response.json()["data"]
    assert selection["artifact_version_id"] == str(prepared.version_id)
    assert selection["selection_method"] == "teacher_selected"
    assert selection["snapshot"]["option_key"] == prepared.option_keys[0]
    return selection


async def test_intro_options_prefers_approved_version_and_teacher_selection_is_public(
    postgres_database_url: str,
) -> None:
    transport, engine, factory, prepared = await _approved_harness(postgres_database_url)
    pending_version_id = _submit_pending_revision(factory, prepared)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            options = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
            selected = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-select-approved-v1"},
                json=_selection_payload(prepared),
            )
            replay = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-select-approved-v1"},
                json=_selection_payload(prepared),
            )
            forged_policy = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-forged-policy"},
                json=_selection_payload(prepared) | {"selection_method": "policy_default"},
            )
            refreshed = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
    finally:
        engine.dispose()

    _assert_approved_with_pending(options, prepared, pending_version_id)
    selection = _assert_public_selection(selected, prepared)
    assert replay.status_code == 201
    assert replay.json()["data"] == selection
    assert forged_policy.status_code == 422
    assert forged_policy.json()["error"]["code"] == "VALIDATION_FAILED"
    assert refreshed.json()["data"]["current_selection"]["selection_id"] == selection[
        "selection_id"
    ]


async def test_intro_options_exposes_stale_and_revoked_as_not_selectable(
    postgres_database_url: str,
) -> None:
    transport, engine, factory, prepared = await _approved_harness(postgres_database_url)
    try:
        with factory() as session, session.begin():
            artifact = session.get(Artifact, prepared.artifact_id)
            assert artifact is not None
            artifact.status = "stale"
            artifact.stale_reason_json = {
                "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
                "replaced_upstream_version_id": str(new_uuid7()),
                "replacement_version_id": str(new_uuid7()),
                "bindings": [],
            }
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            stale = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
        with factory() as session, session.begin():
            artifact = session.get(Artifact, prepared.artifact_id)
            assert artifact is not None
            artifact.status = "approved"
            artifact.stale_reason_json = None
            ArtifactService(session, prepared.actor).review(
                prepared.version_id,
                action="revoke",
                comment="Revoke for Issue 129 public projection test.",
                request_id="issue-129-revoke",
            )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            revoked = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
    finally:
        engine.dispose()

    stale_display = stale.json()["data"]["display_version"]
    assert stale.status_code == 200
    assert stale_display["approval_status"] == "approved"
    assert stale_display["stale"] is True
    assert stale_display["selectable"] is False
    revoked_data = revoked.json()["data"]
    assert revoked.status_code == 200
    assert revoked_data["current_approved_version_id"] is None
    assert revoked_data["display_version"]["approval_status"] == "revoked"
    assert revoked_data["display_version"]["selectable"] is False


async def test_intro_selection_replay_reauthorizes_and_cross_tenant_is_hidden(
    postgres_database_url: str,
) -> None:
    transport, engine, factory, prepared = await _approved_harness(postgres_database_url)
    payload = _selection_payload(prepared)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-reauthorize-replay"},
                json=payload,
            )
        with factory() as session, session.begin():
            membership = session.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == prepared.project_id,
                    ProjectMember.user_id == prepared.actor.user_id,
                )
            )
            assert membership is not None
            membership.role = "viewer"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            denied_replay = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-reauthorize-replay"},
                json=payload,
            )
        foreign_actor = _foreign_actor(factory)
        override_test_identity(transport.app, foreign_actor)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            hidden_get = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
            hidden_post = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "issue-129-cross-tenant"},
                json=payload,
            )
    finally:
        engine.dispose()

    assert created.status_code == 201
    assert denied_replay.status_code == 403
    assert denied_replay.json()["error"]["code"] == "PERMISSION_DENIED"
    assert hidden_get.status_code == 404
    assert hidden_post.status_code == 404


async def test_concurrent_teacher_selections_converge_to_one_active_fact(
    postgres_database_url: str,
) -> None:
    transport, engine, factory, prepared = await _approved_harness(postgres_database_url)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first, second = await asyncio.gather(
                client.post(
                    f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                    headers={"Idempotency-Key": "issue-129-concurrent-first"},
                    json=_selection_payload(prepared, prepared.option_keys[0]),
                ),
                client.post(
                    f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                    headers={"Idempotency-Key": "issue-129-concurrent-second"},
                    json=_selection_payload(prepared, prepared.option_keys[1]),
                ),
            )
        with factory() as session:
            active_count = session.scalar(
                select(func.count())
                .select_from(IntroSelection)
                .where(
                    IntroSelection.lesson_unit_id == prepared.lesson_unit_id,
                    IntroSelection.active.is_(True),
                )
            )
    finally:
        engine.dispose()

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert active_count == 1


def _foreign_actor(factory: sessionmaker[Session]) -> ActorContext:
    with factory() as session, session.begin():
        organization_id = new_uuid7()
        session.add(
            Organization(
                id=organization_id,
                slug=f"issue-129-{organization_id.hex[:12]}",
                name="Issue 129 foreign tenant",
                status="active",
            )
        )
        session.flush()
        return seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"issue-129-{organization_id.hex[:8]}@example.test",
        )
