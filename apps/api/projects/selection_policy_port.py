"""AutomationPolicy-owned decision facts for policy default Intro selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError

from apps.api.errors import ApiError
from apps.api.projects.policy_schemas import AutomationNodeRule


@dataclass(frozen=True, slots=True)
class AutoSelectPolicyFact:
    evidence: dict[str, Any]


class AutomationPolicySelectionReader:
    def require_auto_select(
        self,
        *,
        node_run_id: UUID,
        workflow_definition_version_id: UUID,
        policy_version: int,
        mode: object,
        node_rules: object,
    ) -> AutoSelectPolicyFact:
        rules = _rules(node_rules)
        exact = [rule for rule in rules if rule.node_key == "intro.select"]
        if len(exact) != 1 or exact[0].auto_select is not True:
            raise _denied("The fixed policy does not explicitly allow intro.select auto_select.")
        return AutoSelectPolicyFact(
            evidence={
                "node_run_id": str(node_run_id),
                "policy_version": policy_version,
                "workflow_definition_version_id": str(workflow_definition_version_id),
                "mode": mode,
                "auto_select": True,
            }
        )


def _rules(raw: object) -> tuple[AutomationNodeRule, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise _denied("The NodeRun policy rules are invalid.")
    values = cast(Sequence[object], raw)
    try:
        return tuple(AutomationNodeRule.model_validate(item) for item in values)
    except ValidationError as exc:
        raise _denied("The NodeRun policy rules are invalid.") from exc


def _denied(message: str) -> ApiError:
    return ApiError(status_code=409, code="INTRO_POLICY_AUTO_SELECT_DENIED", message=message)
