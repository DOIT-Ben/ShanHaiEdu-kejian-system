"""Application guard for ordinary Artifact authoring mutations."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Artifact, ArtifactDraft
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicyUnavailable,
    AuthoringViolation,
)
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext

INITIAL_LOCKED_FIELDS_REPORT_KEY = "initial_locked_fields"


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

    @staticmethod
    def record_initial_locked_fields(
        report: dict[str, Any],
        fields: Mapping[str, Any],
    ) -> None:
        report[INITIAL_LOCKED_FIELDS_REPORT_KEY] = deepcopy(dict(fields))

    @staticmethod
    def initial_locked_fields(draft: ArtifactDraft) -> dict[str, Any] | None:
        fields = draft.validation_report_json.get(INITIAL_LOCKED_FIELDS_REPORT_KEY)
        if fields is None:
            return None
        if not isinstance(fields, dict):
            raise ArtifactAuthoringGuard._baseline_error()
        raw_fields = cast(dict[object, object], fields)
        baseline: dict[str, Any] = {}
        for key, value in raw_fields.items():
            if not isinstance(key, str):
                raise ArtifactAuthoringGuard._baseline_error()
            baseline[key] = deepcopy(value)
        if not baseline:
            raise ArtifactAuthoringGuard._baseline_error()
        return baseline

    @staticmethod
    def preserve_initial_locked_fields(
        previous_report: dict[str, Any],
        report: dict[str, Any],
    ) -> None:
        fields = previous_report.get(INITIAL_LOCKED_FIELDS_REPORT_KEY)
        if fields is not None:
            report[INITIAL_LOCKED_FIELDS_REPORT_KEY] = deepcopy(fields)

    def validate(
        self,
        definition_id: UUID,
        content: dict[str, Any],
        *,
        baseline: dict[str, Any] | None,
    ) -> None:
        try:
            policy = AuthoringPolicyLoader(self._session).require_by_id(definition_id)
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
