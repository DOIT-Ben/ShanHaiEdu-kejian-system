"""Database adapter for immutable published authoring policies."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicy,
    AuthoringPolicyUnavailable,
    compile_authoring_policy,
)
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageItemVersion,
    ContentPackageVersion,
)
from workflow.content_package import canonical_json_sha256


class AuthoringPolicyLoader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def require(self, definition: ContentDefinitionVersion) -> AuthoringPolicy:
        row = self._session.execute(
            select(ContentPackageItemVersion, ContentPackageVersion)
            .join(
                ContentPackageVersion,
                ContentPackageVersion.id == ContentPackageItemVersion.content_package_version_id,
            )
            .where(
                ContentPackageItemVersion.content_package_version_id
                == definition.content_package_version_id,
                ContentPackageItemVersion.item_key == definition.definition_key,
                ContentPackageItemVersion.kind == "content_definition",
                ContentPackageVersion.status == "published",
            )
        ).one_or_none()
        if row is None:
            raise AuthoringPolicyUnavailable(
                "published content definition has no authoring policy source"
            )
        item, _package = row
        if (
            item.checksum != definition.checksum
            or canonical_json_sha256(item.payload_json) != item.checksum
        ):
            raise AuthoringPolicyUnavailable(
                "published content definition authoring policy checksum differs"
            )
        policy = compile_authoring_policy(item.payload_json, checksum=item.checksum)
        if policy.definition_key != definition.definition_key:
            raise AuthoringPolicyUnavailable(
                "published content definition authoring policy identity differs"
            )
        return policy
