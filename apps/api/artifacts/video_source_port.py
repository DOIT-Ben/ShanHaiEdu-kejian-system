"""Immutable artifact lineage facts consumed by video generation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import ArtifactVersion


@dataclass(frozen=True, slots=True)
class VideoSourceArtifact:
    context_snapshot_id: UUID | None
    prompt_snapshot_id: UUID | None


class VideoSourceArtifactReader:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def get(self, version_id: UUID) -> VideoSourceArtifact | None:
        row = self._session.execute(
            select(
                ArtifactVersion.artifact_id,
                ArtifactVersion.version_no,
                ArtifactVersion.source_kind,
                ArtifactVersion.context_snapshot_id,
                ArtifactVersion.prompt_snapshot_id,
            ).where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._organization_id,
            )
        ).one_or_none()
        if row is None:
            return None
        if row.context_snapshot_id is None or row.prompt_snapshot_id is None:
            return self._manual_lineage(row.artifact_id, row.version_no, row.source_kind)
        return VideoSourceArtifact(
            context_snapshot_id=row.context_snapshot_id,
            prompt_snapshot_id=row.prompt_snapshot_id,
        )

    def _manual_lineage(
        self, artifact_id: UUID, version_no: int, source_kind: str
    ) -> VideoSourceArtifact | None:
        if source_kind != "manual":
            return None
        row = self._session.execute(
            select(
                ArtifactVersion.context_snapshot_id,
                ArtifactVersion.prompt_snapshot_id,
            )
            .where(
                ArtifactVersion.organization_id == self._organization_id,
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.version_no < version_no,
                ArtifactVersion.context_snapshot_id.is_not(None),
                ArtifactVersion.prompt_snapshot_id.is_not(None),
            )
            .order_by(ArtifactVersion.version_no.desc())
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        return VideoSourceArtifact(
            context_snapshot_id=row.context_snapshot_id,
            prompt_snapshot_id=row.prompt_snapshot_id,
        )
