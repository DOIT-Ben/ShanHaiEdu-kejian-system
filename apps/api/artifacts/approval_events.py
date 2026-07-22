"""Transactional events shared by artifact approval actions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.models import Artifact
from apps.api.identity.context import ActorContext
from apps.api.reliability.events import EventResource, EventWriter


def append_stale_approval_event(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
    source_version_id: UUID,
    stale_ids: list[UUID],
    reason_code: str,
    request_id: str | None,
) -> None:
    if not stale_ids:
        return
    EventWriter(session, actor.organization_id).append(
        project_id=artifact.project_id,
        event_type="workflow.downstream_stale.propagated",
        resource=EventResource(type="artifact", id=artifact.id),
        payload={
            "source_version_id": str(source_version_id),
            "affected_resource_ids": [str(item) for item in stale_ids],
            "reason_code": reason_code,
        },
        request_id=request_id,
    )
