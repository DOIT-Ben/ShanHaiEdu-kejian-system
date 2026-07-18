"""Authorization boundary for project-backed and standalone creation batches."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.creation.models import CreationBatch
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService


class CreationBatchAccessService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require(
        self,
        batch: CreationBatch,
        action: ProjectAction,
        *,
        for_update: bool = False,
    ) -> None:
        if batch.source_project_id is not None:
            ProjectAccessService(self._session, self._actor).require(
                batch.source_project_id,
                action,
                for_update=for_update,
            )
            return
        if (
            self._actor.user_id is not None
            and not self._actor.is_system
            and batch.owner_user_id == self._actor.user_id
        ):
            return
        raise ApiError(status_code=403, code="PERMISSION_DENIED", message="Access denied.")
