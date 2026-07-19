"""Freeze and read tenant-safe prompt runtime snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.prompt_runtime.repository import PromptSnapshotRepository
from apps.api.prompt_runtime.schemas import PromptEditPolicyRead, PromptPreviewRead
from apps.api.workflows.models import NodeRun, WorkflowRun
from apps.api.workflows.repository import WorkflowRuntimeRepository
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import AssembledContext, CompiledPrompt


class PromptSnapshotError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class FrozenPromptSnapshots:
    context: ContextSnapshot
    prompt: PromptSnapshot


class PromptSnapshotService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = PromptSnapshotRepository(session, actor)
        self._workflow_repository = WorkflowRuntimeRepository(session, actor)

    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: AssembledContext,
        prompt: CompiledPrompt,
    ) -> FrozenPromptSnapshots:
        node, run = self._require_node_and_run(
            node_run_id,
            action=ProjectAction.GENERATE,
            for_update=True,
        )
        if prompt.context_hash != context.content_hash:
            raise PromptSnapshotError(
                "PROMPT_CONTEXT_HASH_MISMATCH",
                "compiled prompt does not reference the supplied context snapshot",
            )
        existing = self._existing(node.id)
        if existing is not None:
            if (
                existing.context.content_hash == context.content_hash
                and existing.prompt.content_hash == prompt.content_hash
            ):
                return existing
            raise PromptSnapshotError(
                "PROMPT_SNAPSHOT_ALREADY_FROZEN",
                "node prompt snapshots already exist with different content",
            )
        if NodeStatus(node.status) not in {NodeStatus.READY, NodeStatus.DRAFT}:
            raise PromptSnapshotError(
                "PROMPT_SNAPSHOT_NODE_FROZEN",
                "prompt snapshots must be created before node execution starts",
            )

        context_record = ContextSnapshot(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=run.project_id,
            node_run_id=node.id,
            bindings_json={"bindings": list(context.bindings)},
            content_hash=context.content_hash,
            created_by=self._actor.principal_id,
        )
        self._session.add(context_record)
        self._session.flush()
        preview = asdict(prompt.preview)
        preview["schema"] = preview.pop("output_schema")
        prompt_record = PromptSnapshot(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=run.project_id,
            node_run_id=node.id,
            context_snapshot_id=context_record.id,
            template_refs_json=prompt.template_refs,
            layers_json={"layers": list(prompt.layers)},
            editable_prompt=prompt.editable_prompt,
            user_diff_json=prompt.user_diff,
            compiled_prompt=prompt.compiled_prompt,
            request_schema_json=prompt.request_schema,
            preview_json=preview,
            content_hash=prompt.content_hash,
            created_by=self._actor.principal_id,
        )
        self._session.add(prompt_record)
        self._session.flush()
        return FrozenPromptSnapshots(context=context_record, prompt=prompt_record)

    def get_prompt(self, node_run_id: UUID) -> PromptSnapshot:
        self._require_node_and_run(node_run_id, action=ProjectAction.VIEW)
        prompt = self._repository.prompt_for_node(node_run_id)
        if prompt is None:
            raise PromptSnapshotError(
                "PROMPT_SNAPSHOT_NOT_FOUND",
                "prompt snapshot was not found",
            )
        return prompt

    def get_public_preview(self, node_run_id: UUID) -> PromptPreviewRead:
        prompt = self.get_prompt(node_run_id)
        return PromptPreviewRead(
            prompt_snapshot_id=prompt.id,
            content_hash=prompt.content_hash,
            editable_prompt=prompt.editable_prompt,
            edit_policy=self._public_edit_policy(prompt.preview_json),
        )

    @staticmethod
    def _public_edit_policy(preview_json: dict[str, object]) -> PromptEditPolicyRead:
        candidate = preview_json.get("edit_policy")
        if isinstance(candidate, dict):
            try:
                return PromptEditPolicyRead.model_validate(candidate)
            except ValueError:
                pass
        return PromptEditPolicyRead(mode="replace_editable_layer", max_chars=100_000)

    def _existing(self, node_run_id: UUID) -> FrozenPromptSnapshots | None:
        context = self._repository.context_for_node(node_run_id)
        prompt = self._repository.prompt_for_node(node_run_id)
        if context is None and prompt is None:
            return None
        if context is None or prompt is None or prompt.context_snapshot_id != context.id:
            raise PromptSnapshotError(
                "PROMPT_SNAPSHOT_INCONSISTENT",
                "node prompt snapshot records are inconsistent",
            )
        return FrozenPromptSnapshots(context=context, prompt=prompt)

    def _require_node_and_run(
        self,
        node_run_id: UUID,
        *,
        action: ProjectAction,
        for_update: bool = False,
    ) -> tuple[NodeRun, WorkflowRun]:
        node = self._workflow_repository.get_node(node_run_id, for_update=for_update)
        if node is None:
            raise PromptSnapshotError("NODE_RUN_NOT_FOUND", "node run was not found")
        run = self._workflow_repository.get_run(node.workflow_run_id)
        if run is None:
            raise PromptSnapshotError("NODE_RUN_NOT_FOUND", "node run was not found")
        ProjectAccessService(self._session, self._actor).require(run.project_id, action)
        return node, run
