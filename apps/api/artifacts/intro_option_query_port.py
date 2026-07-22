"""Artifact-owned safe projections for the Intro options HTTP query."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext

ApprovalStatus = Literal[
    "approved",
    "pending_review",
    "changes_requested",
    "revoked",
    "unapproved",
]


@dataclass(frozen=True, slots=True)
class IntroOptionVersionFact:
    artifact_version_id: UUID
    version_no: int
    approval_status: ApprovalStatus
    stale: bool
    selectable: bool
    option_set: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IntroOptionArtifactFact:
    artifact_id: UUID
    current_approved_version_id: UUID | None
    display_version: IntroOptionVersionFact | None
    pending_version: IntroOptionVersionFact | None


class IntroOptionQueryReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def for_lesson(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        lesson_key: str,
    ) -> IntroOptionArtifactFact | None:
        artifact = self._session.scalar(
            select(Artifact).where(
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == project_id,
                Artifact.lesson_unit_id == lesson_unit_id,
                Artifact.artifact_key == f"intro-options:{lesson_key}",
                Artifact.artifact_type == "intro_option_set",
                Artifact.branch_key == "intro_options",
                Artifact.deleted_at.is_(None),
            )
        )
        if artifact is None:
            return None
        versions = list(
            self._session.scalars(
                select(ArtifactVersion)
                .where(
                    ArtifactVersion.organization_id == self._actor.organization_id,
                    ArtifactVersion.artifact_id == artifact.id,
                )
                .order_by(ArtifactVersion.version_no.desc())
            )
        )
        by_id = {version.id: version for version in versions}
        approved_candidate = (
            by_id.get(artifact.current_approved_version_id)
            if artifact.current_approved_version_id is not None
            else None
        )
        approved = (
            approved_candidate
            if approved_candidate is not None
            and self._latest_action(approved_candidate.id) in {"approve", "accept_stale"}
            else None
        )
        submitted = (
            by_id.get(artifact.current_submitted_version_id)
            if artifact.current_submitted_version_id is not None
            else None
        )
        display = approved or submitted or (versions[0] if versions else None)
        pending = submitted if approved is not None and submitted is not approved else None
        return IntroOptionArtifactFact(
            artifact_id=artifact.id,
            current_approved_version_id=approved.id if approved is not None else None,
            display_version=self._version_fact(artifact, display),
            pending_version=self._version_fact(artifact, pending),
        )

    def _version_fact(
        self,
        artifact: Artifact,
        version: ArtifactVersion | None,
    ) -> IntroOptionVersionFact | None:
        if version is None:
            return None
        latest_action = self._latest_action(version.id)
        current_approved = artifact.current_approved_version_id == version.id and latest_action in {
            "approve",
            "accept_stale",
        }
        current_submitted = artifact.current_submitted_version_id == version.id
        stale = current_approved and artifact.status == "stale"
        return IntroOptionVersionFact(
            artifact_version_id=version.id,
            version_no=version.version_no,
            approval_status=_approval_status(
                current_approved=current_approved,
                current_submitted=current_submitted,
                latest_action=latest_action,
            ),
            stale=stale,
            selectable=(
                current_approved
                and not stale
                and artifact.status != "archived"
                and latest_action in {"approve", "accept_stale"}
            ),
            option_set=_public_option_set(version.content_json, version.created_at),
        )

    def _latest_action(self, artifact_version_id: UUID) -> str | None:
        return self._session.scalar(
            select(Approval.action)
            .where(
                Approval.organization_id == self._actor.organization_id,
                Approval.artifact_version_id == artifact_version_id,
            )
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .limit(1)
        )


def _approval_status(
    *,
    current_approved: bool,
    current_submitted: bool,
    latest_action: str | None,
) -> ApprovalStatus:
    if current_approved:
        return "approved"
    if current_submitted or latest_action == "submit":
        return "pending_review"
    if latest_action == "request_changes":
        return "changes_requested"
    if latest_action == "revoke":
        return "revoked"
    return "unapproved"


def _public_option_set(content: dict[str, Any], created_at: datetime) -> dict[str, Any]:
    raw_options: object = content.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        raise ApiError(
            status_code=409,
            code="INTRO_OPTIONS_INVALID",
            message="The Intro option set has no displayable options.",
        )
    safe_options: list[dict[str, Any]] = []
    for item in cast(list[object], raw_options):
        if not isinstance(item, dict):
            raise ApiError(
                status_code=409,
                code="INTRO_OPTIONS_INVALID",
                message="The Intro option set contains an invalid display option.",
            )
        typed_item = cast(dict[str, Any], item)
        safe_options.append(deepcopy(typed_item))
    ordered = sorted(
        safe_options,
        key=lambda option: (
            -int(option.get("recommendation_score", 0)),
            str(option.get("option_key", "")),
        ),
    )
    return {
        "generation_mode": content.get("generation_mode"),
        "lesson_unit_key": content.get("source_lesson_unit_key"),
        "knowledge_point": content.get("source_knowledge_point"),
        "options": ordered,
        "created_at": created_at,
    }
