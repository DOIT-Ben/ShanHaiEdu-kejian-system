"""Public application interface for invalidating exported creation packages."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.creation.models import CreationPackage
from apps.api.database import utc_now


class CreationPackageStalenessService:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def mark_source_nodes_stale(self, node_run_ids: list[UUID]) -> list[UUID]:
        if not node_run_ids:
            return []
        packages = list(
            self._session.scalars(
                select(CreationPackage)
                .where(
                    CreationPackage.organization_id == self._organization_id,
                    CreationPackage.source_node_run_id.in_(node_run_ids),
                    CreationPackage.source_stale_at.is_(None),
                )
                .order_by(CreationPackage.id)
                .with_for_update()
            )
        )
        marked_at = utc_now()
        for package in packages:
            package.source_stale_at = marked_at
        self._session.flush()
        return [package.id for package in packages]
