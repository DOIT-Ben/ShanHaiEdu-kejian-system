"""Artifact dependency graph writes and precise stale propagation."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from apps.api.artifacts.domain import (
    ArtifactImpactScope,
    ArtifactInvariantError,
    ArtifactRelationType,
    StaleImpactSelection,
    ensure_relation_is_acyclic,
)
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

    def lock_review_target(
        self,
        *,
        version_id: UUID,
        project_id: UUID,
        action: ProjectAction = ProjectAction.REVIEW,
        require_owner: bool = False,
    ) -> tuple[ArtifactVersion, Artifact]:
        """Acquire the shared write order before approval mutates an artifact."""
        self._lock_relation_graph()
        self._require_project(project_id, action=action, for_update=True)
        if require_owner and not self._actor.is_system:
            ProjectAccessService(self._session, self._actor).require_owner(project_id)
        record = self._repository.get_version(version_id, for_update_artifact=True)
        if record is None or record[1].project_id != project_id:
            raise self._not_found()
        return record

    def add(
        self,
        *,
        from_version_id: UUID,
        to_version_id: UUID,
        relation_type: str,
        binding_key: str,
        impact_scope: Mapping[str, Any],
    ) -> ArtifactRelation:
        try:
            relation_kind = ArtifactRelationType(relation_type)
        except ValueError as exc:
            raise self._invalid("The artifact relation type is invalid.") from exc
        if not binding_key.strip() or len(binding_key) > 160:
            raise self._invalid("The binding_key value is invalid.")
        scope = self._parse_scope(impact_scope)

        source = self._repository.get_version(from_version_id)
        target = self._repository.get_version(to_version_id)
        if source is None or target is None:
            raise self._not_found()
        source_version, source_artifact = source
        target_version, target_artifact = target
        self._require_project(source_artifact.project_id, action=ProjectAction.EDIT)
        self._require_project(target_artifact.project_id, action=ProjectAction.EDIT)
        if source_artifact.project_id != target_artifact.project_id:
            raise self._invalid("Artifact relations cannot cross project boundaries.")

        # All mutating graph paths acquire the organization lock before row locks.
        self._lock_relation_graph()
        self._require_project(
            source_artifact.project_id, action=ProjectAction.EDIT, for_update=True
        )
        if str(source_artifact.id) <= str(target_artifact.id):
            locked_source = self._repository.get_version(
                source_version.id, for_update_artifact=True
            )
            locked_target = self._repository.get_version(
                target_version.id, for_update_artifact=True
            )
        else:
            locked_target = self._repository.get_version(
                target_version.id, for_update_artifact=True
            )
            locked_source = self._repository.get_version(
                source_version.id, for_update_artifact=True
            )
        if locked_source is None or locked_target is None:
            raise self._not_found()
        source_version, source_artifact = locked_source
        target_version, target_artifact = locked_target

        if relation_kind is ArtifactRelationType.SUPERSEDES:
            if source_artifact.id != target_artifact.id:
                raise self._invalid("supersedes requires the same artifact.")
            if source_version.version_no >= target_version.version_no:
                raise self._conflict(
                    "ARTIFACT_SUPERSEDES_VERSION_ORDER",
                    "supersedes must point from an older version to a newer version.",
                )
            if scope.mode != "all":
                raise self._scope_error("supersedes only accepts an all impact scope.")
        else:
            if source_artifact.id == target_artifact.id:
                raise self._invalid("Dependency relations require different artifacts.")
            if source_artifact.current_approved_version_id != source_version.id:
                raise self._conflict(
                    "ARTIFACT_SOURCE_VERSION_STALE",
                    "The relation source is no longer the current approved version.",
                )
            self._ensure_acyclic(source_artifact.id, target_artifact.id)

        existing = self._find_existing(
            source_version.id, target_version.id, relation_kind, binding_key
        )
        if existing is not None:
            if existing.impact_scope_json == scope.as_dict():
                return existing
            raise self._conflict(
                "ARTIFACT_RELATION_SCOPE_CONFLICT",
                "The relation already exists with a different impact scope.",
            )
        relation = ArtifactRelation(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            from_artifact_version_id=source_version.id,
            to_artifact_version_id=target_version.id,
            relation_type=relation_kind.value,
            binding_key=binding_key,
            impact_scope_json=scope.as_dict(),
            created_by=self._actor.principal_id,
        )
        self._session.add(relation)
        self._session.flush()
        return relation

    def propagate_stale(
        self,
        previous_version_id: UUID | None,
        replacement_version_id: UUID | None,
        *,
        selection: StaleImpactSelection | None = None,
    ) -> tuple[list[UUID], list[UUID]]:
        if previous_version_id is None or previous_version_id == replacement_version_id:
            return [], []
        self._lock_relation_graph()
        source_record = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == previous_version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
            )
        ).one_or_none()
        if source_record is None:
            return [], []
        _, source_artifact = source_record
        self._require_project(
            source_artifact.project_id, action=ProjectAction.REVIEW, for_update=True
        )
        self._repository.get_version(previous_version_id, for_update_artifact=True)
        grouped = self._group_downstream_relations(previous_version_id)
        target_artifact_ids = sorted(grouped, key=str)
        locked_targets = {
            artifact_id: self._repository.get(artifact_id, for_update=True)
            for artifact_id in target_artifact_ids
        }
        stale_ids: list[UUID] = []
        stale_node_ids: list[UUID] = []
        reason_code = (
            "UPSTREAM_APPROVAL_REVOKED"
            if replacement_version_id is None
            else "UPSTREAM_APPROVED_VERSION_CHANGED"
        )
        for artifact_id in target_artifact_ids:
            downstream = locked_targets[artifact_id]
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
                and relation.relation_type != ArtifactRelationType.SUPERSEDES.value
            ]
            if not active:
                continue
            matched = self._matched_relations(active, selection, replacement_version_id)
            if not matched:
                continue
            stale_reason = self._stale_reason(
                previous_version_id, replacement_version_id, matched, reason_code
            )
            downstream.status = "stale"
            downstream.stale_reason_json = stale_reason
            self._touch(downstream)
            stale_node_ids.extend(self._mark_nodes_stale(matched, stale_reason))
            stale_ids.append(downstream.id)
        return stale_ids, stale_node_ids

    def _matched_relations(
        self,
        relations: list[ArtifactRelation],
        selection: StaleImpactSelection | None,
        replacement_version_id: UUID | None,
    ) -> list[tuple[ArtifactRelation, ArtifactImpactScope]]:
        if selection is None:
            selection = StaleImpactSelection.all()
        matched: list[tuple[ArtifactRelation, ArtifactImpactScope]] = []
        for relation in relations:
            scope = self._parse_scope(relation.impact_scope_json)
            if (
                replacement_version_id is not None
                and scope.mode == "keyed"
                and selection.mode == "all"
            ):
                raise self._conflict(
                    "ARTIFACT_IMPACT_SELECTION_REQUIRED",
                    "A keyed relation requires an exact analyzer selection.",
                )
            try:
                effective = selection.matches(scope)
            except ArtifactInvariantError as exc:
                raise self._conflict(
                    "ARTIFACT_IMPACT_SELECTION_INVALID",
                    str(exc),
                ) from exc
            if effective is not None:
                matched.append((relation, effective))
        return matched

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
        relations: list[tuple[ArtifactRelation, ArtifactImpactScope]],
        stale_reason: dict[str, Any],
    ) -> list[UUID]:
        target_ids = {relation.to_artifact_version_id for relation, _ in relations}
        nodes = list(
            self._session.scalars(
                select(NodeRun)
                .where(
                    NodeRun.organization_id == self._actor.organization_id,
                    NodeRun.active_artifact_version_id.in_(target_ids),
                    NodeRun.deleted_at.is_(None),
                )
                .order_by(NodeRun.id)
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
        relations: list[tuple[ArtifactRelation, ArtifactImpactScope]],
        reason_code: str,
    ) -> dict[str, Any]:
        bindings = [
            {
                "relation_type": relation.relation_type,
                "binding_key": relation.binding_key,
                "impact_scope": effective_scope.as_dict(),
            }
            for relation, effective_scope in relations
        ]
        bindings.sort(
            key=lambda item: (
                item["relation_type"],
                item["binding_key"],
                json.dumps(item["impact_scope"], sort_keys=True),
            )
        )
        return {
            "reason_code": reason_code,
            "replaced_upstream_version_id": str(previous_version_id),
            "replacement_version_id": (
                str(replacement_version_id) if replacement_version_id is not None else None
            ),
            "bindings": bindings,
        }

    def _find_existing(
        self,
        source_version_id: UUID,
        target_version_id: UUID,
        relation_type: ArtifactRelationType,
        binding_key: str,
    ) -> ArtifactRelation | None:
        return self._session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.organization_id == self._actor.organization_id,
                ArtifactRelation.from_artifact_version_id == source_version_id,
                ArtifactRelation.to_artifact_version_id == target_version_id,
                ArtifactRelation.relation_type == relation_type.value,
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
            .where(
                ArtifactRelation.organization_id == self._actor.organization_id,
                ArtifactRelation.relation_type != ArtifactRelationType.SUPERSEDES.value,
            )
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

    @staticmethod
    def _parse_scope(value: Mapping[str, Any]) -> ArtifactImpactScope:
        try:
            return ArtifactImpactScope.from_mapping(value)
        except ArtifactInvariantError as exc:
            raise ApiError(
                status_code=422,
                code="INVALID_ARTIFACT_RELATION_SCOPE",
                message=str(exc),
            ) from exc

    def _lock_relation_graph(self) -> None:
        lock_id = int.from_bytes(
            self._actor.organization_id.bytes[:8], byteorder="big", signed=True
        )
        self._session.execute(select(func.pg_advisory_xact_lock(lock_id)))

    def _require_project(
        self,
        project_id: UUID,
        *,
        action: ProjectAction,
        for_update: bool = False,
    ) -> Project:
        if not self._actor.is_system:
            return ProjectAccessService(self._session, self._actor).require(
                project_id, action, for_update=for_update
            )
        statement = select(Project).where(
            Project.id == project_id,
            Project.organization_id == self._actor.organization_id,
            Project.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        project = self._session.scalar(statement)
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

    @staticmethod
    def _scope_error(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_ARTIFACT_RELATION_SCOPE", message=message)

    @staticmethod
    def _conflict(code: str, message: str) -> ApiError:
        return ApiError(status_code=409, code=code, message=message)
