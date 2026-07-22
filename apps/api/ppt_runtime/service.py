"""Two-transaction orchestration around deterministic PPT rendering and object I/O."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact, PublishedPptxObject
from apps.api.ppt_rendering.models import (
    MAX_BACKGROUND_BYTES,
    AssemblyManifest,
    AssemblyRequest,
    PptxFileFact,
)
from apps.api.ppt_rendering.ports import PptRenderingPort
from apps.api.ppt_rendering.service import assemble_pages, export_pptx
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage

from .contracts import (
    PptRenderProduct,
    PptRuntimeError,
    PptRuntimeResult,
    PptRuntimeTransactionFactory,
    PreparedPptRuntime,
)
from .layout import build_assembly_request

_NON_TERMINAL_PREPARE_CODES = frozenset(
    {
        "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
        "NODE_EXECUTION_IN_FLIGHT",
        "PPT_RUNTIME_IN_FLIGHT",
    }
)


class _BuiltInPptRenderer:
    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest:
        return assemble_pages(request)

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact:
        return export_pptx(request)


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
        self._renderer = renderer or cast(PptRenderingPort, _BuiltInPptRenderer())

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
        try:
            product = self._render(prepared)
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
            self._terminalize(prepared, code, cancelled=cancelled, latency_ms=latency_ms)
            cause = cleanup_error or exc
            raise _runtime_error(code, "PPT runtime execution failed", cause) from cause

    def _render(self, prepared: PreparedPptRuntime) -> PptRenderProduct:
        with TemporaryDirectory(prefix="shanhai-ppt-runtime-") as directory:
            payloads = self._download_backgrounds(prepared, Path(directory))
            request = build_assembly_request(
                prepared.page_spec_content,
                prepared.backgrounds,
                payloads,
            )
            if prepared.definition.executor_ref == "executor.ppt.pages_assemble":
                manifest = self._renderer.assemble_pages(request)
                return PptRenderProduct(request=request, manifest=manifest, pptx=None)
            if prepared.definition.executor_ref != "executor.ppt.pptx_export":
                raise PptRuntimeError(
                    "PPT_RUNTIME_EXECUTOR_UNSUPPORTED",
                    "the published deterministic PPT executor is unsupported",
                )
            result = self._renderer.export_pptx(request)
            self._verify_assembly_input(prepared, result.assembly_manifest)
            return PptRenderProduct(
                request=request,
                manifest=result.assembly_manifest,
                pptx=result,
            )

    def _download_backgrounds(
        self,
        prepared: PreparedPptRuntime,
        directory: Path,
    ) -> dict[UUID, bytes]:
        values: dict[UUID, bytes] = {}
        for index, fact in enumerate(prepared.backgrounds, 1):
            destination = directory / f"background-{index:02d}.png"
            metadata = self._storage.download_to_path(
                bucket=fact.storage_bucket,
                key=fact.storage_key,
                destination=destination,
                max_bytes=MAX_BACKGROUND_BYTES,
            )
            if not _matches_background(metadata, fact):
                raise PptRuntimeError(
                    "PPT_RUNTIME_BACKGROUND_OBJECT_MISMATCH",
                    "an exact background object differs from its immutable file fact",
                )
            values[fact.file_asset_version_id] = destination.read_bytes()
        return values

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
            return PublishedPptxObject(
                bucket=published.bucket,
                key=published.key,
                etag=published.etag,
                mime_type=published.media_type,
                size_bytes=published.size_bytes,
                sha256=cast(str, published.sha256),
            )
        except Exception:
            self._storage.delete(bucket=self._storage_bucket, key=final_key)
            raise
        finally:
            self._storage.delete(bucket=self._storage_bucket, key=staging_key)

    @staticmethod
    def _verify_assembly_input(
        prepared: PreparedPptRuntime,
        manifest: AssemblyManifest,
    ) -> None:
        content = prepared.assembly_content
        if prepared.assembly_artifact_version_id is None or content is None:
            raise PptRuntimeError(
                "PPT_RUNTIME_ASSEMBLY_INPUT_MISSING",
                "PPTX export requires one exact approved assembly artifact",
            )
        expected_backgrounds = [str(item.file_asset_version_id) for item in prepared.backgrounds]
        raw_pages = content.get("pages")
        if not isinstance(raw_pages, Sequence) or isinstance(
            raw_pages,
            (str, bytes, bytearray),
        ):
            raise PptRuntimeError(
                "PPT_RUNTIME_ASSEMBLY_INPUT_INVALID",
                "the exact assembly artifact has no page facts",
            )
        pages = cast(Sequence[object], raw_pages)
        actual_backgrounds: list[object] = []
        for page in pages:
            if not isinstance(page, Mapping):
                raise PptRuntimeError(
                    "PPT_RUNTIME_ASSEMBLY_INPUT_INVALID",
                    "the exact assembly page facts are invalid",
                )
            typed_page = cast(Mapping[str, object], page)
            actual_backgrounds.append(typed_page.get("background_file_asset_version_id"))
        if (
            content.get("content_hash") != manifest.content_hash
            or content.get("source_page_spec_version_id") != str(prepared.page_spec_version_id)
            or content.get("page_count") != len(manifest.pages)
            or actual_backgrounds != expected_backgrounds
        ):
            raise PptRuntimeError(
                "PPT_RUNTIME_ASSEMBLY_INPUT_STALE",
                "the exact assembly artifact differs from the current render inputs",
            )

    def _fail_prepare(self, node_run_id: UUID, code: str) -> None:
        try:
            with self._transactions.begin() as transaction:
                transaction.fail_prepare(node_run_id, code=code)
        except Exception:
            return

    def _terminalize(
        self,
        prepared: PreparedPptRuntime,
        code: str,
        *,
        cancelled: bool,
        latency_ms: int,
    ) -> None:
        try:
            with self._transactions.begin() as transaction:
                transaction.terminalize_failure(
                    prepared,
                    code=code,
                    cancelled=cancelled,
                    latency_ms=latency_ms,
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


def _matches_background(metadata: ObjectMetadata, fact: PptBackgroundFact) -> bool:
    return (
        metadata.bucket == fact.storage_bucket
        and metadata.key == fact.storage_key
        and metadata.media_type == fact.mime_type
        and metadata.size_bytes == fact.size_bytes
        and metadata.sha256 == fact.sha256
    )


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
