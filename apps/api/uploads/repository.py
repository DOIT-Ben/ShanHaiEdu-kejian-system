"""Tenant-scoped source material queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.uploads.models import SourceMaterial


class SourceMaterialRepository:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def list_textbooks_page(
        self,
        project_id: UUID,
        *,
        cursor: UUID | None,
        limit: int,
    ) -> tuple[list[SourceMaterial], str | None]:
        statement = (
            select(SourceMaterial)
            .where(
                SourceMaterial.organization_id == self._organization_id,
                SourceMaterial.project_id == project_id,
                SourceMaterial.material_kind == "textbook",
                SourceMaterial.deleted_at.is_(None),
            )
            .order_by(SourceMaterial.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            statement = statement.where(SourceMaterial.id < cursor)
        materials = list(self._session.scalars(statement))
        page = materials[:limit]
        next_cursor = str(page[-1].id) if len(materials) > limit and page else None
        return page, next_cursor
