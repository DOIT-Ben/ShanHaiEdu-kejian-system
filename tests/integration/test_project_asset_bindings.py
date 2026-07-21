from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.assets.project_service import ProjectAssetService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.errors import ApiError
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from tests.fakes.content_runtime import ensure_test_authoring_definition
from tests.fakes.identity import seed_test_actor


def create_project(session, actor, title: str = "Fractions"):
    return ProjectRepository(session, actor).create(
        CreateProjectRequest(title=title, knowledge_point="One half")
    )


def seed_lesson(
    session,
    actor,
    project,
    *,
    key: str = "lesson-01",
    position: int = 1,
) -> LessonUnit:
    lesson = LessonUnit(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project.id,
        lesson_key=key,
        position=position,
        title="Understanding one half",
        scope_summary="Recognize one half.",
        objective_summary="Explain equal parts.",
        estimated_minutes=40,
        source_division_version_id=new_uuid7(),
        status="active",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(lesson)
    session.flush()
    return lesson


def seed_file_version(
    session,
    actor,
    *,
    asset_kind: str = "image",
    mime_type: str = "image/png",
    organization_id=None,
) -> FileAssetVersion:
    resolved_organization_id = organization_id or actor.organization_id
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=resolved_organization_id,
        asset_key=f"test:{asset_kind}:{new_uuid7()}",
        asset_kind=asset_kind,
        status="active",
        retention_class="project_asset",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(asset)
    session.flush()
    version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=resolved_organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="shanhaiedu",
        storage_key=f"immutable/{asset.id}/asset.bin",
        mime_type=mime_type,
        byte_size=4,
        sha256="a" * 64,
        etag=f"etag-{asset.id}",
        scan_status="clean",
        metadata_json={},
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    return version


def declare_slot(
    service: ProjectAssetService,
    project_id,
    *,
    cardinality: AssetCardinality,
    lesson_unit_id=None,
) -> ProjectAssetSlot:
    return service.declare_slot(
        project_id,
        AssetSlotDeclaration(
            slot_key=(
                "lesson.01.image.candidates"
                if cardinality == AssetCardinality.MANY
                else "lesson.01.image.selected"
            ),
            lesson_unit_id=lesson_unit_id,
            asset_type="image",
            cardinality=cardinality,
            required=True,
            target_contract=AssetTargetContract(
                allowed_mime_types=("image/png",),
                require_clean_scan=True,
            ),
        ),
        request_id="req-declare-slot",
    )


def test_one_slot_replace_preserves_history_and_atomic_audit(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            lesson = seed_lesson(session, actor, project)
            first_version = seed_file_version(session, actor)
            second_version = seed_file_version(session, actor)
            service = ProjectAssetService(session, actor)
            slot = declare_slot(
                service,
                project.id,
                cardinality=AssetCardinality.ONE,
                lesson_unit_id=lesson.id,
            )
            with pytest.raises(ApiError) as empty_replace:
                service.bind(
                    slot.id,
                    file_asset_version_id=first_version.id,
                    source_artifact_version_id=None,
                    replace_mode=ReplaceMode.REPLACE_ACTIVE,
                    position=None,
                    request_id="req-replace-empty",
                )
            assert empty_replace.value.code == "ASSET_SLOT_EMPTY"
            first = service.bind(
                slot.id,
                file_asset_version_id=first_version.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id="req-bind-first",
            )
            replacement = service.bind(
                slot.id,
                file_asset_version_id=second_version.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.REPLACE_ACTIVE,
                position=None,
                request_id="req-bind-replacement",
            )

        bindings = list(
            session.scalars(
                select(AssetBinding)
                .where(AssetBinding.project_asset_slot_id == slot.id)
                .order_by(AssetBinding.bound_at, AssetBinding.id)
            )
        )
        persisted_slot = session.get(ProjectAssetSlot, slot.id)

        assert [binding.id for binding in bindings] == [first.id, replacement.id]
        assert bindings[0].is_active is False
        assert bindings[0].unbound_at is not None
        assert bindings[1].is_active is True
        assert bindings[1].position == 0
        assert persisted_slot is not None and persisted_slot.status == "satisfied"
        assert session.get(FileAssetVersion, first_version.id).sha256 == "a" * 64
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 3
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 3

        with pytest.raises(DBAPIError), session.begin_nested():
            session.delete(bindings[0])
            session.flush()


def test_many_slot_positions_are_unique_and_unbind_updates_satisfaction(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            first_version = seed_file_version(session, actor)
            second_version = seed_file_version(session, actor)
            service = ProjectAssetService(session, actor)
            slot = declare_slot(service, project.id, cardinality=AssetCardinality.MANY)
            first = service.bind(
                slot.id,
                file_asset_version_id=first_version.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.APPEND,
                position=None,
                request_id="req-append-first",
            )
            second = service.bind(
                slot.id,
                file_asset_version_id=second_version.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.APPEND,
                position=None,
                request_id="req-append-second",
            )

        assert (first.position, second.position) == (1, 2)
        slot_id = slot.id
        first_binding_id = first.id
        second_binding_id = second.id
        second_version_id = second_version.id
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                AssetBinding(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    project_asset_slot_id=slot.id,
                    file_asset_version_id=second_version.id,
                    source_generation_result_id=None,
                    source_artifact_version_id=None,
                    save_operation_id=None,
                    position=1,
                    is_active=True,
                    bound_at=utc_now(),
                    bound_by=actor.principal_id,
                    unbound_at=None,
                    unbound_by=None,
                )
            )
            session.flush()
        session.rollback()

        with pytest.raises(ApiError) as invalid_position:
            with session.begin():
                ProjectAssetService(session, actor).bind(
                    slot_id,
                    file_asset_version_id=second_version_id,
                    source_artifact_version_id=None,
                    replace_mode=ReplaceMode.APPEND,
                    position=0,
                    request_id="req-position-zero",
                )
        assert invalid_position.value.code == "ASSET_POSITION_INVALID"

        with pytest.raises(ApiError) as occupied:
            with session.begin():
                ProjectAssetService(session, actor).bind(
                    slot_id,
                    file_asset_version_id=second_version_id,
                    source_artifact_version_id=None,
                    replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                    position=1,
                    request_id="req-position-conflict",
                )
        assert occupied.value.code == "ASSET_POSITION_OCCUPIED"

        with session.begin():
            ProjectAssetService(session, actor).unbind(
                first_binding_id, request_id="req-unbind-first"
            )
            ProjectAssetService(session, actor).unbind(
                second_binding_id, request_id="req-unbind-second"
            )
        persisted_slot = session.get(ProjectAssetSlot, slot_id)
        assert persisted_slot is not None and persisted_slot.status == "empty"


def test_binding_rejects_wrong_type_lesson_and_tenant(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = create_project(session, actor)
        other_project = create_project(session, actor, "Decimals")
        lesson = seed_lesson(session, actor, project)
        other_lesson = seed_lesson(session, actor, other_project, key="lesson-other")
        service = ProjectAssetService(session, actor)
        slot = declare_slot(
            service,
            project.id,
            cardinality=AssetCardinality.ONE,
            lesson_unit_id=lesson.id,
        )
        video = seed_file_version(session, actor, asset_kind="video", mime_type="video/mp4")

        with pytest.raises(ApiError) as wrong_lesson:
            service.declare_slot(
                project.id,
                AssetSlotDeclaration(
                    slot_key="lesson.other.image.selected",
                    lesson_unit_id=other_lesson.id,
                    asset_type="image",
                    cardinality=AssetCardinality.ONE,
                    target_contract=AssetTargetContract(),
                ),
                request_id="req-wrong-lesson",
            )
        assert wrong_lesson.value.code == "ASSET_SLOT_LESSON_MISMATCH"

        with pytest.raises(ApiError) as wrong_type:
            service.bind(
                slot.id,
                file_asset_version_id=video.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id="req-wrong-type",
            )
        assert wrong_type.value.code == "ASSET_TYPE_MISMATCH"

        foreign_organization_id = uuid4()
        session.add(
            Organization(
                id=foreign_organization_id,
                slug=f"foreign-{foreign_organization_id.hex[:12]}",
                name="Foreign organization",
                status="active",
                created_at=utc_now(),
            )
        )
        session.flush()
        foreign_version = seed_file_version(
            session,
            actor,
            organization_id=foreign_organization_id,
        )
        with pytest.raises(ApiError) as cross_tenant:
            service.bind(
                slot.id,
                file_asset_version_id=foreign_version.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id="req-cross-tenant",
            )
        assert cross_tenant.value.code == "FILE_ASSET_VERSION_NOT_FOUND"

        hidden = ProjectAssetService(session, replace(actor, organization_id=uuid4()))
        with pytest.raises(ApiError) as hidden_slot:
            hidden.bind(
                slot.id,
                file_asset_version_id=video.id,
                source_artifact_version_id=None,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id="req-hidden-slot",
            )
        assert hidden_slot.value.code == "ASSET_SLOT_NOT_FOUND"


def test_binding_preserves_matching_artifact_source_and_rejects_wrong_lesson(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = create_project(session, actor)
        target_lesson = seed_lesson(session, actor, project)
        other_lesson = seed_lesson(
            session,
            actor,
            project,
            key="lesson-02",
            position=2,
        )
        file_version = seed_file_version(session, actor)
        slot = declare_slot(
            ProjectAssetService(session, actor),
            project.id,
            cardinality=AssetCardinality.ONE,
            lesson_unit_id=target_lesson.id,
        )

        artifact_service = ArtifactService(session, actor)
        definition_id = ensure_test_authoring_definition(session, project.id)
        wrong_artifact = artifact_service.create(
            project.id,
            artifact_key="lesson-plan:lesson-02",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            content_definition_version_id=definition_id,
            draft_branch="main",
            initial_content={"title": "Wrong lesson"},
            request_id="req-wrong-source-create",
            lesson_unit_id=other_lesson.id,
        )
        wrong_draft = ArtifactRepository(session, actor).get_draft(wrong_artifact.id, "main")
        assert wrong_draft is not None
        wrong_version = artifact_service.submit(
            wrong_artifact.id,
            "main",
            expected_lock_version=wrong_draft.lock_version,
            source_kind="manual",
            request_id="req-wrong-source-submit",
        )

        with pytest.raises(ApiError) as wrong_source:
            ProjectAssetService(session, actor).bind(
                slot.id,
                file_asset_version_id=file_version.id,
                source_artifact_version_id=wrong_version.id,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id="req-wrong-source-bind",
            )
        assert wrong_source.value.code == "ASSET_SOURCE_MISMATCH"

        matching_artifact = artifact_service.create(
            project.id,
            artifact_key="lesson-plan:lesson-01",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            content_definition_version_id=definition_id,
            draft_branch="main",
            initial_content={"title": "Matching lesson"},
            request_id="req-matching-source-create",
            lesson_unit_id=target_lesson.id,
        )
        matching_draft = ArtifactRepository(session, actor).get_draft(matching_artifact.id, "main")
        assert matching_draft is not None
        matching_version = artifact_service.submit(
            matching_artifact.id,
            "main",
            expected_lock_version=matching_draft.lock_version,
            source_kind="manual",
            request_id="req-matching-source-submit",
        )
        binding = ProjectAssetService(session, actor).bind(
            slot.id,
            file_asset_version_id=file_version.id,
            source_artifact_version_id=matching_version.id,
            replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
            position=None,
            request_id="req-matching-source-bind",
        )

        assert binding.source_artifact_version_id == matching_version.id


def test_binding_and_event_roll_back_together(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            version = seed_file_version(session, actor)
            slot = declare_slot(
                ProjectAssetService(session, actor),
                project.id,
                cardinality=AssetCardinality.ONE,
            )
        baseline_events = session.scalar(select(func.count()).select_from(EventStreamEntry))
        baseline_outbox = session.scalar(select(func.count()).select_from(OutboxEvent))
        session.rollback()

        with pytest.raises(RuntimeError, match="rollback"):
            with session.begin():
                ProjectAssetService(session, actor).bind(
                    slot.id,
                    file_asset_version_id=version.id,
                    source_artifact_version_id=None,
                    replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                    position=None,
                    request_id="req-rollback",
                )
                raise RuntimeError("rollback")

        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 0
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == baseline_events
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == baseline_outbox


def test_concurrent_one_slot_keeps_one_active_binding(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = create_project(session, actor)
        versions = (seed_file_version(session, actor), seed_file_version(session, actor))
        slot = declare_slot(
            ProjectAssetService(session, actor),
            project.id,
            cardinality=AssetCardinality.ONE,
        )

    def bind(version_id):
        try:
            with factory() as worker_session, worker_session.begin():
                binding = ProjectAssetService(worker_session, actor).bind(
                    slot.id,
                    file_asset_version_id=version_id,
                    source_artifact_version_id=None,
                    replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                    position=None,
                    request_id=f"req-concurrent-{version_id}",
                )
                return str(binding.id)
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(bind, (versions[0].id, versions[1].id)))

    assert results.count("ASSET_SLOT_OCCUPIED") == 1
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AssetBinding)
                .where(AssetBinding.project_asset_slot_id == slot.id, AssetBinding.is_active)
            )
            == 1
        )
