from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import pytest

from apps.api.artifact_quality.contracts import (
    ArtifactQualityReportResult,
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.artifact_quality.service import ArtifactQualityError, ArtifactQualityService

NODE_RUN_ID = UUID("10000000-0000-4000-8000-000000000133")
SOURCE_VERSION_ID = UUID("10000000-0000-4000-8000-000000000134")
REPORT_ID = UUID("10000000-0000-4000-8000-000000000135")
ORGANIZATION_ID = UUID("10000000-0000-4000-8000-000000000136")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000137")
CONTENT_RELEASE_ID = UUID("10000000-0000-4000-8000-000000000138")
WORKFLOW_VERSION_ID = UUID("10000000-0000-4000-8000-000000000139")
VALIDATOR_REF = ValidatorRef(
    key="validator.fixture",
    semantic_version="1.0.0",
    implementation_digest="a" * 64,
)


def validation_context() -> QualityValidationContext:
    return QualityValidationContext(
        organization_id=ORGANIZATION_ID,
        project_id=PROJECT_ID,
        lesson_unit_id=None,
        content_release_id=CONTENT_RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_VERSION_ID,
        node_run_id=NODE_RUN_ID,
        source_artifact_version_id=SOURCE_VERSION_ID,
        source_content_hash="b" * 64,
        source_content={"title": "Fractions"},
        validator_refs=(VALIDATOR_REF,),
        validator_set_hash="c" * 64,
    )


@dataclass
class FakeValidator:
    events: list[str]
    outcome: ValidatorOutcome | None = None
    error: Exception | None = None

    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        self.events.append("validate")
        assert context == validation_context()
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


class FakeRegistry:
    def __init__(self, events: list[str], validator: FakeValidator) -> None:
        self.events = events
        self.validator = validator

    def resolve(self, refs: tuple[ValidatorRef, ...]) -> tuple[FakeValidator, ...]:
        self.events.append("resolve")
        assert refs == (VALIDATOR_REF,)
        return (self.validator,)


@dataclass
class FakeTransaction:
    events: list[str]
    complete_error: Exception | None = None

    def prepare(self, node_run_id: UUID) -> QualityValidationContext:
        self.events.append("prepare")
        assert node_run_id == NODE_RUN_ID
        return validation_context()

    def complete(
        self,
        context: QualityValidationContext,
        *,
        conclusion: Literal["passed", "failed"],
        outcomes: tuple[ValidatorOutcome, ...],
    ) -> ArtifactQualityReportResult:
        self.events.append(f"complete:{conclusion}")
        assert context == validation_context()
        assert len(outcomes) == 1
        if self.complete_error is not None:
            raise self.complete_error
        return ArtifactQualityReportResult(
            report_id=REPORT_ID,
            node_run_id=NODE_RUN_ID,
            conclusion=conclusion,
        )

    def fail_technical(self, context: QualityValidationContext, *, code: str) -> None:
        self.events.append(f"technical:{code}")
        assert context == validation_context()


class FakeTransactionFactory:
    def __init__(
        self,
        events: list[str],
        *,
        complete_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.complete_error = complete_error

    @contextmanager
    def begin(self) -> Iterator[FakeTransaction]:
        self.events.append("tx:open")
        try:
            yield FakeTransaction(self.events, self.complete_error)
        except Exception:
            self.events.append("tx:rollback")
            raise
        else:
            self.events.append("tx:commit")


@pytest.mark.parametrize(
    ("passed", "expected_conclusion"),
    [(True, "passed"), (False, "failed")],
)
def test_quality_outcome_report_node_terminal_state_and_event_share_one_transaction(
    passed: bool,
    expected_conclusion: Literal["passed", "failed"],
) -> None:
    events: list[str] = []
    outcome = ValidatorOutcome(
        validator=VALIDATOR_REF,
        passed=passed,
        findings=() if passed else ({"code": "FIXTURE_FAILED"},),
        evidence={"checked": True},
    )
    service = ArtifactQualityService(
        FakeTransactionFactory(events),
        FakeRegistry(events, FakeValidator(events, outcome=outcome)),
    )

    result = service.execute(NODE_RUN_ID)

    assert result.conclusion == expected_conclusion
    assert events == [
        "tx:open",
        "prepare",
        "resolve",
        "validate",
        f"complete:{expected_conclusion}",
        "tx:commit",
    ]


def test_validator_exception_marks_node_failed_without_fabricating_report() -> None:
    events: list[str] = []
    service = ArtifactQualityService(
        FakeTransactionFactory(events),
        FakeRegistry(events, FakeValidator(events, error=RuntimeError("validator crashed"))),
    )

    with pytest.raises(ArtifactQualityError) as captured:
        service.execute(NODE_RUN_ID)

    assert captured.value.code == "QUALITY_VALIDATION_TECHNICAL_FAILURE"
    assert events == [
        "tx:open",
        "prepare",
        "resolve",
        "validate",
        "technical:QUALITY_VALIDATION_TECHNICAL_FAILURE",
        "tx:commit",
    ]


def test_report_or_terminal_event_failure_rolls_back_the_whole_transaction() -> None:
    events: list[str] = []
    outcome = ValidatorOutcome(
        validator=VALIDATOR_REF,
        passed=True,
        findings=(),
        evidence={"checked": True},
    )
    service = ArtifactQualityService(
        FakeTransactionFactory(events, complete_error=RuntimeError("event write failed")),
        FakeRegistry(events, FakeValidator(events, outcome=outcome)),
    )

    with pytest.raises(ArtifactQualityError) as captured:
        service.execute(NODE_RUN_ID)

    assert captured.value.code == "QUALITY_REPORT_COMMIT_FAILED"
    assert events == [
        "tx:open",
        "prepare",
        "resolve",
        "validate",
        "complete:passed",
        "tx:rollback",
    ]
