"""Artifact dependency graph writes and precise stale propagation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from apps.api.artifacts.domain import ArtifactInvariantError, ensure_relation_is_acyclic
from apps.api.artifacts.models import Artifact, ArtifactDraft, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.projects.models import Project
from apps.api.workflows.models import NodeRun


class ArtifactRelationService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ArtifactRepository(session, actor)

    def add(
        self,
        *,
        from_version_id: UUID,
        to_version_id: UUID,
        relation_type: str,
        binding_key: str,
        impact_scope: dict[str, Any],
    ) -> ArtifactRelation:
        if relation_type not in {"derives_from", "references", "constrains", "supersedes"}:
            raise self._invalid("The artifact relation type is invalid.")
        if not binding_key.strip() or len(binding_key) > 160:
            raise self._invalid("The binding_key value is invalid.")
        source = self._repository.get_version(from_version_id)
        target = self._repository.get_version(to_version_id)
        if source is None or target is None:
            raise self._not_found()
        source_version, source_artifact = source
        target_version, target_artifact = target
        self._require_project(source_artifact.project_id)
        self._require_project(target_artifact.project_id)
        if source_artifact.project_id != target_artifact.project_id:
            raise self._invalid("Artifact relations cannot cross project boundaries.")
        self._lock_relation_graph()
        existing = self._find_existing(
            source_version.id, target_version.id, relation_type, binding_key
        )
        if existing is not None:
            return existing
        self._ensure_acyclic(source_artifact.id, target_artifact.id)
        relation = ArtifactRelation(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            from_artifact_version_id=source_version.id,
            to_artifact_version_id=target_version.id,
            relation_type=relation_type,
            binding_key=binding_key,
            impact_scope_json=impact_scope,
            created_by=self._actor.principal_id,
        )
        self._session.add(relation)
        self._session.flush()
        return relation

    def propagate_stale(
        self,
        previous_version_id: UUID | None,
        replacement_version_id: UUID | None,
    ) -> tuple[list[UUID], list[UUID]]:
        if previous_version_id is None or previous_version_id == replacement_version_id:
            return [], []
        grouped = self._group_downstream_relations(previous_version_id)
        stale_ids: list[UUID] = []
        stale_node_ids: list[UUID] = []
        for artifact_id in sorted(grouped, key=str):
            downstream = self._repository.get(artifact_id, for_update=True)
            if downstream is None:
                continue
            current_ids = {
                downstream.current_submitted_version_id,
                downstream.current_approved_version_id,
            }
            active = [
                relation
                for relation in grouped[artifact_id]
                if relation.to_artifact_version_id in current_ids
            ]
            if not active:
                continue
            downstream.status = "stale"
            downstream.stale_reason_json = self._stale_reason(
                previous_version_id, replacement_version_id, active
            )
            self._touch(downstream)
            stale_node_ids.extend(self._mark_nodes_stale(active, downstream.stale_reason_json))
            stale_ids.append(downstream.id)
        return stale_ids, stale_node_ids

    def _group_downstream_relations(
        self,
        version_id: UUID,
    ) -> dict[UUID, list[ArtifactRelation]]:
        grouped: dict[UUID, list[ArtifactRelation]] = defaultdict(list)
        for relation in self._repository.downstream_relations(version_id):
            downstream_version = self._session.get(ArtifactVersion, relation.to_artifact_version_id)
            if downstream_version is not None:
                grouped[downstream_version.artifact_id].append(relation)
        return grouped

    def _mark_nodes_stale(
        self,
        relations: list[ArtifactRelation],
        stale_reason: dict[str, Any] | None,
    ) -> list[UUID]:
        target_ids = {relation.to_artifact_version_id for relation in relations}
        nodes = list(
            self._session.scalars(
                select(NodeRun)
                .where(
                    NodeRun.organization_id == self._actor.organization_id,
                    NodeRun.active_artifact_version_id.in_(target_ids),
                    NodeRun.deleted_at.is_(None),
                )
                .with_for_update()
            )
        )
        for node in nodes:
            node.status = "stale"
            node.stale_reason_json = stale_reason
            self._touch(node)
        return [node.id for node in nodes]

    @staticmethod
    def _stale_reason(
        previous_version_id: UUID,
        replacement_version_id: UUID | None,
        relations: list[ArtifactRelation],
    ) -> dict[str, Any]:
        return {
            "replaced_upstream_version_id": str(previous_version_id),
            "replacement_version_id": (
                str(replacement_version_id) if replacement_version_id is not None else None
            ),
            "bindings": [
                {
                    "binding_key": relation.binding_key,
                    "impact_scope": relation.impact_scope_json,
                }
                for relation in relations
            ],
        }

    def _find_existing(
        self,
        source_version_id: UUID,
        target_version_id: UUID,
        relation_type: str,
        binding_key: str,
    ) -> ArtifactRelation | None:
        return self._session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.organization_id == self._actor.organization_id,
                ArtifactRelation.from_artifact_version_id == source_version_id,
                ArtifactRelation.to_artifact_version_id == target_version_id,
                ArtifactRelation.relation_type == relation_type,
                ArtifactRelation.binding_key == binding_key,
            )
        )

    def _ensure_acyclic(self, source_artifact_id: UUID, target_artifact_id: UUID) -> None:
        source = aliased(ArtifactVersion)
        target = aliased(ArtifactVersion)
        rows = self._session.execute(
            select(source.artifact_id, target.artifact_id)
            .select_from(ArtifactRelation)
            .join(source, source.id == ArtifactRelation.from_artifact_version_id)
            .join(target, target.id == ArtifactRelation.to_artifact_version_id)
            .where(ArtifactRelation.organization_id == self._actor.organization_id)
        )
        try:
            ensure_relation_is_acyclic(
                existing_edges=[(row[0], row[1]) for row in rows],
                from_artifact_id=source_artifact_id,
                to_artifact_id=target_artifact_id,
            )
        except ArtifactInvariantError as exc:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_RELATION_CYCLE",
                message="The artifact relation would create a dependency cycle.",
            ) from exc

    def _lock_relation_graph(self) -> None:
        lock_id = int.from_bytes(
            self._actor.organization_id.bytes[:8], byteorder="big", signed=True
        )
        self._session.execute(select(func.pg_advisory_xact_lock(lock_id)))

    def _require_project(self, project_id: UUID) -> Project:
        if not self._actor.is_system:
            return ProjectAccessService(self._session, self._actor).require(
                project_id, ProjectAction.EDIT
            )
        project = self._session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        return project

    def _touch(self, record: Artifact | ArtifactDraft | NodeRun) -> None:
        record.updated_at = utc_now()
        record.updated_by = self._actor.principal_id
        record.lock_version += 1

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="ARTIFACT_NOT_FOUND",
            message="The artifact resource was not found.",
        )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_ARTIFACT", message=message)
