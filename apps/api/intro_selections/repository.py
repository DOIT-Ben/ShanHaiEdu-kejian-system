"""IntroSelection-owned persistence operations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.intro_selections.models import IntroSelection


class IntroSelectionRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def replace_active(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        source_approval_id: UUID,
        selection_method: str,
        option_key: str,
        snapshot: dict[str, Any],
        policy_evidence: dict[str, Any],
        recommendation_evidence: dict[str, Any],
        reason: str,
    ) -> IntroSelection:
        current = self.current(lesson_unit_id, for_update=True)
        now = utc_now()
        if current is not None:
            current.active = False
            current.deactivated_at = now
            current.deactivated_by = self._actor.principal_id
            self._session.flush()
        record = IntroSelection(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
            artifact_version_id=artifact_version_id,
            source_approval_id=source_approval_id,
            selection_method=selection_method,
            option_key=option_key,
            snapshot_json=deepcopy(snapshot),
            actor_type=self._actor.actor_type,
            actor_user_id=self._actor.user_id,
            policy_evidence_json=deepcopy(policy_evidence),
            recommendation_evidence_json=deepcopy(recommendation_evidence),
            reason=reason.strip(),
            active=True,
            selected_at=now,
            created_by=self._actor.principal_id,
            deactivated_at=None,
            deactivated_by=None,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def get(self, selection_id: UUID) -> IntroSelection | None:
        return self._session.scalar(
            select(IntroSelection).where(
                IntroSelection.id == selection_id,
                IntroSelection.organization_id == self._actor.organization_id,
            )
        )

    def current(
        self,
        lesson_unit_id: UUID,
        *,
        for_update: bool = False,
    ) -> IntroSelection | None:
        statement = select(IntroSelection).where(
            IntroSelection.organization_id == self._actor.organization_id,
            IntroSelection.lesson_unit_id == lesson_unit_id,
            IntroSelection.active.is_(True),
        )
        if for_update:
            statement = statement.with_for_update(of=IntroSelection)
        return self._session.scalar(statement)
