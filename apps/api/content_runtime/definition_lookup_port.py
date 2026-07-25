"""Content-runtime-owned lookup for one published definition in a release."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)


@dataclass(frozen=True, slots=True)
class PublishedContentDefinitionFact:
    id: UUID


class PublishedContentDefinitionReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_unique(
        self,
        *,
        content_release_id: UUID,
        definition_key: str,
    ) -> PublishedContentDefinitionFact | None:
        definition_ids = list(
            self._session.scalars(
                select(ContentDefinitionVersion.id)
                .join(
                    ContentPackageVersion,
                    ContentPackageVersion.id == ContentDefinitionVersion.content_package_version_id,
                )
                .join(
                    ContentReleaseItem,
                    ContentReleaseItem.content_package_version_id == ContentPackageVersion.id,
                )
                .where(
                    ContentReleaseItem.content_release_id == content_release_id,
                    ContentPackageVersion.status == "published",
                    ContentDefinitionVersion.definition_key == definition_key,
                )
            )
        )
        if len(definition_ids) != 1:
            return None
        return PublishedContentDefinitionFact(id=definition_ids[0])
