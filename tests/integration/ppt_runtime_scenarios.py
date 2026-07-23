from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.ppt_runtime_support import PptSeed
from workflow.node_state import NodeStatus


@dataclass(frozen=True, slots=True)
class PageRevision:
    version_id: UUID
    stale_artifact_ids: tuple[UUID, ...]
    stale_node_ids: tuple[UUID, ...]


def create_export_node(factory: sessionmaker[Session], seeded: PptSeed) -> UUID:
    with factory() as session, session.begin():
        node = WorkflowRuntimeService(session, seeded.actor).create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="pptx.export",
            status=NodeStatus.READY,
        )
    return node.id


def create_assemble_node(factory: sessionmaker[Session], seeded: PptSeed) -> UUID:
    with factory() as session, session.begin():
        node = WorkflowRuntimeService(session, seeded.actor).create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="ppt.pages.assemble",
            status=NodeStatus.READY,
        )
    return node.id


def revise_first_page_title(
    factory: sessionmaker[Session],
    seeded: PptSeed,
    *,
    title: str,
) -> PageRevision:
    with factory() as session, session.begin():
        previous = session.get(ArtifactVersion, seeded.page_specs_version_id)
        assert previous is not None
        artifact = session.get(Artifact, previous.artifact_id)
        assert artifact is not None
        content = deepcopy(previous.content_json)
        content["page_specs"][0]["editable_text_blocks"][0]["content"] = title
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=previous.organization_id,
            artifact_id=previous.artifact_id,
            version_no=previous.version_no + 1,
            content_json=content,
            content_hash=canonical_content_hash(content),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        relations = ArtifactRelationService(session, seeded.actor)
        relations.add(
            from_version_id=previous.id,
            to_version_id=replacement.id,
            relation_type="supersedes",
            binding_key="page-title-revision",
            impact_scope={"mode": "all"},
        )
        stale_artifact_ids, stale_node_ids = relations.propagate_stale(
            previous.id,
            replacement.id,
        )
        for action in ("submit", "approve"):
            session.add(
                Approval(
                    id=new_uuid7(),
                    organization_id=previous.organization_id,
                    artifact_version_id=replacement.id,
                    node_run_id=None,
                    action=action,
                    actor_type=seeded.actor.actor_type,
                    actor_user_id=seeded.actor.user_id,
                    comment="Golden page title revision.",
                    quality_evidence_json={},
                    policy_snapshot_json={},
                    created_by=seeded.actor.principal_id,
                )
            )
        artifact.current_submitted_version_id = None
        artifact.current_approved_version_id = replacement.id
        artifact.status = "approved"
        artifact.stale_reason_json = None
        artifact.updated_at = utc_now()
        artifact.updated_by = seeded.actor.principal_id
        artifact.lock_version += 1
        session.flush()
    return PageRevision(
        version_id=replacement.id,
        stale_artifact_ids=tuple(stale_artifact_ids),
        stale_node_ids=tuple(stale_node_ids),
    )
