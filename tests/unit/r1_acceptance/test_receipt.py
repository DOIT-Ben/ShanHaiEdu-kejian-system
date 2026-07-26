from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from apps.api.settings import Settings
from scripts.r1_provider_acceptance import (
    R1ProviderAcceptanceError,
    R1ProviderAcceptanceReceipt,
    UsageEvidence,
    _attempt_evidence,  # pyright: ignore[reportPrivateUsage]
    controlled_real_provider_configured,
    validate_controlled_real_provider,
)

ROOT = Path(__file__).resolve().parents[3]


def test_receipt_serializes_only_the_allowlisted_provider_and_exact_fact_fields() -> None:
    ids = [uuid4() for _ in range(40)]
    receipt = R1ProviderAcceptanceReceipt.model_validate(
        {
            "schema_version": 1,
            "conclusion": "passed",
            "utc": datetime.now(UTC),
            "project_id": ids[0],
            "lesson_division_project_id": ids[3],
            "lesson_unit_id": ids[1],
            "isolation_lesson_unit_id": ids[2],
            "provider": {"name": "controlled-provider", "configured_model": "text-model"},
            "artifacts": [
                {
                    "kind": kind,
                    "project_id": ids[project_index],
                    "lesson_unit_id": None if lesson_index is None else ids[lesson_index],
                    "artifact_id": ids[artifact_index],
                    "generated_version_id": ids[artifact_index + 1],
                    "approved_version_id": ids[artifact_index + 2],
                    "content_hash": "a" * 64,
                    "quality_report_id": ids[artifact_index + 3],
                    "quality_evidence_hash": "b" * 64,
                    "approval_id": ids[artifact_index + 4],
                }
                for kind, project_index, lesson_index, artifact_index in (
                    ("lesson_division", 3, None, 4),
                    ("lesson_plan", 0, 1, 9),
                    ("intro_option_set", 0, 1, 14),
                )
            ],
            "jobs": [
                {
                    "job_id": ids[job_index],
                    "project_id": ids[project_index],
                    "lesson_unit_id": None if lesson_index is None else ids[lesson_index],
                    "node_run_id": ids[node_run_index],
                    "node_key": node_key,
                    "result_artifact_version_id": ids[result_index],
                    "status": "succeeded",
                }
                for (
                    node_key,
                    project_index,
                    lesson_index,
                    job_index,
                    node_run_index,
                    result_index,
                ) in (
                    ("lesson.division.generate", 3, None, 19, 20, 5),
                    ("lesson_plan.generate", 0, 1, 21, 22, 10),
                    ("intro.generate_options", 0, 1, 23, 24, 15),
                    ("lesson_plan.generate", 0, 2, 25, 26, 27),
                )
            ],
            "attempts": [
                {
                    "attempt_id": ids[attempt_index],
                    "project_id": ids[project_index],
                    "generation_job_id": ids[job_index],
                    "node_run_id": ids[node_run_index],
                    "capability": "text.structured.zh_primary_math",
                    "provider": "controlled-provider",
                    "configured_model": "text-model",
                    "actual_model": "text-model-2026",
                    "request_id": f"request-{attempt_index}",
                    "provider_request_id": f"provider-request-{attempt_index}",
                    "request_hash": "c" * 64,
                    "latency_ms": 120,
                    "usage": {
                        "input_units": {"prompt_tokens": 10},
                        "output_units": {"completion_tokens": 20, "total_tokens": 30},
                        "actual_cost": Decimal("0.001200"),
                        "currency": "USD",
                    },
                }
                for attempt_index, project_index, job_index, node_run_index in (
                    (29, 3, 19, 20),
                    (30, 0, 21, 22),
                    (31, 0, 23, 24),
                    (32, 0, 25, 26),
                )
            ],
            "selection": {
                "selection_id": ids[33],
                "artifact_version_id": ids[16],
                "source_approval_id": ids[18],
                "option_key": "science-1",
            },
            "isolation": {
                "lesson_unit_id": ids[2],
                "lesson_plan_artifact_id": ids[28],
                "lesson_plan_version_id": ids[27],
                "lesson_plan_content_hash": "d" * 64,
                "lesson_plan_job_id": ids[25],
                "lesson_plan_node_run_id": ids[26],
                "intro_artifact_count": 0,
                "intro_job_count": 0,
            },
        }
    )

    payload = json.loads(receipt.model_dump_json())
    schema = json.loads(
        (ROOT / "contracts/r1-provider-acceptance-receipt.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(
        schema,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    cast(Any, validator).validate(payload)
    assert set(payload) == {
        "schema_version",
        "conclusion",
        "utc",
        "project_id",
        "lesson_division_project_id",
        "lesson_unit_id",
        "isolation_lesson_unit_id",
        "provider",
        "artifacts",
        "jobs",
        "attempts",
        "selection",
        "isolation",
    }
    assert not _keys(payload).intersection(
        {"prompt", "content_json", "raw_response", "api_key", "secret"}
    )


@pytest.mark.parametrize(
    ("provider", "provider_request_id"),
    [
        ("r1-rescue-deterministic", "provider-request"),
        ("controlled-provider", "fake:request"),
        ("fake", "provider-request"),
    ],
)
def test_receipt_rejects_fake_provider_evidence(
    provider: str,
    provider_request_id: str,
) -> None:
    with pytest.raises(R1ProviderAcceptanceError) as captured:
        validate_controlled_real_provider(
            actual_provider=provider,
            expected_provider="controlled-provider",
            provider_request_id=provider_request_id,
        )

    assert captured.value.code == "R1_PROVIDER_EVIDENCE_NOT_REAL"


def test_receipt_rejects_a_provider_outside_the_configured_route() -> None:
    with pytest.raises(R1ProviderAcceptanceError) as captured:
        validate_controlled_real_provider(
            actual_provider="other-provider",
            expected_provider="controlled-provider",
            provider_request_id="provider-request",
        )

    assert captured.value.code == "R1_PROVIDER_ROUTE_MISMATCH"


def test_receipt_rejects_negative_usage_units_before_serialization() -> None:
    with pytest.raises(ValidationError):
        UsageEvidence(
            input_units={"prompt_tokens": -1},
            output_units={"completion_tokens": 1},
            actual_cost=Decimal("0.001"),
            currency="USD",
        )


def test_receipt_requires_the_current_real_provider_route_and_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_environment = "SHANHAI_R1_TEST_PROVIDER_SECRET"
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+psycopg://test:test@127.0.0.1:5432/test",
            "text_provider_name": "controlled-provider",
            "text_provider_base_url": "https://provider.example/v1",
            "text_provider_model": "controlled-model",
            "text_provider_secret_env": secret_environment,
        }
    )
    monkeypatch.delenv(secret_environment, raising=False)
    assert controlled_real_provider_configured(settings) is False

    monkeypatch.setenv(secret_environment, "not-a-real-secret")
    assert controlled_real_provider_configured(settings) is True

    monkeypatch.setenv(secret_environment, "   ")
    assert controlled_real_provider_configured(settings) is False


def test_receipt_does_not_label_the_configured_model_as_the_actual_model() -> None:
    organization_id, project_id, node_run_id, job_id, attempt_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    job = SimpleNamespace(
        id=job_id,
        organization_id=organization_id,
        project_id=project_id,
        node_run_id=node_run_id,
    )
    attempt = SimpleNamespace(
        id=attempt_id,
        organization_id=organization_id,
        project_id=project_id,
        node_run_id=node_run_id,
        provider_name="controlled-provider",
        provider_model="configured-model",
        provider_request_id="provider-request",
        request_id="request-id",
        request_hash="a" * 64,
        latency_ms=10,
        capability="text.structured.zh_primary_math",
    )
    usage = SimpleNamespace(
        organization_id=organization_id,
        project_id=project_id,
        node_run_id=node_run_id,
        capability=attempt.capability,
        provider_name=attempt.provider_name,
        provider_model=None,
    )

    def scalars(_statement: object) -> list[object]:
        return [attempt]

    def scalar(_statement: object) -> object:
        return usage

    session = SimpleNamespace(
        scalars=scalars,
        scalar=scalar,
    )

    with pytest.raises(R1ProviderAcceptanceError) as captured:
        _attempt_evidence(
            cast(Any, session),
            cast(Any, job),
            expected_provider="controlled-provider",
            configured_model="configured-model",
        )

    assert captured.value.code == "R1_ACCEPTANCE_ATTEMPT_EVIDENCE_MISSING"


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return set(mapping).union(*(_keys(item) for item in mapping.values()))
    if isinstance(value, list):
        items = cast(list[object], value)
        keys: set[str] = set()
        for item in items:
            keys.update(_keys(item))
        return keys
    return set()
