"""Versioned project automation policy reads and updates."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.projects.models import AutomationPolicy
from apps.api.projects.policy_schemas import (
    AutomationNodeRule,
    AutomationPolicyMode,
    AutomationPolicyRead,
    UpdateAutomationPolicyRequest,
)
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import CommandResult, IdempotencyService


class AutomationPolicyService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get(self, project_id: UUID, *, for_update: bool = False) -> AutomationPolicyRead:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.VIEW,
            for_update=for_update,
        )
        policy = self._current(project_id, for_update=for_update)
        if policy is None:
            raise ApiError(
                status_code=409,
                code="AUTOMATION_POLICY_MISSING",
                message="The project automation policy has not been initialized.",
            )
        return self._read(policy)

    def update(
        self,
        project_id: UUID,
        payload: UpdateAutomationPolicyRequest,
        *,
        idempotency_key: str,
        request_id: str,
        ttl_seconds: int,
        expected_version: int | None = None,
    ) -> AutomationPolicyRead:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        request_payload = payload.model_dump(mode="json", exclude_none=True)
        if expected_version is not None:
            request_payload["if_match"] = expected_version

        def command() -> CommandResult:
            current = self._current(project_id, for_update=True)
            if current is None:
                raise ApiError(
                    status_code=409,
                    code="AUTOMATION_POLICY_MISSING",
                    message="The project automation policy has not been initialized.",
                )
            if expected_version is not None and current.policy_version != expected_version:
                raise ApiError(
                    status_code=409,
                    code="EDIT_CONFLICT",
                    message="The automation policy changed after it was loaded.",
                    details={"current_version": current.policy_version},
                )
            record = AutomationPolicy(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                project_id=current.project_id,
                workflow_definition_version_id=current.workflow_definition_version_id,
                mode=payload.mode or current.mode,
                node_rules_json=(
                    [rule.model_dump(mode="json", exclude_none=True) for rule in payload.node_rules]
                    if payload.node_rules is not None
                    else current.node_rules_json
                ),
                policy_version=current.policy_version + 1,
                created_at=utc_now(),
                created_by=self._actor.principal_id,
            )
            self._session.add(record)
            self._session.flush()
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=project_id,
                event_type="automation.policy.updated",
                resource=EventResource(type="automation_policy", id=record.id),
                payload={
                    "mode": record.mode,
                    "policy_version": record.policy_version,
                    "workflow_definition_version_id": str(record.workflow_definition_version_id),
                },
                request_id=request_id,
            )
            body = self._read(record).model_dump(mode="json")
            return CommandResult(
                status_code=200,
                body=body,
                resource_type="automation_policy",
                resource_id=record.id,
            )

        result = IdempotencyService(
            self._session,
            self._actor.organization_id,
            ttl_seconds=ttl_seconds,
        ).execute(
            scope=f"automation_policy.update:{project_id}",
            key=idempotency_key,
            payload=request_payload,
            command=command,
        )
        return AutomationPolicyRead.model_validate(result.body)

    def snapshot(self, project_id: UUID) -> dict[str, object]:
        policy = self.get(project_id)
        return {
            "mode": policy.mode,
            "node_rules": [rule.model_dump(exclude_none=True) for rule in policy.node_rules],
            "policy_version": policy.policy_version,
            "workflow_definition_version_id": str(policy.workflow_definition_version_id),
        }

    def _current(self, project_id: UUID, *, for_update: bool) -> AutomationPolicy | None:
        statement = (
            select(AutomationPolicy)
            .where(
                AutomationPolicy.organization_id == self._actor.organization_id,
                AutomationPolicy.project_id == project_id,
            )
            .order_by(AutomationPolicy.policy_version.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update(of=AutomationPolicy)
        return self._session.scalar(statement)

    @staticmethod
    def _read(policy: AutomationPolicy) -> AutomationPolicyRead:
        return AutomationPolicyRead(
            project_id=policy.project_id,
            workflow_definition_version_id=policy.workflow_definition_version_id,
            mode=cast(AutomationPolicyMode, policy.mode),
            node_rules=[AutomationNodeRule.model_validate(rule) for rule in policy.node_rules_json],
            policy_version=policy.policy_version,
            updated_at=policy.created_at,
        )
