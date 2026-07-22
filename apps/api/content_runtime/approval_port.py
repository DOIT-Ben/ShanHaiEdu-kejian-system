"""Published content-definition facts exposed to artifact approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)


@dataclass(frozen=True, slots=True)
class ContentDefinitionApprovalFact:
    definition_key: str
    schema: dict[str, Any]


class ContentDefinitionApprovalReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def definition_key(
        self,
        *,
        definition_id: UUID,
        content_release_id: UUID,
    ) -> str | None:
        fact = self.definition_fact(
            definition_id=definition_id,
            content_release_id=content_release_id,
        )
        return fact.definition_key if fact is not None else None

    def definition_fact(
        self,
        *,
        definition_id: UUID,
        content_release_id: UUID,
    ) -> ContentDefinitionApprovalFact | None:
        row = self._session.execute(
            select(ContentDefinitionVersion.definition_key, ContentDefinitionVersion.schema_json)
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
        ).one_or_none()
        if row is None:
            return None
        return ContentDefinitionApprovalFact(
            definition_key=row.definition_key,
            schema=dict(row.schema_json),
        )
