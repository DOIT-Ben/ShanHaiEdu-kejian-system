"""Transactional application service for teacher and policy Intro selections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.intro_selection_port import (
    ApprovedIntroOptionSetFact,
    IntroSelectionArtifactReader,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_selections.domain import (
    IntroSelectionDecisionError,
    unique_highest_option,
)
from apps.api.intro_selections.models import IntroSelection
from apps.api.intro_selections.repository import IntroSelectionRepository
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.lessons.selection_port import LessonSelectionReader
from apps.api.projects.selection_policy_port import (
    AutomationPolicySelectionReader,
    AutoSelectPolicyFact,
)
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.workflows.intro_selection_port import IntroSelectionWorkflowReader


class IntroSelectionService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = IntroSelectionRepository(session, actor)
        self._artifacts = IntroSelectionArtifactReader(session, actor)

    def select_teacher(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        option_key: str,
        reason: str,
        idempotency_key: str,
        ttl_seconds: int,
    ) -> IntroSelectionRead:
        if self._actor.is_system:
            raise _invalid("Teacher selection requires an authenticated user actor.")
        payload = {
            "project_id": str(project_id),
            "lesson_unit_id": str(lesson_unit_id),
            "artifact_version_id": str(artifact_version_id),
            "option_key": option_key,
            "reason": reason,
        }
        return self._execute(
            scope=f"intro_selection.teacher:{lesson_unit_id}",
            key=idempotency_key,
            payload=payload,
            ttl_seconds=ttl_seconds,
            authorize=lambda: self._authorize_teacher(project_id),
            command=lambda: self._select_teacher(
                project_id, lesson_unit_id, artifact_version_id, option_key, reason
            ),
        )

    def select_policy_default(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        node_run_id: UUID,
        reason: str,
        idempotency_key: str,
        ttl_seconds: int,
    ) -> IntroSelectionRead:
        workflow = IntroSelectionWorkflowReader(self._session, self._actor)
        policy = AutomationPolicySelectionReader()

        def authorize() -> AutoSelectPolicyFact:
            source = workflow.require_policy_source(
                node_run_id=node_run_id,
                project_id=project_id,
                lesson_unit_id=lesson_unit_id,
            )
            return policy.require_auto_select(
                node_run_id=source.node_run_id,
                workflow_definition_version_id=source.workflow_definition_version_id,
                policy_version=source.policy_version,
                mode=source.mode,
                node_rules=source.node_rules,
            )

        payload = {
            "project_id": str(project_id),
            "lesson_unit_id": str(lesson_unit_id),
            "artifact_version_id": str(artifact_version_id),
            "node_run_id": str(node_run_id),
            "reason": reason,
        }
        return self._execute(
            scope=f"intro_selection.policy:{lesson_unit_id}",
            key=idempotency_key,
            payload=payload,
            ttl_seconds=ttl_seconds,
            authorize=authorize,
            command=lambda: self._select_policy(
                project_id, lesson_unit_id, artifact_version_id, reason, authorize
            ),
        )

    def get(self, selection_id: UUID) -> IntroSelectionRead:
        record = self._repository.get(selection_id)
        if record is None:
            raise _not_found()
        self._authorize_read(record.project_id)
        return self._read(record)

    def current_consumable(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
    ) -> IntroSelectionRead:
        self._authorize_read(project_id)
        record = self._repository.current(lesson_unit_id)
        if record is None or record.project_id != project_id:
            raise _not_found()
        read = self._read(record)
        if not read.consumable:
            raise ApiError(
                status_code=409,
                code="INTRO_SELECTION_NOT_CONSUMABLE",
                message="The active Intro selection no longer has its exact source approval.",
                details={"reason": read.unconsumable_reason},
            )
        return read

    def current(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
    ) -> IntroSelectionRead | None:
        self._authorize_read(project_id)
        record = self._repository.current(lesson_unit_id)
        if record is None or record.project_id != project_id:
            return None
        return self._read(record)

    def _select_teacher(
        self,
        project_id: UUID,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        option_key: str,
        reason: str,
    ) -> IntroSelection:
        lesson = LessonSelectionReader(self._session, self._actor).require(
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
        )
        source = self._artifacts.require_approved(
            project_id=project_id,
            lesson_unit_id=lesson.id,
            lesson_key=lesson.lesson_key,
            artifact_version_id=artifact_version_id,
        )
        return self._replace(source, project_id, lesson_unit_id, option_key, reason)

    def _select_policy(
        self,
        project_id: UUID,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        reason: str,
        authorize: Callable[[], AutoSelectPolicyFact],
    ) -> IntroSelection:
        lesson = LessonSelectionReader(self._session, self._actor).require(
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
        )
        if self._repository.current(lesson_unit_id, for_update=True) is not None:
            raise _invalid("Policy default cannot replace an existing active selection.")
        policy = authorize()
        source = self._artifacts.require_approved(
            project_id=project_id,
            lesson_unit_id=lesson.id,
            lesson_key=lesson.lesson_key,
            artifact_version_id=artifact_version_id,
        )
        try:
            option, recommendation = unique_highest_option(source.options)
        except IntroSelectionDecisionError as exc:
            raise _invalid(str(exc)) from exc
        return self._replace(
            source,
            project_id,
            lesson_unit_id,
            str(option["option_key"]),
            reason,
            policy_evidence=policy.evidence,
            recommendation_evidence=recommendation,
        )

    def _replace(
        self,
        source: ApprovedIntroOptionSetFact,
        project_id: UUID,
        lesson_unit_id: UUID,
        option_key: str,
        reason: str,
        *,
        policy_evidence: dict[str, Any] | None = None,
        recommendation_evidence: dict[str, Any] | None = None,
    ) -> IntroSelection:
        if not reason.strip():
            raise _invalid("A selection reason is required.")
        return self._repository.replace_active(
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
            artifact_version_id=source.artifact_version_id,
            source_approval_id=source.source_approval_id,
            selection_method=(
                "policy_default" if policy_evidence is not None else "teacher_selected"
            ),
            option_key=option_key,
            snapshot=source.option(option_key),
            policy_evidence=policy_evidence or {},
            recommendation_evidence=recommendation_evidence or {},
            reason=reason,
        )

    def _execute(
        self,
        *,
        scope: str,
        key: str,
        payload: Mapping[str, Any],
        ttl_seconds: int,
        authorize: Callable[[], object],
        command: Callable[[], IntroSelection],
    ) -> IntroSelectionRead:
        def create() -> CommandResult:
            record = command()
            return CommandResult(
                status_code=201,
                body={"selection_id": str(record.id)},
                resource_type="intro_selection",
                resource_id=record.id,
            )

        result = IdempotencyService(
            self._session,
            self._actor.organization_id,
            ttl_seconds=ttl_seconds,
        ).execute(scope=scope, key=key, payload=payload, authorize=authorize, command=create)
        if result.resource_id is None:
            raise _invalid("The idempotent selection result is incomplete.")
        record = self._repository.get(result.resource_id)
        if record is None:
            raise _not_found()
        return self._read(record)

    def _read(self, record: IntroSelection) -> IntroSelectionRead:
        source = self._artifacts.consumability(
            record.artifact_version_id,
            record.source_approval_id,
        )
        return IntroSelectionRead(
            id=record.id,
            organization_id=record.organization_id,
            project_id=record.project_id,
            lesson_unit_id=record.lesson_unit_id,
            artifact_version_id=record.artifact_version_id,
            source_approval_id=record.source_approval_id,
            selection_method=cast(Any, record.selection_method),
            option_key=record.option_key,
            snapshot=dict(record.snapshot_json),
            actor_type=cast(Any, record.actor_type),
            actor_user_id=record.actor_user_id,
            policy_evidence=dict(record.policy_evidence_json),
            recommendation_evidence=dict(record.recommendation_evidence_json),
            reason=record.reason,
            active=record.active,
            consumable=record.active and source.consumable,
            unconsumable_reason=(
                None if record.active and source.consumable else _reason(record, source.reason)
            ),
            selected_at=record.selected_at,
            deactivated_at=record.deactivated_at,
        )

    def _authorize_teacher(self, project_id: UUID) -> object:
        return ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )

    def _authorize_read(self, project_id: UUID) -> None:
        if not self._actor.is_system:
            ProjectAccessService(self._session, self._actor).require(
                project_id,
                ProjectAction.VIEW,
            )


def _reason(record: IntroSelection, source_reason: str | None) -> str:
    return "superseded" if not record.active else source_reason or "source_unavailable"


def _invalid(message: str) -> ApiError:
    return ApiError(status_code=409, code="INTRO_SELECTION_INVALID", message=message)


def _not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="INTRO_SELECTION_NOT_FOUND",
        message="The Intro selection was not found.",
    )
