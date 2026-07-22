"""Artifact-owned approved-version facts for Intro selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext


@dataclass(frozen=True, slots=True)
class ApprovedIntroOptionSetFact:
    artifact_version_id: UUID
    source_approval_id: UUID
    options: tuple[dict[str, Any], ...]

    def option(self, option_key: str) -> dict[str, Any]:
        matching = [option for option in self.options if option.get("option_key") == option_key]
        if len(matching) != 1:
            raise _invalid("The selected option key is not unique in the approved version.")
        return deepcopy(matching[0])


@dataclass(frozen=True, slots=True)
class IntroSelectionConsumability:
    consumable: bool
    reason: str | None


class IntroSelectionArtifactReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_approved(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        lesson_key: str,
        artifact_version_id: UUID,
    ) -> ApprovedIntroOptionSetFact:
        row = self._source_row(artifact_version_id, for_update=True)
        if row is None:
            raise _invalid("The Intro option-set version is unavailable.")
        version, artifact = row
        approval = self._latest_approval(version.id)
        if (
            artifact.project_id != project_id
            or artifact.lesson_unit_id != lesson_unit_id
            or artifact.artifact_key != f"intro-options:{lesson_key}"
            or artifact.artifact_type != "intro_option_set"
            or artifact.branch_key != "intro_options"
            or artifact.status != "approved"
            or artifact.current_approved_version_id != version.id
            or approval is None
            or approval.action not in {"approve", "accept_stale"}
        ):
            raise _invalid("The source is not the exact current approved Intro option set.")
        return ApprovedIntroOptionSetFact(
            artifact_version_id=version.id,
            source_approval_id=approval.id,
            options=_options(version.content_json),
        )

    def consumability(
        self,
        artifact_version_id: UUID,
        source_approval_id: UUID,
    ) -> IntroSelectionConsumability:
        row = self._source_row(artifact_version_id, for_update=False)
        if row is None:
            return IntroSelectionConsumability(False, "source_unavailable")
        version, artifact = row
        if artifact.status == "stale":
            return IntroSelectionConsumability(False, "source_stale")
        approval = self._latest_approval(version.id)
        if (
            artifact.status != "approved"
            or artifact.current_approved_version_id != version.id
            or approval is None
            or approval.id != source_approval_id
            or approval.action not in {"approve", "accept_stale"}
        ):
            return IntroSelectionConsumability(False, "source_approval_changed")
        return IntroSelectionConsumability(True, None)

    def _source_row(
        self,
        artifact_version_id: UUID,
        *,
        for_update: bool,
    ) -> tuple[ArtifactVersion, Artifact] | None:
        statement = (
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == artifact_version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=Artifact)
        row = self._session.execute(statement).one_or_none()
        return None if row is None else (row[0], row[1])

    def _latest_approval(self, artifact_version_id: UUID) -> Approval | None:
        return self._session.scalar(
            select(Approval)
            .where(
                Approval.organization_id == self._actor.organization_id,
                Approval.artifact_version_id == artifact_version_id,
            )
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .limit(1)
        )


def _options(content: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw = content.get("options")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise _invalid("The approved Intro option set has no selectable options.")
    values = cast(Sequence[object], raw)
    if not values or any(not isinstance(item, Mapping) for item in values):
        raise _invalid("The approved Intro option set contains invalid options.")
    options = tuple(deepcopy(dict(cast(Mapping[str, Any], item))) for item in values)
    return options


def _invalid(message: str) -> ApiError:
    return ApiError(status_code=409, code="INTRO_SELECTION_INVALID", message=message)
