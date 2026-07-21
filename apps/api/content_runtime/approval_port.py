"""Published content-definition facts exposed to artifact approval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)


class ContentDefinitionApprovalReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def definition_key(
        self,
        *,
        definition_id: UUID,
        content_release_id: UUID,
    ) -> str | None:
        return self._session.scalar(
            select(ContentDefinitionVersion.definition_key)
            .join(
                ContentPackageVersion,
                ContentPackageVersion.id == ContentDefinitionVersion.content_package_version_id,
            )
            .join(
                ContentReleaseItem,
                ContentReleaseItem.content_package_version_id == ContentPackageVersion.id,
            )
            .where(
                ContentDefinitionVersion.id == definition_id,
                ContentReleaseItem.content_release_id == content_release_id,
                ContentPackageVersion.status == "published",
            )
        )
