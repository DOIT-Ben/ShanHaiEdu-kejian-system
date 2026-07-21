"""Prompt snapshot adapter used by the generic node execution transaction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.prompt_runtime.service import PromptSnapshotError, PromptSnapshotService
from apps.api.runtime_boundary.ports import FrozenSnapshotRefs
from workflow.prompt_runtime import AssembledContext, CompiledPrompt


class SqlAlchemyPromptSnapshotPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._service = PromptSnapshotService(session, actor)

    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: AssembledContext,
        prompt: CompiledPrompt,
    ) -> FrozenSnapshotRefs:
        try:
            frozen = self._service.freeze(node_run_id, context=context, prompt=prompt)
        except PromptSnapshotError:
            raise
        return FrozenSnapshotRefs(
            context_snapshot_id=frozen.context.id,
            prompt_snapshot_id=frozen.prompt.id,
            context_hash=frozen.context.content_hash,
            prompt_hash=frozen.prompt.content_hash,
        )

    def verify(self, refs: FrozenSnapshotRefs) -> None:
        context = self._session.get(ContextSnapshot, refs.context_snapshot_id)
        prompt = self._session.get(PromptSnapshot, refs.prompt_snapshot_id)
        if (
            context is None
            or prompt is None
            or context.organization_id != self._actor.organization_id
            or prompt.organization_id != self._actor.organization_id
            or context.content_hash != refs.context_hash
            or prompt.content_hash != refs.prompt_hash
        ):
            raise PromptSnapshotError(
                "NODE_EXECUTION_SNAPSHOT_MISMATCH",
                "a frozen prompt or context snapshot is no longer valid",
            )
