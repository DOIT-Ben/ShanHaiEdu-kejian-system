"""Immutable exact optional-Artifact selection owned by Workflow runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.workflows.models import NodeInputSnapshot, NodeRun, WorkflowRun
from workflow.node_state import NodeStatus

ARTIFACT_INPUT_SELECTION_KEY = "runtime.artifact_input_selection"


class ArtifactInputSelectionWriter:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        error_code: str = "ARTIFACT_WORKFLOW_RUNTIME_INVALID",
    ) -> None:
        self._session = session
        self._actor = actor
        self._error_code = error_code

    def freeze(self, node_run_id: UUID, selection: Mapping[str, UUID]) -> None:
        row = self._session.execute(
            select(NodeRun, WorkflowRun)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(
                NodeRun.id == node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.deleted_at.is_(None),
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.deleted_at.is_(None),
            )
            .with_for_update(of=NodeRun)
        ).one_or_none()
        if row is None:
            raise self._invalid("The Artifact generation node is unavailable.")
        node, run = row
        if NodeStatus(node.status) is not NodeStatus.READY:
            raise self._invalid("The Artifact generation node is not ready.")
        payload = artifact_input_selection_payload(selection)
        content_hash = artifact_input_selection_hash(payload)
        existing = self._session.scalar(
            select(NodeInputSnapshot)
            .where(
                NodeInputSnapshot.node_run_id == node.id,
                NodeInputSnapshot.input_key == ARTIFACT_INPUT_SELECTION_KEY,
            )
            .with_for_update(of=NodeInputSnapshot)
        )
        if existing is not None:
            if existing.content_hash == content_hash and existing.snapshot_json == payload:
                return
            raise self._invalid("The generation node already has another exact input selection.")
        self._session.add(
            NodeInputSnapshot(
                id=new_uuid7(),
                node_run_id=node.id,
                input_key=ARTIFACT_INPUT_SELECTION_KEY,
                source_type="workflow_definition",
                source_id=run.id,
                source_version_id=run.workflow_definition_version_id,
                content_hash=content_hash,
                snapshot_json=payload,
                created_by=self._actor.principal_id,
            )
        )
        self._session.flush()

    def _invalid(self, message: str) -> ApiError:
        return ApiError(status_code=409, code=self._error_code, message=message)


class ArtifactInputSelectionReader:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        error_code: str = "ARTIFACT_WORKFLOW_RUNTIME_INVALID",
    ) -> None:
        self._session = session
        self._actor = actor
        self._error_code = error_code

    def for_node(self, node_run_id: UUID) -> dict[str, UUID] | None:
        row = self._session.execute(
            select(NodeInputSnapshot, NodeRun, WorkflowRun)
            .join(NodeRun, NodeRun.id == NodeInputSnapshot.node_run_id)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(
                NodeRun.id == node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.deleted_at.is_(None),
                NodeInputSnapshot.input_key == ARTIFACT_INPUT_SELECTION_KEY,
            )
        ).one_or_none()
        if row is None:
            return None
        snapshot, node, run = row
        if (
            snapshot.source_type != "workflow_definition"
            or snapshot.source_id != node.workflow_run_id
            or snapshot.source_version_id != run.workflow_definition_version_id
        ):
            raise self._invalid("The exact Artifact input selection is outside the workflow.")
        try:
            return parse_artifact_input_selection(snapshot)
        except ValueError as exc:
            raise self._invalid(str(exc)) from exc

    def _invalid(self, message: str) -> ApiError:
        return ApiError(status_code=409, code=self._error_code, message=message)


def artifact_input_selection_payload(selection: Mapping[str, UUID]) -> dict[str, Any]:
    if any(
        type(key) is not str or not key or type(value) is not UUID
        for key, value in selection.items()
    ):
        raise ValueError("artifact input selection is invalid")
    return {
        "artifact_versions": {
            key: str(value) for key, value in sorted(selection.items(), key=lambda item: item[0])
        }
    }


def artifact_input_selection_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_artifact_input_selection(snapshot: NodeInputSnapshot) -> dict[str, UUID]:
    payload = cast(Mapping[str, Any], snapshot.snapshot_json)
    if snapshot.content_hash != artifact_input_selection_hash(payload):
        raise ValueError("artifact input selection hash differs")
    raw = payload.get("artifact_versions")
    if not isinstance(raw, Mapping):
        raise ValueError("artifact input selection is invalid")
    try:
        values: dict[str, UUID] = {}
        for key, value in cast(Mapping[object, object], raw).items():
            if type(key) is not str:
                raise ValueError("artifact input selection key is invalid")
            values[key] = UUID(str(value))
        return values
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact input selection is invalid") from exc
