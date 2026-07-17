"""Tenant- and membership-scoped artifact persistence queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import (
    Approval,
    Artifact,
    ArtifactDraft,
    ArtifactRelation,
    ArtifactVersion,
)
from apps.api.identity.context import ActorContext
from apps.api.identity.models import ProjectMember


class ArtifactRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get(self, artifact_id: UUID, *, for_update: bool = False) -> Artifact | None:
        statement = self._visible_artifacts().where(Artifact.id == artifact_id)
        if for_update:
            statement = statement.with_for_update(of=Artifact)
        return self._session.scalar(statement)

    def get_by_key(self, project_id: UUID, artifact_key: str) -> Artifact | None:
        return self._session.scalar(
            self._visible_artifacts().where(
                Artifact.project_id == project_id,
                Artifact.artifact_key == artifact_key,
            )
        )

    def get_draft(
        self,
        artifact_id: UUID,
        draft_branch: str,
        *,
        for_update: bool = False,
    ) -> ArtifactDraft | None:
        statement = (
            select(ArtifactDraft)
            .join(Artifact, Artifact.id == ArtifactDraft.artifact_id)
            .where(
                ArtifactDraft.artifact_id == artifact_id,
                ArtifactDraft.draft_branch == draft_branch,
                ArtifactDraft.organization_id == self._actor.organization_id,
                ArtifactDraft.deleted_at.is_(None),
                Artifact.organization_id == self._actor.organization_id,
                Artifact.deleted_at.is_(None),
            )
        )
        statement = self._scope_to_member(statement)
        if for_update:
            statement = statement.with_for_update(of=ArtifactDraft)
        return self._session.scalar(statement)

    def get_version(
        self,
        version_id: UUID,
        *,
        for_update_artifact: bool = False,
    ) -> tuple[ArtifactVersion, Artifact] | None:
        statement = (
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.deleted_at.is_(None),
            )
        )
        statement = self._scope_to_member(statement)
        if for_update_artifact:
            statement = statement.with_for_update(of=Artifact)
        row = self._session.execute(statement).one_or_none()
        return None if row is None else (row[0], row[1])

    def next_version_no(self, artifact_id: UUID) -> int:
        return (
            int(
                self._session.scalar(
                    select(func.coalesce(func.max(ArtifactVersion.version_no), 0)).where(
                        ArtifactVersion.artifact_id == artifact_id
                    )
                )
                or 0
            )
            + 1
        )

    def latest_action(self, version_id: UUID, action: str) -> Approval | None:
        return self._session.scalar(
            select(Approval)
            .where(
                Approval.organization_id == self._actor.organization_id,
                Approval.artifact_version_id == version_id,
                Approval.action == action,
            )
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .limit(1)
        )

    def downstream_relations(self, version_id: UUID) -> list[ArtifactRelation]:
        return list(
            self._session.scalars(
                select(ArtifactRelation)
                .where(
                    ArtifactRelation.organization_id == self._actor.organization_id,
                    ArtifactRelation.from_artifact_version_id == version_id,
                )
                .order_by(ArtifactRelation.binding_key, ArtifactRelation.id)
            )
        )

    def _visible_artifacts(self) -> Select[tuple[Artifact]]:
        statement = select(Artifact).where(
            Artifact.organization_id == self._actor.organization_id,
            Artifact.deleted_at.is_(None),
        )
        return self._scope_to_member(statement)

    def _scope_to_member(self, statement: Select[Any]) -> Select[Any]:
        if self._actor.user_id is None or self._actor.is_system:
            return statement
        return statement.join(
            ProjectMember,
            (ProjectMember.project_id == Artifact.project_id)
            & (ProjectMember.user_id == self._actor.user_id),
        )
