"""Tenant-scoped prompt snapshot persistence queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot


class PromptSnapshotRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def context_for_node(self, node_run_id: UUID) -> ContextSnapshot | None:
        return self._session.scalar(
            select(ContextSnapshot).where(
                ContextSnapshot.node_run_id == node_run_id,
                ContextSnapshot.organization_id == self._actor.organization_id,
            )
        )

    def prompt_for_node(self, node_run_id: UUID) -> PromptSnapshot | None:
        return self._session.scalar(
            select(PromptSnapshot).where(
                PromptSnapshot.node_run_id == node_run_id,
                PromptSnapshot.organization_id == self._actor.organization_id,
            )
        )
