from __future__ import annotations

import pytest

from apps.api.model_gateway.contracts import GatewayErrorCode
from apps.api.model_gateway.openai_compatible import map_provider_error


@pytest.mark.parametrize(
    ("status", "error_type", "expected", "retryable"),
    [
        (429, "rate_limit_exceeded", GatewayErrorCode.PROVIDER_RATE_LIMITED, True),
        (408, "timeout", GatewayErrorCode.TIMEOUT, True),
        (401, "authentication", GatewayErrorCode.PROVIDER_AUTH_FAILED, False),
        (402, "payment_required", GatewayErrorCode.PROVIDER_BUDGET_EXHAUSTED, False),
        (403, "content_policy_violation", GatewayErrorCode.REJECTED, False),
        (404, "not_found", GatewayErrorCode.ROUTE_UNAVAILABLE, False),
        (502, "provider_unavailable", GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (500, "server", GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (500, None, GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (504, None, GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (400, "invalid_request", GatewayErrorCode.INVALID_RESPONSE, False),
    ],
)
def test_provider_errors_map_to_stable_platform_codes(
    status: int,
    error_type: str | None,
    expected: GatewayErrorCode,
    retryable: bool,
) -> None:
    error = map_provider_error(status, error_type)

    assert error.code == expected
    assert error.retryable is retryable


def test_submission_unknown_is_a_non_retryable_platform_error() -> None:
    error = GatewayErrorCode.SUBMISSION_UNKNOWN

    assert error.value == "MODEL_SUBMISSION_UNKNOWN"


def test_audit_unavailable_has_a_stable_platform_error() -> None:
    assert GatewayErrorCode.AUDIT_UNAVAILABLE.value == "MODEL_AUDIT_UNAVAILABLE"
