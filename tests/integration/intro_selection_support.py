from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.models import Approval, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.identity.context import ActorContext
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from tests.integration.test_intro_option_runtime import (
    _generate_default_nine,  # pyright: ignore[reportPrivateUsage]
    _open_gate,  # pyright: ignore[reportPrivateUsage]
    _validate,  # pyright: ignore[reportPrivateUsage]
)


@dataclass(frozen=True, slots=True)
class ApprovedOptionSet:
    actor: ActorContext
    project_id: UUID
    lesson_unit_id: UUID
    artifact_id: UUID
    version_id: UUID
    approval_id: UUID
    select_node_run_id: UUID
    option_keys: tuple[str, ...]


async def prepare_approved_option_set(
    factory: sessionmaker[Session],
) -> ApprovedOptionSet:
    prepared = await _generate_default_nine(factory)
    _validate(factory, prepared.actor, prepared.version_id)
    _open_gate(factory, prepared.actor, prepared.version_id)
    with factory() as session, session.begin():
        approval = ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve options for Issue 128 selection tests.",
            request_id="issue-128-approve-options",
        )
    with factory() as session:
        select_node_run_id = session.scalar(
            select(NodeRun.id)
            .join(BranchRun, BranchRun.id == NodeRun.branch_run_id)
            .where(
                BranchRun.lesson_unit_id == prepared.lesson_unit_id,
                NodeRun.node_key == "intro.select",
            )
        )
        record = session.get(Approval, approval.id)
        assert select_node_run_id is not None and record is not None
        version = record.artifact_version_id
        artifact_version = session.get(ArtifactVersion, version)
        assert artifact_version is not None
        options = artifact_version.content_json["options"]
        assert isinstance(options, list)
        option_keys = tuple(str(option["option_key"]) for option in options)
    return ApprovedOptionSet(
        actor=prepared.actor,
        project_id=prepared.project_id,
        lesson_unit_id=prepared.lesson_unit_id,
        artifact_id=prepared.artifact_id,
        version_id=prepared.version_id,
        approval_id=approval.id,
        select_node_run_id=select_node_run_id,
        option_keys=option_keys,
    )


def set_select_policy_snapshot(
    factory: sessionmaker[Session],
    prepared: ApprovedOptionSet,
    *,
    mode: str,
    node_rules: list[dict[str, object]],
    policy_version: int,
) -> None:
    with factory() as session, session.begin():
        node = session.get(NodeRun, prepared.select_node_run_id)
        assert node is not None
        run = session.get(WorkflowRun, node.workflow_run_id)
        assert run is not None
        node.automation_policy_snapshot_json = {
            "mode": mode,
            "node_rules": node_rules,
            "policy_version": policy_version,
            "workflow_definition_version_id": str(run.workflow_definition_version_id),
        }
