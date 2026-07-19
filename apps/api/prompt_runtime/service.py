"""Freeze and read tenant-safe prompt runtime snapshots."""

from __future__ import annotations

import hashlib
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


@dataclass(frozen=True, slots=True)
class _LegacyContextProjection:
    technical_chunk: str
    public_chunk: str | None


_LEGACY_SUMMARY_KEYS = frozenset(
    {"binding_key", "source", "exposure", "item_count", "content_hash"}
)
_LEGACY_BINDING_KEYS = frozenset({"binding_key", "source", "exposure", "items"})
_LEGACY_ITEM_KEYS = frozenset({"source_id", "source_version_id", "content"})


def _project_legacy_editable_prompt(
    editable_prompt: str,
    preview_json: dict[str, object],
    bindings_json: dict[str, object],
) -> str:
    projections = _validated_legacy_context_projections(
        editable_prompt,
        preview_json,
        bindings_json,
    )
    if not projections:
        return editable_prompt
    chunks = editable_prompt.split("\n\n")
    technical_suffix = [projection.technical_chunk for projection in projections]
    if len(chunks) < len(technical_suffix) or chunks[-len(technical_suffix) :] != technical_suffix:
        return editable_prompt
    public_suffix = [
        projection.public_chunk for projection in projections if projection.public_chunk is not None
    ]
    return "\n\n".join([*chunks[: -len(technical_suffix)], *public_suffix])


def _validated_legacy_context_projections(
    editable_prompt: str,
    preview_json: dict[str, object],
    bindings_json: dict[str, object],
) -> tuple[_LegacyContextProjection, ...] | None:
    if preview_json.get("editable_prompt") != editable_prompt:
        return None
    summaries = preview_json.get("context_summary")
    bindings_container = _exact_object(bindings_json, frozenset({"bindings"}))
    if not isinstance(summaries, list) or bindings_container is None:
        return None
    bindings = bindings_container["bindings"]
    if not isinstance(bindings, list):
        return None
    summary_items = cast(list[object], summaries)
    binding_items = cast(list[object], bindings)
    if len(summary_items) != len(binding_items):
        return None

    projections: list[_LegacyContextProjection] = []
    for raw_summary, raw_binding in zip(
        summary_items,
        binding_items,
        strict=True,
    ):
        valid, projection = _validate_legacy_context_pair(raw_summary, raw_binding)
        if not valid:
            return None
        if projection is not None:
            projections.append(projection)
    return tuple(projections)


def _validate_legacy_context_pair(
    raw_summary: object,
    raw_binding: object,
) -> tuple[bool, _LegacyContextProjection | None]:
    summary = _exact_object(raw_summary, _LEGACY_SUMMARY_KEYS)
    binding = _exact_object(raw_binding, _LEGACY_BINDING_KEYS)
    if summary is None or binding is None:
        return False, None
    exposure = summary["exposure"]
    binding_key = summary["binding_key"]
    source = summary["source"]
    item_count = summary["item_count"]
    content_hash = summary["content_hash"]
    if not (
        exposure in {"full", "summary", "hidden"}
        and isinstance(binding_key, str)
        and isinstance(source, str)
        and isinstance(item_count, int)
        and not isinstance(item_count, bool)
        and item_count >= 0
        and isinstance(content_hash, str)
        and binding["binding_key"] == binding_key
        and binding["source"] == source
        and binding["exposure"] == exposure
    ):
        return False, None
    items = _validated_legacy_items(binding["items"])
    if items is None or len(items) != item_count:
        return False, None
    canonical_items = _canonical_json_text({"items": items})
    if (
        canonical_items is None
        or hashlib.sha256(canonical_items.encode()).hexdigest() != content_hash
    ):
        return False, None
    if exposure == "hidden":
        return True, None
    if exposure == "summary":
        return (
            True,
            _LegacyContextProjection(
                technical_chunk=(
                    f"[context:{binding_key}] source={source} "
                    f"items={item_count} hash={content_hash}"
                ),
                public_chunk=None,
            ),
        )
    technical_chunk = _canonical_json_text({"context": items})
    public_chunk = _canonical_json_text({"context": [item["content"] for item in items]})
    if technical_chunk is None or public_chunk is None:
        return False, None
    return True, _LegacyContextProjection(
        technical_chunk=technical_chunk,
        public_chunk=public_chunk,
    )


def _validated_legacy_items(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list):
        return None
    items: list[dict[str, object]] = []
    sort_keys: list[tuple[str, str]] = []
    for raw_item in cast(list[object], value):
        item = _exact_object(raw_item, _LEGACY_ITEM_KEYS)
        if item is None:
            return None
        source_id = item["source_id"]
        source_version_id = item["source_version_id"]
        if (
            not isinstance(source_id, str)
            or not source_id
            or not isinstance(source_version_id, str | None)
        ):
            return None
        items.append(item)
        sort_keys.append((source_id, source_version_id or ""))
    if sort_keys != sorted(sort_keys):
        return None
    return items


def _exact_object(value: object, keys: frozenset[str]) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result = cast(dict[str, object], value)
    if frozenset(result) != keys:
        return None
    return result


def _canonical_json_text(value: object) -> str | None:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None


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
        context = self._repository.context_for_node(node_run_id)
        editable_prompt = prompt.editable_prompt
        if context is not None:
            editable_prompt = _project_legacy_editable_prompt(
                editable_prompt,
                prompt.preview_json,
                context.bindings_json,
            )
        return PromptPreviewRead(
            prompt_snapshot_id=prompt.id,
            content_hash=prompt.content_hash,
            editable_prompt=editable_prompt,
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
