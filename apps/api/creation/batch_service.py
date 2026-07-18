"""Creation batch source validation and initialization."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.creation.models import CreationBatch, CreationItem
from apps.api.creation.presenters import present_batch
from apps.api.creation.repository import CreationRepository
from apps.api.creation.schemas import (
    CreateCreationBatchRequest,
    LegacyCreateCreationBatchRequest,
    ProjectCreateCreationBatchRequest,
    ProjectCreationBatchRead,
    StandaloneCreateCreationBatchRequest,
    StandaloneCreationBatchRead,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter, append_outbox_only
from apps.api.reliability.idempotency import CommandResult, IdempotencyService


class CreationBatchService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = CreationRepository(session, actor.organization_id)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def create(
        self,
        payload: CreateCreationBatchRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> ProjectCreationBatchRead | StandaloneCreationBatchRead:
        current = self._normalize_request(payload)

        def command() -> CommandResult:
            if isinstance(current, ProjectCreateCreationBatchRequest):
                batch = self._create_project(current, request_id=request_id)
            else:
                batch = self._create_standalone(current, request_id=request_id)
            body = present_batch(batch, self._repository.batch_items(batch.id)).model_dump(
                mode="json"
            )
            return CommandResult(201, body, "creation_batch", batch.id)

        result = self._idempotency.execute(
            scope=f"creation_batches.create:{self._actor.principal_id}",
            key=idempotency_key,
            payload=current.model_dump(mode="json"),
            command=command,
        )
        if result.body.get("source_kind") == "project":
            return ProjectCreationBatchRead.model_validate(result.body)
        return StandaloneCreationBatchRead.model_validate(result.body)

    def _create_project(
        self,
        payload: ProjectCreateCreationBatchRequest,
        *,
        request_id: str,
    ) -> CreationBatch:
        package = self._repository.get_package(payload.creation_package_id, for_update=True)
        if package is None or package.status != "ready" or package.source_stale_at is not None:
            raise ApiError(
                status_code=422,
                code="CREATION_PACKAGE_REQUIRED",
                message="A current ready creation package is required.",
            )
        ProjectAccessService(self._session, self._actor).require(
            package.source_project_id,
            ProjectAction.GENERATE,
        )
        if package.package_type != payload.studio_type:
            raise ApiError(
                status_code=422,
                code="CREATION_SOURCE_MISMATCH",
                message="The creation package type does not match the studio.",
            )
        package_items = self._repository.package_items(package.id)
        if not package_items or any(not item.target_slot_key for item in package_items):
            raise ApiError(
                status_code=422,
                code="CREATION_PACKAGE_REQUIRED",
                message="The creation package must contain fixed target slots.",
            )
        batch = self._new_batch(
            source_kind="project",
            creation_package_id=package.id,
            source_project_id=package.source_project_id,
            source_workflow_run_id=package.source_workflow_run_id,
            source_node_run_id=package.source_node_run_id,
            studio_type=payload.studio_type,
            title=payload.title,
            status="ready",
        )
        for package_item in package_items:
            self._session.add(
                CreationItem(
                    id=new_uuid7(),
                    organization_id=self._actor.organization_id,
                    creation_batch_id=batch.id,
                    creation_package_item_id=package_item.id,
                    item_key=package_item.item_key,
                    title=package_item.title,
                    status="ready",
                    current_prompt_version_id=None,
                    active_adoption_id=None,
                    target_slot_key=package_item.target_slot_key,
                    created_by=self._actor.principal_id,
                    updated_by=self._actor.principal_id,
                )
            )
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=package.source_project_id,
            event_type="creation.batch.created",
            resource=EventResource(type="creation_batch", id=batch.id),
            payload={"source_kind": "project", "creation_package_id": str(package.id)},
            request_id=request_id,
        )
        return batch

    def _create_standalone(
        self,
        payload: StandaloneCreateCreationBatchRequest,
        *,
        request_id: str,
    ) -> CreationBatch:
        if self._actor.user_id is None or self._actor.is_system:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="Standalone creation requires a user actor.",
            )
        batch = self._new_batch(
            source_kind="standalone",
            creation_package_id=None,
            source_project_id=None,
            source_workflow_run_id=None,
            source_node_run_id=None,
            studio_type=payload.studio_type,
            title=payload.title,
            status="draft",
        )
        append_outbox_only(
            self._session,
            self._actor.organization_id,
            event_type="creation.batch.created",
            resource=EventResource(type="creation_batch", id=batch.id),
            payload={"source_kind": "standalone", "creation_package_id": None},
            request_id=request_id,
        )
        return batch

    def _new_batch(self, **values: object) -> CreationBatch:
        batch = CreationBatch(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            owner_user_id=self._actor.user_id,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
            **values,
        )
        self._session.add(batch)
        self._session.flush()
        return batch

    @staticmethod
    def _normalize_request(
        payload: CreateCreationBatchRequest,
    ) -> ProjectCreateCreationBatchRequest | StandaloneCreateCreationBatchRequest:
        if isinstance(payload, LegacyCreateCreationBatchRequest):
            if payload.creation_package_id is not None:
                return ProjectCreateCreationBatchRequest(
                    source_kind="project",
                    studio_type=payload.studio_type,
                    title=payload.title,
                    creation_package_id=payload.creation_package_id,
                )
            return StandaloneCreateCreationBatchRequest(
                source_kind="standalone",
                studio_type=payload.studio_type,
                title=payload.title,
            )
        return payload
