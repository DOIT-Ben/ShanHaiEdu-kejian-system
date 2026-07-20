"""Prompt snapshot adapter used by the generic node execution transaction."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.prompt_runtime.service import PromptSnapshotError, PromptSnapshotService
from apps.api.runtime_boundary.ports import FrozenSnapshotRefs
from workflow.prompt_runtime import AssembledContext, CompiledPrompt


class SqlAlchemyPromptSnapshotPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
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
