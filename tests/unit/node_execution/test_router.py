from __future__ import annotations

from apps.api.node_execution.contracts import NodeExecutionError
from apps.api.node_execution.router import _execution_error


def test_provider_unavailable_is_exposed_as_retryable_service_failure() -> None:
    error = _execution_error(
        NodeExecutionError("MODEL_PROVIDER_UNAVAILABLE", "model invocation failed")
    )

    assert error.status_code == 503
    assert error.retryable is True


def test_node_state_conflict_remains_non_retryable_conflict() -> None:
    error = _execution_error(
        NodeExecutionError("NODE_EXECUTION_STATE_CONFLICT", "node run is not ready")
    )

    assert error.status_code == 409
    assert error.retryable is False
