"""Freeze and read tenant-safe prompt runtime snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import cast
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
            editable_prompt=self._public_editable_prompt(prompt),
            edit_policy=self._public_edit_policy(prompt.preview_json),
        )

    @classmethod
    def _public_editable_prompt(cls, prompt: PromptSnapshot) -> str:
        legacy_summaries, full_context_counts = cls._legacy_context_metadata(prompt.preview_json)
        full_context_index = 0
        chunks: list[str] = []
        for chunk in prompt.editable_prompt.split("\n\n"):
            if chunk in legacy_summaries:
                continue
            if full_context_index < len(full_context_counts):
                sanitized = cls._sanitize_legacy_full_context(
                    chunk,
                    expected_items=full_context_counts[full_context_index],
                )
                if sanitized != chunk:
                    chunk = sanitized
                    full_context_index += 1
            chunks.append(chunk)
        return "\n\n".join(chunks)

    @staticmethod
    def _legacy_context_metadata(
        preview_json: dict[str, object],
    ) -> tuple[set[str], tuple[int, ...]]:
        summaries = preview_json.get("context_summary")
        if not isinstance(summaries, list):
            return set(), ()
        chunks: set[str] = set()
        full_context_counts: list[int] = []
        for raw_summary in cast(list[object], summaries):
            if not isinstance(raw_summary, dict):
                continue
            summary = cast(dict[str, object], raw_summary)
            exposure = summary.get("exposure")
            binding_key = summary.get("binding_key")
            source = summary.get("source")
            item_count = summary.get("item_count")
            content_hash = summary.get("content_hash")
            if not (
                isinstance(binding_key, str)
                and isinstance(source, str)
                and isinstance(item_count, int)
                and not isinstance(item_count, bool)
                and isinstance(content_hash, str)
            ):
                continue
            if exposure == "summary":
                chunks.add(
                    f"[context:{binding_key}] source={source} "
                    f"items={item_count} hash={content_hash}"
                )
            elif exposure == "full":
                full_context_counts.append(item_count)
        return chunks, tuple(full_context_counts)

    @staticmethod
    def _sanitize_legacy_full_context(chunk: str, *, expected_items: int) -> str:
        try:
            payload: object = json.loads(chunk)
        except json.JSONDecodeError:
            return chunk
        if not isinstance(payload, dict):
            return chunk
        payload_dict = cast(dict[str, object], payload)
        if set(payload_dict) != {"context"}:
            return chunk
        context = payload_dict["context"]
        if not isinstance(context, list):
            return chunk
        context_items = cast(list[object], context)
        if len(context_items) != expected_items:
            return chunk
        contents: list[object] = []
        for raw_item in context_items:
            if not isinstance(raw_item, dict):
                return chunk
            item = cast(dict[str, object], raw_item)
            if "content" not in item or not ({"source_id", "source_version_id"} & item.keys()):
                return chunk
            contents.append(item["content"])
        return json.dumps(
            {"context": contents},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
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
