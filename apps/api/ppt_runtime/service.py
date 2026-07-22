"""Two-transaction orchestration around deterministic PPT rendering and object I/O."""

from __future__ import annotations

import time
from typing import cast
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PublishedPptxObject
from apps.api.ppt_rendering import ManifestPage, PptxFileFact
from apps.api.ppt_rendering.ports import PptRenderingPort
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage

from .contracts import (
    PptRuntimeError,
    PptRuntimeResult,
    PptRuntimeTransactionFactory,
    PreparedPptRuntime,
)
from .rendering import PptRuntimeRenderer

_NON_TERMINAL_PREPARE_CODES = frozenset(
    {
        "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
        "NODE_EXECUTION_IN_FLIGHT",
        "PPT_RUNTIME_IN_FLIGHT",
    }
)


class PptRuntimeService:
    def __init__(
        self,
        transactions: PptRuntimeTransactionFactory,
        storage: ObjectStorage,
        *,
        storage_bucket: str,
        renderer: PptRenderingPort | None = None,
    ) -> None:
        if not storage_bucket.strip():
            raise ValueError("PPT runtime storage bucket is required")
        self._transactions = transactions
        self._storage = storage
        self._storage_bucket = storage_bucket
        self._rendering = PptRuntimeRenderer(storage, renderer)

    def execute(self, node_run_id: UUID, *, request_id: str) -> PptRuntimeResult:
        if not request_id.strip():
            raise PptRuntimeError("PPT_RUNTIME_REQUEST_ID_INVALID", "request ID is required")
        try:
            with self._transactions.begin() as transaction:
                prepared = transaction.prepare(node_run_id, request_id)
        except Exception as exc:
            code = _error_code(exc, "PPT_RUNTIME_PREPARE_FAILED")
            if code not in _NON_TERMINAL_PREPARE_CODES:
                self._fail_prepare(node_run_id, code)
            raise _runtime_error(code, "PPT runtime preparation failed", exc) from exc
        if isinstance(prepared, PptRuntimeResult):
            return prepared

        started = time.monotonic()
        published: PublishedPptxObject | None = None
        completed_pages = list(prepared.recovered_pages)
        try:
            product = self._rendering.render(prepared, completed_pages)
            published = self._publish(prepared, product.pptx)
            latency_ms = _elapsed_ms(started)
            with self._transactions.begin() as transaction:
                return transaction.complete(
                    prepared,
                    product,
                    published,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            latency_ms = _elapsed_ms(started)
            cleanup_error = self._cleanup_published(published)
            code = _error_code(exc, "PPT_RUNTIME_EXECUTION_FAILED")
            if cleanup_error is not None:
                code = "PPT_RUNTIME_OBJECT_CLEANUP_FAILED"
            cancelled = code in {
                "NODE_EXECUTION_CANCEL_REQUESTED",
                "PPT_RUNTIME_CANCEL_REQUESTED",
            }
            self._terminalize(
                prepared,
                code,
                cancelled=cancelled,
                latency_ms=latency_ms,
                completed_pages=tuple(completed_pages),
            )
            cause = cleanup_error or exc
            raise _runtime_error(code, "PPT runtime execution failed", cause) from cause

    def _publish(
        self,
        prepared: PreparedPptRuntime,
        result: PptxFileFact | None,
    ) -> PublishedPptxObject | None:
        if result is None:
            return None
        prefix = (
            f"ppt-runtime/{prepared.execution.organization_id}/"
            f"{prepared.execution.project_id}/{prepared.execution.lesson_unit_id}/"
            f"{prepared.execution.node_run_id}/{prepared.attempt.attempt_id}"
        )
        staging_key = f"{prefix}/staging.pptx"
        final_key = f"{prefix}/{result.sha256}.pptx"
        try:
            staged = self._storage.put_bytes(
                bucket=self._storage_bucket,
                key=staging_key,
                payload=result.content,
                media_type=result.media_type,
            )
            _require_pptx_metadata(staged, result)
            published = self._storage.copy(
                source_bucket=self._storage_bucket,
                source_key=staging_key,
                destination_bucket=self._storage_bucket,
                destination_key=final_key,
            )
            _require_pptx_metadata(published, result)
            fact = PublishedPptxObject(
                bucket=published.bucket,
                key=published.key,
                etag=published.etag,
                mime_type=published.media_type,
                size_bytes=published.size_bytes,
                sha256=cast(str, published.sha256),
            )
            self._storage.delete(bucket=self._storage_bucket, key=staging_key)
            return fact
        except Exception:
            cleanup_error = self._cleanup_objects(final_key, staging_key)
            if cleanup_error is not None:
                raise PptRuntimeError(
                    "PPT_RUNTIME_OBJECT_CLEANUP_FAILED",
                    "the incomplete PPTX publish could not be compensated",
                ) from cleanup_error
            raise

    def _cleanup_objects(self, *keys: str) -> Exception | None:
        first_error: Exception | None = None
        for key in keys:
            try:
                self._storage.delete(bucket=self._storage_bucket, key=key)
            except Exception as exc:
                first_error = first_error or exc
        return first_error

    def _fail_prepare(self, node_run_id: UUID, code: str) -> None:
        try:
            with self._transactions.begin() as transaction:
                transaction.fail_prepare(node_run_id, code=code)
        except Exception as exc:
            raise PptRuntimeError(
                "PPT_RUNTIME_FAILURE_COMMIT_FAILED",
                "the PPT runtime preparation failure could not be committed",
            ) from exc

    def _terminalize(
        self,
        prepared: PreparedPptRuntime,
        code: str,
        *,
        cancelled: bool,
        latency_ms: int,
        completed_pages: tuple[ManifestPage, ...],
    ) -> None:
        try:
            with self._transactions.begin() as transaction:
                transaction.terminalize_failure(
                    prepared,
                    code=code,
                    cancelled=cancelled,
                    latency_ms=latency_ms,
                    completed_pages=completed_pages,
                )
        except Exception as exc:
            raise PptRuntimeError(
                "PPT_RUNTIME_FAILURE_COMMIT_FAILED",
                "the PPT runtime failure could not be committed",
            ) from exc

    def _cleanup_published(self, published: PublishedPptxObject | None) -> Exception | None:
        if published is None:
            return None
        try:
            self._storage.delete(bucket=published.bucket, key=published.key)
        except Exception as exc:
            return exc
        return None


def _require_pptx_metadata(metadata: ObjectMetadata, result: PptxFileFact) -> None:
    if (
        metadata.media_type != result.media_type
        or metadata.size_bytes != result.size_bytes
        or metadata.sha256 != result.sha256
        or not metadata.etag
    ):
        raise PptRuntimeError(
            "PPT_RUNTIME_PUBLISHED_OBJECT_MISMATCH",
            "the published PPTX object differs from the rendered file fact",
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _error_code(exc: Exception, fallback: str) -> str:
    code = getattr(exc, "code", fallback)
    return code if isinstance(code, str) and code == code.upper() else fallback


def _runtime_error(code: str, message: str, cause: Exception) -> PptRuntimeError:
    detail = str(cause) if isinstance(cause, PptRuntimeError) and cause.code == code else message
    error = PptRuntimeError(code, detail)
    error.__cause__ = cause
    return error
