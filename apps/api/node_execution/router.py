"""HTTP command for the existing synchronous text node executor."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session, sessionmaker

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import GatewayErrorCode, ModelGatewayError
from apps.api.model_gateway.factory import build_real_text_gateway
from apps.api.node_execution.contracts import NodeExecutionError
from apps.api.node_execution.schemas import (
    NodeExecutionEnvelope,
    NodeExecutionRead,
    StartNodeRunRequest,
)
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.settings import Settings

router = APIRouter(tags=["node-execution"])

_GATEWAY_ERROR_CODES = {code.value for code in GatewayErrorCode}
_RETRYABLE_GATEWAY_ERROR_CODES = {
    GatewayErrorCode.PROVIDER_UNAVAILABLE.value,
    GatewayErrorCode.PROVIDER_RATE_LIMITED.value,
    GatewayErrorCode.TIMEOUT.value,
}


@router.post(
    "/api/v2/node-runs/{node_run_id}/start",
    response_model=NodeExecutionEnvelope,
    operation_id="startNodeRun",
)
async def start_node_run(
    node_run_id: UUID,
    payload: StartNodeRunRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> NodeExecutionEnvelope:
    factory = cast(sessionmaker[Session] | None, request.app.state.session_factory)
    if factory is None:
        raise ApiError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="Database persistence is not configured.",
            retryable=True,
        )
    settings = cast(Settings, request.app.state.settings)
    try:
        gateway, _provider = build_real_text_gateway(
            settings,
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        )
        result = await NodeExecutionService(
            SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
            gateway,
        ).execute(
            node_run_id,
            request_id=idempotency_key,
            user_revision=payload.user_revision,
        )
    except ModelGatewayError as error:
        raise ApiError(
            status_code=503,
            code=error.code.value,
            message="The configured text provider is unavailable.",
            retryable=error.retryable,
        ) from error
    except NodeExecutionError as error:
        raise _execution_error(error) from error
    return NodeExecutionEnvelope(
        data=NodeExecutionRead.model_validate(result, from_attributes=True),
        request_id=request.state.request_id,
    )


def _execution_error(error: NodeExecutionError) -> ApiError:
    if error.code in _GATEWAY_ERROR_CODES:
        return ApiError(
            status_code=503,
            code=error.code,
            message="The text generation request failed.",
            retryable=error.code in _RETRYABLE_GATEWAY_ERROR_CODES,
        )
    status_code = 404 if error.code == "NODE_EXECUTION_NOT_FOUND" else 409
    return ApiError(
        status_code=status_code,
        code=error.code,
        message="The node run cannot execute from its current state.",
        retryable=False,
    )
