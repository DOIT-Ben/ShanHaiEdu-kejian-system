from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)
from apps.api.assets.project_models import AssetBinding
from apps.api.assets.project_service import ProjectAssetService
from apps.api.creation.models import (
    Adoption,
    CreationBatch,
    CreationItem,
    CreationPackage,
    CreationPackageItem,
    CreationPromptVersion,
    GenerationResult,
    SaveToProjectOperation,
)
from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    GenerateCreationItemRequest,
    ProjectCreateCreationBatchRequest,
    ProjectSourceSaveRequest,
    SavePromptVersionRequest,
    StandaloneCreateCreationBatchRequest,
    StandaloneSourceSaveRequest,
)
from apps.api.creation.service import CreationService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.errors import ApiError
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor
from tests.integration.test_project_asset_bindings import seed_file_version
from workflow.node_state import NodeStatus


def seed_project_package(session, actor, project, slot_key: str):
    run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
    node = WorkflowRuntimeService(session, actor).create_project_node_run(
        run.id,
        node_key="prepare",
        status=NodeStatus.READY,
    )
    context = ContextSnapshot(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project.id,
        node_run_id=node.id,
        bindings_json={},
        content_hash="c" * 64,
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(context)
    session.flush()
    prompt = PromptSnapshot(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project.id,
        node_run_id=node.id,
        context_snapshot_id=context.id,
        template_refs_json={},
        layers_json={},
        editable_prompt="Prepare a visual.",
        user_diff_json={},
        compiled_prompt="Prepare a visual.",
        request_schema_json={},
        preview_json={},
        content_hash="d" * 64,
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(prompt)
    session.flush()
    package = CreationPackage(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        package_key=f"package:{new_uuid7()}",
        source_project_id=project.id,
        source_workflow_run_id=run.id,
        source_node_run_id=node.id,
        context_snapshot_id=context.id,
        source_prompt_snapshot_id=prompt.id,
        package_type="image",
        status="ready",
        target_rules_json={"replace_modes": ["reject_if_occupied", "replace_active"]},
        content_hash="a" * 64,
        source_stale_at=None,
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(package)
    session.flush()
    item = CreationPackageItem(
        id=new_uuid7(),
        creation_package_id=package.id,
        item_key="ppt.page.05.main_visual",
        position=1,
        title="Main visual",
        business_prompt="Show three percentage examples.",
        prompt_json={},
        reference_asset_version_ids=[],
        output_spec_json={"mime_type": "image/png"},
        target_slot_key=slot_key,
        consistency_key=None,
        content_hash="b" * 64,
    )
    session.add(item)
    session.flush()
    return package, item


def declare_target_slot(session, actor, project, slot_key: str):
    return ProjectAssetService(session, actor).declare_slot(
        project.id,
        AssetSlotDeclaration(
            slot_key=slot_key,
            asset_type="image",
            cardinality=AssetCardinality.ONE,
            required=True,
            target_contract=AssetTargetContract(
                allowed_mime_types=("image/png",),
                require_clean_scan=True,
            ),
        ),
        request_id="req-declare-target",
    )


def test_project_creation_lifecycle_keeps_four_actions_separate_and_idempotent(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            slot_key = "lesson.01.ppt.page.05.main_visual"
            slot = declare_target_slot(session, actor, project, slot_key)
            package, _ = seed_project_package(session, actor, project, slot_key)
            file_version = seed_file_version(session, actor)

        service = CreationService(session, actor, idempotency_ttl_seconds=3600)
        with session.begin():
            batch = service.create_batch(
                ProjectCreateCreationBatchRequest(
                    source_kind="project",
                    studio_type="image",
                    title="PPT images",
                    creation_package_id=package.id,
                ),
                idempotency_key="creation-batch-project-001",
                request_id="req-create-batch",
            )
        item = batch.items[0]

        prompt_payload = SavePromptVersionRequest(
            business_prompt="Show three percentage examples with a white background.",
            reference_asset_version_ids=[],
            output_spec={"mime_type": "image/png"},
            generation_profile="quality",
        )
        with session.begin():
            prompt = service.save_prompt_version(
                item.id,
                prompt_payload,
                idempotency_key="prompt-version-save-001",
                request_id="req-save-prompt",
            )
        with session.begin():
            replayed_prompt = service.save_prompt_version(
                item.id,
                prompt_payload,
                idempotency_key="prompt-version-save-001",
                request_id="req-save-prompt-replay",
            )

        assert prompt.id == replayed_prompt.id
        assert session.scalar(select(func.count()).select_from(CreationPromptVersion)) == 1
        assert session.scalar(select(func.count()).select_from(GenerationJob)) == 0
        session.rollback()

        with session.begin():
            accepted_job = service.generate_item(
                item.id,
                GenerateCreationItemRequest(prompt_version_id=prompt.id, candidate_count=1),
                idempotency_key="creation-generate-001",
                request_id="req-generate",
            )
        assert accepted_job.status == "queued"
        assert session.scalar(select(func.count()).select_from(Adoption)) == 0
        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 0
        session.rollback()

        with session.begin():
            result = GenerationResult(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                creation_item_id=item.id,
                generation_job_id=accepted_job.job_id,
                candidate_no=1,
                status="available",
                file_asset_version_id=file_version.id,
                output_json={},
                created_at=utc_now(),
            )
            session.add(result)

        with session.begin():
            adoption = service.adopt_result(
                result.id,
                AdoptGenerationResultRequest(reason="Best teaching fit"),
                idempotency_key="creation-adopt-001",
                request_id="req-adopt",
            )
        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 0
        session.rollback()

        save_payload = ProjectSourceSaveRequest(
            source_kind="project",
            replace_mode="reject_if_occupied",
        )
        with session.begin():
            saved = service.save_adoption(
                adoption.id,
                save_payload,
                idempotency_key="creation-save-project-001",
                request_id="req-save-project",
            )
        with session.begin():
            replayed_save = service.save_adoption(
                adoption.id,
                save_payload,
                idempotency_key="creation-save-project-001",
                request_id="req-save-project-replay",
            )

        assert saved.operation_id == replayed_save.operation_id
        assert saved.target_project_id == project.id
        assert saved.target_slot_key == slot_key
        assert session.scalar(select(func.count()).select_from(SaveToProjectOperation)) == 1
        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 1
        binding = session.scalar(select(AssetBinding))
        assert binding is not None
        assert binding.project_asset_slot_id == slot.id
        assert binding.source_generation_result_id == result.id
        assert binding.save_operation_id == saved.operation_id
        event_types = set(session.scalars(select(EventStreamEntry.event_type)))
        assert "creation.prompt_version.saved" in event_types
        assert "creation.candidate.adopted" in event_types
        assert "creation.project_save.completed" in event_types
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) >= 3


def test_creation_source_and_target_boundaries_are_enforced(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        service = CreationService(session, actor, idempotency_ttl_seconds=3600)

        with pytest.raises(ApiError) as missing_package:
            service.create_batch(
                ProjectCreateCreationBatchRequest(
                    source_kind="project",
                    studio_type="image",
                    title="Missing package",
                    creation_package_id=uuid4(),
                ),
                idempotency_key="creation-package-missing-001",
                request_id="req-missing-package",
            )
        assert missing_package.value.code == "CREATION_PACKAGE_REQUIRED"

        standalone = service.create_batch(
            StandaloneCreateCreationBatchRequest(
                source_kind="standalone",
                studio_type="image",
                title="Independent image",
            ),
            idempotency_key="creation-batch-standalone-001",
            request_id="req-standalone-batch",
        )
        assert standalone.source_kind == "standalone"
        assert standalone.items == []

        with pytest.raises(ApiError) as source_mismatch:
            service.resolve_save_target(
                standalone.id,
                ProjectSourceSaveRequest(
                    source_kind="project",
                    replace_mode="reject_if_occupied",
                ),
            )
        assert source_mismatch.value.code == "CREATION_SOURCE_MISMATCH"

        with pytest.raises(ApiError) as forbidden_target:
            service.resolve_save_target(
                standalone.id,
                StandaloneSourceSaveRequest(
                    source_kind="standalone",
                    project_id=uuid4(),
                    slot_key="lesson.01.image.selected",
                    replace_mode="reject_if_occupied",
                ),
            )
        assert forbidden_target.value.code == "PROJECT_TARGET_FORBIDDEN"


def test_standalone_creation_is_private_to_its_creator_even_on_idempotent_replay(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        owner = seed_test_actor(session)
        other = seed_test_actor(
            session,
            user_id=uuid4(),
            principal_id=uuid4(),
            member_id=uuid4(),
            email="other-teacher@example.test",
            display_name="Other Teacher",
        )
        owner_service = CreationService(session, owner, idempotency_ttl_seconds=3600)
        batch = owner_service.create_batch(
            StandaloneCreateCreationBatchRequest(
                source_kind="standalone",
                studio_type="image",
                title="Owner-only image",
            ),
            idempotency_key="standalone-private-batch-001",
            request_id="req-standalone-private-batch",
        )
        item = CreationItem(
            id=new_uuid7(),
            organization_id=owner.organization_id,
            creation_batch_id=batch.id,
            creation_package_item_id=None,
            item_key="private.image.01",
            title="Private image",
            status="draft",
            current_prompt_version_id=None,
            active_adoption_id=None,
            target_slot_key=None,
            created_by=owner.principal_id,
            updated_by=owner.principal_id,
        )
        session.add(item)
        session.flush()
        payload = SavePromptVersionRequest(
            business_prompt="Show a private classroom image.",
            reference_asset_version_ids=[],
            output_spec={"mime_type": "image/png"},
            generation_profile="balanced",
        )
        owner_service.save_prompt_version(
            item.id,
            payload,
            idempotency_key="standalone-private-prompt-001",
            request_id="req-standalone-private-prompt-owner",
        )

        other_service = CreationService(session, other, idempotency_ttl_seconds=3600)
        for key in ("standalone-private-prompt-001", "standalone-private-prompt-002"):
            with pytest.raises(ApiError) as forbidden:
                other_service.save_prompt_version(
                    item.id,
                    payload,
                    idempotency_key=key,
                    request_id=f"req-{key}",
                )
            assert forbidden.value.code == "PERMISSION_DENIED"


def test_standalone_creation_can_save_an_adopted_result_to_an_authorized_project(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            slot_key = "lesson.01.image.independent"
            slot = declare_target_slot(session, actor, project, slot_key)
            file_version = seed_file_version(session, actor)
            service = CreationService(session, actor, idempotency_ttl_seconds=3600)
            batch = service.create_batch(
                StandaloneCreateCreationBatchRequest(
                    source_kind="standalone",
                    studio_type="image",
                    title="Independent teaching image",
                ),
                idempotency_key="standalone-positive-batch-001",
                request_id="req-standalone-positive-batch",
            )
            item = CreationItem(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                creation_batch_id=batch.id,
                creation_package_item_id=None,
                item_key="independent.image.01",
                title="Independent image",
                status="draft",
                current_prompt_version_id=None,
                active_adoption_id=None,
                target_slot_key=None,
                created_by=actor.principal_id,
                updated_by=actor.principal_id,
            )
            session.add(item)
            session.flush()

        with session.begin():
            with pytest.raises(ApiError) as missing_reference:
                service.save_prompt_version(
                    item.id,
                    SavePromptVersionRequest(
                        business_prompt="Use a missing reference.",
                        reference_asset_version_ids=[uuid4()],
                        output_spec={"mime_type": "image/png"},
                        generation_profile="balanced",
                    ),
                    idempotency_key="standalone-missing-reference-001",
                    request_id="req-standalone-missing-reference",
                )
            assert missing_reference.value.code == "FILE_ASSET_VERSION_NOT_FOUND"

        with session.begin():
            prompt = service.save_prompt_version(
                item.id,
                SavePromptVersionRequest(
                    business_prompt="Show one half with two equal paper pieces.",
                    reference_asset_version_ids=[],
                    output_spec={"mime_type": "image/png"},
                    generation_profile="balanced",
                ),
                idempotency_key="standalone-positive-prompt-001",
                request_id="req-standalone-positive-prompt",
            )
        with session.begin():
            job = service.generate_item(
                item.id,
                GenerateCreationItemRequest(prompt_version_id=prompt.id, candidate_count=1),
                idempotency_key="standalone-positive-generate-001",
                request_id="req-standalone-positive-generate",
            )
        with session.begin():
            result = GenerationResult(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                creation_item_id=item.id,
                generation_job_id=job.job_id,
                candidate_no=1,
                status="available",
                file_asset_version_id=file_version.id,
                output_json={},
                created_at=utc_now(),
            )
            session.add(result)
        with session.begin():
            adoption = service.adopt_result(
                result.id,
                AdoptGenerationResultRequest(reason="Fits the independent request"),
                idempotency_key="standalone-positive-adopt-001",
                request_id="req-standalone-positive-adopt",
            )
        with session.begin():
            saved = service.save_adoption(
                adoption.id,
                StandaloneSourceSaveRequest(
                    source_kind="standalone",
                    project_id=project.id,
                    slot_key=slot_key,
                    replace_mode="reject_if_occupied",
                ),
                idempotency_key="standalone-positive-save-001",
                request_id="req-standalone-positive-save",
            )

        assert saved.target_project_id == project.id
        assert saved.target_slot_key == slot_key
        binding = session.get(AssetBinding, saved.binding_id)
        assert binding is not None
        assert binding.project_asset_slot_id == slot.id
        assert binding.source_generation_result_id == result.id
        outbox_topics = set(session.scalars(select(OutboxEvent.topic)))
        assert {
            "creation.batch.created",
            "creation.prompt_version.saved",
            "generation.job.queued",
            "creation.candidate.adopted",
            "creation.project_save.completed",
        }.issubset(outbox_topics)


def test_database_rejects_cross_tenant_batches_and_project_target_overrides(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        source_project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        other_project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Percentages", knowledge_point="Ten percent")
        )
        source_slot_key = "lesson.01.image.source"
        other_slot_key = "lesson.01.image.other"
        declare_target_slot(session, actor, source_project, source_slot_key)
        declare_target_slot(session, actor, other_project, other_slot_key)
        package, _ = seed_project_package(session, actor, source_project, source_slot_key)
        file_version = seed_file_version(session, actor)
        service = CreationService(session, actor, idempotency_ttl_seconds=3600)
        batch = service.create_batch(
            ProjectCreateCreationBatchRequest(
                source_kind="project",
                studio_type="image",
                title="Project images",
                creation_package_id=package.id,
            ),
            idempotency_key="database-scope-batch-001",
            request_id="req-database-scope-batch",
        )
        item = batch.items[0]
        prompt = service.save_prompt_version(
            item.id,
            SavePromptVersionRequest(
                business_prompt="Create the package-bound image.",
                reference_asset_version_ids=[],
                output_spec={"mime_type": "image/png"},
                generation_profile="balanced",
            ),
            idempotency_key="database-scope-prompt-001",
            request_id="req-database-scope-prompt",
        )
        job = service.generate_item(
            item.id,
            GenerateCreationItemRequest(prompt_version_id=prompt.id, candidate_count=1),
            idempotency_key="database-scope-generate-001",
            request_id="req-database-scope-generate",
        )
        result = GenerationResult(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            creation_item_id=item.id,
            generation_job_id=job.job_id,
            candidate_no=1,
            status="available",
            file_asset_version_id=file_version.id,
            output_json={},
            created_at=utc_now(),
        )
        session.add(result)
        session.flush()
        adoption = Adoption(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            creation_item_id=item.id,
            generation_result_id=result.id,
            adoption_mode="teacher",
            reason=None,
            adopted_at=utc_now(),
            adopted_by=actor.principal_id,
        )
        session.add(adoption)
        session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            session.add(
                SaveToProjectOperation(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    idempotency_key="database-target-override-001",
                    source_adoption_id=adoption.id,
                    target_project_id=other_project.id,
                    target_slot_key=other_slot_key,
                    replace_mode="reject_if_occupied",
                    authorization_snapshot_json={},
                    status="pending",
                    created_binding_id=None,
                    completed_at=None,
                    created_at=utc_now(),
                    created_by=actor.principal_id,
                )
            )
            session.flush()

        foreign_organization_id = new_uuid7()
        session.add(
            Organization(
                id=foreign_organization_id,
                slug=f"foreign-{foreign_organization_id}",
                name="Foreign tenant",
                status="active",
                created_at=utc_now(),
            )
        )
        session.flush()
        with pytest.raises(DBAPIError), session.begin_nested():
            session.add(
                CreationBatch(
                    id=new_uuid7(),
                    organization_id=foreign_organization_id,
                    source_kind="project",
                    creation_package_id=package.id,
                    source_project_id=package.source_project_id,
                    source_workflow_run_id=package.source_workflow_run_id,
                    source_node_run_id=package.source_node_run_id,
                    studio_type="image",
                    title="Cross-tenant batch",
                    status="ready",
                    created_by=actor.principal_id,
                    updated_by=actor.principal_id,
                )
            )
            session.flush()


def test_creation_package_allows_one_stale_marker_but_rejects_content_changes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        package, _ = seed_project_package(session, actor, project, "lesson.01.image.immutable")
        package.source_stale_at = utc_now()
        session.flush()
        assert package.source_stale_at is not None

        with pytest.raises(DBAPIError), session.begin_nested():
            package.target_rules_json = {"replace_modes": ["append"]}
            session.flush()
