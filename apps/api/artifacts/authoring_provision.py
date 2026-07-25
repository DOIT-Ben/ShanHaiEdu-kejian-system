"""Narrow server-only capabilities for authoring locked generated content."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.authoring_guard import ArtifactAuthoringGuard
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicy,
    AuthoringPolicyUnavailable,
    AuthoringViolation,
)
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7


@dataclass(frozen=True, slots=True)
class GeneratedDraftRequest:
    artifact_id: UUID
    artifact_version_id: UUID
    expected_content_hash: str
    draft_branch: str


@dataclass(frozen=True, slots=True)
class RepeatableItemProvision:
    artifact_id: UUID
    draft_id: UUID
    based_on_version_id: UUID
    baseline_content_hash: str
    expected_draft_content_hash: str
    expected_lock_version: int
    field_path: tuple[str, ...]
    parent_identities: tuple[str, ...]
    provision_key: str


class RepeatableItemProvisioner(Protocol):
    def materialize(self, provision_key: str) -> Mapping[str, Any]: ...


class ArtifactAuthoringProvisionPort:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        provisioner: RepeatableItemProvisioner | None = None,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = ArtifactRepository(session, actor)
        self._validation = ArtifactValidation(session, actor)
        self._provisioner = provisioner

    def open_generated_draft(self, request: GeneratedDraftRequest) -> ArtifactDraft:
        self._require_system()
        artifact = self._require_artifact(request.artifact_id)
        version = self._require_generated_version(
            artifact,
            request.artifact_version_id,
            request.expected_content_hash,
        )
        definition = self._validation.require_artifact_definition(artifact)
        self._require_policy(definition.id)
        self._validate_draft_branch(request.draft_branch)
        validation_report = self._validation.validation_report(
            definition,
            version.content_json,
        )
        existing = self._repository.get_draft(
            artifact.id,
            request.draft_branch,
            for_update=True,
        )
        if existing is not None:
            return self._reuse_or_reset_generated_draft(
                artifact,
                existing,
                version,
                validation_report,
            )
        draft = ArtifactDraft(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_id=artifact.id,
            draft_branch=request.draft_branch,
            content_json=version.content_json,
            validation_report_json=validation_report,
            based_on_version_id=version.id,
            autosaved_at=utc_now(),
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(draft)
        self._session.flush()
        artifact.current_draft_id = draft.id
        self._touch_artifact(artifact)
        self._session.flush()
        return draft

    def _reuse_or_reset_generated_draft(
        self,
        artifact: Artifact,
        draft: ArtifactDraft,
        version: ArtifactVersion,
        validation_report: dict[str, Any],
    ) -> ArtifactDraft:
        draft_hash = canonical_content_hash(draft.content_json)
        if draft.based_on_version_id == version.id and draft_hash == version.content_hash:
            return draft
        baseline = (
            self._repository.get_version(draft.based_on_version_id)
            if draft.based_on_version_id is not None
            else None
        )
        if (
            baseline is None
            or baseline[1].id != artifact.id
            or draft_hash != baseline[0].content_hash
        ):
            raise self._conflict("The generated authoring draft already differs.")
        draft.content_json = deepcopy(version.content_json)
        draft.validation_report_json = validation_report
        draft.based_on_version_id = version.id
        draft.autosaved_at = utc_now()
        draft.updated_at = utc_now()
        draft.updated_by = self._actor.principal_id
        draft.lock_version += 1
        artifact.current_draft_id = draft.id
        self._touch_artifact(artifact)
        self._session.flush()
        return draft

    def provision_initial_locked_fields(
        self,
        *,
        artifact_id: UUID,
        draft_branch: str,
        expected_lock_version: int,
        fields: Mapping[str, Any],
    ) -> ArtifactDraft:
        self._require_system()
        artifact = self._require_artifact(artifact_id)
        draft = self._repository.get_draft(artifact.id, draft_branch, for_update=True)
        if (
            draft is None
            or draft.based_on_version_id is not None
            or draft.lock_version != expected_lock_version
        ):
            raise self._conflict("The initial authoring draft changed or is unavailable.")
        policy = self._require_policy(artifact.content_definition_version_id)
        locked = {field.field_key for field in policy.fields if not field.editable}
        invalid = sorted(key for key in fields if key not in locked or key in draft.content_json)
        if not fields or invalid:
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_VIOLATION",
                message="Only missing locked fields can be provisioned.",
                details={"paths": invalid},
            )
        content = deepcopy(draft.content_json)
        content.update(deepcopy(dict(fields)))
        report = self._validation.validation_report(
            self._validation.require_artifact_definition(artifact),
            content,
        )
        if not report["valid"]:
            raise ApiError(
                status_code=422,
                code="INVALID_ARTIFACT",
                message="The provisioned draft does not match the published schema.",
            )
        ArtifactAuthoringGuard.record_initial_locked_fields(report, fields)
        draft.content_json = content
        draft.validation_report_json = report
        draft.autosaved_at = utc_now()
        draft.updated_at = utc_now()
        draft.updated_by = self._actor.principal_id
        draft.lock_version += 1
        artifact.current_draft_id = draft.id
        self._touch_artifact(artifact)
        self._session.flush()
        return draft

    def replace_material_scope_draft(
        self,
        *,
        artifact_id: UUID,
        draft_branch: str,
        content: Mapping[str, Any],
        locked_fields: Mapping[str, Any],
    ) -> ArtifactDraft:
        self._require_system()
        artifact = self._require_artifact(artifact_id)
        if (
            artifact.artifact_key != "material-scope"
            or artifact.artifact_type != "material_scope"
            or artifact.branch_key != "project"
            or artifact.lesson_unit_id is not None
        ):
            raise self._conflict("The material-scope artifact identity is unavailable.")
        expected_locked = {
            "source_material_id",
            "material_parse_version_id",
            "page_start",
            "page_end",
        }
        candidate = deepcopy(dict(content))
        supplied_locked = deepcopy(dict(locked_fields))
        if set(supplied_locked) != expected_locked or any(
            candidate.get(key) != value for key, value in supplied_locked.items()
        ):
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_VIOLATION",
                message="The material-scope locked fields are incomplete or inconsistent.",
                details={"paths": sorted(expected_locked)},
            )
        policy = self._require_policy(artifact.content_definition_version_id)
        policy_locked = {field.field_key for field in policy.fields if not field.editable}
        if not expected_locked <= policy_locked:
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_UNAVAILABLE",
                message="The published material-scope authoring policy is unavailable.",
            )
        definition = self._validation.require_artifact_definition(artifact)
        report = self._validation.validation_report(definition, candidate)
        if not report["valid"]:
            raise ApiError(
                status_code=422,
                code="INVALID_ARTIFACT",
                message="The material-scope content does not match the published schema.",
                details={"validation": report},
            )
        draft = self._repository.get_draft(artifact.id, draft_branch, for_update=True)
        if draft is None:
            raise self._conflict("The material-scope authoring draft is unavailable.")
        ArtifactAuthoringGuard.record_initial_locked_fields(report, supplied_locked)
        draft.content_json = candidate
        draft.validation_report_json = report
        draft.based_on_version_id = None
        draft.autosaved_at = utc_now()
        draft.updated_at = utc_now()
        draft.updated_by = self._actor.principal_id
        draft.lock_version += 1
        artifact.current_draft_id = draft.id
        self._touch_artifact(artifact)
        self._session.flush()
        return draft

    def provision_repeatable_item(
        self,
        request: RepeatableItemProvision,
    ) -> ArtifactDraft:
        self._require_system()
        artifact = self._require_artifact(request.artifact_id)
        draft = self._require_draft(artifact, request)
        baseline = self._require_generated_version(
            artifact,
            request.based_on_version_id,
            request.baseline_content_hash,
        )
        definition = self._validation.require_artifact_definition(artifact)
        policy = self._require_policy(definition.id)
        if self._provisioner is None:
            raise self._conflict("The owning authoring provisioner is unavailable.")
        item = self._provisioner.materialize(request.provision_key)
        try:
            content = policy.provision_repeatable_item(
                baseline.content_json,
                draft.content_json,
                field_path=request.field_path,
                parent_identities=request.parent_identities,
                item=item,
            )
        except AuthoringViolation as exc:
            raise self._violation(exc) from exc
        report = self._validation.validation_report(definition, content)
        if not report["valid"]:
            raise ApiError(
                status_code=422,
                code="INVALID_ARTIFACT",
                message="The provisioned item does not match the published schema.",
            )
        draft.content_json = content
        draft.validation_report_json = report
        draft.autosaved_at = utc_now()
        draft.updated_at = utc_now()
        draft.updated_by = self._actor.principal_id
        draft.lock_version += 1
        artifact.current_draft_id = draft.id
        self._touch_artifact(artifact)
        self._session.flush()
        return draft

    def _require_draft(
        self,
        artifact: Artifact,
        request: RepeatableItemProvision,
    ) -> ArtifactDraft:
        draft = self._session.scalar(
            select(ArtifactDraft)
            .where(
                ArtifactDraft.id == request.draft_id,
                ArtifactDraft.artifact_id == artifact.id,
                ArtifactDraft.organization_id == self._actor.organization_id,
                ArtifactDraft.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if draft is None:
            raise self._conflict("The authoring draft is unavailable.")
        if (
            draft.based_on_version_id != request.based_on_version_id
            or draft.lock_version != request.expected_lock_version
            or canonical_content_hash(draft.content_json) != request.expected_draft_content_hash
        ):
            raise self._conflict("The authoring draft changed after the supplied baseline.")
        return draft

    def _require_artifact(self, artifact_id: UUID) -> Artifact:
        artifact = self._repository.get(artifact_id, for_update=True)
        if artifact is None:
            raise self._conflict("The authoring artifact is unavailable.")
        return artifact

    def _require_generated_version(
        self,
        artifact: Artifact,
        version_id: UUID,
        expected_hash: str,
    ) -> ArtifactVersion:
        row = self._repository.get_version(version_id)
        if row is None or row[1].id != artifact.id:
            raise self._conflict("The generated authoring baseline is unavailable.")
        version = row[0]
        if (
            version.source_kind != "model"
            or version.source_node_run_id is None
            or version.context_snapshot_id is None
            or version.prompt_snapshot_id is None
            or version.content_hash != expected_hash
            or version.content_hash != canonical_content_hash(version.content_json)
        ):
            raise self._conflict("The generated authoring baseline is unavailable.")
        return version

    def _require_policy(self, definition_id: UUID) -> AuthoringPolicy:
        try:
            return AuthoringPolicyLoader(self._session).require_by_id(definition_id)
        except AuthoringPolicyUnavailable as exc:
            raise ApiError(
                status_code=422,
                code="AUTHORING_POLICY_UNAVAILABLE",
                message="The artifact cannot be changed without a published authoring policy.",
            ) from exc

    def _require_system(self) -> None:
        if not self._actor.is_system:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="Locked authoring values can only be provisioned by a server capability.",
            )

    @staticmethod
    def _validate_draft_branch(value: str) -> None:
        if not value.strip() or len(value) > 80:
            raise ApiError(
                status_code=422,
                code="INVALID_ARTIFACT",
                message="The artifact draft branch is invalid.",
            )

    def _touch_artifact(self, artifact: Artifact) -> None:
        artifact.updated_at = utc_now()
        artifact.updated_by = self._actor.principal_id
        artifact.lock_version += 1

    @staticmethod
    def _violation(error: AuthoringViolation) -> ApiError:
        return ApiError(
            status_code=422,
            code="AUTHORING_POLICY_VIOLATION",
            message="The artifact change is not allowed by its published authoring policy.",
            details={"paths": list(error.paths)},
        )

    @staticmethod
    def _conflict(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="AUTHORING_PROVISION_CONFLICT",
            message=message,
        )
