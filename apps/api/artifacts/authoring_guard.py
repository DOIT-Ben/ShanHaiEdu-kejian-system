"""Application guard for ordinary Artifact authoring mutations."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Artifact, ArtifactDraft
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicyUnavailable,
    AuthoringViolation,
)
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext


class ArtifactAuthoringGuard:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._repository = ArtifactRepository(session, actor)

    def baseline(
        self,
        artifact: Artifact,
        draft: ArtifactDraft,
    ) -> dict[str, Any] | None:
        if draft.based_on_version_id is None:
            return None
        baseline = self._repository.get_version(draft.based_on_version_id)
        if baseline is None or baseline[1].id != artifact.id:
            raise self._baseline_error()
        version = baseline[0]
        if version.content_hash != canonical_content_hash(version.content_json):
            raise self._baseline_error()
        return version.content_json

    def validate(
        self,
        definition: ContentDefinitionVersion,
        content: dict[str, Any],
        *,
        baseline: dict[str, Any] | None,
    ) -> None:
        try:
            policy = AuthoringPolicyLoader(self._session).require(definition)
            if baseline is None:
                policy.validate_create(content)
            else:
                policy.validate_update(baseline, content)
        except AuthoringPolicyUnavailable as exc:
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_UNAVAILABLE",
                message="The artifact cannot be changed without a published authoring policy.",
            ) from exc
        except AuthoringViolation as exc:
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_VIOLATION",
                message="The artifact change is not allowed by its published authoring policy.",
                details={"paths": list(exc.paths)},
            ) from exc

    @staticmethod
    def _baseline_error() -> ApiError:
        return ApiError(
            status_code=409,
            code="AUTHORING_BASELINE_INVALID",
            message="The artifact authoring baseline is unavailable.",
        )
