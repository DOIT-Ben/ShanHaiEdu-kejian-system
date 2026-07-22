"""Atomic lock and lineage handling for immutable artifact replacements."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.approval_completion import retire_declared_approval_gate
from apps.api.artifacts.domain import ArtifactRelationType
from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.artifacts.models import Approval, Artifact, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.ports import GeneratedArtifactWrite
from apps.api.workflows.approval_port import WorkflowApprovalReader


class ArtifactReplacementService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ArtifactRepository(session, actor)
        self._relations = ArtifactRelationService(session, actor)

    def lock_project_mutation(self, project_id: UUID, *, action: ProjectAction) -> None:
        self._relations.lock_project_mutation(project_id, action=action)

    def lock_artifact_mutation(
        self,
        artifact_id: UUID,
        *,
        action: ProjectAction,
    ) -> Artifact:
        visible = self._repository.get(artifact_id)
        if visible is None:
            raise _not_found()
        self.lock_project_mutation(visible.project_id, action=action)
        locked = self._repository.get(artifact_id, for_update=True)
        if locked is None or locked.project_id != visible.project_id:
            raise _not_found()
        return locked

    def prepare_manual(
        self,
        artifact: Artifact,
        gate_version_id: UUID | None,
        lineage_version_id: UUID | None,
        replacement: ArtifactVersion,
    ) -> None:
        if gate_version_id is not None:
            project = self._relations.lock_project_mutation(
                artifact.project_id,
                action=ProjectAction.EDIT,
            )
            self._retire_gate(
                artifact,
                self._require_previous(artifact, gate_version_id),
                fixed_release=(
                    project.content_release_id,
                    project.workflow_definition_version_id,
                ),
            )
        carry_version_id = gate_version_id or lineage_version_id
        if carry_version_id is not None:
            previous = self._require_previous(artifact, carry_version_id)
            self._carry_incoming_dependencies(previous.id, replacement.id)

    def prepare_generated(
        self,
        artifact: Artifact,
        previous_version_id: UUID | None,
        replacement: ArtifactVersion,
        *,
        node_run_id: UUID,
    ) -> None:
        if previous_version_id is None:
            return
        fixed_release = WorkflowApprovalReader(self._session).fixed_release_for_node(
            node_run_id,
            organization_id=self._actor.organization_id,
            project_id=artifact.project_id,
        )
        if fixed_release is None:
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_FIXED_RELEASE_MISSING",
                "the replacement artifact has no fixed workflow release",
            )
        previous = self._require_previous(artifact, previous_version_id)
        self._retire_gate(
            artifact,
            previous,
            fixed_release=fixed_release,
        )
        self._carry_incoming_dependencies(previous.id, replacement.id)

    def submit_generated(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        write: GeneratedArtifactWrite,
    ) -> None:
        self._session.add(
            Approval(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                artifact_version_id=version.id,
                node_run_id=write.node_run_id,
                action="submit",
                actor_type=self._actor.actor_type,
                actor_user_id=self._actor.user_id,
                comment=None,
                quality_evidence_json={"status": "validated"},
                policy_snapshot_json={},
                created_by=self._actor.principal_id,
            )
        )
        artifact.current_submitted_version_id = version.id
        artifact.status = "in_review"
        artifact.stale_reason_json = None
        artifact.updated_at = utc_now()
        artifact.updated_by = self._actor.principal_id
        artifact.lock_version += 1
        self._session.flush()

    def _retire_gate(
        self,
        artifact: Artifact,
        previous: ArtifactVersion,
        *,
        fixed_release: tuple[UUID, UUID],
    ) -> None:
        retire_declared_approval_gate(
            self._session,
            self._actor,
            artifact,
            previous,
            fixed_release=fixed_release,
            review_completion=False,
        )

    def _require_previous(
        self,
        artifact: Artifact,
        version_id: UUID,
    ) -> ArtifactVersion:
        previous = self._session.get(ArtifactVersion, version_id)
        if previous is None or previous.artifact_id != artifact.id:
            raise _not_found()
        return previous

    def _carry_incoming_dependencies(
        self,
        previous_version_id: UUID,
        replacement_version_id: UUID,
    ) -> None:
        rows = self._session.execute(
            select(
                ArtifactRelation,
                ArtifactVersion.artifact_id,
                Artifact.current_approved_version_id,
                Artifact.status,
                Artifact.deleted_at,
            )
            .join(
                ArtifactVersion,
                ArtifactVersion.id == ArtifactRelation.from_artifact_version_id,
            )
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactRelation.organization_id == self._actor.organization_id,
                ArtifactRelation.to_artifact_version_id == previous_version_id,
                ArtifactRelation.relation_type != ArtifactRelationType.SUPERSEDES.value,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
            )
            .order_by(
                ArtifactVersion.artifact_id,
                ArtifactRelation.relation_type,
                ArtifactRelation.binding_key,
                ArtifactRelation.id,
            )
        ).all()
        grouped: dict[tuple[UUID, str, str], list[tuple[ArtifactRelation, bool]]] = defaultdict(
            list
        )
        for relation, source_artifact_id, current_version_id, status, deleted_at in rows:
            key = (source_artifact_id, relation.relation_type, relation.binding_key)
            grouped[key].append(
                (
                    relation,
                    current_version_id == relation.from_artifact_version_id
                    and status == "approved"
                    and deleted_at is None,
                )
            )
        for relation in _current_incoming_relations(grouped):
            self._relations.add(
                from_version_id=relation.from_artifact_version_id,
                to_version_id=replacement_version_id,
                relation_type=relation.relation_type,
                binding_key=relation.binding_key,
                impact_scope=relation.impact_scope_json,
            )


def _current_incoming_relations(
    grouped: Mapping[tuple[UUID, str, str], list[tuple[ArtifactRelation, bool]]],
) -> list[ArtifactRelation]:
    selected: list[ArtifactRelation] = []
    for candidates in grouped.values():
        current = [relation for relation, active in candidates if active]
        if len(current) != 1:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_SOURCE_VERSION_STALE",
                message="An inherited artifact dependency is no longer current and approved.",
            )
        selected.append(current[0])
    return selected


def _not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="ARTIFACT_NOT_FOUND",
        message="The artifact resource was not found.",
    )
