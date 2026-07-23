"""Submit, poll and commit one real video candidate without auto-adoption."""

from __future__ import annotations

from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
)

from .contracts import (
    PreparedVideoRuntime,
    VideoFileValidator,
    VideoRuntimeError,
    VideoRuntimeGateway,
    VideoRuntimeResult,
    VideoRuntimeTransactionFactory,
)


class VideoRuntimeService:
    def __init__(
        self,
        transactions: VideoRuntimeTransactionFactory,
        gateway: VideoRuntimeGateway,
        validator: VideoFileValidator,
    ) -> None:
        self._transactions = transactions
        self._gateway = gateway
        self._validator = validator

    async def start(
        self,
        node_run_id: UUID,
        *,
        keyframe_file_version_id: UUID,
        request_id: str,
    ) -> VideoRuntimeResult:
        if not request_id.strip():
            raise VideoRuntimeError("VIDEO_RUNTIME_REQUEST_ID_INVALID", "request ID is required")
        with self._transactions.begin() as transaction:
            prepared = transaction.prepare_start(
                node_run_id,
                keyframe_file_version_id,
                request_id,
            )
        if isinstance(prepared, VideoRuntimeResult):
            return prepared
        request = VideoModelRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id=request_id,
            prompt=prepared.prompt,
            duration_seconds=prepared.duration_seconds,
            references=[prepared.keyframe],
        )
        try:
            result = await self._gateway.submit_video(
                request,
                audit_context=prepared.audit_context,
                media_organization_id=prepared.organization_id,
            )
        except ModelGatewayError as exc:
            code = exc.code.value
            self._terminalize(prepared, code)
            raise VideoRuntimeError(code, "video provider submission failed") from exc
        return self._settle(prepared, result)

    async def poll(self, node_run_id: UUID, *, request_id: str) -> VideoRuntimeResult:
        if not request_id.strip():
            raise VideoRuntimeError("VIDEO_RUNTIME_REQUEST_ID_INVALID", "request ID is required")
        with self._transactions.begin() as transaction:
            prepared = transaction.prepare_poll(node_run_id, request_id)
        if isinstance(prepared, VideoRuntimeResult):
            return prepared
        if prepared.provider_task_id is None:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_PROVIDER_TASK_MISSING",
                "video generation has no recoverable provider task",
            )
        request = VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id=request_id,
            provider_task_id=prepared.provider_task_id,
        )
        try:
            result = await self._gateway.poll_video(
                request,
                audit_context=prepared.audit_context,
            )
        except ModelGatewayError as exc:
            code = exc.code.value
            self._terminalize(prepared, code)
            raise VideoRuntimeError(code, "video provider polling failed") from exc
        return self._settle(prepared, result)

    def _settle(
        self,
        prepared: PreparedVideoRuntime,
        result: VideoGatewayResult,
    ) -> VideoRuntimeResult:
        if result.status in {VideoOperationStatus.SUBMITTED, VideoOperationStatus.POLLING}:
            try:
                with self._transactions.begin() as transaction:
                    return transaction.record_pending(prepared, result)
            except Exception as exc:
                self._terminalize(prepared, "VIDEO_RUNTIME_COMMIT_FAILED")
                raise VideoRuntimeError(
                    "VIDEO_RUNTIME_COMMIT_FAILED",
                    "video pending state could not be committed",
                ) from exc
        if result.status is VideoOperationStatus.SUCCEEDED:
            if len(result.files) != 1:
                self._terminalize(prepared, "VIDEO_RUNTIME_FILE_FACT_MISMATCH")
                raise VideoRuntimeError(
                    "VIDEO_RUNTIME_FILE_FACT_MISMATCH",
                    "video provider did not return exactly one file",
                )
            try:
                validated = self._validator.validate(result.files[0])
                with self._transactions.begin() as transaction:
                    return transaction.complete(prepared, result, validated)
            except VideoRuntimeError as exc:
                self._terminalize(prepared, exc.code)
                raise
            except Exception as exc:
                self._terminalize(prepared, "VIDEO_RUNTIME_COMMIT_FAILED")
                raise VideoRuntimeError(
                    "VIDEO_RUNTIME_COMMIT_FAILED",
                    "video candidate could not be committed",
                ) from exc
        code = _terminal_code(result.status)
        self._terminalize(prepared, code)
        raise VideoRuntimeError(code, "video provider failed")

    def _terminalize(self, prepared: PreparedVideoRuntime, code: str) -> None:
        try:
            with self._transactions.begin() as transaction:
                transaction.terminalize_failure(prepared, code=code)
        except Exception as exc:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_FAILURE_COMMIT_FAILED",
                "video failure state could not be committed",
            ) from exc


def _terminal_code(status: VideoOperationStatus) -> str:
    if status is VideoOperationStatus.CANCELLED:
        return GatewayErrorCode.CANCELLED.value
    if status is VideoOperationStatus.SUBMISSION_UNKNOWN:
        return GatewayErrorCode.SUBMISSION_UNKNOWN.value
    return "VIDEO_RUNTIME_PROVIDER_FAILED"
